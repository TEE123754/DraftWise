from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from test_offline_processing import write_bundle

from app.api import gmail
from app.api.dependencies import Principal, principal
from app.config import Settings
from app.main import create_app
from app.services.dataset_import import build_manifest, open_source
from app.services.sample_fetch import fetch_all_samples

ORIGIN = {"Origin": "http://localhost:3000"}


async def test_fetching_the_sample_mailbox_reuses_what_the_demo_already_holds(database, tmp_path):
    bundle = tmp_path / "mailbox.zip"
    write_bundle(bundle)
    settings = Settings(environment="test", demo_enabled=True, demo_dataset_path=str(bundle))
    app = create_app(settings)
    app.state.database = database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api:
        session = await api.post("/api/v1/demo/session", headers=ORIGIN)
        assert session.status_code == 201, session.text
        headers = {
            **ORIGIN,
            "X-Demo-Mode": "true",
            "X-Workspace-Id": session.json()["workspace_id"],
            "Idempotency-Key": "fetch-all",
        }
        # No email ID: the whole sample mailbox.
        fetched = await api.post("/api/v1/demo/gmail/fetch", headers=headers, json={})
        assert fetched.status_code == 200, fetched.text
        body = fetched.json()
        assert (body["fetched"], body["imported"], body["reused"]) == (6, 0, 6)
        assert body["simulation"] is True and "6 emails" in body["message"]
        # A single email can still be fetched by ID.
        one = await api.post("/api/v1/demo/gmail/fetch", headers=headers, json={"email_id": "email_001"})
        assert one.status_code == 200 and one.json()["imported"] is False
        async with database.connection() as connection:
            total = await (
                await connection.execute("select count(*) as n from public.emails where workspace_id=%s",
                                         (session.json()["workspace_id"],))
            ).fetchone()
        assert total["n"] == 6  # nothing was duplicated


async def test_fetching_into_an_empty_workspace_imports_every_sample_email_once(
    database, workspace_factory, tmp_path
):
    bundle = tmp_path / "mailbox.zip"
    write_bundle(bundle)
    workspace = (await workspace_factory())["workspace"]
    source = open_source(str(bundle))
    manifest = build_manifest(source)
    async with database.connection() as connection:
        first = await fetch_all_samples(connection, source, manifest, workspace, "k1")
        second = await fetch_all_samples(connection, source, manifest, workspace, "k2")
        count = await (
            await connection.execute(
                "select count(*) as n from public.emails where workspace_id=%s and source_namespace='demo-bundle'",
                (workspace,),
            )
        ).fetchone()
    source.close()
    assert (first["fetched"], first["imported"], first["reused"]) == (6, 6, 0)
    assert (second["fetched"], second["imported"], second["reused"]) == (6, 0, 6)
    assert count["n"] == 6


def gmail_client(database, context, *, demo=False):
    app = create_app(Settings(environment="test"))
    app.state.database = database
    app.dependency_overrides[principal] = lambda: Principal(context["user"], context["workspace"], "reviewer")
    headers = {"X-Demo-Mode": "true"} if demo else {}
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers)


async def test_a_real_user_who_tries_to_fetch_from_gmail_is_told_it_is_future_development(
    database, workspace_factory
):
    context = await workspace_factory()
    async with gmail_client(database, context) as api:
        listing = (await api.get("/api/v1/gmail/connections")).json()
        assert (listing["available"], listing["future"]) == (False, True)
        assert listing["message"] == gmail.FUTURE_MESSAGE
        for response in (
            await api.get("/api/v1/gmail/connect"),
            await api.post(f"/api/v1/gmail/connections/{uuid4()}/sync"),
        ):
            assert response.status_code == 501
            error = response.json()["error"]
            assert error["code"] == "GMAIL_FUTURE_DEVELOPMENT" and "future release" in error["message"]


async def test_asking_to_sync_never_marks_a_connection_as_syncing(database, workspace_factory):
    context = await workspace_factory()
    connection_id = uuid4()
    async with database.connection() as connection:
        await connection.execute(
            """insert into public.mailbox_connections(id,workspace_id,email,state,access_token,refresh_token)
            values(%s,%s,'someone@example.test','active','x','y')""",
            (connection_id, context["workspace"]),
        )
    async with gmail_client(database, context) as api:
        listed = (await api.get("/api/v1/gmail/connections")).json()
        assert [item["email"] for item in listed["items"]] == ["someone@example.test"]  # still listed to disconnect
        assert (await api.post(f"/api/v1/gmail/connections/{connection_id}/sync")).status_code == 501
    async with database.connection() as connection:
        row = await (
            await connection.execute("select state from public.mailbox_connections where id=%s", (connection_id,))
        ).fetchone()
    assert row["state"] == "active"


async def test_the_demo_keeps_its_own_message(database, workspace_factory):
    context = await workspace_factory()
    async with gmail_client(database, context, demo=True) as api:
        listing = (await api.get("/api/v1/gmail/connections")).json()
    assert listing["message"] == gmail.DEMO_MESSAGE
