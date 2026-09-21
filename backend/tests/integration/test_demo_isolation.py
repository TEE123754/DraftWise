import json
from zipfile import ZipFile

from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


async def test_demo_sessions_are_isolated_and_expire(database, tmp_path):
    bundle = tmp_path / "bundle.zip"
    with ZipFile(bundle, "w") as archive:
        archive.writestr(
            "inbox/email_001.json",
            json.dumps(
                {
                    "email_id": "email_001",
                    "from": "sender@example.test",
                    "subject": "Draft",
                    "body": "Please check the draft BL",
                    "attachments": ["attachments/email_001_SI.txt"],
                }
            ),
        )
        archive.writestr(
            "attachments/email_001_SI.txt", "SHIPPING INSTRUCTIONS\nShipper: Sample Exporter"
        )
    app = create_app(
        Settings(
            environment="test", demo_enabled=True, demo_dataset_path=str(bundle), database_url=None
        )
    )
    app.state.database = database
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as alice,
        AsyncClient(transport=transport, base_url="http://test") as bob,
    ):
        assert (await alice.post("/api/v1/demo/session")).status_code == 403
        origin = {"Origin": "http://localhost:3000"}
        first = await alice.post("/api/v1/demo/session", headers=origin)
        assert first.status_code == 201, first.text
        assert "HttpOnly" in first.headers["set-cookie"]
        alice_id = first.json()["workspace_id"]
        assert (await alice.post("/api/v1/demo/session", headers=origin)).json()[
            "workspace_id"
        ] == alice_id
        second = await bob.post("/api/v1/demo/session", headers=origin)
        assert second.status_code == 201, second.text
        bob_id = second.json()["workspace_id"]
        assert alice_id != bob_id
        headers = {"X-Demo-Mode": "true", "X-Workspace-Id": alice_id, **origin}
        response = await alice.get("/api/v1/emails", headers=headers)
        assert response.status_code == 200, response.text
        email_id = response.json()["items"][0]["id"]
        summary = await alice.get("/api/v1/dashboard", headers=headers)
        assert summary.status_code == 200, summary.text
        assert summary.json()["emails_total"] == 1
        assert summary.json()["emails_classified"] == 1
        assert summary.json()["spam_count"] == 0
        chat = await alice.post("/api/v1/chat", headers=headers, json={"message": "Give me a progress summary"})
        assert chat.status_code == 200, chat.text
        assert "1 emails" in chat.json()["answer"]
        assert chat.json()["method"] == "read_only_summary"
        # The one email is classified and needs no one, so nothing is waiting on a person.
        attention = await alice.post("/api/v1/chat", headers=headers, json={"message": "What needs my attention?"})
        assert attention.json()["answer"] == "Nothing needs a person right now."
        assert (await alice.post("/api/v1/chat", json={"message": "status"})).status_code == 401
        assert (await bob.get("/api/v1/dashboard", headers=headers)).status_code == 403
        queue = await alice.get("/api/v1/cases?readiness=needs_source&readiness=changes_required", headers=headers)
        assert queue.status_code == 200, queue.text
        assert len(queue.json()["items"]) == 1
        assert (await alice.get("/api/v1/gmail/connect", headers=headers)).status_code == 503
        forbidden = await bob.get("/api/v1/emails", headers=headers)
        assert forbidden.status_code == 403
        hidden = await bob.get(
            f"/api/v1/emails/{email_id}", headers={**headers, "X-Workspace-Id": bob_id}
        )
        assert hidden.status_code == 404
        assert (await alice.delete("/api/v1/demo/session", headers=origin)).status_code == 200
        assert (await alice.get("/api/v1/emails", headers=headers)).status_code == 401
        assert (
            await bob.get("/api/v1/emails", headers={**headers, "X-Workspace-Id": bob_id})
        ).status_code == 200


async def test_demo_disabled_by_default(database):
    app = create_app(Settings(environment="test", database_url=None))
    app.state.database = database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (
            await client.post("/api/v1/demo/session", headers={"Origin": "http://localhost:3000"})
        ).status_code == 404
