"""Who gets the workers first: a visitor who has just opened the demo must not wait behind a backlog."""

from uuid import uuid4

from inbox_support import add_document, add_email

from app.repositories.jobs import claim, enqueue, promote
from app.services.offline_processing import queue_offline_processing
from app.services.workflow import start_workflow


async def make_demo(connection, context, minutes_old):
    await connection.execute(
        """insert into public.demo_sessions(token_hash,workspace_id,actor_id,manifest_sha256,created_at)
        values(%s,%s,%s,%s,now()-%s*interval '1 minute')""",
        (uuid4().hex + uuid4().hex, context["workspace"], context["user"], "0" * 64, minutes_old),
    )


async def add_job(connection, context, key, kind="extract"):
    return await enqueue(
        connection, workspace_id=context["workspace"], kind=kind, key=key, payload={"key": key}
    )


async def claim_all(connection, count):
    return [(await claim(connection))["idempotency_key"] for _ in range(count)]


async def test_real_workspaces_first_then_the_newest_demo_session(database, workspace_factory):
    real, old, new = await workspace_factory(), await workspace_factory(), await workspace_factory()
    async with database.connection() as connection:
        await make_demo(connection, old, minutes_old=30)
        await make_demo(connection, new, minutes_old=1)
        # Queued oldest-first, so plain first-come-first-served would answer old, new, real.
        for name, context in (("old", old), ("new", new), ("real", real)):
            await add_job(connection, context, name)
        assert await claim_all(connection, 3) == ["real", "new", "old"]
        assert await claim(connection) is None


async def test_within_a_workspace_comparisons_finish_before_new_reading_starts(database, workspace_factory):
    context = await workspace_factory()
    async with database.connection() as connection:
        await add_job(connection, context, "read-1")
        await add_job(connection, context, "compare-1", kind="verify")
        await add_job(connection, context, "read-2")
        assert await claim_all(connection, 3) == ["compare-1", "read-1", "read-2"]


async def test_a_click_is_answered_before_the_bulk_reading_of_the_mailbox(database, workspace_factory):
    context = await workspace_factory()
    async with database.connection() as connection:
        for name in ("bulk-1", "bulk-2"):  # seeded first, so oldest
            await enqueue(
                connection, workspace_id=context["workspace"], kind="extract", key=name,
                payload={"offline": True, "key": name},
            )
        await add_job(connection, context, "clicked", kind="classify")  # queued last
        await enqueue(
            connection, workspace_id=context["workspace"], kind="verify", key="compare",
            payload={"offline": True},
        )
        assert await claim_all(connection, 4) == ["compare", "clicked", "bulk-1", "bulk-2"]


async def test_a_mailbox_is_read_in_inbox_order(database, workspace_factory):
    context = await workspace_factory()
    workspace = context["workspace"]
    async with database.connection() as connection:
        await connection.execute("delete from public.cases where workspace_id=%s", (workspace,))
        await connection.execute("delete from public.emails where workspace_id=%s", (workspace,))
        made = {}
        for name in ("email_003", "email_001", "email_010", "email_002"):  # stored out of order
            email = await add_email(connection, workspace, name, category="BL_COMPARISON")
            await add_document(connection, workspace, email, f"{name}_SI.txt", "SI", extract=False)
            await add_document(connection, workspace, email, f"{name}_BL.txt", "BL", extract=False)
            made[email] = name
        assert (await queue_offline_processing(connection, workspace))["queued"] == 4
        claimed = [(await claim(connection))["email_id"] for _ in range(4)]
    assert [made[email] for email in claimed] == ["email_001", "email_002", "email_003", "email_010"]


async def test_promote_moves_a_waiting_job_to_the_front_but_not_a_backing_off_one(
    database, workspace_factory
):
    context = await workspace_factory()
    async with database.connection() as connection:
        await add_job(connection, context, "first")
        wanted = await add_job(connection, context, "wanted")
        backing_off = await add_job(connection, context, "backing-off")
        await connection.execute(
            "update public.processing_jobs set state='retry_wait',available_at=now()+interval '5 minutes' where id=%s",
            (backing_off["id"],),
        )
        await promote(connection, context["workspace"], wanted["id"])
        await promote(connection, context["workspace"], backing_off["id"])
        assert await claim_all(connection, 2) == ["wanted", "first"]
        assert await claim(connection) is None  # the backing-off job keeps its delay


async def test_asking_again_for_a_queued_email_moves_it_to_the_front(database, workspace_factory):
    context = await workspace_factory()
    workspace = context["workspace"]
    async with database.connection() as connection:
        await connection.execute("delete from public.cases where workspace_id=%s", (workspace,))
        await connection.execute("delete from public.emails where workspace_id=%s", (workspace,))
        emails = {}
        for name in ("email_001", "email_002", "email_003"):
            email = await add_email(connection, workspace, name, category="BL_COMPARISON")
            await add_document(connection, workspace, email, f"{name}_SI.txt", "SI", extract=False)
            await add_document(connection, workspace, email, f"{name}_BL.txt", "BL", extract=False)
            emails[name] = email
        await queue_offline_processing(connection, workspace)
        # A reviewer clicks "Review with local rules" on the email at the back of the queue.
        answer = await start_workflow(connection, workspace, emails["email_003"], "click-1", False)
        first = await claim(connection)
        queued_jobs = await (
            await connection.execute(
                "select count(*) as n from public.processing_jobs where workspace_id=%s", (workspace,)
            )
        ).fetchone()
    assert answer["email_id"] == str(emails["email_003"])
    assert first["email_id"] == emails["email_003"]
    assert queued_jobs["n"] == 3  # promoted, not duplicated
