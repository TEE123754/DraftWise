from app.services.action_planner import next_action
from app.services.readiness import case_readiness
from app.services.verification import verify


def test_missing_source_precedes_old_report(document_factory):
    si, q1 = document_factory()
    bl, q2 = document_factory("BL")
    report = verify(si, bl, evidence_quality=q1 | q2)
    assert case_readiness(report, has_si=True, has_bl=False) == "needs_source"
    assert next_action(report, needs_source=True).kind == "add_sources"
    assert next_action(report, failed=True).kind == "retry"


def test_shared_request_never_overrides_verified_result(document_factory):
    si, q1 = document_factory()
    bl, q2 = document_factory("BL")
    report = verify(si, bl, evidence_quality=q1 | q2)
    assert case_readiness(report, has_si=True, has_bl=True, shared=True) == "checked"
