import hashlib
import secrets
from uuid import uuid4

from psycopg.types.json import Jsonb

from app.api.uploads import MIMES
from app.domain.errors import DomainError
from app.services.classification import classify_explicit, segment_email
from app.services.demo_retention import purge_expired_samples
from app.services.email_safety import assess_email
from app.services.offline_processing import queue_offline_processing


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def seed_session(connection, source, manifest, *, offline_processing=True):
    # Bound anonymous provisioning across concurrent API processes.
    await connection.execute("select pg_advisory_xact_lock(84291731)")
    await purge_expired_samples(connection)
    count = await (
        await connection.execute("select count(*) as count from public.demo_sessions where purged_at is null")
    ).fetchone()
    if count["count"] >= 20:
        raise DomainError(
            "DEMO_CAPACITY",
            "Demo capacity reached. An administrator can provision a fresh demo environment.",
            status=429,
        )
    recent = await (
        await connection.execute(
            "select count(*) as count from public.demo_sessions where created_at>now()-interval '1 hour'"
        )
    ).fetchone()
    if recent["count"] >= 20:
        raise DomainError("DEMO_RATE_LIMIT", "Demo creation limit reached. Try again in an hour.", status=429)
    actor = uuid4()
    await connection.execute("insert into auth.users(id) values(%s)", (actor,))
    row = await (
        await connection.execute(
            "select workspace_id from public.memberships where user_id=%s", (actor,)
        )
    ).fetchone()
    workspace = row["workspace_id"]
    await connection.execute(
        "update public.workspaces set name='DraftWise demo' where id=%s", (workspace,)
    )
    token = secrets.token_urlsafe(32)
    await connection.execute(
        "insert into public.demo_sessions(token_hash,workspace_id,actor_id,manifest_sha256) values(%s,%s,%s,%s)",
        (token_hash(token), workspace, actor, manifest["sha256"]),
    )

    emails, attachments, classifications, cases, safety = [], [], [], [], []
    available = {
        item["path"]: item for item in manifest["attachments"] if item["state"] == "available"
    }

    for email in source.emails():
        email_id = uuid4()
        emails.append(
            {
                "id": str(email_id),
                "external_id": email.email_id,
                "sender": email.sender,
                "subject": email.subject,
                "body": email.body,
                "sha256": next(
                    x["sha256"] for x in manifest["emails"] if x["email_id"] == email.email_id
                ),
                "segments": segment_email(email.subject, email.body),
            }
        )
        assessment = assess_email(
            email.sender, None, email.subject, email.body, list(email.attachments)
        ).to_dict()
        safety.append({"email_id": str(email_id), **assessment})

        # Rules only: an email the rules cannot decide stays unclassified until someone asks for AI.
        classified = classify_explicit(email.subject, email.body)
        has_files = any(path in available for path in email.attachments)
        if classified:
            classifications.append(
                {
                    "id": str(uuid4()),
                    "email_id": str(email_id),
                    "category": classified.category,
                    "evidence": classified.model_dump(mode="json"),
                    "decided_by": "rule",
                    "run_metadata": {"provider": "rule", "demo": True},
                }
            )
            # A case is opened only where there are documents to compare; the rest are waiting
            # on the sender and are shown in the inbox, not as empty cases.
            if classified.category == "BL_COMPARISON" and has_files:
                cases.append(
                    {"id": str(uuid4()), "email_id": str(email_id), "reference": email.email_id}
                )

        for path in email.attachments:
            if path not in available:
                continue
            item = available[path]
            attachment_id = uuid4()
            attachments.append(
                {
                    "id": str(attachment_id),
                    "email_id": str(email_id),
                    "name": path.split("/")[-1],
                    "key": f"demo-seed/{workspace}/{attachment_id}/{path}",
                    "mime": MIMES[item["format"]],
                    "size": item["bytes"],
                    "sha256": item["sha256"],
                }
            )

    await connection.execute(
        """insert into public.emails(id,workspace_id,source_namespace,external_id,sender,subject,body,content_sha256,segments)
        select x.id,%s,'demo-bundle',x.external_id,x.sender,x.subject,x.body,x.sha256,x.segments from jsonb_to_recordset(%s)
        as x(id uuid,external_id text,sender text,subject text,body text,sha256 text,segments jsonb)""",
        (workspace, Jsonb(emails)),
    )
    await connection.execute(
        """insert into public.attachments(id,workspace_id,email_id,original_name,storage_key,mime_type,byte_size,sha256,state,metadata)
        select x.id,%s,x.email_id,x.name,x.key,x.mime,x.size,x.sha256,'validated','{"source":"provided_bundle","parser_validation":"pending"}'::jsonb
        from jsonb_to_recordset(%s) as x(id uuid,email_id uuid,name text,key text,mime text,size bigint,sha256 text)""",
        (workspace, Jsonb(attachments)),
    )
    await connection.execute(
        """insert into public.email_classifications(id,workspace_id,email_id,revision,category,ambiguous,confidence,decided_by,evidence,run_metadata)
        select x.id,%s,x.email_id,1,x.category::public.email_category,false,1,coalesce(x.decided_by,'rule'),x.evidence,coalesce(x.run_metadata,'{"provider":"rule","demo":true}'::jsonb)
        from jsonb_to_recordset(%s) as x(id uuid,email_id uuid,category text,evidence jsonb,decided_by text,run_metadata jsonb)""",
        (workspace, Jsonb(classifications)),
    )
    await connection.execute(
        """insert into public.cases(id,workspace_id,email_id,reference)
        select x.id,%s,x.email_id,x.reference from jsonb_to_recordset(%s) as x(id uuid,email_id uuid,reference text)""",
        (workspace, Jsonb(cases)),
    )
    await connection.execute(
        """insert into public.email_safety(workspace_id,email_id,risk_state,severity,signals,held_for_review)
        select %s,x.email_id,x.risk_state,x.severity,x.signals,x.held_for_review from jsonb_to_recordset(%s)
        as x(email_id uuid,risk_state text,severity text,signals jsonb,held_for_review boolean)""",
        (workspace, Jsonb(safety)),
    )
    await connection.execute(
        """insert into public.drift_alerts(workspace_id,alert_type,severity,title,description,sample_email_ids)
        select workspace_id,case when risk_state='spam' then 'spam' else 'phishing' end,severity,'Email safety review',
        'Static signals require inspection; no external link was fetched.',jsonb_build_array(email_id::text)
        from public.email_safety where workspace_id=%s and risk_state in ('spam','suspected_phishing')""",
        (workspace,),
    )
    # Read and compare every comparison email's documents in the background, rules only: the
    # inbox fills in as the worker goes, and no AI provider is called.
    processing = (
        await queue_offline_processing(connection, workspace) if offline_processing else {"queued": 0}
    )
    return token, {
        "workspace_id": str(workspace),
        "email_count": len(emails),
        "attachment_count": len(attachments),
        "classified_count": len(classifications),
        "queued_for_reading": processing["queued"],
        "manifest_sha256": manifest["sha256"],
        "role": "admin",
    }
