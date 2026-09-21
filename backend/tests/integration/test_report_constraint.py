from uuid import uuid4

import pytest
from inbox_support import add_document, add_email
from psycopg.errors import CheckViolation
from psycopg.types.json import Jsonb

from app.ai.grounding import ground_extraction
from app.config import Settings
from app.parsers.registry import parse_document
from app.repositories.emails import load_inbox
from app.services.extraction import extract_labelled
from app.services.verification import verify
from app.workers.handlers import Handlers

SI = b"""SHIPPING INSTRUCTION
Shipper: ACME LTD
Consignee: BETA LLC
Notify: BETA LLC
Port of Loading: ROTTERDAM
Port of Discharge: SANTOS
Containers: 3 x 40HC
Gross Weight: 20,000 KG
"""
# A real difference (the consignee) plus a blank value (the discharge port is "TBA").
BL = SI.replace(b"SHIPPING INSTRUCTION", b"DRAFT BILL OF LADING").replace(
    b"Consignee: BETA LLC", b"Consignee: OTHER GMBH"
).replace(b"Port of Discharge: SANTOS", b"Port of Discharge: TBA")


def extraction(data, name):
    document = parse_document(data, name)
    result = extract_labelled(document)
    return result, ground_extraction(result, document)


async def test_worker_saves_a_mismatch_that_also_has_a_blank_value(database, workspace_factory):
    context = await workspace_factory()
    workspace = context["workspace"]
    si, si_quality = extraction(SI, "si.txt")
    bl, bl_quality = extraction(BL, "bl.txt")
    report = verify(si, bl, evidence_quality={**si_quality, **bl_quality})
    assert (report.status, report.complete, report.review_reasons) == (
        "MISMATCH", False, ("port_of_discharge",)
    )  # the case that used to violate the table's CHECK constraint

    async with database.connection() as connection:
        email = await add_email(connection, workspace, "email_50", category="BL_COMPARISON")
        si_id = await add_document(connection, workspace, email, "email_50_SI.txt", "SI")
        bl_id = await add_document(connection, workspace, email, "email_50_BL.txt", "BL")
    prepared = {"report": report, "si_id": si_id, "bl_id": bl_id, "equivalence_rules": [],
                "input_fingerprint": "mismatch-with-blank"}
    job = {"id": uuid4(), "workspace_id": workspace, "email_id": email, "kind": "verify", "payload": {}}
    async with database.connection() as connection:
        saved = await Handlers(database, None, Settings(environment="test")).persist(connection, job, prepared)
    assert saved["status"] == "MISMATCH"

    async with database.connection() as connection:
        row = await (await connection.execute(
            "select status,complete,review_reasons from public.verification_reports where email_id=%s", (email,)
        )).fetchone()
        assert (row["status"], row["complete"], row["review_reasons"]) == ("MISMATCH", False, ["port_of_discharge"])
        fields = await (await connection.execute(
            "select field,decision from public.discrepancies where report_id=%s order by field", (saved["verification_id"],)
        )).fetchall()
        assert {(f["field"], f["decision"]) for f in fields} == {("consignee", "mismatch"), ("port_of_discharge", "missing")}
        item = (await load_inbox(connection, workspace, email))[0]
    assert item["state"] == "mismatch_found"
    assert item["reasons"][0]["fields"] == ["consignee"]


@pytest.mark.parametrize(
    ("status", "complete", "reasons"),
    [
        ("OK", True, ["gross_weight_kg"]),        # OK must have nothing unresolved
        ("OK", False, []),                        # ...and must be complete
        ("MISMATCH", True, ["gross_weight_kg"]),  # complete but claims unresolved fields
        ("MISMATCH", False, []),                  # incomplete but nothing unresolved
        ("NEEDS_REVIEW", True, ["gross_weight_kg"]),
        ("NEEDS_REVIEW", False, []),              # needs review, yet no reason given
    ],
)
async def test_report_status_and_completeness_must_agree(database, workspace_factory, status, complete, reasons):
    workspace = (await workspace_factory())["workspace"]
    async with database.connection() as connection:
        email = await add_email(connection, workspace, "email_51", category="BL_COMPARISON")
        si_id = await add_document(connection, workspace, email, "email_51_SI.txt", "SI")
        bl_id = await add_document(connection, workspace, email, "email_51_BL.txt", "BL")
    with pytest.raises(CheckViolation):
        async with database.connection() as connection:
            await connection.execute(
                """insert into public.verification_reports(workspace_id,email_id,si_extraction_id,bl_extraction_id,revision,status,
                complete,confidence,comparison_version,input_fingerprint,review_reasons,report)
                values(%s,%s,%s,%s,1,%s,%s,1,'v1','fp',%s,%s)""",
                (workspace, email, si_id, bl_id, status, complete, reasons, Jsonb({"comparisons": []})),
            )
