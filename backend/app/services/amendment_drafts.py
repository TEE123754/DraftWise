from app.services.correction_previews import CorrectionPreview


def draft_request(reference: str, preview: CorrectionPreview) -> str:
    lines = [
        f"Please amend draft BL for {reference} to match the pinned shipping instructions:",
        "",
    ]
    for patch in preview.changes:
        unit = " kg" if patch.field == "gross_weight_kg" else ""
        lines.append(
            f"- {patch.field.value.replace('_', ' ').title()}: {patch.current}{unit} → {patch.required}{unit}"
        )
    lines.extend(["", "Please return the revised draft for verification."])
    if preview.remaining_blocker_count:
        lines.append(
            f"{preview.remaining_blocker_count} additional field(s) still need review; this request does not resolve them."
        )
    return "\n".join(lines)
