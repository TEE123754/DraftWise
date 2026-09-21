import pytest

from app.services.classification import (
    attachments_expected,
    classify_explicit,
    requests_draft,
    segment_email,
)


def test_quoted_comparison_does_not_override_current_invoice_action():
    body = "Please cancel this invoice.\nOn Tuesday Someone wrote:\nPlease check the draft BL."
    assert classify_explicit("Re: draft BL", body).category == "INVOICE_QUERY"
    assert "check" not in segment_email("", body)[1]["text"]


def test_attachments_and_subject_alone_do_not_trigger_comparison():
    assert classify_explicit("Draft BL", "Thank you for the update.") is None


@pytest.mark.parametrize(
    "body",
    [
        "Please assist to send the draft BL for SIN123 for checking asap.",
        "Kindly send the bill of lading draft for verification.",
        "We are reviewing the draft BL and will confirm.",
    ],
)
def test_inflected_comparison_verbs_are_comparison_requests(body):
    assert classify_explicit("Shipment 5AAA-1", body).category == "BL_COMPARISON"


def test_bulk_pending_shipment_reminder_is_informational_not_a_new_si_request():
    body = "Reminder: Please submit SI & AED for all pending shipments by end of day. Refer to the attached list."
    result = classify_explicit("Reminder", body)
    assert result.category == "GENERAL"
    assert classify_explicit("", "Please submit SI for shipment 5AAA-1.").category == "SI_REQUEST"


def test_holiday_notice_from_automated_billing_job_is_general():
    body = "Wishing everyone a happy and prosperous New Year! Office resumes normal operations on 2 January."
    assert classify_explicit("_RPA_ Billing Process Completed", body).category == "GENERAL"


def test_only_the_message_itself_claims_attachments_not_security_banners_or_history():
    banner = "WARNING: exercise caution with links or attachments.\nPlease send the draft BL."
    assert not attachments_expected("Draft BL", banner)
    assert attachments_expected("", "Attached are the SI and draft BL for OC 5AAA-1.")
    assert attachments_expected("", "Please compare the SI and draft BL (attachments appear to have been dropped).")
    assert not attachments_expected("", "Thanks.\nOn Monday Sam wrote:\nSee attached.")


def test_asking_for_the_draft_to_be_sent_is_different_from_asking_to_check_a_missing_one():
    assert requests_draft("", "Please assist to send the draft BL for SIN123 for checking asap.")
    assert not requests_draft("", "Please check draft BL")
    assert not requests_draft("", "Please compare the SI and draft BL and confirm.")


def test_billing_complaint_mentioning_the_draft_bl_is_not_answered_by_a_rule():
    body = "Why was I charged USD 75 for the draft bill of lading amendment? I need a refund."
    assert classify_explicit("Draft BL fee", body) is None  # deferred to the AI or a person


def test_attached_commercial_invoice_is_not_a_billing_complaint():
    body = "Please find attached the SI and the Commercial Invoice. Kindly confirm the BL is in order."
    assert classify_explicit("TO CONFIRM DOCS", body).category == "BL_COMPARISON"


def test_multiple_current_actions_require_ai_or_review():
    assert (
        classify_explicit("", "Please prepare shipping instructions and check the draft BL.")
        is None
    )
