from datetime import timedelta
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from inbox_support import SEEDED_AT, add_document, add_email, add_report

from app.api.dependencies import Principal, principal
from app.config import Settings
from app.main import create_app

DRAFT_REQUEST = "Please assist to send the draft BL for SIN1 for checking asap."


async def build_mailbox(database, workspace):
    """Returns {name: (email_id, expected_state)}."""
    async with database.connection() as connection:
        made = {}

        async def pair(external_id, status, comparisons=(), reasons=()):
            email = await add_email(connection, workspace, external_id, category="BL_COMPARISON")
            si = await add_document(connection, workspace, email, f"{external_id}_SI.txt", "SI")
            bl = await add_document(connection, workspace, email, f"{external_id}_BL.txt", "BL")
            await add_report(connection, workspace, email, si, bl, status, comparisons, reasons)
            return email

        made["checked"] = (await pair("email_2", "OK"), "checked")
        made["mismatch"] = (
            await pair("email_10", "MISMATCH", [{"field": "consignee", "decision": "mismatch"},
                                                {"field": "shipper", "decision": "match"}]),
            "mismatch_found",
        )
        made["review"] = (await pair("email_9", "NEEDS_REVIEW", reasons=["gross_weight_kg"]), "needs_review")
        waiting = await add_email(connection, workspace, "email_7", category="BL_COMPARISON", body=DRAFT_REQUEST)
        made["waiting"] = (waiting, "waiting_for_draft")
        only_si = await add_email(connection, workspace, "email_11", category="BL_COMPARISON")
        await add_document(connection, workspace, only_si, "email_11_SI.txt", "SI")
        made["only_si"] = (only_si, "needs_documents")
        unread = await add_email(connection, workspace, "email_12", category="BL_COMPARISON")
        await add_document(connection, workspace, unread, "email_12_SI.txt", "SI", extract=False)
        made["unread"] = (unread, "needs_review")
        made["spam"] = (await add_email(connection, workspace, "email_13", category="SPAM"), "spam")
        made["held"] = (
            await add_email(connection, workspace, "email_14", category="GENERAL", safety="suspected_phishing"),
            "held",
        )
        made["unclassified"] = (await add_email(connection, workspace, "email_15"), "needs_review")
        made["si_request"] = (await add_email(connection, workspace, "email_16", category="SI_REQUEST"), "classified")
        made["manual"] = (
            await add_email(connection, workspace, str(uuid4()), namespace="manual", category="GENERAL",
                            created=SEEDED_AT + timedelta(days=1)),
            "classified",
        )
    return made


def client_for(app, context):
    app.dependency_overrides[principal] = lambda: Principal(context["user"], context["workspace"], "viewer")
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_inbox_lists_every_email_with_its_state_id_order_and_filters(database, workspace_factory):
    context = await workspace_factory()
    async with database.connection() as connection:  # the factory adds one plain email and case; start clean
        await connection.execute("delete from public.cases where workspace_id=%s", (context["workspace"],))
        await connection.execute("delete from public.emails where workspace_id=%s", (context["workspace"],))
    made = await build_mailbox(database, context["workspace"])
    app = create_app(Settings(environment="test"))
    app.state.database = database
    async with client_for(app, context) as client:
        body = (await client.get("/api/v1/emails?limit=100")).json()
        items = body["items"]
        assert body["total"] == len(made) == len(items)

        # Newest first (the manual email), then natural order of the ID: email_2 < email_7 < email_10.
        ids = [item["display_id"] for item in items]
        assert ids[0] == "M-001"
        assert ids[1:] == ["email_2", "email_7", "email_9", "email_10", "email_11", "email_12",
                           "email_13", "email_14", "email_15", "email_16"]

        by_email = {item["id"]: item for item in items}
        for name, (email_id, expected) in made.items():
            assert by_email[str(email_id)]["state"] == expected, name
        mismatch = by_email[str(made["mismatch"][0])]
        assert mismatch["reasons"][0]["fields"] == ["consignee"]
        assert mismatch["documents"] == {"count": 2, "si": True, "bl": True, "other": 0, "unread": 0}
        assert by_email[str(made["only_si"][0])]["reasons"][0]["code"] == "missing_bl"
        assert by_email[str(made["unread"][0])]["reasons"][0]["code"] == "documents_unread"
        assert by_email[str(made["waiting"][0])]["action"]["kind"] == "await_draft"

        # Filters: the ID a row shows never depends on the filter, and paging keeps the filter.
        checked = (await client.get("/api/v1/emails?state=checked")).json()
        assert [i["display_id"] for i in checked["items"]] == ["email_2"]
        spam = (await client.get("/api/v1/emails?category=SPAM")).json()
        assert [i["display_id"] for i in spam["items"]] == ["email_13"]
        assert [i["display_id"] for i in (await client.get("/api/v1/emails?q=email_10")).json()["items"]] == ["email_10"]
        first = (await client.get("/api/v1/emails?state=needs_review&limit=2")).json()
        assert (len(first["items"]), first["total"], first["next_cursor"]) == (2, 3, "2")
        second = (await client.get("/api/v1/emails?state=needs_review&limit=2&offset=2")).json()
        assert (len(second["items"]), second["next_cursor"]) == (1, None)
        assert {i["state"] for i in first["items"] + second["items"]} == {"needs_review"}
        assert (await client.get("/api/v1/emails?state=bogus")).status_code == 422

        # Needs-attention view: only what a person can act on, most urgent state first.
        urgent = (await client.get("/api/v1/emails?attention=true&limit=100")).json()
        order = [item["state"] for item in urgent["items"]]
        assert order == ["held", "mismatch_found", "needs_review", "needs_review", "needs_review", "needs_documents"]
        assert urgent["total"] == 6

        counts = (await client.get("/api/v1/emails/counts")).json()
        assert counts["total"] == len(made)
        assert sum(counts["by_state"].values()) == len(made)
        assert counts["by_state"]["needs_review"] == 3
        assert counts["by_category"]["unclassified"] == 1
        assert sum(counts["by_category"].values()) == len(made)

        detail = (await client.get(f"/api/v1/emails/{made['mismatch'][0]}")).json()
        assert (detail["display_id"], detail["state"], detail["tone"]) == ("email_10", "mismatch_found", "yellow")


def field(value):
    return {"state": "present", "raw_value": value, "alternatives": [], "evidence": [{"block_id": "b1", "quote": f"Value: {value}"}]}


async def test_email_detail_lays_out_si_bl_and_email_values_from_the_stored_report(database, workspace_factory):
    context = await workspace_factory()
    body = "Please check the draft.\nGross weight: 22 MT\nPort of loading: CNSHA"
    async with database.connection() as connection:
        email = await add_email(connection, context["workspace"], "email_10", category="BL_COMPARISON", body=body)
        si = await add_document(connection, context["workspace"], email, "SI.txt", "SI",
                                fields={"gross_weight_kg": field("22000 KG"), "port_of_loading": field("SGSIN")})
        bl = await add_document(connection, context["workspace"], email, "BL.txt", "BL",
                                fields={"gross_weight_kg": field("23000 KG"), "port_of_loading": field("SGSIN")})
        await add_report(
            connection, context["workspace"], email, si, bl, "MISMATCH",
            [
                {"field": "gross_weight_kg", "decision": "mismatch", "explanation": "Gross weight differs.",
                 "si": {"normalized": "22000"}, "bl": {"normalized": "23000"}},
                {"field": "port_of_loading", "decision": "match", "explanation": "Match.",
                 "si": {"normalized": "SGSIN"}, "bl": {"normalized": "SGSIN"}},
            ],
        )
    app = create_app(Settings(environment="test"))
    app.state.database = database
    async with client_for(app, context) as client:
        detail = (await client.get(f"/api/v1/emails/{email}")).json()

    table = detail["field_table"]
    assert (table["status"], table["documents"]) == ("MISMATCH", {"si": True, "bl": True})
    rows = {row["field"]: row for row in table["rows"]}
    weight = rows["gross_weight_kg"]
    assert (weight["si"]["value"], weight["bl"]["value"]) == ("22000 KG", "23000 KG")
    assert (weight["decision"], weight["explanation"]) == ("mismatch", "Gross weight differs.")
    assert weight["si"]["quote"] == "Value: 22000 KG"
    # "22 MT" in the email is 22000 kg: it agrees with the SI but not with the BL.
    assert weight["email"]["value"] == "22 MT" and weight["email"]["mark"] == "differs"
    # The email says Shanghai; both documents say Singapore.
    assert (rows["port_of_loading"]["email"]["value"], rows["port_of_loading"]["email"]["mark"]) == ("CNSHA", "differs")
    assert rows["shipper"]["si"]["state"] == "missing" and rows["shipper"]["decision"] is None
    assert detail["classification_summary"]["method"] == "rules"
    assert detail["classification_summary"]["category"] == "BL_COMPARISON"


async def test_email_detail_without_documents_still_returns_an_empty_table(database, workspace_factory):
    context = await workspace_factory()
    async with database.connection() as connection:
        email = await add_email(connection, context["workspace"], "email_20")
    app = create_app(Settings(environment="test"))
    app.state.database = database
    async with client_for(app, context) as client:
        detail = (await client.get(f"/api/v1/emails/{email}")).json()
    assert detail["field_table"]["documents"] == {"si": False, "bl": False}
    assert detail["field_table"]["status"] is None
    assert detail["classification_summary"] is None


async def test_inbox_is_scoped_to_the_workspace(database, workspace_factory):
    mine, other = await workspace_factory(), await workspace_factory()
    async with database.connection() as connection:
        await add_email(connection, other["workspace"], "email_secret", category="GENERAL")
    app = create_app(Settings(environment="test"))
    app.state.database = database
    async with client_for(app, mine) as client:
        body = (await client.get("/api/v1/emails?limit=100")).json()
    assert "email_secret" not in [item["display_id"] for item in body["items"]]


async def test_email_detail_says_whether_the_email_matches_its_own_documents(database, workspace_factory):
    context = await workspace_factory()
    async with database.connection() as connection:
        matching = await add_email(
            connection, context["workspace"], "email_20", category="BL_COMPARISON",
            body="Please check the draft BL for SIN525534192. Booking ref: BK12345.",
        )
        elsewhere = await add_email(
            connection, context["workspace"], "email_21", category="BL_COMPARISON",
            body="Please check the draft BL. Booking ref: ZZ99999.",
        )
        bare = await add_email(connection, context["workspace"], "email_22", category="GENERAL")
        for email in (matching, elsewhere):
            await add_document(connection, context["workspace"], email, f"{email}_SI.txt", "SI")
        rows = await (await connection.execute(
            "select id,email_id from public.attachments where workspace_id=%s", (context["workspace"],)
        )).fetchall()
        for row in rows:
            await connection.execute(
                """insert into public.source_blocks(id,workspace_id,attachment_id,parser_version,ordinal,text_content,locator,quality)
                values(%s,%s,%s,'v1',0,'Booking no: BK12345 / SIN525534192','{}',1)""",
                (uuid4(), context["workspace"], row["id"]),
            )
    app = create_app(Settings(environment="test"))
    app.state.database = database
    async with client_for(app, context) as client:
        good = (await client.get(f"/api/v1/emails/{matching}")).json()["reference_check"]
        assert good["status"] == "matches"
        assert {row["code"] for row in good["cited"]} == {"BK12345", "SIN525534192"}
        assert all(row["in_documents"] for row in good["cited"])

        bad = (await client.get(f"/api/v1/emails/{elsewhere}")).json()["reference_check"]
        assert bad["status"] == "flagged" and bad["cited"][0]["code"] == "ZZ99999"
        assert bad["cited"][0]["in_documents"] is False

        assert (await client.get(f"/api/v1/emails/{bare}")).json()["reference_check"]["status"] == "no_documents"
