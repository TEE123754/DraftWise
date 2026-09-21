from app.config import Settings
from app.domain.errors import DomainError
from app.services.dataset_import import InputEmail
from app.services.pipeline import process_email_record


def email(body, attachments=()):
    return InputEmail(
        email_id="email_test",
        **{"from": "sender@example.test"},
        subject="",
        body=body,
        attachments=attachments,
    )


def test_unknown_intent_is_not_silently_general():
    result = process_email_record(email("An ambiguous request"), None, Settings())
    assert result["prediction"] is None
    assert result["review_reason"] == "unresolved_classification"


def test_noncomparison_does_not_read_attachments():
    def read(_):
        raise AssertionError("Noncomparison must not parse attachments")

    result = process_email_record(email("Please prepare shipping instructions"), read, Settings())
    assert result["prediction"]["category"] == "SI_REQUEST"
    assert result["prediction"]["has_defect"] is False


def test_missing_comparison_documents_require_review():
    result = process_email_record(email("Please check draft BL"), None, Settings())
    assert result["prediction"]["review_reason"] == "missing_attachment"


def test_request_to_send_the_draft_has_nothing_to_review_yet():
    result = process_email_record(
        email("Please assist to send the draft BL for SIN123 for checking asap."), None, Settings()
    )
    assert result["prediction"]["category"] == "BL_COMPARISON"
    assert result["prediction"]["status"] == "OK"
    assert result["prediction"]["review_reason"] is None
    assert result["prediction"]["has_defect"] is False


def test_claimed_but_absent_attachments_still_need_a_person():
    body = "Please compare the SI and draft BL for OC 5AAA-1 (attachments appear to have been dropped)."
    result = process_email_record(email(body), None, Settings())
    assert result["prediction"]["status"] == "NEEDS_REVIEW"
    assert result["prediction"]["review_reason"] == "missing_attachment"


def test_dict_records_use_the_same_no_attachment_rule():
    record = {"email_id": "e1", "subject": "", "body": "Please assist to send the draft BL for X for checking."}
    result = process_email_record(record, lambda _: b"", Settings())
    assert result.prediction.status == "OK"
    claimed = {"email_id": "e2", "subject": "", "body": "Attached are the SI and draft BL. Please check."}
    assert process_email_record(claimed, lambda _: b"", Settings()).prediction.review_reason == "missing_attachment"


def test_attachment_that_cannot_be_opened_is_unreadable_not_missing(monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("No /Root object! - Is this really a PDF?")

    monkeypatch.setattr("app.services.pipeline.parse_document", broken)
    record = {
        "email_id": "e3",
        "subject": "",
        "body": "Attached are the SI and draft BL. Please check.",
        "attachments": ["attachments/e3_SI.pdf", "attachments/e3_BL.pdf"],
    }
    prediction = process_email_record(record, lambda _: b"junk", Settings()).prediction
    assert prediction.status == "NEEDS_REVIEW"
    assert prediction.review_reason == "unreadable"


def test_missing_ocr_routes_to_review_without_crashing(monkeypatch):
    def parse(*args):
        raise DomainError("OCR_UNAVAILABLE", "OCR engine unavailable")

    monkeypatch.setattr("app.services.pipeline.parse_bounded", parse)
    result = process_email_record(
        email("Please check draft BL", ("attachments/test.pdf",)), lambda _: b"scanned", Settings()
    )
    assert result["prediction"]["status"] == "NEEDS_REVIEW"
    assert result["prediction"]["review_reason"] == "unreadable"
    assert result["errors"][0]["code"] == "OCR_UNAVAILABLE"
