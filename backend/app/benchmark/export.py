from typing import Literal

from app.domain.errors import DomainError
from app.domain.models import EmailCategory, FieldName, StrictModel, VerificationReport

ReviewReason = Literal["wrong_doc_type", "missing_attachment", "unreadable", "missing_value"]


class Prediction(StrictModel):
    category: EmailCategory
    status: Literal["OK", "MISMATCH", "NEEDS_REVIEW"]
    review_reason: ReviewReason | None
    has_defect: bool
    defect_fields: tuple[FieldName, ...]


def export_prediction(
    category: EmailCategory,
    report: VerificationReport | None = None,
    *,
    review_reason: ReviewReason | None = None,
    awaiting_documents: bool = False,
) -> Prediction:
    # The export schema has no "waiting" status. A request that the draft BL be sent, with no
    # documents claimed, has nothing to compare and nothing wrong to review, so it exports as
    # OK / no defect. The application keeps such a case as awaiting documents, not "checked".
    if category != "BL_COMPARISON" or awaiting_documents:
        return Prediction(
            category=category, status="OK", review_reason=None, has_defect=False, defect_fields=()
        )
    if report is None:
        if review_reason is None:
            raise DomainError(
                "EXPORT_INCOMPLETE",
                "A comparison needs a report or an explicit source-readiness result",
            )
        return Prediction(
            category=category,
            status="NEEDS_REVIEW",
            review_reason=review_reason,
            has_defect=False,
            defect_fields=(),
        )
    if report.status == "NEEDS_REVIEW":
        return Prediction(
            category=category,
            status="NEEDS_REVIEW",
            review_reason=review_reason or "missing_value",
            has_defect=False,
            defect_fields=(),
        )
    # A MISMATCH report may still have unresolved fields; its confirmed defects are reported and the
    # submission schema requires review_reason to be null for any non-NEEDS_REVIEW status.
    defects = tuple(sorted(row.field for row in report.comparisons if row.decision == "mismatch"))
    return Prediction(
        category=category,
        status=report.status,
        review_reason=None,
        has_defect=bool(defects),
        defect_fields=defects,
    )
