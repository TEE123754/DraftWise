from app.domain.models import VerificationReport


def case_readiness(
    report: VerificationReport | None,
    *,
    has_si: bool,
    has_bl: bool,
    processing: bool = False,
    failed: bool = False,
    shared: bool = False,
) -> str:
    if processing:
        return "checking"
    if not has_si or not has_bl:
        return "needs_source"
    if failed:
        return "failed"
    if report is None or report.status == "NEEDS_REVIEW":
        return "needs_decision"
    if report.status == "OK":
        return "checked"
    return "awaiting_revision" if shared else "changes_required"
