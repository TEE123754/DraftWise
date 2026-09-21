from dataclasses import dataclass

from app.domain.models import Extraction


@dataclass(frozen=True)
class Pairing:
    si: Extraction | None
    bl: Extraction | None
    review_reason: str | None


def pair_within_email(documents: list[Extraction]) -> Pairing:
    instructions = [item for item in documents if item.document_type == "SI"]
    drafts = [item for item in documents if item.document_type == "BL"]
    if len(instructions) > 1 or len(drafts) > 1:
        return Pairing(None, None, "ambiguous_pair")
    si, bl = next(iter(instructions), None), next(iter(drafts), None)
    reason = (
        None
        if si and bl
        else (
            "wrong_doc_type"
            if any(item.document_type not in {"SI", "BL", "UNKNOWN"} for item in documents)
            else "missing_attachment"
        )
    )
    return Pairing(si, bl, reason)
