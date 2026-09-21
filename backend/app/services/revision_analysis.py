from typing import Literal
from uuid import UUID

from app.domain.errors import DomainError
from app.domain.models import Decision, FieldName, StrictModel, VerificationReport


class FieldChange(StrictModel):
    field: FieldName
    change: Literal["fixed", "unchanged", "new", "regressed", "unresolved", "unchanged_match"]
    previous_decision: Decision | None
    current_decision: Decision


class RevisionSummary(StrictModel):
    case_id: UUID
    baseline_version: int
    si_extraction_id: UUID
    previous_bl_id: UUID | None
    new_bl_id: UUID
    policy_version: str
    fields: tuple[FieldChange, ...]


def analyze_revision(
    previous: VerificationReport | None,
    current: VerificationReport,
    *,
    case_id: UUID,
    baseline_version: int,
    policy_version: str,
    previous_policy_version: str | None = None,
) -> RevisionSummary:
    if previous is not None and previous_policy_version != policy_version:
        raise DomainError("REBASELINE_REQUIRED", "Both reports must use the same frozen policy")
    si_ids = {row.si.extraction_id for row in current.comparisons}
    bl_ids = {row.bl.extraction_id for row in current.comparisons}
    if len(si_ids) != 1 or None in si_ids or len(bl_ids) != 1 or None in bl_ids:
        raise DomainError("SOURCE_REQUIRED", "Revision analysis requires explicit source revisions")
    if previous and (
        {row.si.extraction_id for row in previous.comparisons} != si_ids
        or previous.email_id != current.email_id
    ):
        raise DomainError("REBASELINE_REQUIRED", "Changed SI or shipment requires a new baseline")
    old = {row.field: row for row in previous.comparisons} if previous else {}
    changes = []
    for row in current.comparisons:
        before = old[row.field].decision if old else None
        after = row.decision
        if after not in {"match", "mismatch"} or (
            before is not None and before not in {"match", "mismatch"}
        ):
            change = "unresolved"
        elif before is None:
            change = "new" if after == "mismatch" else "unchanged_match"
        elif before == "mismatch" and after == "match":
            change = "fixed"
        elif before == "match" and after == "mismatch":
            change = "regressed"
        else:
            change = "unchanged" if after == "mismatch" else "unchanged_match"
        changes.append(
            FieldChange(
                field=row.field, change=change, previous_decision=before, current_decision=after
            )
        )
    return RevisionSummary(
        case_id=case_id,
        baseline_version=baseline_version,
        si_extraction_id=UUID(next(iter(si_ids))),
        new_bl_id=UUID(next(iter(bl_ids))),
        previous_bl_id=UUID(previous.comparisons[0].bl.extraction_id) if previous else None,
        policy_version=policy_version,
        fields=tuple(changes),
    )
