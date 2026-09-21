"""Compact AI output, expanded into exact source quotes before validation."""

from pydantic import Field, model_validator

from app.domain.errors import DomainError
from app.domain.models import (
    FIELDS,
    DocumentType,
    Evidence,
    ExtractedField,
    Extraction,
    FieldName,
    StrictModel,
)
from app.domain.placeholders import clear_placeholders


class Candidate(StrictModel):
    value: str | None = Field(default=None, max_length=4000)
    blocks: tuple[int, ...] = Field(default=(), max_length=20)
    alternatives: tuple[str, ...] = Field(default=(), max_length=5)


class ExtractionCandidate(StrictModel):
    document_type: DocumentType
    fields: dict[FieldName, Candidate]

    @model_validator(mode="after")
    def complete_fields(self):
        if set(self.fields) != set(FIELDS):
            raise ValueError("Exactly seven fields are required")
        return self


def expand_candidate(candidate, document):
    fields = {}
    for name, item in candidate.fields.items():
        if any(index < 0 or index >= len(document.blocks) for index in item.blocks):
            raise DomainError("PROVIDER_OUTPUT_INVALID", "Unknown source block")
        evidence = tuple(Evidence(block_id=document.blocks[i].id, quote=document.blocks[i].text)
                         for i in dict.fromkeys(item.blocks))
        if item.alternatives:
            if not evidence or any(value not in " ".join(e.quote for e in evidence) for value in item.alternatives):
                raise DomainError("PROVIDER_OUTPUT_INVALID", "Unsupported alternative value")
            fields[name] = ExtractedField(state="ambiguous", alternatives=item.alternatives, evidence=evidence)
        elif item.value is not None:
            if not evidence:
                raise DomainError("PROVIDER_OUTPUT_INVALID", "A value requires source blocks")
            fields[name] = ExtractedField(state="present", raw_value=item.value, evidence=evidence)
        else:
            fields[name] = ExtractedField()
    # A provider may quote "TBA" or "____" as if it were the value; that is a missing field.
    return clear_placeholders(
        Extraction(document_id=document.source_id, document_type=candidate.document_type,
                   fields=fields, warnings=document.warnings)
    )
