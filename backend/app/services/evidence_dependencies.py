from app.domain.models import ExtractedField, Extraction, FieldName
from app.services.normalization import text_key


def resolve_field(document: Extraction, field: FieldName) -> tuple[ExtractedField, tuple[str, ...]]:
    candidate = document.fields[field]
    if (
        field == FieldName.NOTIFY
        and candidate.state == "present"
        and text_key(candidate.raw_value or "") == "same as consignee"
    ):
        consignee = document.fields[FieldName.CONSIGNEE]
        # Resolve inside this document only; keep the relationship's evidence too.
        return consignee, tuple(e.block_id for e in candidate.evidence)
    return candidate, ()
