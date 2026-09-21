import json
from uuid import uuid4
from zipfile import ZipFile

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.domain.errors import DomainError
from app.infrastructure.storage import Storage
from app.main import create_app
from app.repositories.jobs import claim
from app.services.classification import classify_explicit
from app.services.demo_retention import purge_expired_samples
from app.services.extraction import extract_labelled
from app.workers.handlers import Handlers
from app.workers.runner import execute_job


class TestAI:
    __test__ = False

    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    async def classify(self, subject, body, attachments):
        self.calls += 1
        if self.fail:
            raise DomainError("PROVIDER_UNAVAILABLE", "Offline")
        return classify_explicit(subject, body), {"provider": "test_ai", "model": "fixture"}

    async def extract(self, document):
        self.calls += 1
        if self.fail:
            raise DomainError("PROVIDER_UNAVAILABLE", "Offline")
        return extract_labelled(document), {"provider": "test_ai", "model": "fixture"}


@pytest.mark.parametrize("ai_mode", ["success", "failure", "quota", "rules"])
async def test_fetch_review_compare_isolated(database, tmp_path, ai_mode):
    bundle = tmp_path / "workflow.zip"
    values = "Shipper: Acme Export\nConsignee: Buyer Ltd\nNotify party: Buyer Ltd\nPort of Loading: Singapore\nPort of Discharge: Port Klang\nContainer Count: 2 x 40HC\nGross Weight (KG): 12000 KG\n"
    with ZipFile(bundle, "w") as z:
        z.writestr(
            "inbox/email_001.json",
            json.dumps(
                {
                    "email_id": "email_001",
                    "from": "ops@example.test",
                    "subject": "Review shipment",
                    "body": "Please compare the SI and draft BL.",
                    "attachments": ["attachments/email_001_SI.txt", "attachments/email_001_BL.txt"],
                }
            ),
        )
        z.writestr("attachments/email_001_SI.txt", "SHIPPING INSTRUCTIONS\n" + values)
        z.writestr("attachments/email_001_BL.txt", "BILL OF LADING (DRAFT)\n" + values)
    settings = Settings(
        environment="test",
        demo_enabled=True,
        demo_dataset_path=str(bundle),
        demo_ai_call_limit=0 if ai_mode in {"quota", "rules"} else 3,
        # This test is about the explicit review workflow; seed-time reading has its own test.
        demo_offline_processing=False,
    )
    app = create_app(settings)
    app.state.database = database
    ai = TestAI(fail=ai_mode == "failure")
    handlers = Handlers(database, Storage(settings), settings, ai)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        origin = {"Origin": "http://localhost:3000"}
        session = await client.post("/api/v1/demo/session", headers=origin)
        assert session.status_code == 201, session.text
        workspace = session.json()["workspace_id"]
        headers = {
            **origin,
            "X-Demo-Mode": "true",
            "X-Workspace-Id": workspace,
            "Idempotency-Key": "sample-fetch",
        }
        fetched = await client.post(
            "/api/v1/demo/gmail/fetch",
            headers=headers,
            json={"email_id": "email_001", "prefer_ai": ai_mode != "rules"},
        )
        assert fetched.status_code == 200, fetched.text
        email_id = fetched.json()["email_id"]
        assert fetched.json()["imported"] is False
        repeat = await client.post(
            "/api/v1/demo/gmail/fetch",
            headers=headers,
            json={"email_id": "email_001", "prefer_ai": ai_mode != "rules"},
        )
        assert repeat.json()["job_id"] == fetched.json()["job_id"]
        for _ in range(8):
            async with database.connection() as connection:
                job = await claim(connection)
            if not job:
                break
            await execute_job(database, handlers, uuid4(), job)
        detail = await client.get(f"/api/v1/emails/{email_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        result = detail.json()
        assert result["workflow"]["state"] == "checked", result
        assert len(result["attachments"]) == 2
        assert len(result["extractions"]) == 2
        method = (
            "ai" if ai_mode == "success" else "rules" if ai_mode == "rules" else "rule_fallback"
        )
        assert result["classification"]["run_metadata"]["method"] == method
        assert all(
            x["run_metadata"]["method"] == ("labelled_parser" if ai_mode == "rules" else method)
            for x in result["extractions"]
        )
        case = await client.get(f"/api/v1/cases/{result['workflow']['case_id']}", headers=headers)
        assert case.json()["case"]["readiness"] == "checked", case.text
        assert all(
            x["decision"] == "match" and x["evidence_ids"]
            for x in case.json()["latest_report"]["comparisons"]
        )
        assert ai.calls == (0 if ai_mode in {"quota", "rules"} else 3)
        summary = await client.get("/api/v1/dashboard", headers=headers)
        assert summary.json()["document_checks"] == 1
        assert summary.json()["cases_checked"] == 1
        assert (await client.get("/api/v1/emails?verified=true", headers=headers)).json()["items"][
            0
        ]["id"] == email_id
        prefs = await client.post(
            "/api/v1/dashboard/preferences",
            headers=headers,
            json={"sections": ["quality", "metrics"]},
        )
        assert prefs.status_code == 200, prefs.text
        assert (await client.get("/api/v1/dashboard/preferences", headers=headers)).json()[
            "sections"
        ] == ["quality", "metrics"]
        assert (await client.get("/api/v1/quality/monitor", headers=headers)).json()[
            "state"
        ] == "baseline_required"
        held = await client.post(
            "/api/v1/emails",
            headers=headers,
            json={
                "external_id": "security-test",
                "from": "sender@example.test",
                "subject": "Account",
                "body": "Verify your account immediately at https://example.test/login",
            },
        )
        assert held.status_code == 201, held.text
        held_id = held.json()["id"]
        stopped = await client.post(
            f"/api/v1/emails/{held_id}/process", headers=headers, json={"prefer_ai": True}
        )
        assert stopped.json()["state"] == "held"
        assert ai.calls == (0 if ai_mode in {"quota", "rules"} else 3)
        assert (await client.get("/api/v1/alerts", headers=headers)).json()["items"]
        assert (
            await client.post(
                f"/api/v1/emails/{held_id}/release",
                headers=headers,
                json={"reason": "Reviewed synthetic test message"},
            )
        ).status_code == 200
        assert not (await client.get(f"/api/v1/emails/{held_id}", headers=headers)).json()[
            "safety"
        ]["held_for_review"]
        if ai_mode == "rules":
            case_id = result["workflow"]["case_id"]
            current_case = (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()
            original = next(x for x in result["extractions"] if x["document_type"] == "SI")
            review_body = {"expected_version": current_case["case"]["version"], "field": "shipper",
                          "value": original["output"]["fields"]["shipper"], "reason": "Verified against the original source"}
            review_path = f"/api/v1/cases/{case_id}/extractions/{original['id']}/review"
            bad = {**review_body, "value": {**review_body["value"], "raw_value": "Invented shipper"}}
            rejected = await client.post(review_path, headers={**headers, "Idempotency-Key": "bad-review"}, json=bad)
            assert rejected.status_code == 422, rejected.text
            assert rejected.json()["error"]["code"] == "PROVIDER_OUTPUT_INVALID"
            reviewed = await client.post(review_path, headers={**headers, "Idempotency-Key": "human-review"}, json=review_body)
            assert reviewed.status_code == 202, reviewed.text
            assert (await client.post(review_path, headers={**headers, "Idempotency-Key": "human-review"}, json=review_body)).json() == reviewed.json()
            assert (await client.post(review_path, headers={**headers, "Idempotency-Key": "stale-review"}, json=review_body)).status_code == 409
            async with database.connection() as connection:
                job = await claim(connection)
            assert job
            await execute_job(database, handlers, uuid4(), job)
            checked = (await client.get(f"/api/v1/cases/{case_id}", headers=headers)).json()
            assert checked["case"]["readiness"] == "checked"
            assert checked["active_sources"]["si_extraction_id"] != original["id"]
            assert (await client.get(f"/api/v1/extractions/{original['id']}", headers=headers)).json()["output"] == original["output"]
            async with database.connection() as connection:
                await connection.execute(
                    """insert into public.audit_logs(workspace_id,actor_type,action,entity_type,request_id)
                    values(%s,'system','retention_test','workspace',%s)""", (workspace, uuid4()),
                )
                assert await purge_expired_samples(connection) == 0
                await connection.execute(
                    "update public.demo_sessions set expires_at=now()-interval '3 minutes' where workspace_id=%s",
                    (workspace,),
                )
                assert await purge_expired_samples(connection) == 1
                assert (await (await connection.execute(
                    "select count(*) as n from public.emails where workspace_id=%s", (workspace,)
                )).fetchone())["n"] == 0
                assert await purge_expired_samples(connection) == 0
                assert (await (await connection.execute(
                    "select count(*) as n from public.audit_logs where workspace_id=%s", (workspace,)
                )).fetchone())["n"] > 0
            assert (await client.get("/api/v1/emails", headers=headers)).status_code == 401
