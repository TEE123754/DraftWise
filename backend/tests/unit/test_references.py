from app.services.references import reference_check, references


def codes(found):
    return {(item["kind"], item["code"]) for item in found}


def test_generic_codes_are_found_only_when_asked_and_only_in_capitals():
    text = "Draft BL for SIN525534192 please. Ref abc123456789, ABC123 and 20260921 are not codes."
    assert references(text) == []
    assert codes(references(text, generic=True)) == {("code", "SIN525534192")}


def test_labelled_references_are_unchanged_and_generic_adds_to_them():
    text = "Booking ref: BK12345, see also SIN525534192"
    assert codes(references(text)) == {("booking", "BK12345")}
    assert codes(references(text, generic=True)) == {("booking", "BK12345"), ("code", "SIN525534192")}


def cited(*pairs):
    return [{"kind": kind, "code": code, "quote": code} for kind, code in pairs]


def test_no_documents_means_nothing_to_check_against():
    assert reference_check(cited(("booking", "BK12345")), [], has_documents=False) == {"status": "no_documents", "cited": []}


def test_an_email_that_cites_nothing_is_not_flagged():
    assert reference_check([], cited(("bl", "BL99999")), has_documents=True) == {"status": "none_cited", "cited": []}


def test_matches_partial_and_flagged():
    own = cited(("bl", "BK12345"), ("code", "SIN525534192"))
    matches = reference_check(cited(("booking", "BK12345"), ("code", "SIN525534192")), own, has_documents=True)
    assert matches["status"] == "matches" and all(row["in_documents"] for row in matches["cited"])
    partial = reference_check(cited(("booking", "BK12345"), ("oc", "OC777777")), own, has_documents=True)
    assert partial["status"] == "partial"
    assert [(row["code"], row["in_documents"]) for row in partial["cited"]] == [("BK12345", True), ("OC777777", False)]
    assert reference_check(cited(("booking", "ZZ99999")), own, has_documents=True)["status"] == "flagged"


def test_the_label_does_not_matter_only_the_code_and_repeats_are_listed_once():
    # "Booking ref" in the email, "B/L no." in the document: the same identifier.
    own = cited(("bl", "BK12345"))
    result = reference_check(cited(("booking", "BK12345"), ("booking", "BK12345")), own, has_documents=True)
    assert result["status"] == "matches" and len(result["cited"]) == 1
