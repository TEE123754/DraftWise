import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import Field

from app.domain.errors import DomainError
from app.domain.models import FieldName, StrictModel, VerificationReport
from app.services.normalization import text_key


class Patch(StrictModel):
    field: FieldName
    current: str | int
    required: str | int
    evidence_ids: tuple[str, ...]


class CorrectionPreview(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    case_version: int
    report_id: UUID
    fingerprint: str
    kind: str = "simulation"
    changes: tuple[Patch, ...]
    remaining_fields: tuple[FieldName, ...]
    remaining_blocker_count: int
    expires_at: datetime


def fingerprint(
    report: VerificationReport,
    *,
    workspace_id: UUID,
    case_id: UUID,
    case_version: int,
    policy_version: str,
    fields: tuple[FieldName, ...],
) -> str:
    payload = {
        "workspace": str(workspace_id),
        "case": str(case_id),
        "version": case_version,
        "policy": policy_version,
        "fields": sorted(fields),
        "report": report.model_dump(mode="json"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def create_preview(
    report: VerificationReport,
    *,
    workspace_id: UUID,
    case_id: UUID,
    case_version: int,
    policy_version: str,
    fields: tuple[FieldName, ...],
    now: datetime | None = None,
    ttl_seconds: int = 1800,
) -> CorrectionPreview:
    if not fields or len(set(fields)) != len(fields) or case_version < 1:
        raise DomainError("INVALID_PREVIEW", "Choose one or more distinct supported discrepancies")
    if not 0 < ttl_seconds <= 1800:
        raise DomainError("INVALID_PREVIEW", "Preview lifetime cannot exceed 30 minutes")
    rows = {row.field: row for row in report.comparisons}
    changes = []
    for field in fields:
        row = rows[field]
        if (
            row.decision != "mismatch"
            or row.si.normalized is None
            or row.bl.normalized is None
            or not row.evidence_ids
        ):
            raise DomainError(
                "UNSUPPORTED_CORRECTION", "Only evidence-supported mismatches can be previewed"
            )
        changes.append(
            Patch(
                field=field,
                current=row.bl.normalized,
                required=row.si.normalized,
                evidence_ids=row.evidence_ids,
            )
        )
    remaining = tuple(
        row.field
        for row in report.comparisons
        if row.decision != "match" and row.field not in fields
    )
    # Changing BL consignee also changes SAME AS CONSIGNEE, so it must be rechecked.
    notify = rows[FieldName.NOTIFY]
    consignee = rows[FieldName.CONSIGNEE]
    if FieldName.CONSIGNEE in fields and FieldName.NOTIFY not in fields:
        dependent = text_key(notify.bl.raw or "") == "same as consignee"
        if dependent:
            remaining = tuple(field for field in remaining if field != FieldName.NOTIFY)
            if notify.si.normalized is None or notify.si.normalized != consignee.si.normalized:
                remaining += (FieldName.NOTIFY,)
    return CorrectionPreview(
        case_id=case_id,
        case_version=case_version,
        report_id=report.id,
        fingerprint=fingerprint(
            report,
            workspace_id=workspace_id,
            case_id=case_id,
            case_version=case_version,
            policy_version=policy_version,
            fields=fields,
        ),
        changes=tuple(changes),
        remaining_fields=remaining,
        remaining_blocker_count=len(remaining),
        expires_at=(now or datetime.now(UTC)) + timedelta(seconds=ttl_seconds),
    )


def validate_preview(
    preview: CorrectionPreview,
    report: VerificationReport,
    *,
    workspace_id: UUID,
    case_id: UUID,
    case_version: int,
    policy_version: str,
    now: datetime | None = None,
) -> None:
    expected = fingerprint(
        report,
        workspace_id=workspace_id,
        case_id=case_id,
        case_version=case_version,
        policy_version=policy_version,
        fields=tuple(change.field for change in preview.changes),
    )
    if preview.expires_at <= (now or datetime.now(UTC)) or preview.fingerprint != expected:
        raise DomainError(
            "STALE_PREVIEW", "Sources or decisions changed. Create a new preview.", status=409
        )
