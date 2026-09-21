import asyncio
import logging
import time
from contextlib import suppress
from uuid import uuid4

from psycopg import InterfaceError, OperationalError
from psycopg_pool import PoolTimeout

from app.ai.provider import create_provider
from app.config import Settings
from app.domain.errors import DomainError
from app.infrastructure.database import Database
from app.infrastructure.storage import Storage
from app.repositories.jobs import claim, fail, fence, finish, recover
from app.services.demo_retention import purge_expired_samples
from app.services.storage_cleanup import process_storage_cleanup
from app.services.trash_retention import purge_trash
from app.workers.handlers import Handlers

logger = logging.getLogger(__name__)
DATABASE_ERRORS = (OperationalError, InterfaceError, PoolTimeout)


async def heartbeat(database, worker_id, job=None):
    async with database.connection() as connection:
        await connection.execute(
            "insert into public.worker_heartbeats(id,last_seen) values(%s,now()) on conflict(id) do update set last_seen=now()",
            (worker_id,),
        )
        await connection.execute(
            "delete from public.worker_heartbeats where last_seen<now()-interval '1 day'"
        )
        if job:
            cursor = await connection.execute(
                """update public.processing_jobs set leased_until=now()+interval '90 seconds'
                where workspace_id=%s and id=%s and lease_token=%s and state='running' and leased_until>now() returning id""",
                (job["workspace_id"], job["id"], job["lease_token"]),
            )
            if await cursor.fetchone() is None:
                raise DomainError("JOB_LEASE_LOST", "Worker lease expired")


async def keep_alive(database, worker_id, job):
    while True:
        await asyncio.sleep(20)
        await heartbeat(database, worker_id, job)


async def execute_job(database, handlers, worker_id, job):
    renewal = asyncio.create_task(keep_alive(database, worker_id, job))
    try:
        prepared = await handlers.prepare(job)
        if renewal.done():
            renewal.result()
        async with database.connection() as connection:
            await fence(connection, job)
            result = await handlers.persist(connection, job, prepared)
            await finish(connection, job, result)
    except Exception as exc:
        error = (
            exc
            if isinstance(exc, DomainError)
            else DomainError("PROCESSING_FAILED", "Processing failed", retryable=True)
        )
        logger.warning("Job failed id=%s code=%s", job["id"], error.code)
        async with database.connection() as connection:
            await fail(connection, job, error)
    finally:
        renewal.cancel()
        with suppress(asyncio.CancelledError, DomainError, *DATABASE_ERRORS):
            await renewal


# Readiness accepts a heartbeat up to 60 s old and leases last 90 s, so neither needs to run on
# every poll; on a hosted database each avoided statement saves ~100 ms per job.
HEARTBEAT_EVERY = 15
RECOVER_EVERY = 20
_last_heartbeat: dict = {}
_last_recover = [-1e9]


async def poll_once(database, handlers, worker_id):
    now = time.monotonic()
    if now - _last_heartbeat.get(worker_id, -1e9) >= HEARTBEAT_EVERY:
        await heartbeat(database, worker_id)
        _last_heartbeat[worker_id] = now
    async with database.connection() as connection:
        if now - _last_recover[0] >= RECOVER_EVERY:
            _last_recover[0] = now
            await recover(connection)
        job = await claim(connection)
    if job:
        await execute_job(database, handlers, worker_id, job)
    else:
        await asyncio.sleep(2)


async def serve(database, handlers, worker_id, *, cleanup=True):
    delay = 1
    next_cleanup = 0
    while True:
        try:
            if cleanup and time.monotonic() >= next_cleanup:
                # Scheduled before the attempt so a failing cleanup can never starve job polling.
                next_cleanup = time.monotonic() + 60
                try:
                    async with database.connection() as connection:
                        await purge_expired_samples(connection)
                        await purge_trash(connection)
                    await process_storage_cleanup(database, handlers.storage)
                except DATABASE_ERRORS:
                    raise
                except Exception:
                    logger.exception("Expired sample cleanup failed; jobs continue")
            await poll_once(database, handlers, worker_id)
            delay = 1
        except DATABASE_ERRORS:
            # The pool replaces broken connections. Lost job leases are recovered
            # on the next successful poll; never persist without fencing the lease.
            logger.warning("Database unavailable; worker will retry in %s seconds", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)
        except Exception:
            # Unexpected errors must not end the only worker; job failures are handled in
            # execute_job, so this is a bug elsewhere in the loop. Log it and back off.
            logger.exception("Unexpected worker error; retrying in %s seconds", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)


async def run():
    settings = Settings()
    pool = 2 * settings.worker_concurrency + 2  # each slot holds a transaction and a heartbeat
    database = Database(settings, max_size=pool)
    ai = create_provider(settings)
    handlers = Handlers(database, Storage(settings), settings, ai)
    worker_id = uuid4()
    delay = 1
    try:
        while True:
            try:
                await database.open()
                break
            except DATABASE_ERRORS:
                logger.warning("Database unavailable at startup; retrying in %s seconds", delay)
                await database.close()
                database = Database(settings, max_size=pool)
                handlers = Handlers(database, Storage(settings), settings, ai)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
        # Concurrent slots share one process; only the first runs the periodic cleanup.
        await asyncio.gather(
            serve(database, handlers, worker_id),
            *(
                serve(database, handlers, uuid4(), cleanup=False)
                for _ in range(settings.worker_concurrency - 1)
            ),
        )
    finally:
        if ai:
            await ai.close()
        await database.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import selectors
    import sys

    try:
        factory = (
            (lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
            if sys.platform == "win32"
            else asyncio.SelectorEventLoop
        )
        with asyncio.Runner(loop_factory=factory) as runner:
            runner.run(run())
    except KeyboardInterrupt:
        pass
