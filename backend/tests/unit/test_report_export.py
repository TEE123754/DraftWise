import csv
import io

from app.parsers.registry import parse_document
from app.services.extraction import extract_labelled
from app.services.report_export import COLUMNS, report_rows, to_csv
from app.services.verification import verify

TAIL = "Notify Party: ACME TRADING LLC\nPort of Loading: SHANGHAI\nPort of Discharge: ROTTERDAM\n"


def build(si_containers="3", bl_containers="4", si_shipper="ALPHA EXPORTS LTD", bl_consignee="Consignee: ACME TRADING LLC"):
    texts = {
        "si.txt": f"SHIPPING INSTRUCTIONS\nShipper: {si_shipper}\nConsignee (Non-Negotiable): ACME TRADING LLC\n{TAIL}"
        f"Container Count: {si_containers}\nGross Weight: 22000 KG\n",
        "bl.txt": f"DRAFT BILL OF LADING\nShipper: ALPHA EXPORTS LTD\n{bl_consignee}\n{TAIL}"
        f"Container Count: {bl_containers}\nGross Weight: 22000 KG\n",
    }
    si, bl = (extract_labelled(parse_document(text.encode(), name)) for name, text in texts.items())
    report = verify(si, bl, evidence_quality={}).model_dump(mode="json")
    outputs = {si.document_id: si.model_dump(mode="json"), bl.document_id: bl.model_dump(mode="json")}
    return report, outputs


EMAIL = {"external_id": "email_007", "subject": "Draft BL for SIN1"}


def parse(data: bytes):
    assert data.startswith(b"\xef\xbb\xbf")  # BOM so Excel reads UTF-8
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


def test_only_flagged_fields_by_default_with_the_reason_and_the_source_quote():
    report, outputs = build()
    rows = parse(to_csv(report_rows(EMAIL, report, outputs, include_matches=False)))
    assert [row["field"] for row in rows] == ["container_count"]
    row = rows[0]
    assert (row["email_id"], row["report_status"], row["decision"]) == ("email_007", "MISMATCH", "mismatch")
    assert (row["si_value"], row["bl_value"]) == ("3", "4")
    assert row["explanation"] == "Container Count differs: SI 3; BL 4."
    assert (row["handled_by"], row["severity"], row["confidence"]) == ("Human review", "high", "1.00")
    assert row["next_step"].startswith("Confirm the difference")
    assert "Container Count: 3" in row["si_evidence"] and "Container Count: 4" in row["bl_evidence"]


def test_include_matches_gives_all_seven_fields_and_marks_matches_automated():
    report, outputs = build()
    rows = parse(to_csv(report_rows(EMAIL, report, outputs, include_matches=True)))
    assert len(rows) == 7
    matched = [row for row in rows if row["decision"] == "match"]
    assert len(matched) == 6
    assert {(row["handled_by"], row["next_step"]) for row in matched} == {("Automated", "None")}


def test_all_seven_fields_matching_exports_nothing_by_default():
    report, outputs = build(bl_containers="3")
    assert report_rows(EMAIL, report, outputs, include_matches=False) == []
    assert parse(to_csv([])) == []


def test_header_row_is_always_written():
    assert to_csv([]).decode("utf-8-sig").splitlines() == [",".join(COLUMNS)]


def test_to_the_order_of_note_is_informational_and_only_in_the_all_fields_export():
    report, outputs = build(bl_containers="3", bl_consignee="To the Order of: ACME TRADING LLC")
    assert report_rows(EMAIL, report, outputs, include_matches=False) == []  # not a defect, not a review item
    rows = parse(to_csv(report_rows(EMAIL, report, outputs, include_matches=True)))
    row = next(row for row in rows if row["field"] == "consignee")
    assert (row["decision"], row["severity"], row["handled_by"]) == ("match", "low", "Automated")
    assert "BL type" in row["next_step"] and "negotiable" in row["explanation"]


def test_cells_that_could_run_as_formulas_are_neutralised():
    report, outputs = build(si_shipper="=HYPERLINK(\"http://evil\")")
    unsafe = {"external_id": "email_007", "subject": "@SUM(A1)"}
    rows = parse(to_csv(report_rows(unsafe, report, outputs, include_matches=True)))
    assert all(not row["subject"].startswith("@") for row in rows)
    shipper = next(row for row in rows if row["field"] == "shipper")
    assert shipper["si_value"].startswith("'=")
