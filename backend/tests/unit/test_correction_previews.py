from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.errors import DomainError
from app.domain.models import FieldName
from app.services.correction_previews import create_preview, validate_preview
from app.services.verification import verify


def test_preview_does_not_mutate_report_and_keeps_blockers(document_factory):
    si, q1 = document_factory()
    bl, q2 = document_factory("BL", container_count="4", gross_weight_kg="23 MT")
    report = verify(si, bl, evidence_quality=q1 | q2)
    original = report.model_dump_json()
    preview = create_preview(
        report,
        workspace_id=uuid4(),
        case_id=uuid4(),
        case_version=1,
        policy_version="v1",
        fields=(FieldName.CONTAINERS,),
    )
    assert preview.remaining_fields == (FieldName.WEIGHT,)
    assert preview.remaining_blocker_count == 1
    assert report.model_dump_json() == original
    assert report.status == "MISMATCH"


def test_version_and_expiry_reject_stale_preview(document_factory):
    si, q1 = document_factory()
    bl, q2 = document_factory("BL", container_count="4")
    report = verify(si, bl, evidence_quality=q1 | q2)
    context = dict(workspace_id=uuid4(), case_id=uuid4(), case_version=1, policy_version="v1")
    now = datetime.now(UTC)
    preview = create_preview(report, **context, fields=(FieldName.CONTAINERS,), now=now)
    validate_preview(preview, report, **context, now=now)
    with pytest.raises(DomainError):
        validate_preview(preview, report, **(context | {"case_version": 2}), now=now)
    with pytest.raises(DomainError):
        validate_preview(preview, report, **context, now=now + timedelta(minutes=31))


def test_missing_values_cannot_be_patched(document_factory):
    si, q1 = document_factory(container_count=None)
    bl, q2 = document_factory("BL")
    with pytest.raises(DomainError):
        create_preview(
            verify(si, bl, evidence_quality=q1 | q2),
            workspace_id=uuid4(),
            case_id=uuid4(),
            case_version=1,
            policy_version="v1",
            fields=(FieldName.CONTAINERS,),
        )
