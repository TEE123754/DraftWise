from uuid import uuid4

import pytest

from app.domain.errors import DomainError
from app.domain.models import FieldName
from app.services.revision_analysis import analyze_revision
from app.services.verification import verify


def test_fixed_issue_and_new_regression(document_factory):
    si, q1 = document_factory()
    old, q2 = document_factory("BL", container_count="4")
    new, q3 = document_factory("BL", gross_weight_kg="23 MT")
    previous = verify(si, old, evidence_quality=q1 | q2)
    current = verify(si, new, evidence_quality=q1 | q3)
    summary = analyze_revision(
        previous,
        current,
        case_id=uuid4(),
        baseline_version=1,
        policy_version="v1",
        previous_policy_version="v1",
    )
    changes = {item.field: item.change for item in summary.fields}
    assert changes[FieldName.CONTAINERS] == "fixed"
    assert changes[FieldName.WEIGHT] == "regressed"


def test_changed_si_requires_rebaseline(document_factory):
    si, q1 = document_factory()
    replacement, q2 = document_factory()
    bl, q3 = document_factory("BL")
    with pytest.raises(DomainError, match="Changed SI"):
        analyze_revision(
            verify(si, bl, evidence_quality=q1 | q3),
            verify(replacement, bl, evidence_quality=q2 | q3),
            case_id=uuid4(),
            baseline_version=1,
            policy_version="v1",
            previous_policy_version="v1",
        )


def test_missing_returned_field_is_unresolved(document_factory):
    si, q1 = document_factory()
    old, q2 = document_factory("BL", container_count="4")
    new, q3 = document_factory("BL", container_count=None)
    summary = analyze_revision(
        verify(si, old, evidence_quality=q1 | q2),
        verify(si, new, evidence_quality=q1 | q3),
        case_id=uuid4(),
        baseline_version=1,
        policy_version="v1",
        previous_policy_version="v1",
    )
    assert (
        next(row for row in summary.fields if row.field == FieldName.CONTAINERS).change
        == "unresolved"
    )
