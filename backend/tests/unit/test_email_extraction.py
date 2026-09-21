from app.services.email_extraction import extract_email_body


def test_email_values_have_exact_offsets_and_exclude_history():
    body = "Hello\r\nShipper: Current Ltd\r\nGross weight: 1200 kg\r\nOn Monday wrote:\r\nShipper: Old Ltd"
    result = extract_email_body("test", "Shipper: Misleading subject", body)
    fields = result["extraction"]["fields"]
    assert fields["shipper"]["raw_value"] == "Current Ltd"
    assert fields["gross_weight_kg"]["raw_value"] == "1200 kg"
    assert result["quoted_history_excluded"]
    assert result["requires_source_confirmation"]
    assert result["extraction"]["document_type"] == "UNKNOWN"
    for block in result["source"]["blocks"]:
        location = block["locator"]
        assert body[location["start"] : location["end"]] == block["text"]


def test_conflicts_missing_and_numeric_senses_remain_unresolved():
    result = extract_email_body(
        "test", "", "Consignee: A\nConsignee: B\nNet weight: 10 kg\nPackages: 20"
    )
    fields = result["extraction"]["fields"]
    assert fields["consignee"]["state"] == "ambiguous"
    assert fields["gross_weight_kg"]["state"] == "missing"
    assert fields["container_count"]["state"] == "missing"


def test_plain_prose_does_not_invent_fields():
    result = extract_email_body("test", "", "Please check the attached draft. Thank you.")
    assert all(field["state"] == "missing" for field in result["extraction"]["fields"].values())


import pytest  # noqa: E402


@pytest.mark.parametrize(
    "subject",
    [
        # Real subjects from the sample mailbox: the word "to" or "from" is not a route.
        "TO CONFIRM DOCS _ 5RSG-00133 _ CALLAO_PERU _ MOORIM SP CO., LTD _ MEDUUD104332",
        "RE: TO CANCEL BOOKING 5AAT-03056",
        "To avoid demurrage please send the total charges",
        "Draft BL from Singapore to Rotterdam",
        "Destination charges query",
    ],
)
def test_ordinary_subject_words_are_not_ports(subject):
    fields = extract_email_body("test", subject, "Please check the draft.")["extraction"]["fields"]
    assert fields["port_of_discharge"]["state"] == "missing"
    assert fields["port_of_loading"]["state"] == "missing"


def test_an_explicitly_labelled_subject_still_gives_ports():
    result = extract_email_body("test", "Draft BL POL: SGSIN / POD: CNSHA", "Please check.")
    fields = result["extraction"]["fields"]
    assert (fields["port_of_loading"]["raw_value"], fields["port_of_discharge"]["raw_value"]) == ("SGSIN", "CNSHA")
    assert fields["port_of_discharge"]["evidence"][0]["quote"].startswith("POD")
    assert result["method"] == "subject_email_fields_v1"


def test_body_labels_still_win_over_the_subject():
    result = extract_email_body("test", "POD: CNSHA", "Port of discharge: ROTTERDAM, NL")
    assert result["extraction"]["fields"]["port_of_discharge"]["raw_value"] == "ROTTERDAM, NL"


def test_reconcile_with_attachment():
    from app.domain.models import Evidence, ExtractedField, Extraction, FieldName
    from app.services.email_extraction import reconcile_with_attachment

    # Create dummy attachment extraction with missing pod
    fields_att = {f: ExtractedField() for f in FieldName}
    fields_att[FieldName.SHIPPER] = ExtractedField(
        raw_value="Shipper Corp", state="present", evidence=(Evidence(block_id="att:1", quote="Shipper Corp"),)
    )
    att_ext = Extraction(document_id="att_1", document_type="SI", fields=fields_att)

    # Body extraction with POD present
    fields_body = {f: ExtractedField() for f in FieldName}
    fields_body[FieldName.POD] = ExtractedField(
        raw_value="CALLAO, PERU", state="present", evidence=(Evidence(block_id="body:1", quote="POD: CALLAO, PERU"),)
    )
    body_ext = Extraction(document_id="body_1", document_type="UNKNOWN", fields=fields_body)

    reconciled, notes = reconcile_with_attachment(att_ext, body_ext)
    assert reconciled.fields[FieldName.SHIPPER].raw_value == "Shipper Corp"
    assert reconciled.fields[FieldName.POD].raw_value == "CALLAO, PERU"
    assert any("promoted from email body" in note for note in notes)

