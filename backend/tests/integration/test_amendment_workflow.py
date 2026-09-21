import hashlib

from httpx import ASGITransport, AsyncClient

from app.api.dependencies import Principal, principal
from app.config import Settings
from app.main import create_app
from app.repositories.jobs import claim
from app.workers.handlers import Handlers
from app.workers.runner import execute_job


class TestStorage:
    __test__ = False

    def __init__(self):
        self.files = {}

    async def reserve(self, key):
        return key

    async def download(self, key):
        return self.files[key]


def document(role, *, count=3, weight="22 MT"):
    return (
        f"{'SHIPPING INSTRUCTION' if role == 'SI' else 'BILL OF LADING'}\n"
        "Shipper: Example Export Ltd\nConsignee: Example Import Ltd\nNotify Party: Example Import Ltd\n"
        "Port of Loading: Port Klang, Malaysia\nPort of Discharge: Singapore\n"
        f"Container Count: {count}\nGross Weight: {weight}\n"
    ).encode()


async def test_full_api_worker_amendment_flow(database, workspace_factory):
    identity = await workspace_factory()
    settings = Settings(environment="test", database_url=None)
    app = create_app(settings)
    app.state.database = database
    storage = TestStorage()
    app.state.storage = storage
    context = Principal(identity["user"], identity["workspace"], "reviewer")
    app.dependency_overrides[principal] = lambda: context
    handlers = Handlers(database, storage, settings)
    request_number = 0

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        async def post(path, body):
            nonlocal request_number
            request_number += 1
            result = await client.post(
                f"/api/v1{path}",
                json=body,
                headers={"Idempotency-Key": f"request-{request_number}"},
            )
            assert result.is_success, result.text
            return result.json()

        async def process_next():
            async with database.connection() as connection:
                job = await claim(connection)
            assert job is not None
            await execute_job(database, handlers, identity["user"], job)
            result = await client.get(f"/api/v1/jobs/{job['id']}")
            assert result.json()["state"] == "succeeded", result.text
            return result.json()["result"]

        async def upload(role, **values):
            data = document(role, **values)
            reserved = await post(
                "/uploads",
                {
                    "email_id": str(identity["email"]),
                    "filename": f"{role}.txt",
                    "mime_type": "text/plain",
                    "byte_size": len(data),
                },
            )
            storage.files[reserved["upload_url"]] = data
            await post(
                f"/uploads/{reserved['attachment_id']}/complete",
                {"sha256": hashlib.sha256(data).hexdigest()},
            )
            await post("/extract", {"attachment_ids": [reserved["attachment_id"]]})
            result = await process_next()
            assert result["items"][0]["state"] == "succeeded", result
            return result["items"][0]["extraction_id"]

        await post("/classify", {"email_id": str(identity["email"])})
        assert (await process_next())["category"] == "BL_COMPARISON"
        si_id = await upload("SI")
        old_bl_id = await upload("BL", count=4)
        case_path = f"/cases/{identity['case']}"
        await post(
            case_path + "/sources",
            {
                "expected_version": 1,
                "si_extraction_id": si_id,
                "bl_extraction_id": old_bl_id,
                "reason": "Confirmed source pair",
            },
        )
        await process_next()
        detail = (await client.get("/api/v1" + case_path)).json()
        assert detail["case"]["readiness"] == "changes_required"
        assert detail["latest_report"]["status"] == "MISMATCH"
        issue = next(issue for issue in detail["issues"] if issue["field"] == "container_count")
        preview = await post(
            case_path + "/previews",
            {
                "expected_version": detail["case"]["version"],
                "report_id": detail["latest_report"]["id"],
                "issue_ids": [issue["id"]],
            },
        )
        assert preview["remaining_blocker_count"] == 0
        saved = await post(
            case_path + "/requests",
            {
                "expected_version": detail["case"]["version"],
                "preview_id": preview["id"],
                "message": preview["suggested_message"],
            },
        )
        unchanged = (await client.get("/api/v1" + case_path)).json()
        assert unchanged["case"]["readiness"] == "changes_required"
        shared = await post(
            case_path + f"/requests/{saved['id']}/shared",
            {
                "expected_version": detail["case"]["version"],
                "note": "Shared outside the application",
            },
        )
        assert shared["readiness"] == "awaiting_revision"
        new_bl_id = await upload("BL", count=3, weight="23 MT")
        await post(
            case_path + "/sources",
            {
                "expected_version": shared["case_version"],
                "si_extraction_id": si_id,
                "bl_extraction_id": new_bl_id,
                "reason": "Confirmed returned draft belongs to this shipment",
            },
        )
        await process_next()
        returned = (await client.get("/api/v1" + case_path)).json()
        changes = {
            field["field"]: field["change"] for field in returned["rounds"][0]["summary"]["fields"]
        }
        assert changes["container_count"] == "fixed"
        assert changes["gross_weight_kg"] == "regressed"
        assert returned["case"]["readiness"] == "changes_required"
        stale = await client.post(
            "/api/v1" + case_path + "/requests",
            json={
                "expected_version": detail["case"]["version"],
                "preview_id": preview["id"],
                "message": preview["suggested_message"],
            },
        )
        assert stale.status_code == 409
