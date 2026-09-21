from app.domain.models import FieldName, StrictModel, VerificationReport


class NextAction(StrictModel):
    kind: str
    title: str
    fields: tuple[FieldName, ...] = ()


def next_action(
    report: VerificationReport | None,
    *,
    processing: bool = False,
    awaiting_revision: bool = False,
    failed: bool = False,
    needs_source: bool = False,
) -> NextAction:
    if processing:
        return NextAction(kind="wait", title="Checking the latest documents")
    if failed:
        return NextAction(kind="retry", title="Retry the document check")
    if report is None or needs_source:
        return NextAction(kind="add_sources", title="Add shipping instructions and a draft BL")
    unresolved = tuple(
        row.field for row in report.comparisons if row.decision not in {"match", "mismatch"}
    )
    if unresolved:
        # Consignee is a parent of notify party and should be resolved first.
        first = FieldName.CONSIGNEE if FieldName.CONSIGNEE in unresolved else unresolved[0]
        return NextAction(
            kind="review_evidence",
            title=f"Confirm {first.value.replace('_', ' ')} from the source",
            fields=(first,),
        )
    if report.status == "OK":
        return NextAction(
            kind="view_checks", title="All seven fields match the pinned instructions"
        )
    if awaiting_revision:
        return NextAction(kind="add_draft", title="Add the returned draft to check the changes")
    return NextAction(
        kind="preview_corrections",
        title="Preview the correction request",
        fields=tuple(row.field for row in report.comparisons if row.decision == "mismatch"),
    )
