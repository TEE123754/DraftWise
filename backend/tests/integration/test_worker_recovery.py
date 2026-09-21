import pytest

from app.domain.errors import DomainError
from app.repositories.jobs import claim, enqueue, fail, fence, finish, recover


async def test_expired_worker_cannot_commit_after_reclaim(database, workspace_factory):
    context = await workspace_factory()
    async with database.connection() as connection:
        await enqueue(
            connection,
            workspace_id=context["workspace"],
            kind="classify",
            key="recovery",
            payload={},
            email_id=context["email"],
        )
        original = await claim(connection)
    async with database.connection() as connection:
        await connection.execute(
            "update public.processing_jobs set leased_until=now()-interval '1 second' where id=%s",
            (original["id"],),
        )
        await recover(connection)
        await connection.execute(
            "update public.processing_jobs set available_at=now() where id=%s", (original["id"],)
        )
        replacement = await claim(connection)
    assert replacement["id"] == original["id"]
    assert replacement["lease_token"] != original["lease_token"]
    with pytest.raises(DomainError):
        async with database.connection() as connection:
            await finish(connection, original, {"stale": True})
    async with database.connection() as connection:
        await finish(connection, replacement, {"fresh": True})
    async with database.connection() as connection:
        job = await (
            await connection.execute(
                "select state,result,attempt from public.processing_jobs where id=%s",
                (original["id"],),
            )
        ).fetchone()
    assert job == {"state": "succeeded", "result": {"fresh": True}, "attempt": 2}


async def test_artifacts_and_success_roll_back_together(database, workspace_factory):
    context = await workspace_factory()
    async with database.connection() as connection:
        await enqueue(
            connection,
            workspace_id=context["workspace"],
            kind="classify",
            key="rollback",
            payload={},
            email_id=context["email"],
        )
        job = await claim(connection)
    with pytest.raises(RuntimeError):
        async with database.connection() as connection:
            await fence(connection, job)
            await connection.execute(
                "update public.cases set reference='SHOULD ROLLBACK' where id=%s",
                (context["case"],),
            )
            await finish(connection, job, {})
            raise RuntimeError("Simulated failure before transaction commit")
    async with database.connection() as connection:
        case = await (
            await connection.execute(
                "select reference from public.cases where id=%s", (context["case"],)
            )
        ).fetchone()
        state = await (
            await connection.execute(
                "select state from public.processing_jobs where id=%s", (job["id"],)
            )
        ).fetchone()
    assert case["reference"] == "TEST-001"
    assert state["state"] == "running"


@pytest.mark.parametrize("stale,expired", [(False, False), (True, False), (False, True)])
async def test_terminal_failure_only_projects_current_case(
    database, workspace_factory, stale, expired
):
    context = await workspace_factory()
    async with database.connection() as connection:
        await connection.execute(
            "update public.cases set readiness='checking' where id=%s", (context["case"],)
        )
        await enqueue(
            connection,
            workspace_id=context["workspace"],
            kind="verify",
            key="failure",
            payload={
                "case_id": str(context["case"]),
                "case_version": 1,
                "si_extraction_id": None,
                "bl_extraction_id": None,
            },
            email_id=context["email"],
        )
        job = await claim(connection)
        if stale:
            await connection.execute(
                "update public.cases set version=2 where id=%s", (context["case"],)
            )
        if expired:
            await connection.execute(
                "update public.processing_jobs set leased_until=now()-interval '1 second',attempt=max_attempts where id=%s",
                (job["id"],),
            )
            await fail(connection, job, DomainError("TEST_FAILURE", "Test failure"))
            before = await (
                await connection.execute(
                    "select readiness from public.cases where id=%s", (context["case"],)
                )
            ).fetchone()
            assert before["readiness"] == "checking"
            await recover(connection)
        else:
            await fail(connection, job, DomainError("TEST_FAILURE", "Test failure"))
    async with database.connection() as connection:
        case = await (
            await connection.execute(
                "select readiness from public.cases where id=%s", (context["case"],)
            )
        ).fetchone()
    assert case["readiness"] == ("checking" if stale else "failed")
