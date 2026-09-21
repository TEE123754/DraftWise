import asyncio
import time
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from psycopg.types.json import Jsonb

from app.ai.grounding import ground_extraction
from app.domain.errors import DomainError
from app.domain.models import Extraction, FieldName, VerificationReport
from app.infrastructure.parsing import parse_bounded
from app.repositories.jobs import digest, enqueue
from app.services.bounded_ai import BoundedAI
from app.services.classification import Classification, classify_explicit, segment_email
from app.services.disambiguation import email_senses, field_senses
from app.services.drift_detection import monitor
from app.services.email_actions import active_email
from app.services.equivalence_rules import EquivalenceRule
from app.services.extraction import extract_labelled
from app.services.pairing import pair_within_email
from app.services.safety_review import require_safe
from app.services.verification import verify
from app.services.workflow import workflow_state

DEMO_CHECK_TTL = 30  # seconds a workspace's demo status is reused between jobs


class Handlers:
    def __init__(self, database, storage, settings, ai=None):
        self.database, self.storage, self.settings, self.ai = database, storage, settings, ai
        self._demo_cache: dict = {}

    async def _demo_session(self, workspace_id):
        """The workspace's demo session, cached briefly: a mailbox's jobs all ask the same question."""
        checked, demo = self._demo_cache.get(workspace_id, (-1e9, None))
        if time.monotonic() - checked < DEMO_CHECK_TTL:
            return demo
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                "select expires_at>now() as active from public.demo_sessions where workspace_id=%s",
                (workspace_id,),
            )
            demo = await cursor.fetchone()
        self._demo_cache[workspace_id] = (time.monotonic(), demo)
        return demo

    async def prepare(self, job):
        if not job.get("_demo_checked"):
            demo = await self._demo_session(job["workspace_id"])
            if demo and not demo["active"]:
                raise DomainError("DEMO_EXPIRED", "Demo session has ended")
            # Demo or not, live AI is counted, budgeted and cached (see bounded_ai).
            provider = (
                BoundedAI(self.ai, self.database, job["workspace_id"], self.settings)
                if self.ai
                else None
            )
            return await Handlers(self.database, self.storage, self.settings, provider).prepare(
                {**job, "_demo_checked": True}
            )
        async with self.database.connection() as connection:
            email_ids = [job["email_id"]] if job.get("email_id") else []
            if job["kind"] == "extract":
                rows = await (
                    await connection.execute(
                        "select distinct email_id from public.attachments where workspace_id=%s and id=any(%s)",
                        (job["workspace_id"], [UUID(x) for x in job["payload"]["attachment_ids"]]),
                    )
                ).fetchall()
                email_ids += [r["email_id"] for r in rows]
            for email_id in set(email_ids):
                await require_safe(connection, job["workspace_id"], email_id)
        if job["kind"] == "classify":
            return await self.classify(job)
        if job["kind"] == "extract":
            return await self.extract(job)
        if job["kind"] == "verify" and job["payload"].get("operation") == "compare":
            return await self.verify(job)
        raise DomainError("JOB_UNSUPPORTED", "This operation is not supported by this worker")

    async def classify(self, job):
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                "select subject,body from public.emails where workspace_id=%s and id=%s",
                (job["workspace_id"], job["email_id"]),
            )
            email = await cursor.fetchone()
            cursor = await connection.execute(
                "select original_name from public.attachments where workspace_id=%s and email_id=%s",
                (job["workspace_id"], job["email_id"]),
            )
            attachments = [row["original_name"] for row in await cursor.fetchall()]
        if email is None:
            raise DomainError("NOT_FOUND", "Email is no longer available", status=404)
        result = classify_explicit(email["subject"], email["body"])
        metadata = {
            "provider": "rule",
            "version": "v2",
            "method": "rules",
            "confidence_calibrated": False,
        }
        if (
            self.ai
            and job["payload"].get("prefer_ai", True)
            and (job["payload"].get("prefer_ai") or result is None)
        ):
            try:
                result, metadata = await self.ai.classify(
                    email["subject"], email["body"], attachments
                )
                metadata["method"] = "ai"
            except DomainError as exc:
                metadata["method"], metadata["fallback_reason"] = "rule_fallback", exc.code
        elif job["payload"].get("prefer_ai"):
            metadata["method"], metadata["fallback_reason"] = (
                "rule_fallback",
                "PROVIDER_NOT_CONFIGURED",
            )
        if result is None:
            result = Classification(
                category="GENERAL",
                ambiguous=True,
                evidence_span_ids=("current",),
                reason_code="conflicting_intent",
            )
            metadata["abstained"] = True
        metadata["reason_code"] = result.reason_code
        metadata["senses"] = email_senses(email["subject"], email["body"])
        metadata["evidence"] = [
            x
            for x in segment_email(email["subject"], email["body"])
            if x["id"] in result.evidence_span_ids
        ]
        return {"classification": result, "metadata": metadata}

    async def extract(self, job):
        items = []
        for attachment_id in job["payload"]["attachment_ids"]:
            try:
                async with self.database.connection() as connection:
                    cursor = await connection.execute(
                        "select * from public.attachments where workspace_id=%s and id=%s and state='validated'",
                        (job["workspace_id"], attachment_id),
                    )
                    attachment = await cursor.fetchone()
                if attachment is None:
                    raise DomainError("NOT_FOUND", "Attachment is not available", status=404)
                data = await self.storage.download(attachment["storage_key"])
                document = await asyncio.to_thread(
                    parse_bounded, data, attachment_id, self.settings
                )
                if document.sha256 != attachment["sha256"]:
                    raise DomainError(
                        "SOURCE_CHANGED",
                        "Document bytes changed after upload finalization",
                        status=409,
                    )
                blocks = tuple(
                    block.model_copy(update={"id": str(uuid5(NAMESPACE_URL, block.id))})
                    for block in document.blocks
                )
                document = document.model_copy(update={"blocks": blocks})
                extraction = extract_labelled(document)
                metadata = {
                    "provider": "labelled_parser",
                    "parser_version": document.parser_version,
                }
                if (
                    self.ai
                    and job["payload"].get("prefer_ai", True)
                    and (
                        job["payload"].get("prefer_ai")
                        or extraction.document_type == "UNKNOWN"
                        or any(field.state != "present" for field in extraction.fields.values())
                    )
                ):
                    try:
                        extraction, metadata = await self.ai.extract(document)
                        metadata["method"] = "ai"
                    except DomainError as exc:
                        metadata["method"], metadata["fallback_reason"] = "rule_fallback", exc.code
                elif job["payload"].get("prefer_ai"):
                    metadata["method"], metadata["fallback_reason"] = (
                        "rule_fallback",
                        "PROVIDER_NOT_CONFIGURED",
                    )
                metadata.setdefault("method", "labelled_parser")
                metadata["senses"] = field_senses(extraction)
                metadata["quality"] = ground_extraction(extraction, document)
                hint = job["payload"].get("role_hints", {}).get(attachment_id)
                if hint and hint != "UNKNOWN" and hint != extraction.document_type:
                    metadata["role_conflict"] = True
                items.append(
                    {
                        "attachment_id": attachment_id,
                        "document": document,
                        "extraction": extraction,
                        "metadata": metadata,
                    }
                )
            except DomainError as exc:
                if exc.retryable:
                    raise
                items.append({"attachment_id": attachment_id, "error_code": exc.code})
        return {"items": items}

    async def verify(self, job):
        async with self.database.connection() as connection:
            cursor = await connection.execute(
                """select distinct on(x.attachment_id) x.* from public.document_extractions x
                join public.attachments a on a.workspace_id=x.workspace_id and a.id=x.attachment_id
                where x.workspace_id=%s and a.email_id=%s and a.state='validated'
                order by x.attachment_id,x.revision desc""",
                (job["workspace_id"], job["email_id"]),
            )
            rows = await cursor.fetchall()
            explicit_ids = [
                job["payload"].get(name) for name in ("si_extraction_id", "bl_extraction_id")
            ]
            if any(explicit_ids):
                cursor = await connection.execute(
                    """select x.* from public.document_extractions x join public.attachments a
                    on a.workspace_id=x.workspace_id and a.id=x.attachment_id where x.workspace_id=%s and x.id=any(%s) and a.email_id=%s and a.state='validated'""",
                    (
                        job["workspace_id"],
                        [UUID(value) for value in explicit_ids if value],
                        job["email_id"],
                    ),
                )
                rows = await cursor.fetchall()
                if len(rows) != sum(value is not None for value in explicit_ids):
                    raise DomainError(
                        "SOURCE_CHANGED",
                        "The selected source revisions are unavailable",
                        status=409,
                    )
            customer_id = None
            if job["payload"].get("customer_id"):
                customer_id = UUID(str(job["payload"]["customer_id"]))
            elif job["payload"].get("case_id"):
                case_cursor = await connection.execute(
                    "select customer_id from public.cases where workspace_id=%s and id=%s",
                    (job["workspace_id"], UUID(str(job["payload"]["case_id"]))),
                )
                case_row = await case_cursor.fetchone()
                if case_row and case_row.get("customer_id"):
                    customer_id = case_row["customer_id"]

            equivalence_rules = []
            if customer_id:
                rules_cursor = await connection.execute(
                    """select id, workspace_id, customer_id, field, left_value, right_value, evidence, rationale, version, state, canonical_port_code, authority_reference
                    from public.equivalence_rules
                    where workspace_id=%s and customer_id=%s and state='approved'""",
                    (job["workspace_id"], customer_id),
                )
                for r in await rules_cursor.fetchall():
                    try:
                        equivalence_rules.append(
                            EquivalenceRule(
                                id=r["id"],
                                workspace_id=r["workspace_id"],
                                customer_id=r["customer_id"],
                                field=FieldName(r["field"]),
                                left=r["left_value"],
                                right=r["right_value"],
                                evidence_ids=tuple(r["evidence"] if isinstance(r["evidence"], list) else []),
                                rationale=r.get("rationale") or "Approved customer equivalence",
                                version=r["version"],
                                state=r["state"],
                                canonical_port_code=r.get("canonical_port_code"),
                                authority_reference=r.get("authority_reference"),
                            )
                        )
                    except Exception:
                        continue

        documents, qualities = [], {}
        for row in rows:
            extraction = Extraction.model_validate(row["output"]).model_copy(
                update={"document_id": str(row["id"])}
            )
            documents.append(extraction)
            qualities.update(row["run_metadata"].get("quality", {}))
        pair = pair_within_email(documents)
        report = verify(
            pair.si,
            pair.bl,
            email_id=str(job["email_id"]),
            evidence_quality=qualities,
            equivalence_rules=tuple(equivalence_rules),
            workspace_id=job["workspace_id"],
            customer_id=customer_id,
        )
        return {
            "report": report,
            "si_id": pair.si.document_id if pair.si else None,
            "bl_id": pair.bl.document_id if pair.bl else None,
            "equivalence_rules": [
                {
                    "id": str(r.id),
                    "version": r.version,
                    "field": r.field.value,
                    "left": r.left,
                    "right": r.right,
                    "rationale": r.rationale,
                }
                for r in equivalence_rules
            ],
            "input_fingerprint": digest(
                {
                    "sources": sorted(str(row["id"]) for row in rows),
                    "policy": job["payload"]["policy_version"],
                    "rules": sorted(str(r.id) for r in equivalence_rules),
                }
            ),
        }

    async def persist(self, connection, job, prepared):
        # Caller holds the live job lease lock for this entire artifact transaction.
        workspace, email_id = job["workspace_id"], job["email_id"]
        if email_id:
            await active_email(connection, workspace, email_id, lock=True)
        if job["kind"] == "classify":
            await connection.execute(
                "select id from public.emails where workspace_id=%s and id=%s for update",
                (workspace, email_id),
            )
            cursor = await connection.execute(
                "select coalesce(max(revision),0)+1 as revision from public.email_classifications where workspace_id=%s and email_id=%s",
                (workspace, email_id),
            )
            revision = (await cursor.fetchone())["revision"]
            result, metadata = prepared["classification"], prepared["metadata"]
            classification_id = uuid4()
            await connection.execute(
                """insert into public.email_classifications(id,workspace_id,email_id,revision,category,ambiguous,confidence,decided_by,evidence,run_metadata)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    classification_id,
                    workspace,
                    email_id,
                    revision,
                    result.category,
                    result.ambiguous,
                    0.5 if result.ambiguous else 0.9,
                    "rule" if metadata["provider"] == "rule" else "ai",
                    Jsonb(list(result.evidence_span_ids)),
                    Jsonb(metadata),
                ),
            )
            if job["payload"].get("workflow"):
                if not result.ambiguous and result.category == "BL_COMPARISON":
                    rows = await (
                        await connection.execute(
                            "select id from public.attachments where workspace_id=%s and email_id=%s and state='validated' order by id",
                            (workspace, email_id),
                        )
                    ).fetchall()
                    if rows:
                        next_job = await enqueue(
                            connection,
                            workspace_id=workspace,
                            kind="extract",
                            key=f"workflow:{job['id']}",
                            email_id=email_id,
                            payload={
                                "attachment_ids": [str(r["id"]) for r in rows][:20],
                                "workflow": True,
                                "prefer_ai": job["payload"].get("prefer_ai", False),
                            },
                        )
                        await workflow_state(
                            connection,
                            job,
                            "extracting",
                            {"classification_method": metadata["method"]},
                            next_job,
                        )
                    else:
                        await workflow_state(
                            connection,
                            job,
                            "needs_review",
                            {"next_action": "Add shipping instructions and a draft bill of lading"},
                        )
                else:
                    await workflow_state(
                        connection,
                        job,
                        "needs_review" if result.ambiguous else "classified",
                        {
                            "category": None if result.ambiguous else result.category,
                            "method": metadata["method"],
                            "next_action": "Review uncertain email intent"
                            if result.ambiguous
                            else {
                                "SI_REQUEST": "Prepare or request the shipping instructions",
                                "INVOICE_QUERY": "Review the billing question with the invoice team",
                                "GENERAL": "Read the message; no document comparison requested",
                                "SPAM": "Inspect spam signals before taking any action",
                            }.get(result.category, "Review the request"),
                        },
                    )
            await monitor(connection, workspace)
            return {
                "method": metadata["method"],
                "classification_id": str(classification_id),
                "email_id": str(email_id),
                **result.model_dump(mode="json"),
                "next_action": "review"
                if result.ambiguous
                else ("verify" if result.category == "BL_COMPARISON" else "none"),
            }
        if job["kind"] == "extract":
            results = []
            for item in prepared["items"]:
                if "error_code" in item:
                    results.append(
                        {
                            "attachment_id": item["attachment_id"],
                            "extraction_id": None,
                            "state": "failed",
                            "error_code": item["error_code"],
                        }
                    )
                    continue
                document, extraction, metadata = (
                    item["document"],
                    item["extraction"],
                    item["metadata"],
                )
                attachment_id = UUID(item["attachment_id"])
                cache_key = digest(
                    {
                        "source": document.sha256,
                        "parser": document.parser_version,
                        "method": metadata.get("method", metadata["provider"]),
                        "output": extraction.model_dump(mode="json"),
                    }
                )
                await connection.execute(
                    "select id from public.attachments where workspace_id=%s and id=%s for update",
                    (workspace, attachment_id),
                )
                cursor = await connection.execute(
                    "select id from public.document_extractions where workspace_id=%s and attachment_id=%s and cache_key=%s",
                    (workspace, attachment_id, cache_key),
                )
                existing = await cursor.fetchone()
                if existing:
                    extraction_id = existing["id"]
                else:
                    # One statement per document: each round trip to a hosted database costs ~100 ms.
                    await connection.execute(
                        """insert into public.source_blocks(id,workspace_id,attachment_id,parser_version,ordinal,text_content,locator,quality)
                        select x.id,%s,%s,%s,x.ordinal,x.text,x.locator,x.quality
                        from jsonb_to_recordset(%s) as x(id uuid,ordinal integer,text text,locator jsonb,quality numeric)
                        on conflict(workspace_id,attachment_id,parser_version,ordinal) do nothing""",
                        (
                            workspace,
                            attachment_id,
                            document.parser_version,
                            Jsonb(
                                [
                                    {
                                        "id": block.id,
                                        "ordinal": ordinal,
                                        "text": block.text,
                                        "locator": block.locator,
                                        "quality": block.quality,
                                    }
                                    for ordinal, block in enumerate(document.blocks)
                                ]
                            ),
                        ),
                    )
                    cursor = await connection.execute(
                        "select coalesce(max(revision),0)+1 as revision from public.document_extractions where workspace_id=%s and attachment_id=%s",
                        (workspace, attachment_id),
                    )
                    revision = (await cursor.fetchone())["revision"]
                    extraction_id = uuid4()
                    await connection.execute(
                        """insert into public.document_extractions(id,workspace_id,attachment_id,revision,document_type,schema_version,cache_key,output,run_metadata)
                        values(%s,%s,%s,%s,%s,'v1',%s,%s,%s)""",
                        (
                            extraction_id,
                            workspace,
                            attachment_id,
                            revision,
                            extraction.document_type,
                            cache_key,
                            Jsonb(extraction.model_dump(mode="json")),
                            Jsonb(metadata),
                        ),
                    )
                needs_review = (
                    metadata.get("role_conflict")
                    or extraction.document_type == "UNKNOWN"
                    or any(field.state != "present" for field in extraction.fields.values())
                )
                results.append(
                    {
                        "attachment_id": str(attachment_id),
                        "extraction_id": str(extraction_id),
                        "state": "needs_review" if needs_review else "succeeded",
                        "error_code": None,
                        "method": metadata.get("method", metadata["provider"]),
                    }
                )
            if job["payload"].get("workflow"):
                rows = await (
                    await connection.execute(
                        """select distinct on (attachment_id) id,document_type from public.document_extractions
                    where workspace_id=%s and attachment_id=any(%s) order by attachment_id,revision desc""",
                        (workspace, [UUID(x) for x in job["payload"]["attachment_ids"]]),
                    )
                ).fetchall()
                si = [r for r in rows if r["document_type"] == "SI"]
                bl = [r for r in rows if r["document_type"] == "BL"]
                email = await (
                    await connection.execute(
                        "select external_id from public.emails where workspace_id=%s and id=%s for update",
                        (workspace, email_id),
                    )
                ).fetchone()
                case = await (
                    await connection.execute(
                        "select * from public.cases where workspace_id=%s and email_id=%s for update",
                        (workspace, email_id),
                    )
                ).fetchone()
                if not case:
                    case = await (
                        await connection.execute(
                            "insert into public.cases(workspace_id,email_id,reference) values(%s,%s,%s) returning *",
                            (workspace, email_id, email["external_id"][:120]),
                        )
                    ).fetchone()
                if (
                    len(si) == 1
                    and len(bl) == 1
                    and all(r["state"] != "failed" for r in results)
                    and not case["latest_report_id"]
                ):
                    version = case["version"] + 1
                    await connection.execute(
                        "update public.cases set active_si_id=%s,active_bl_id=%s,version=%s,readiness='checking',updated_at=now() where workspace_id=%s and id=%s",
                        (si[0]["id"], bl[0]["id"], version, workspace, case["id"]),
                    )
                    next_job = await enqueue(
                        connection,
                        workspace_id=workspace,
                        kind="verify",
                        key=f"workflow:{job['id']}",
                        email_id=email_id,
                        payload={
                            "workflow": True,
                            "operation": "compare",
                            "case_id": str(case["id"]),
                            "case_version": version,
                            "si_extraction_id": str(si[0]["id"]),
                            "bl_extraction_id": str(bl[0]["id"]),
                            "policy_version": "v1",
                        },
                    )
                    await workflow_state(
                        connection, job, "checking", {"extractions": results}, next_job, case["id"]
                    )
                else:
                    await workflow_state(
                        connection,
                        job,
                        "needs_review",
                        {
                            "next_action": "Confirm document sources in the case",
                            "extractions": results,
                        },
                        case_id=case["id"],
                    )
            return {"items": results}
        if job["kind"] == "verify":
            await connection.execute(
                "select id from public.emails where workspace_id=%s and id=%s for update",
                (workspace, email_id),
            )
            cursor = await connection.execute(
                "select id,report from public.verification_reports where workspace_id=%s and email_id=%s and input_fingerprint=%s",
                (workspace, email_id, prepared["input_fingerprint"]),
            )
            existing = await cursor.fetchone()
            if existing:
                report = VerificationReport.model_validate(existing["report"])
            else:
                cursor = await connection.execute(
                    "select coalesce(max(revision),0)+1 as revision from public.verification_reports where workspace_id=%s and email_id=%s",
                    (workspace, email_id),
                )
                revision = (await cursor.fetchone())["revision"]
                report = prepared["report"].model_copy(update={"revision": revision})
                await connection.execute(
                    """insert into public.verification_reports(id,workspace_id,email_id,si_extraction_id,bl_extraction_id,revision,status,complete,confidence,comparison_version,input_fingerprint,review_reasons,report)
                    values(%s,%s,%s,%s,%s,%s,%s,%s,%s,'v1',%s,%s,%s)""",
                    (
                        report.id,
                        workspace,
                        email_id,
                        prepared["si_id"],
                        prepared["bl_id"],
                        revision,
                        report.status,
                        report.complete,
                        report.confidence,
                        prepared["input_fingerprint"],
                        list(report.review_reasons),
                        Jsonb(report.model_dump(mode="json")),
                    ),
                )
                differences = [
                    {
                        "field": row.field.value,
                        "decision": row.decision,
                        "severity": row.severity,
                        "confidence": row.confidence,
                        "details": row.model_dump(mode="json"),
                    }
                    for row in report.comparisons
                    if row.decision != "match"
                ]
                if differences:
                    await connection.execute(
                        """insert into public.discrepancies(workspace_id,report_id,field,decision,severity,confidence,details)
                        select %s,%s,x.field::public.field_name,x.decision,x.severity,x.confidence,x.details
                        from jsonb_to_recordset(%s) as x(field text,decision text,severity text,confidence numeric,details jsonb)""",
                        (workspace, report.id, Jsonb(differences)),
                    )
                for row in report.comparisons:
                    if row.decision == "match" and row.rule == "equivalence_rule_v1":
                        for rule_data in prepared.get("equivalence_rules", []):
                            if rule_data["id"] in row.evidence_ids:
                                await connection.execute(
                                    """insert into public.report_rule_applications(workspace_id,report_id,rule_id,rule_version,rule_snapshot)
                                    values(%s,%s,%s,%s,%s) on conflict(workspace_id,report_id,rule_id) do nothing""",
                                    (
                                        workspace,
                                        report.id,
                                        UUID(rule_data["id"]),
                                        rule_data["version"],
                                        Jsonb(rule_data),
                                    ),
                                )
            if job["payload"].get("case_id"):
                from app.repositories.cases import project_report

                await project_report(connection, job, report, prepared["si_id"], prepared["bl_id"])
            if job["payload"].get("workflow"):
                await workflow_state(
                    connection,
                    job,
                    "checked" if report.status == "OK" else "needs_review",
                    {
                        "status": report.status,
                        "method": "deterministic_comparison",
                        "next_action": "All seven fields match; inspect the evidence"
                        if report.status == "OK"
                        else "Review field differences and source evidence",
                    },
                )
            return {
                "verification_id": str(report.id),
                "status": report.status,
                "revision": report.revision,
                "report_url": f"/api/v1/verification/{report.id}",
            }
        raise DomainError("JOB_UNSUPPORTED", "Unknown output type")
