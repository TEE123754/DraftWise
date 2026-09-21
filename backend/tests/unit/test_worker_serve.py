from contextlib import asynccontextmanager

import pytest
from psycopg import OperationalError

from app.workers import runner


class Stop(BaseException):
    """Ends the otherwise endless serve() loop without being swallowed by it."""


class FakeDatabase:
    @asynccontextmanager
    async def connection(self):
        yield object()


@pytest.fixture
def fast(monkeypatch):
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(runner.asyncio, "sleep", no_sleep)


def stop_after(calls, failures, stop_at):
    async def poll(*_args):
        calls.append(1)
        if len(calls) in failures:
            raise failures[len(calls)]
        if len(calls) >= stop_at:
            raise Stop
    return poll


async def test_worker_survives_unexpected_and_database_errors(monkeypatch, fast):
    calls = []
    failures = {1: RuntimeError("bug"), 2: OperationalError("closed"), 3: ValueError("bug")}
    monkeypatch.setattr(runner, "poll_once", stop_after(calls, failures, 5))

    async def purge(_connection):
        return None

    monkeypatch.setattr(runner, "purge_expired_samples", purge)
    with pytest.raises(Stop):
        await runner.serve(FakeDatabase(), None, "worker")
    assert len(calls) == 5


async def test_failing_cleanup_does_not_block_job_polling(monkeypatch, fast):
    calls, purges = [], []
    monkeypatch.setattr(runner, "poll_once", stop_after(calls, {}, 3))

    async def broken_purge(_connection):
        purges.append(1)
        raise RuntimeError("cleanup bug")

    monkeypatch.setattr(runner, "purge_expired_samples", broken_purge)
    with pytest.raises(Stop):
        await runner.serve(FakeDatabase(), None, "worker")
    assert len(calls) == 3
    assert len(purges) == 1  # retried on the 60 second schedule, not on every loop
