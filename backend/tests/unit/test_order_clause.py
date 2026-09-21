from app.parsers.registry import parse_document
from app.services.extraction import extract_labelled
from app.services.verification import verify

TAIL = (
    "Notify Party: ACME TRADING LLC\nPort of Loading: SHANGHAI\nPort of Discharge: ROTTERDAM\n"
    "Container Count: 3\nGross Weight: 22000 KG\n"
)


def report(si_consignee_line: str, bl_consignee_line: str):
    documents = []
    for title, line, name in (
        ("SHIPPING INSTRUCTIONS", si_consignee_line, "si.txt"),
        ("DRAFT BILL OF LADING", bl_consignee_line, "bl.txt"),
    ):
        text = f"{title}\nShipper: ALPHA EXPORTS LTD\n{line}\n{TAIL}"
        documents.append(extract_labelled(parse_document(text.encode(), name)))
    return verify(*documents, evidence_quality={})


def consignee(result):
    return next(row for row in result.comparisons if row.field == "consignee")


def test_to_the_order_of_against_a_straight_consignee_is_noted_not_hidden():
    row = consignee(report("Consignee (Non-Negotiable): ACME TRADING LLC", "To the Order of: ACME TRADING LLC"))
    assert row.decision == "match"
    assert row.severity == "low"
    assert row.rule == "consignee_order_clause_v1"
    assert "negotiable" in row.explanation and "Confirm the BL type" in row.explanation


def test_a_straight_consignee_on_the_bl_against_an_order_si_is_noted():
    row = consignee(report("Consignee: To the Order of ACME TRADING LLC", "Consignee: ACME TRADING LLC"))
    assert row.decision == "match"
    assert row.severity == "low"
    assert "SI asks for" in row.explanation


def test_both_sides_to_order_is_a_plain_match():
    row = consignee(report("Consignee: To the Order of ACME TRADING LLC", "To the Order of: ACME TRADING LLC"))
    assert (row.decision, row.severity) == ("match", "none")
    assert row.explanation == "Both source values match after deterministic normalization."


def test_two_straight_consignees_are_a_plain_match():
    row = consignee(report("Consignee: ACME TRADING LLC", "Consignee: ACME TRADING LLC"))
    assert (row.decision, row.severity, row.rule) == ("match", "none", "party_normalized_v1")


def test_bare_to_order_stays_a_mismatch_and_says_why():
    row = consignee(report("Consignee: ACME TRADING LLC", "Consignee: TO ORDER"))
    assert row.decision == "mismatch"
    assert "negotiable" in row.explanation


def test_the_note_never_touches_other_fields():
    result = report("Consignee (Non-Negotiable): ACME TRADING LLC", "To the Order of: ACME TRADING LLC")
    assert {row.field: row.severity for row in result.comparisons if row.field != "consignee"} == {
        row.field: "none" for row in result.comparisons if row.field != "consignee"
    }
    assert result.status == "OK"
