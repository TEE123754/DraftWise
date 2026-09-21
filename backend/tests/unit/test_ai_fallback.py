import pytesseract

from app.config import Settings
from app.domain.errors import DomainError
from app.domain.models import (
    FIELDS,
    Evidence,
    ExtractedField,
    Extraction,
    FieldName,
    ParsedDocument,
    SourceBlock,
)
from app.parsers import ocr
from app.services.ai_fallback import fill_missing_with_ai
from app.services.extraction import extract_labelled

SOURCE = "attachments/si.txt"


def block(index, text):
    return SourceBlock(id=f"{SOURCE}:{index}", source_id=SOURCE, text=text, locator={"line": index})


def document(*lines):
    return ParsedDocument(
        source_id=SOURCE,
        sha256="0" * 64,
        format="txt",
        blocks=tuple(block(i, text) for i, text in enumerate(lines)),
    )


def present(source_block, value):
    return ExtractedField(
        state="present",
        raw_value=value,
        evidence=(Evidence(block_id=source_block.id, quote=source_block.text),),
    )


class FakeProvider:
    def __init__(self, proposed=None, error=None):
        self.proposed, self.error, self.calls = proposed, error, 0

    async def extract(self, doc):
        self.calls += 1
        if self.error:
            raise self.error
        return self.proposed, {}


def settings(**overrides):
    return Settings(_env_file=None, **overrides)


def sparse_document():
    return document("Shipping Instructions", "Shipper: Acme Ltd", "Deliver to Beta GmbH")


def proposal(doc, **fields):
    base = {name: ExtractedField() for name in FIELDS}
    base.update(fields)
    return Extraction(document_id=doc.source_id, document_type="SI", fields=base)


def test_ai_fills_only_missing_fields_and_keeps_labelled_values():
    doc = sparse_document()
    labelled = extract_labelled(doc)
    provider = FakeProvider(
        proposal(
            doc,
            consignee=present(doc.blocks[2], "Beta GmbH"),
            # The provider disagrees with the labelled shipper; the labelled value must win.
            shipper=present(doc.blocks[1], "Shipper: Acme Ltd"),
        )
    )
    result = fill_missing_with_ai(labelled, doc, settings(), provider)
    assert provider.calls == 1
    assert result.fields[FieldName.CONSIGNEE].raw_value == "Beta GmbH"
    assert result.fields[FieldName.SHIPPER] == labelled.fields[FieldName.SHIPPER]
    assert result.fields[FieldName.POL].state == "missing"


def test_ai_is_skipped_below_the_missing_field_threshold():
    doc = sparse_document()
    labelled = extract_labelled(doc)
    provider = FakeProvider(proposal(doc))
    result = fill_missing_with_ai(labelled, doc, settings(ai_fallback_min_missing=7), provider)
    assert provider.calls == 0
    assert result is labelled


def test_ai_failure_keeps_the_labelled_extraction():
    doc = sparse_document()
    labelled = extract_labelled(doc)
    provider = FakeProvider(error=DomainError("PROVIDER_UNAVAILABLE", "down"))
    assert fill_missing_with_ai(labelled, doc, settings(), provider) is labelled
    assert provider.calls == 1


def test_no_provider_configured_keeps_the_labelled_extraction():
    doc = sparse_document()
    labelled = extract_labelled(doc)
    config = settings(ai_provider="morpheus", morpheus_api_key=None)
    assert fill_missing_with_ai(labelled, doc, config) is labelled


def test_tesseract_command_loads_from_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("TESSERACT_CMD=C:\\Tools\\Tesseract\\tesseract.exe\n", encoding="utf-8")
    assert Settings(_env_file=env_file).tesseract_cmd == "C:\\Tools\\Tesseract\\tesseract.exe"


def test_ocr_uses_settings_when_process_env_is_unset(monkeypatch):
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr(ocr, "get_settings", lambda: settings(tesseract_cmd="C:\\T\\tesseract.exe"))
    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")
    ocr._configure_tesseract()
    assert pytesseract.pytesseract.tesseract_cmd == "C:\\T\\tesseract.exe"
