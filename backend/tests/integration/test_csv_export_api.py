import csv
import io
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from inbox_support import add_email
from psycopg.types.json import Jsonb

from app.api.dependencies import Principal, principal
from app.config import Settings
from app.main import create_app
from app.parsers.registry import parse_document
from app.services.extraction import extract_labelled
from app.services.verification import verify

TAIL = (
    "Notify Party: ACME TRADING LLC\nPort of Loading: SHANGHAI\nPort of Discharge: ROTTERDAM\n"
    "Gross Weight: 22000 KG\n"
)


async def add_checked_pair(connection, workspace, external_id, si_containers, bl_containers, *, revision=1):
    """An email with an SI and a BL stored as extractions, and the report the verifier really produces."""
    email = await add_email(connection, workspace, external_id, category="BL_COMPARISON")
    extractions = []
    for role, title, containers in (("SI", "SHIPPING INSTRUCTIONS", si_containers), ("BL", "DRAFT BILL OF LADING", bl_containers)):
        attachment, row = uuid4(), uuid4()
        text = f"{title}\nShipper: ALPHA EXPORTS LTD\nConsignee: ACME TRADING LLC\n{TAIL}Container Count: {containers}\n"
        await connection.execute(
            """insert into public.attachments(id,workspace_id,email_id,original_name,storage_key,mime_type,byte_size,state)
            values(%s,%s,%s,%s,%s,'text/plain',10,'validated')""",
            (attachment, workspace, email, f"{external_id}_{role}.txt", f"key-{attachment}"),
        )
        extraction = extract_labelled(parse_document(text.encode(), f"{role}.txt")).model_copy(
            update={"document_id": str(row)}
        )
        await connection.execute(
            """insert into public.document_extractions(id,workspace_id,attachment_id,revision,document_type,schema_version,cache_key,output,run_metadata)
            values(%s,%s,%s,1,%s,'v1',%s,%s,'{}')""",
            (row, workspace, attachment, role, f"cache-{row}", Jsonb(extraction.model_dump(mode="json"))),
        )
        extractions.append(extraction)
    report = verify(*extractions, email_id=external_id, revision=revision, evidence_quality={})
    await connection.execute(
        """insert into public.verification_reports(workspace_id,email_id,si_extraction_id,bl_extraction_id,revision,status,complete,
        confidence,comparison_version,input_fingerprint,review_reasons,report)
        values(%s,%s,%s,%s,%s,%s,%s,1,'v1',%s,%s,%s)""",
        (workspace, email, extractions[0].document_id, extractions[1].document_id, revision, report.status,
         report.complete, f"fp-{email}-{revision}", list(report.review_reasons), Jsonb(report.model_dump(mode="json"))),
    )
    return email


async def clear(connection, *workspaces):
    """The factory adds one plain email and case per workspace; start from an empty mailbox."""
    await connection.execute("delete from public.cases where workspace_id = any(%s)", (list(workspaces),))
    await connection.execute("delete from public.emails where workspace_id = any(%s)", (list(workspaces),))


def client_for(app, context):
    app.dependency_overrides[principal] = lambda: Principal(context["user"], context["workspace"], "viewer")
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def rows_of(response):
    return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))


async def test_export_lists_flagged_fields_of_this_workspace_only(database, workspace_factory):
    mine, other = await workspace_factory(), await workspace_factory()
    async with database.connection() as connection:
        await clear(connection, mine["workspace"], other["workspace"])
        mismatch = await add_checked_pair(connection, mine["workspace"], "email_010", "3", "4")
        await add_checked_pair(connection, mine["workspace"], "email_011", "3", "3")
        trashed = await add_checked_pair(connection, mine["workspace"], "email_012", "3", "5")
        await connection.execute("update public.emails set deleted_at=now() where id=%s", (trashed,))
        await add_checked_pair(connection, other["workspace"], "email_099", "1", "2")
    app = create_app(Settings(environment="test"))
    app.state.database = database
    async with client_for(app, mine) as client:
        response = await client.get("/api/v1/exports/discrepancies.csv")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert 'attachment; filename="draftwise-discrepancies-workspace.csv"' == response.headers["content-disposition"]
        rows = rows_of(response)
        assert [(r["email_id"], r["field"], r["si_value"], r["bl_value"]) for r in rows] == [
            ("email_010", "container_count", "3", "4")
        ]
        assert rows[0]["explanation"] == "Container Count differs: SI 3; BL 4."
        assert "Container Count: 3" in rows[0]["si_evidence"] and "Container Count: 4" in rows[0]["bl_evidence"]

        one = await client.get(f"/api/v1/exports/discrepancies.csv?email_id={mismatch}&include_matches=true")
        assert len(rows_of(one)) == 7
        assert 'filename="draftwise-discrepancies-email.csv"' in one.headers["content-disposition"]


async def test_export_uses_the_latest_report_of_an_email(database, workspace_factory):
    context = await workspace_factory()
    async with database.connection() as connection:
        await clear(connection, context["workspace"])
        email = await add_checked_pair(connection, context["workspace"], "email_020", "3", "4")
        # A corrected revision replaces the older one; only its result is exported.
        await connection.execute(
            "update public.verification_reports set revision=1 where email_id=%s", (email,)
        )
        newer = verify(
            *(
                extract_labelled(parse_document(f"{t}\nContainer Count: 3\n".encode(), f"{r}.txt"))
                for t, r in (("SHIPPING INSTRUCTIONS", "si"), ("DRAFT BILL OF LADING", "bl"))
            ),
            email_id="email_020", revision=2, evidence_quality={},
        )
        await connection.execute(
            """insert into public.verification_reports(workspace_id,email_id,revision,status,complete,confidence,
            comparison_version,input_fingerprint,review_reasons,report)
            values(%s,%s,2,%s,%s,1,'v1','fp-new',%s,%s)""",
            (context["workspace"], email, newer.status, newer.complete, list(newer.review_reasons),
             Jsonb(newer.model_dump(mode="json"))),
        )
    app = create_app(Settings(environment="test"))
    app.state.database = database
    async with client_for(app, context) as client:
        rows = rows_of(await client.get("/api/v1/exports/discrepancies.csv"))
    assert {r["report_status"] for r in rows} == {"NEEDS_REVIEW"}  # revision 2, not the revision-1 mismatch


async def test_single_email_without_a_report_is_not_found(database, workspace_factory):
    context = await workspace_factory()
    app = create_app(Settings(environment="test"))
    app.state.database = database
    async with client_for(app, context) as client:
        response = await client.get(f"/api/v1/exports/discrepancies.csv?email_id={context['email']}")
        assert response.status_code == 404
        empty = await client.get("/api/v1/exports/discrepancies.csv")
        assert empty.status_code == 200 and rows_of(empty) == []
