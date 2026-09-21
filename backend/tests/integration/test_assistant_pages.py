from httpx import ASGITransport, AsyncClient
from inbox_support import add_document, add_email

from app.api.dependencies import Principal, principal
from app.config import Settings
from app.main import create_app


def client_for(app, context):
    app.dependency_overrides[principal] = lambda: Principal(context["user"], context["workspace"], "viewer")
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def ask(client, message, **page):
    response = await client.post("/api/v1/chat", json={"message": message, **({"page": page} if page else {})})
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_assistant_knows_which_email_is_open_and_cites_it(database, workspace_factory):
    context = await workspace_factory()
    async with database.connection() as connection:
        # The factory adds one plain email and case; start with an empty mailbox.
        await connection.execute("delete from public.cases where workspace_id=%s", (context["workspace"],))
        await connection.execute("delete from public.emails where workspace_id=%s", (context["workspace"],))
        only_si = await add_email(connection, context["workspace"], "email_11", category="BL_COMPARISON")
        await add_document(connection, context["workspace"], only_si, "email_11_SI.txt", "SI")
        await add_email(connection, context["workspace"], "email_14", category="GENERAL", safety="suspected_phishing")
        await add_email(connection, context["workspace"], "email_15", category="SPAM")
    app = create_app(Settings(environment="test"))
    app.state.database = database
    async with client_for(app, context) as client:
        reply = await ask(client, "What should I do here?", email_id=str(only_si))
        assert "email_11: Needs documents." in reply["answer"]
        assert "Draft bill of lading not found" in reply["answer"]
        assert "Shipping instructions found; draft BL not found." in reply["answer"]
        assert reply["citations"] == [{"emailId": str(only_si), "label": "email_11"}]
        assert reply["method"] == "read_only_summary" and reply["source"]["href"] == "/inbox"

        # Without an open email "here" means nothing, so it does not guess.
        assert "do not have evidence" in (await ask(client, "What should I do here?"))["answer"]

        attention = await ask(client, "What needs my attention?")
        assert "2 emails need a person" in attention["answer"]  # the held one and the one missing its BL
        assert attention["answer"].index("email_14") < attention["answer"].index("email_11")  # most urgent first
        assert {c["label"] for c in attention["citations"]} == {"email_11", "email_14"}

        missing = await ask(client, "Which emails are missing documents?")
        assert "1 emails are missing documents" in missing["answer"] and missing["citations"][0]["label"] == "email_11"


async def test_an_email_from_another_workspace_is_never_described(database, workspace_factory):
    mine, other = await workspace_factory(), await workspace_factory()
    async with database.connection() as connection:
        secret = await add_email(connection, other["workspace"], "email_secret", category="GENERAL")
    app = create_app(Settings(environment="test"))
    app.state.database = database
    async with client_for(app, mine) as client:
        reply = await ask(client, "Explain this email", email_id=str(secret))
    assert "could not find" in reply["answer"] and reply["citations"] == []
    assert "email_secret" not in str(reply)
