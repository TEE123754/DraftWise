from app.ai.grounding import ground_extraction
from app.domain.models import Evidence, ExtractedField, FieldName
from app.parsers.registry import parse_document
from app.services.extraction import extract_labelled


def test_net_weight_cannot_become_trusted_gross_weight():
    document = parse_document(b"SHIPPING INSTRUCTION\nNet Weight: 22000 KG", "source")
    extracted = extract_labelled(document)
    block = document.blocks[1]
    fields = dict(extracted.fields)
    fields[FieldName.WEIGHT] = ExtractedField(
        raw_value="22000 KG",
        state="present",
        evidence=(Evidence(block_id=block.id, quote=block.text),),
    )
    scores = ground_extraction(extracted.model_copy(update={"fields": fields}), document)
    assert scores[block.id] < 0.9
