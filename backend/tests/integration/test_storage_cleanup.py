from uuid import uuid4

from inbox_support import add_email

from app.services.storage_cleanup import ATTEMPT_LIMIT, process_storage_cleanup
from app.services.trash_retention import purge_trash


class FakeStorage:
    """Records deletions; keys in `broken` fail the way an unreachable storage service would."""

    def __init__(self, broken=(), configured=True):
        self.deleted, self.broken, self._configured = [], set(broken), configured

    def configured(self):
        return self._configured

    async def delete(self, key):
        if key in self.broken:
            raise ConnectionError("storage is down")
        self.deleted.append(key)


async def attach(connection, workspace, email, key, name="file.txt"):
    await connection.execute(
        """insert into public.attachments(id,workspace_id,email_id,original_name,storage_key,mime_type,byte_size,state)
        values(%s,%s,%s,%s,%s,'text/plain',10,'validated')""",
        (uuid4(), workspace, email, name, key),
    )


async def trash(connection, workspace, email, days=31):
    await connection.execute(
        "update public.emails set deleted_at=now()-make_interval(days=>%s),deleted_reason='test' where workspace_id=%s and id=%s",
        (days, workspace, email),
    )


async def rows(database, workspace):
    async with database.connection() as connection:
        found = await (
            await connection.execute(
                "select storage_key,state,attempts,last_error,next_attempt_at>now() as later from public.storage_cleanup where workspace_id=%s",
                (workspace,),
            )
        ).fetchall()
    return {row["storage_key"]: row for row in found}


async def make_expired_email(database, context, keys, *, linked_key=None):
    """An email in Trash for 31 days with one attachment per key; optionally another email linking `linked_key`."""
    workspace = context["workspace"]
    async with database.connection() as connection:
        await connection.execute("delete from public.cases where workspace_id=%s", (workspace,))
        await connection.execute("delete from public.emails where workspace_id=%s", (workspace,))
        gone = await add_email(connection, workspace, "email_1", category="GENERAL")
        for key in keys:
            await attach(connection, workspace, gone, key)
        keeper = await add_email(connection, workspace, "email_2", category="GENERAL")
        if linked_key:
            await attach(connection, workspace, keeper, f"linked-source/{workspace}/{uuid4()}/{linked_key}")
        await trash(connection, workspace, gone)
        await purge_trash(connection)
        return keeper


async def test_purging_queues_the_uploaded_objects_nothing_else_uses(database, workspace_factory):
    context = await workspace_factory()
    workspace = context["workspace"]
    used_elsewhere, alone = f"uploads/{workspace}/a/shared.pdf", f"uploads/{workspace}/b/alone.pdf"
    seed = f"demo-seed/{workspace}/c/attachments/sample.txt"
    await make_expired_email(database, context, [used_elsewhere, alone, seed], linked_key=used_elsewhere)

    queued = await rows(database, workspace)
    # The linked copy still needs the shared bytes, and a bundled demo file is not an uploaded object.
    assert set(queued) == {alone}
    assert queued[alone]["state"] == "pending"
    async with database.connection() as connection:
        left = await (await connection.execute("select count(*) as n from public.emails where workspace_id=%s and external_id='email_1'", (workspace,))).fetchone()
    assert left["n"] == 0  # the database records really are gone


async def test_a_failed_delete_is_retried_later_and_succeeds_without_being_lost(database, workspace_factory):
    context = await workspace_factory()
    workspace = context["workspace"]
    key = f"uploads/{workspace}/x/report.pdf"
    await make_expired_email(database, context, [key])
    down = FakeStorage(broken={key})

    assert await process_storage_cleanup(database, down) == 0
    after_failure = (await rows(database, workspace))[key]
    assert (after_failure["state"], after_failure["attempts"], after_failure["last_error"]) == ("pending", 1, "ConnectionError")
    assert after_failure["later"] is True  # backed off, not retried in a tight loop

    assert await process_storage_cleanup(database, FakeStorage()) == 0  # not due yet: nothing is attempted
    async with database.connection() as connection:
        await connection.execute("update public.storage_cleanup set next_attempt_at=now() where workspace_id=%s", (workspace,))
    healthy = FakeStorage()
    assert await process_storage_cleanup(database, healthy) == 1
    done = (await rows(database, workspace))[key]
    assert (done["state"], done["attempts"], done["last_error"]) == ("deleted", 2, None)
    assert healthy.deleted == [key]
    assert await process_storage_cleanup(database, healthy) == 0  # never deleted twice


async def test_bytes_that_a_link_needs_again_are_kept(database, workspace_factory):
    context = await workspace_factory()
    workspace = context["workspace"]
    key = f"uploads/{workspace}/y/contract.pdf"
    keeper = await make_expired_email(database, context, [key])
    assert (await rows(database, workspace))[key]["state"] == "pending"
    async with database.connection() as connection:  # a linked copy appears after the purge
        await attach(connection, workspace, keeper, f"linked-source/{workspace}/{uuid4()}/{key}")
    storage = FakeStorage()
    assert await process_storage_cleanup(database, storage) == 0
    assert storage.deleted == [] and (await rows(database, workspace))[key]["state"] == "skipped"


async def test_a_permanently_failing_delete_stops_after_the_limit_and_is_left_for_an_administrator(database, workspace_factory):
    context = await workspace_factory()
    workspace = context["workspace"]
    key = f"uploads/{workspace}/z/stuck.pdf"
    await make_expired_email(database, context, [key])
    down = FakeStorage(broken={key})
    for _ in range(ATTEMPT_LIMIT):
        async with database.connection() as connection:
            await connection.execute("update public.storage_cleanup set next_attempt_at=now() where workspace_id=%s and state='pending'", (workspace,))
        await process_storage_cleanup(database, down)
    stuck = (await rows(database, workspace))[key]
    assert (stuck["state"], stuck["attempts"], stuck["last_error"]) == ("failed", ATTEMPT_LIMIT, "ConnectionError")
    async with database.connection() as connection:
        await connection.execute("update public.storage_cleanup set next_attempt_at=now() where workspace_id=%s", (workspace,))
    assert await process_storage_cleanup(database, FakeStorage()) == 0  # a failed row is not picked up again


async def test_nothing_is_attempted_when_storage_is_not_configured(database, workspace_factory):
    context = await workspace_factory()
    workspace = context["workspace"]
    key = f"uploads/{workspace}/w/pending.pdf"
    await make_expired_email(database, context, [key])
    assert await process_storage_cleanup(database, FakeStorage(configured=False)) == 0
    row = (await rows(database, workspace))[key]
    assert (row["state"], row["attempts"]) == ("pending", 0)  # not burnt: it will be tried once storage exists
