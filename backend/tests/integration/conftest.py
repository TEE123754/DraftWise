import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import pytest_asyncio
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from app.config import Settings
from app.infrastructure.database import Database

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def postgres_url():
    admin_url = os.environ.get("TEST_DATABASE_URL")
    if not admin_url:
        pytest.skip("TEST_DATABASE_URL is required for real PostgreSQL integration tests")
    params = conninfo_to_dict(admin_url)
    if params.get("host") not in {"localhost", "127.0.0.1", "::1", "postgres"}:
        raise RuntimeError("Integration tests require an isolated local PostgreSQL host")
    database_name = f"shipping_test_{uuid4().hex}"
    with psycopg.connect(admin_url, autocommit=True) as connection:
        for role in ("anon", "authenticated", "service_role"):
            if not connection.execute(
                "select 1 from pg_roles where rolname=%s", (role,)
            ).fetchone():
                connection.execute(sql.SQL("create role {} nologin").format(sql.Identifier(role)))
        connection.execute(
            sql.SQL(
                "create database {} template template0 encoding 'UTF8' lc_collate 'C' lc_ctype 'C'"
            ).format(sql.Identifier(database_name))
        )
    test_url = make_conninfo(admin_url, dbname=database_name)
    try:
        with psycopg.connect(test_url, autocommit=True) as connection:
            connection.execute("""create schema auth; create schema storage;
                create table auth.users(id uuid primary key);
                create function auth.uid() returns uuid language sql stable as $$
                    select nullif(current_setting('request.jwt.claim.sub', true),'')::uuid
                $$;
                create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
                grant usage on schema auth to authenticated;
                grant execute on function auth.uid() to authenticated;""")
            connection.execute((ROOT / "database/schema.sql").read_text(encoding="utf-8"))
            for migration in sorted((ROOT / "database/migrations").glob("*.sql")):
                connection.execute(migration.read_text(encoding="utf-8"))
        yield test_url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("drop database {} with (force)").format(sql.Identifier(database_name))
            )


@pytest_asyncio.fixture
async def database(postgres_url):
    database = Database(Settings(environment="test", database_url=postgres_url))
    await database.open()
    try:
        yield database
    finally:
        await database.close()


@pytest_asyncio.fixture
async def workspace_factory(database):
    async def create(role="reviewer"):
        user, email, case = uuid4(), uuid4(), uuid4()
        async with database.connection() as connection:
            await connection.execute("insert into auth.users(id) values(%s)", (user,))
            membership = await (
                await connection.execute(
                    "update public.memberships set role=%s where user_id=%s returning workspace_id",
                    (role, user),
                )
            ).fetchone()
            workspace = membership["workspace_id"]
            await connection.execute(
                """insert into public.emails(id,workspace_id,source_namespace,external_id,sender,body,content_sha256)
                values(%s,%s,'test',%s,'test@example.test','Please check the draft BL',%s)""",
                (email, workspace, str(email), "0" * 64),
            )
            await connection.execute(
                "insert into public.cases(id,workspace_id,email_id,reference) values(%s,%s,%s,'TEST-001')",
                (case, workspace, email),
            )
        return {"workspace": workspace, "user": user, "email": email, "case": case}

    return create
