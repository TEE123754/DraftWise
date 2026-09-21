import json
import re

from app.domain.errors import DomainError
from app.domain.models import Extraction, ParsedDocument


def strict_json(text: str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("Non-finite JSON value")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


def whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def ground_extraction(extraction: Extraction, document: ParsedDocument) -> dict[str, float]:
    from app.services.extraction import LABELS

    if extraction.document_id != document.source_id:
        raise DomainError("PROVIDER_OUTPUT_INVALID", "Extraction returned a different source ID")
    blocks = {block.id: block for block in document.blocks}
    quality = {
        block.id: min(block.quality, 0.59) if block.hidden else block.quality
        for block in document.blocks
    }
    for field_name, field in extraction.fields.items():
        quotes = []
        for evidence in field.evidence:
            block = blocks.get(evidence.block_id)
            if (
                block is None
                or block.source_id != document.source_id
                or whitespace(evidence.quote) not in whitespace(block.text)
            ):
                raise DomainError(
                    "PROVIDER_OUTPUT_INVALID", "Extraction contains unsupported evidence"
                )
            quotes.append(evidence.quote)
        if field.state == "present" and whitespace(field.raw_value) not in whitespace(
            " ".join(quotes)
        ):
            raise DomainError(
                "PROVIDER_OUTPUT_INVALID", "Extracted value is not supported by its quoted source"
            )
        if field.state == "present" and not any(
            re.search(LABELS[field_name], blocks[e.block_id].text, re.I) for e in field.evidence
        ):
            for evidence in field.evidence:
                quality[evidence.block_id] = min(quality[evidence.block_id], 0.79)
    return quality
