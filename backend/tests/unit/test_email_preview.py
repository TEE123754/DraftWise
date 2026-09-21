from app.services.email_preview import classification_summary, field_table

SEGMENTS = [
    {"id": "subject", "kind": "subject", "text": "Draft BL for SIN1"},
    {"id": "current", "kind": "current", "text": "Please check the attached draft   BL."},
    {"id": "history", "kind": "quoted_history", "text": ""},
]


def stored(category="BL_COMPARISON", *, by="rule", evidence=None, meta=None, ambiguous=False):
    return {
        "category": category,
        "ambiguous": ambiguous,
        "decided_by": by,
        "evidence": evidence if evidence is not None else [],
        "run_metadata": meta if meta is not None else {},
    }


# --- classification ---------------------------------------------------------------------------


def test_no_classification_gives_nothing():
    assert classification_summary(None, SEGMENTS) is None


def test_worker_rule_result_quotes_the_email_from_its_metadata():
    meta = {
        "method": "rules",
        "reason_code": "comparison_action",
        "evidence": [{"id": "current", "text": "Please check the attached draft BL."}],
    }
    summary = classification_summary(stored(evidence=["current"], meta=meta), SEGMENTS)
    assert (summary["method"], summary["method_label"]) == ("rules", "Rules")
    assert summary["reason"] == "Asks for the draft BL to be checked or compared"
    assert summary["evidence"] == [{"id": "current", "text": "Please check the attached draft BL."}]


def test_demo_seed_stores_the_whole_classification_and_its_span_ids_are_resolved():
    seeded = {"category": "BL_COMPARISON", "ambiguous": False, "reason_code": "comparison_action",
              "evidence_span_ids": ["subject", "current"]}
    summary = classification_summary(stored(evidence=seeded, meta={"provider": "rule", "demo": True}), SEGMENTS)
    assert summary["method"] == "rules"
    assert summary["reason_code"] == "comparison_action"
    # Whitespace is collapsed so a quote reads as one line.
    assert [q["text"] for q in summary["evidence"]] == ["Draft BL for SIN1", "Please check the attached draft BL."]


def test_span_ids_that_do_not_exist_or_are_empty_are_dropped():
    summary = classification_summary(stored(evidence=["history", "gone", "subject"]), SEGMENTS)
    assert [q["id"] for q in summary["evidence"]] == ["subject"]


def test_methods_are_told_apart():
    assert classification_summary(stored(meta={"method": "ai"}), SEGMENTS)["method_label"] == "AI"
    fallback = classification_summary(
        stored(meta={"method": "rule_fallback", "fallback_reason": "PROVIDER_NOT_CONFIGURED"}), SEGMENTS
    )
    assert (fallback["method"], fallback["fallback_reason"]) == ("rule_fallback", "PROVIDER_NOT_CONFIGURED")
    human = classification_summary(
        stored(by="human", meta={"method": "human_review", "reason": "Sender confirmed by phone"}), SEGMENTS
    )
    assert (human["method"], human["method_label"], human["human_reason"]) == (
        "human", "Reviewer", "Sender confirmed by phone",
    )


def test_an_ambiguous_result_has_no_category():
    summary = classification_summary(stored("GENERAL", ambiguous=True), SEGMENTS)
    assert (summary["category"], summary["ambiguous"]) == (None, True)


def test_long_quotes_are_clipped():
    long = [{"id": "current", "kind": "current", "text": "word " * 200}]
    text = classification_summary(stored(evidence=["current"]), long)["evidence"][0]["text"]
    assert len(text) == 240 and text.endswith("…")


# --- field table ------------------------------------------------------------------------------


def cell(value, quote=None, state="present"):
    return {"raw_value": value, "state": state, "alternatives": [],
            "evidence": [{"block_id": "b1", "quote": quote or f"Label: {value}"}] if value else []}


def comparison(field, si, bl, decision, explanation="differs"):
    return {"field": field, "decision": decision, "explanation": explanation,
            "si": {"raw": si, "normalized": si}, "bl": {"raw": bl, "normalized": bl}}


def rows_by_field(table):
    return {row["field"]: row for row in table["rows"]}


def test_every_field_appears_once_in_the_report_order():
    table = field_table(None, None, None, None)
    assert [row["field"] for row in table["rows"]] == [
        "shipper", "consignee", "notify_party", "port_of_loading",
        "port_of_discharge", "container_count", "gross_weight_kg",
    ]
    assert table["status"] is None and table["documents"] == {"si": False, "bl": False}


def test_a_missing_document_is_not_the_same_as_a_missing_value():
    si = {"fields": {"shipper": cell("ACME LTD")}}
    table = field_table(None, si, None, None)
    row = rows_by_field(table)["shipper"]
    assert row["si"] == {"state": "present", "value": "ACME LTD", "quote": "Label: ACME LTD"}
    assert row["bl"]["state"] == "no_document"
    assert rows_by_field(table)["consignee"]["si"]["state"] == "missing"  # SI exists, value not found
    assert table["documents"] == {"si": True, "bl": False}


def test_sparse_or_empty_output_does_not_break_the_table():
    table = field_table({"status": "OK", "report": {}}, {}, {}, {})
    assert all(row["si"]["state"] == "missing" and row["decision"] is None for row in table["rows"])


def test_decisions_and_explanations_come_from_the_stored_report():
    report = {"status": "MISMATCH", "report": {"comparisons": [
        comparison("gross_weight_kg", "22000", "23000", "mismatch", "Gross weight differs."),
        comparison("shipper", "ACME", "ACME", "match", "Both source values match."),
    ]}}
    rows = rows_by_field(field_table(report, {}, {}, None))
    assert (rows["gross_weight_kg"]["decision"], rows["gross_weight_kg"]["explanation"]) == (
        "mismatch", "Gross weight differs.",
    )
    assert (rows["shipper"]["decision"], rows["shipper"]["explanation"]) == ("match", None)  # nothing to explain
    assert rows["consignee"]["decision"] is None
    assert field_table(report, {}, {}, None)["status"] == "MISMATCH"


def test_ambiguous_values_list_their_alternatives():
    si = {"fields": {"shipper": {"state": "ambiguous", "raw_value": None, "alternatives": ["A LTD", "B LTD"], "evidence": []}}}
    assert rows_by_field(field_table(None, si, None, None))["shipper"]["si"]["value"] == "A LTD; B LTD"


def report_for(field, si, bl):
    return {"status": "OK", "report": {"comparisons": [comparison(field, si, bl, "match")]}}


def test_email_marks_match_differs_or_unchecked():
    report = report_for("port_of_loading", "SGSIN", "SGSIN")
    same = rows_by_field(field_table(report, {}, {}, {"port_of_loading": cell("SGSIN")}))
    other = rows_by_field(field_table(report, {}, {}, {"port_of_loading": cell("CNSHA")}))
    silent = rows_by_field(field_table(report, {}, {}, {}))
    no_report = rows_by_field(field_table(None, {}, {}, {"port_of_loading": cell("SGSIN")}))
    assert same["port_of_loading"]["email"]["mark"] == "match"
    assert other["port_of_loading"]["email"]["mark"] == "differs"
    assert silent["port_of_loading"]["email"] == {"state": "missing", "value": None, "quote": None, "mark": "unchecked"}
    assert no_report["port_of_loading"]["email"]["mark"] == "unchecked"  # nothing to check it against


def test_the_email_must_agree_with_every_document_that_has_a_value():
    report = report_for("container_count", 2, 3)
    row = rows_by_field(field_table(report, {}, {}, {"container_count": cell("2 containers")}))["container_count"]
    assert row["email"]["mark"] == "differs"  # equals the SI but not the BL
