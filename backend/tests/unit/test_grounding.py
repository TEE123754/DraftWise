import pytest

from app.ai.grounding import ground_extraction
from app.domain.errors import DomainError
from app.domain.models import Evidence, ExtractedField, FieldName
from app.parsers.registry import parse_document
from app.services.extraction import extract_labelled


def test_citing_real_block_does_not_allow_hallucinated_value():
    document = parse_document(b"SHIPPING INSTRUCTION\nShipper: Example Export Ltd", "si")
    extraction = extract_labelled(document)
    fields = dict(extraction.fields)
    fields[FieldName.SHIPPER] = ExtractedField(
        raw_value="Invented Export Ltd",
        state="present",
        evidence=extraction.fields[FieldName.SHIPPER].evidence,
    )
    with pytest.raises(DomainError):
        ground_extraction(extraction.model_copy(update={"fields": fields}), document)


def test_evidence_cannot_cross_document_boundary():
    document = parse_document(b"SHIPPING INSTRUCTION\nShipper: Example Export Ltd", "si")
    extraction = extract_labelled(document)
    fields = dict(extraction.fields)
    fields[FieldName.SHIPPER] = ExtractedField(
        raw_value="Example Export Ltd",
        state="present",
        evidence=(Evidence(block_id="another-source", quote="Example Export Ltd"),),
    )
    with pytest.raises(DomainError):
        ground_extraction(extraction.model_copy(update={"fields": fields}), document)
