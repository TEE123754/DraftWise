"""Input-bundle adapter. Normal workflow runs after import; no expected outputs here."""

from uuid import uuid4

from psycopg.types.json import Jsonb

from app.api.uploads import MIMES
from app.domain.errors import DomainError
from app.repositories.jobs import digest
from app.services.classification import segment_email
from app.services.offline_processing import queue_offline_processing
from app.services.workflow import start_workflow


async def fetch_sample(connection, source, manifest, workspace, external_id, key, prefer_ai):
    email = next((e for e in source.emails() if e.email_id == external_id), None)
    if email is None:
        raise DomainError("NOT_FOUND", "Sample email does not exist", status=404)
    # Same namespace as the seeded inbox: repeating a fetch cannot duplicate a message.
    record = await (
        await connection.execute(
            """insert into public.emails(workspace_id,source_namespace,external_id,sender,subject,body,content_sha256,segments)
        values(%s,'demo-bundle',%s,%s,%s,%s,%s,%s) on conflict(workspace_id,source_namespace,external_id) do nothing returning id""",
            (
                workspace,
                email.email_id,
                email.sender,
                email.subject,
                email.body,
                digest({"body": email.body, "subject": email.subject}),
                Jsonb(segment_email(email.subject, email.body)),
            ),
        )
    ).fetchone()
    imported = record is not None
    if not record:
        record = await (
            await connection.execute(
                "select id from public.emails where workspace_id=%s and source_namespace='demo-bundle' and external_id=%s for update",
                (workspace, external_id),
            )
        ).fetchone()
    available = {a["path"]: a for a in manifest["attachments"] if a["state"] == "available"}
    for path in email.attachments:
        item = available.get(path)
        if not item:
            continue
        name = path.split("/")[-1]
        exists = await (
            await connection.execute(
                "select id from public.attachments where workspace_id=%s and email_id=%s and original_name=%s",
                (workspace, record["id"], name),
            )
        ).fetchone()
        if not exists:
            attachment = uuid4()
            await connection.execute(
                """insert into public.attachments(id,workspace_id,email_id,original_name,storage_key,mime_type,byte_size,sha256,state,metadata)
                values(%s,%s,%s,%s,%s,%s,%s,%s,'validated',%s)""",
                (
                    attachment,
                    workspace,
                    record["id"],
                    name,
                    f"demo-seed/{workspace}/{attachment}/{path}",
                    MIMES[item["format"]],
                    item["bytes"],
                    item["sha256"],
                    Jsonb({"source": "provided_bundle"}),
                ),
            )
    workflow = await start_workflow(connection, workspace, record["id"], key, prefer_ai)
    return {
        **workflow,
        "simulation": True,
        "imported": imported,
        "message": "Sample fetched"
        if imported
        else "Existing sample reused; no duplicate imported",
    }


async def fetch_all_samples(connection, source, manifest, workspace, key):
    """Simulate fetching the whole sample mailbox, as a first Gmail sync would.

    A demo session is seeded with every sample email, so normally all of them are found already and
    nothing is duplicated; any that are missing are imported the same way a single fetch does. Reading
    of the comparison emails that have not been read yet is queued, rules only.
    """
    emails = list(source.emails())
    present = {
        row["external_id"]
        for row in await (
            await connection.execute(
                "select external_id from public.emails where workspace_id=%s and source_namespace='demo-bundle'",
                (workspace,),
            )
        ).fetchall()
    }
    missing = [email.email_id for email in emails if email.email_id not in present]
    for external_id in missing:
        await fetch_sample(connection, source, manifest, workspace, external_id, f"{key}:{external_id}", False)
    queued = await queue_offline_processing(connection, workspace)
    reused = len(emails) - len(missing)
    return {
        "simulation": True,
        "fetched": len(emails),
        "imported": len(missing),
        "reused": reused,
        "queued_for_reading": queued["queued"],
        "message": (
            f"Fetched {len(emails)} emails from the sample mailbox: {len(missing)} new, "
            f"{reused} already in your workspace (not duplicated)."
        ),
    }
