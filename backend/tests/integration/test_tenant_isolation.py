from uuid import uuid4

import pytest
from psycopg.errors import ForeignKeyViolation

from app.domain.errors import DomainError
from app.repositories.cases import get_case


async def test_new_user_receives_private_admin_workspace(database):
    user_id = uuid4()
    async with database.connection() as connection:
        await connection.execute("insert into auth.users(id) values(%s)", (user_id,))
        membership = await (
            await connection.execute(
                """select m.role,w.name from public.memberships m join public.workspaces w
                on w.id=m.workspace_id where m.user_id=%s""",
                (user_id,),
            )
        ).fetchone()
    assert membership == {"role": "admin", "name": "My shipping team"}


async def test_case_lookup_hides_other_workspace(database, workspace_factory):
    owner, outsider = await workspace_factory(), await workspace_factory()
    async with database.connection() as connection:
        with pytest.raises(DomainError) as error:
            await get_case(connection, outsider["workspace"], owner["case"])
        assert error.value.status == 404


async def test_composite_foreign_keys_reject_cross_tenant_attachment(database, workspace_factory):
    owner, outsider = await workspace_factory(), await workspace_factory()
    with pytest.raises(ForeignKeyViolation):
        async with database.connection() as connection:
            await connection.execute(
                """insert into public.attachments(workspace_id,email_id,original_name,storage_key,mime_type,byte_size)
                values(%s,%s,'document.txt','unique-key','text/plain',20)""",
                (outsider["workspace"], owner["email"]),
            )


async def test_rls_membership_and_workspace_visibility(database, workspace_factory):
    owner, outsider = await workspace_factory(), await workspace_factory()
    async with database.connection() as connection:
        await connection.execute("set local role authenticated")
        await connection.execute(
            "select set_config('request.jwt.claim.sub',%s,true)", (str(owner["user"]),)
        )
        memberships = await (
            await connection.execute("select workspace_id from public.memberships")
        ).fetchall()
        workspaces = await (await connection.execute("select id from public.workspaces")).fetchall()
        assert memberships == [{"workspace_id": owner["workspace"]}]
        assert workspaces == [{"id": owner["workspace"]}]
        assert outsider["workspace"] not in [row["id"] for row in workspaces]
