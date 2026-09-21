import json
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker

from app.benchmark.export import export_prediction
from app.domain.models import FieldName
from app.services.correction_previews import create_preview
from app.services.revision_analysis import analyze_revision
from app.services.verification import verify

ROOT = Path(__file__).resolve().parents[3]


def validate(name, instance):
    schema = json.loads((ROOT / "shared/schemas" / f"{name}.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def test_runtime_outputs_match_shared_contracts(document_factory):
    si, q1 = document_factory()
    bl, q2 = document_factory("BL", container_count="4")
    report = verify(si, bl, evidence_quality=q1 | q2)
    validate("extraction", si.model_dump(mode="json"))
    validate("verification", report.model_dump(mode="json"))
    validate(
        "submission", {"local": export_prediction("BL_COMPARISON", report).model_dump(mode="json")}
    )
    preview = create_preview(
        report,
        workspace_id=uuid4(),
        case_id=uuid4(),
        case_version=1,
        policy_version="v1",
        fields=(FieldName.CONTAINERS,),
    )
    validate("correction-preview", preview.model_dump(mode="json"))
    summary = analyze_revision(
        None, report, case_id=uuid4(), baseline_version=1, policy_version="v1"
    )
    validate("revision-summary", summary.model_dump(mode="json"))


def test_confirmed_mismatch_is_exported_even_with_unresolved_fields(document_factory):
    si, q1 = document_factory()
    bl, q2 = document_factory("BL", container_count="4", gross_weight_kg=None)
    report = verify(si, bl, evidence_quality=q1 | q2)
    result = export_prediction("BL_COMPARISON", report)
    assert report.complete is False
    assert result.status == "MISMATCH"
    assert result.has_defect is True
    assert result.defect_fields == (FieldName.CONTAINERS,)
    assert result.review_reason is None


def test_unresolved_fields_without_mismatch_need_review(document_factory):
    si, q1 = document_factory()
    bl, q2 = document_factory("BL", gross_weight_kg=None)
    result = export_prediction("BL_COMPARISON", verify(si, bl, evidence_quality=q1 | q2))
    assert result.status == "NEEDS_REVIEW"
    assert result.has_defect is False
    assert result.defect_fields == ()
