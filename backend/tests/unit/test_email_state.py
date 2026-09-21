import itertools

import pytest

from app.services.email_state import STATES, EmailFacts, derive_state

BL = "BL_COMPARISON"


def facts(**overrides):
    return EmailFacts(**{"category": BL, **overrides})


def reason_codes(state):
    return [item["code"] for item in state.reasons]


@pytest.mark.parametrize(
    ("given", "state", "tone", "codes", "action"),
    [
        (facts(held=True), "held", "red", ["safety_hold"], "review_safety"),
        (facts(category="SPAM"), "spam", "red", [], "confirm_spam"),
        (facts(category=None, risk_state="spam"), "spam", "red", [], "confirm_spam"),
        (facts(job_active=True), "processing", "grey", [], "wait"),
        (facts(category=None), "needs_review", "yellow", ["unclassified"], "classify"),
        (facts(category="SI_REQUEST"), "classified", "green", [], "reply_si"),
        (facts(category="INVOICE_QUERY"), "classified", "green", [], "reply_invoice"),
        (facts(category="GENERAL"), "classified", "green", [], "none"),
        # A lure phrase on mail that was classified as real business is not called spam.
        (facts(category="INVOICE_QUERY", risk_state="spam"), "classified", "green", [], "reply_invoice"),
    ],
)
def test_state_table(given, state, tone, codes, action):
    result = derive_state(given)
    assert (result.state, result.tone, reason_codes(result), result.action["kind"]) == (
        state, tone, codes, action,
    )


@pytest.mark.parametrize(
    ("body", "state", "codes", "action"),
    [
        ("Please assist to send the draft BL for SIN1 for checking.", "waiting_for_draft", ["awaiting_draft"], "await_draft"),
        (
            "Please compare the SI and draft BL (attachments appear to have been dropped).",
            "needs_documents",
            ["attachments_absent", "missing_si", "missing_bl"],
            "resend",
        ),
        ("Please check draft BL", "needs_documents", ["missing_si", "missing_bl"], "request_both"),
    ],
)
def test_comparison_email_without_files(body, state, codes, action):
    result = derive_state(facts(body_head=body))
    assert (result.state, reason_codes(result), result.action["kind"]) == (state, codes, action)


@pytest.mark.parametrize(
    ("roles", "quarantined", "codes", "action"),
    [
        (("SI",), 0, ["missing_bl"], "request_bl"),
        (("BL",), 0, ["missing_si"], "request_si"),
        (("SI", "INVOICE"), 0, ["missing_bl", "wrong_doc_type"], "request_bl"),
        (("SI", "UNKNOWN"), 0, ["missing_bl", "unrecognised_document"], "request_bl"),
        (("SI",), 1, ["missing_bl", "unreadable"], "request_bl"),
        ((), 0, ["missing_si", "missing_bl"], "request_both"),
    ],
)
def test_missing_or_wrong_documents_name_exactly_what_is_missing(roles, quarantined, codes, action):
    result = derive_state(facts(attachment_count=2, roles=roles, quarantined=quarantined))
    assert result.state == "needs_documents"
    assert (reason_codes(result), result.action["kind"]) == (codes, action)


def test_documents_not_read_yet_are_not_reported_as_missing():
    unread = derive_state(facts(attachment_count=2, unread=2))
    assert (unread.state, reason_codes(unread)) == ("needs_review", ["documents_unread"])
    failed = derive_state(facts(attachment_count=2, unread=2, job_state="failed"))
    assert reason_codes(failed) == ["processing_failed"]


def test_a_finished_job_that_left_a_file_unread_means_the_file_could_not_be_opened():
    result = derive_state(facts(attachment_count=2, roles=("SI",), unread=1, job_state="succeeded"))
    assert (result.state, reason_codes(result), result.action["kind"]) == (
        "needs_review", ["unreadable"], "request_readable",
    )


def test_unreadable_file_with_both_documents_present_needs_review():
    result = derive_state(facts(attachment_count=2, roles=("SI", "BL"), quarantined=1))
    assert (result.state, reason_codes(result)) == ("needs_review", ["unreadable"])


@pytest.mark.parametrize(
    ("report", "mismatch", "unresolved", "state", "tone", "label_part"),
    [
        (None, (), (), "needs_review", "yellow", "not compared"),
        ("OK", (), (), "checked", "green", ""),
        ("MISMATCH", ("consignee", "notify_party"), (), "mismatch_found", "yellow", "consignee, notify party"),
        ("NEEDS_REVIEW", (), ("gross_weight_kg",), "needs_review", "yellow", "gross weight kg"),
    ],
)
def test_compared_documents(report, mismatch, unresolved, state, tone, label_part):
    result = derive_state(
        facts(
            attachment_count=2, roles=("SI", "BL"), report_status=report,
            mismatch_fields=mismatch, unresolved_fields=unresolved,
        )
    )
    assert (result.state, result.tone) == (state, tone)
    if label_part:
        assert label_part in " ".join(item["label"] for item in result.reasons).lower()


def test_api_shape_is_json_ready():
    payload = derive_state(facts(attachment_count=2, roles=("SI", "BL"), report_status="MISMATCH",
                                 mismatch_fields=("consignee",))).to_dict()
    assert payload["state"] == "mismatch_found"
    assert payload["state_label"] == "Mismatch found"
    assert payload["reasons"][0]["fields"] == ["consignee"]
    assert set(payload["action"]) == {"kind", "title"}


def test_nothing_is_green_unless_it_really_passed():
    """Exhaustive check over many fact combinations: the reported bug was green with no comparison."""
    grid = itertools.product(
        (None, "SPAM", "BL_COMPARISON", "SI_REQUEST", "GENERAL"),   # category
        (False, True),                                              # held
        (False, True),                                              # job_active
        (0, 1, 2),                                                  # attachment_count
        (0, 1),                                                     # unread
        (0, 1),                                                     # quarantined
        ((), ("SI",), ("BL",), ("SI", "BL"), ("SI", "INVOICE"), ("SI", "BL", "UNKNOWN")),
        (None, "OK", "MISMATCH", "NEEDS_REVIEW"),                   # report
        ("Please check draft BL", "Please send the draft BL for X"),  # body
    )
    seen = set()
    for category, held, active, count, unread, quarantined, roles, report, body in grid:
        result = derive_state(
            EmailFacts(
                category=category, held=held, job_active=active, attachment_count=count,
                unread=min(unread, count), quarantined=min(quarantined, count), roles=roles,
                report_status=report, body_head=body,
            )
        )
        seen.add(result.state)
        assert result.state in STATES and result.tone == STATES[result.state][1]
        if result.tone == "green" and category == BL:
            assert result.state == "checked"
            assert report == "OK" and {"SI", "BL"} <= set(roles) and not unread and not held and not active
        if result.state == "checked":
            assert category == BL and report == "OK"
    assert seen == set(STATES)  # every state is reachable
