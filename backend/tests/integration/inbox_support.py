"""Helpers that build a small mailbox directly in the test database."""

from datetime import UTC, datetime
from uuid import uuid4

from psycopg.types.json import Jsonb

SEEDED_AT = datetime(2026, 1, 1, tzinfo=UTC)


async def add_email(connection, workspace, external_id, *, category=None, body="Hello", namespace="demo-bundle",
                    created=SEEDED_AT, safety=None, ambiguous=False):
    email = uuid4()
    await connection.execute(
        """insert into public.emails(id,workspace_id,source_namespace,external_id,sender,subject,body,content_sha256,created_at)
        values(%s,%s,%s,%s,'sender@example.test',%s,%s,%s,%s)""",
        (email, workspace, namespace, external_id, f"Subject of {external_id}", body, "0" * 64, created),
    )
    if category:
        await connection.execute(
            """insert into public.email_classifications(workspace_id,email_id,revision,category,ambiguous,confidence,decided_by,run_metadata)
            values(%s,%s,1,%s,%s,1,'rule','{}')""",
            (workspace, email, category, ambiguous),
        )
    if safety:
        await connection.execute(
            "insert into public.email_safety(workspace_id,email_id,risk_state,severity,held_for_review) values(%s,%s,%s,'high',%s)",
            (workspace, email, safety, safety == "suspected_phishing"),
        )
    return email


async def add_document(connection, workspace, email, name, role, *, extract=True, fields=None):
    """Attach a file; when `extract`, also store its extraction and return that extraction's ID."""
    attachment = uuid4()
    await connection.execute(
        """insert into public.attachments(id,workspace_id,email_id,original_name,storage_key,mime_type,byte_size,state)
        values(%s,%s,%s,%s,%s,'text/plain',10,'validated')""",
        (attachment, workspace, email, name, f"key-{attachment}"),
    )
    if extract:
        extraction = uuid4()
        await connection.execute(
            """insert into public.document_extractions(id,workspace_id,attachment_id,revision,document_type,schema_version,cache_key,output,run_metadata)
            values(%s,%s,%s,1,%s,'v1',%s,%s,'{}')""",
            (extraction, workspace, attachment, role, f"cache-{extraction}", Jsonb({"fields": fields or {}})),
        )
        return extraction


async def add_report(connection, workspace, email, si, bl, status, comparisons=(), reasons=()):
    await connection.execute(
        """insert into public.verification_reports(workspace_id,email_id,si_extraction_id,bl_extraction_id,revision,status,complete,
        confidence,comparison_version,input_fingerprint,review_reasons,report)
        values(%s,%s,%s,%s,1,%s,%s,1,'v1',%s,%s,%s)""",
        (workspace, email, si, bl, status, status != "NEEDS_REVIEW", f"fp-{email}", list(reasons),
         Jsonb({"comparisons": list(comparisons)})),
    )
