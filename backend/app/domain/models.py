from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldName(StrEnum):
    SHIPPER = "shipper"
    CONSIGNEE = "consignee"
    NOTIFY = "notify_party"
    POL = "port_of_loading"
    POD = "port_of_discharge"
    CONTAINERS = "container_count"
    WEIGHT = "gross_weight_kg"


FIELDS = tuple(FieldName)
PARTIES = frozenset((FieldName.SHIPPER, FieldName.CONSIGNEE, FieldName.NOTIFY))
PORTS = frozenset((FieldName.POL, FieldName.POD))
Decision = Literal["match", "mismatch", "missing", "partial_match", "uncertain"]
DocumentType = Literal["SI", "BL", "INVOICE", "PACKING_LIST", "CERTIFICATE", "UNKNOWN"]
EmailCategory = Literal["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"]


class Evidence(StrictModel):
    block_id: str = Field(min_length=1, max_length=300)
    quote: str = Field(min_length=1, max_length=4000)


class ExtractedField(StrictModel):
    raw_value: str | None = Field(default=None, max_length=4000)
    state: Literal["present", "missing", "ambiguous", "unreadable"] = "missing"
    evidence: tuple[Evidence, ...] = Field(default=(), max_length=20)
    alternatives: tuple[str, ...] = Field(default=(), max_length=5)

    @model_validator(mode="after")
    def validate_presence(self):
        if self.state == "present":
            if not self.raw_value or not self.raw_value.strip() or not self.evidence:
                raise ValueError("A present field requires a value and source evidence")
            if self.raw_value.strip().casefold() in {"n/a", "null", "none", "unknown", "-"}:
                raise ValueError("Placeholder is not a present value")
        if self.state in {"missing", "unreadable"} and self.raw_value is not None:
            raise ValueError("Missing/unreadable fields must have null values")
        return self


class Extraction(StrictModel):
    document_id: str = Field(min_length=1, max_length=300)
    document_type: DocumentType
    fields: dict[FieldName, ExtractedField]
    warnings: tuple[str, ...] = Field(default=(), max_length=30)

    @model_validator(mode="after")
    def all_fields(self):
        if set(self.fields) != set(FIELDS):
            raise ValueError("Exactly the seven required fields must be supplied")
        return self


class SourceBlock(StrictModel):
    id: str
    source_id: str
    text: str
    kind: Literal["text", "table_cell", "ocr"] = "text"
    locator: dict[str, bool | str | int | float | list[float]]
    quality: float = Field(default=1, ge=0, le=1)
    hidden: bool = False


class ParsedDocument(StrictModel):
    source_id: str
    sha256: str
    format: Literal["txt", "pdf", "docx", "xlsx"]
    parser_version: str = "v1"
    blocks: tuple[SourceBlock, ...]
    warnings: tuple[str, ...] = ()


class Value(StrictModel):
    raw: str | None
    normalized: str | int | None
    extraction_id: str | None


class Comparison(StrictModel):
    field: FieldName
    si: Value
    bl: Value
    decision: Decision
    severity: Literal["none", "low", "medium", "high"]
    confidence: float = Field(ge=0, le=1)
    rule: str
    explanation: str = Field(max_length=2000)
    evidence_ids: tuple[str, ...]


class VerificationReport(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    email_id: str
    revision: int = Field(default=1, ge=1)
    status: Literal["OK", "MISMATCH", "NEEDS_REVIEW"]
    complete: bool
    review_reasons: tuple[str, ...]
    confidence: float = Field(ge=0, le=1)
    comparisons: tuple[Comparison, ...] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def consistency(self):
        if {row.field for row in self.comparisons} != set(FIELDS):
            raise ValueError("Report must cover each field once")
        unresolved = any(row.decision not in {"match", "mismatch"} for row in self.comparisons)
        has_mismatch = any(row.decision == "mismatch" for row in self.comparisons)
        expected = (
            "MISMATCH" if has_mismatch
            else ("NEEDS_REVIEW" if unresolved else "OK")
        )
        if self.status != expected or self.complete == unresolved:
            raise ValueError("Status/completeness contradict field decisions")
        if self.confidence != min(row.confidence for row in self.comparisons):
            raise ValueError("Report confidence must be the minimum field confidence")
        return self
