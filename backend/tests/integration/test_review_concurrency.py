import asyncio

import pytest

from app.domain.errors import DomainError
from app.repositories.cases import get_case, require_version
from app.repositories.jobs import enqueue


async def test_only_one_concurrent_case_edit_commits(database, workspace_factory):
    context = await workspace_factory()

    async def edit():
        try:
            async with database.connection() as connection:
                case = await get_case(connection, context["workspace"], context["case"], lock=True)
                require_version(case, 1)
                await connection.execute(
                    "update public.cases set version=version+1 where workspace_id=%s and id=%s",
                    (context["workspace"], context["case"]),
                )
            return "saved"
        except DomainError:
            return "stale"

    assert sorted(await asyncio.gather(edit(), edit())) == ["saved", "stale"]


async def test_processing_idempotency_is_atomic(database, workspace_factory):
    context = await workspace_factory()

    async def submit():
        async with database.connection() as connection:
            return await enqueue(
                connection,
                workspace_id=context["workspace"],
                kind="classify",
                key="same-key",
                payload={"email_id": str(context["email"])},
                email_id=context["email"],
            )

    first, second = await asyncio.gather(submit(), submit())
    assert first["id"] == second["id"]
    with pytest.raises(DomainError) as error:
        async with database.connection() as connection:
            await enqueue(
                connection,
                workspace_id=context["workspace"],
                kind="classify",
                key="same-key",
                payload={"different": True},
                email_id=context["email"],
            )
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
