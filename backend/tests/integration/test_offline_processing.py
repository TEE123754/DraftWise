import json
from uuid import uuid4
from zipfile import ZipFile

from httpx import ASGITransport, AsyncClient
from inbox_support import add_document, add_email

from app.api.dependencies import Principal, principal
from app.config import Settings
from app.infrastructure.storage import Storage
from app.main import create_app
from app.repositories.jobs import claim
from app.services.offline_processing import queue_offline_processing
from app.workers.handlers import Handlers
from app.workers.runner import execute_job


async def build(database, workspace):
    async with database.connection() as connection:
        await connection.execute("delete from public.cases where workspace_id=%s", (workspace,))
        await connection.execute("delete from public.emails where workspace_id=%s", (workspace,))
        made = {}

        async def with_files(name, *, category="BL_COMPARISON", extract=False, safety=None, files=2):
            email = await add_email(connection, workspace, name, category=category, safety=safety)
            for index in range(files):
                await add_document(connection, workspace, email, f"{name}_{index}.txt", "SI" if index == 0 else "BL", extract=extract)
            made[name] = email

        await with_files("email_1")                                        # unread comparison: queued
        await with_files("email_2", extract=True)                          # already read
        made["email_3"] = await add_email(connection, workspace, "email_3", category="BL_COMPARISON")  # no files
        await with_files("email_4", category="SI_REQUEST")                 # not a comparison
        await with_files("email_5", safety="suspected_phishing")           # held for safety review
        await with_files("email_6", category=None)                         # unclassified
        await with_files("email_7")                                        # unread but already in progress
        await connection.execute(
            """insert into public.processing_jobs(workspace_id,email_id,kind,idempotency_key,request_sha256,payload)
            values(%s,%s,'extract','other',%s,'{}')""",
            (workspace, made["email_7"], "0" * 64),
        )
    return made


async def test_only_unread_comparison_emails_are_queued_and_never_with_ai(database, workspace_factory):
    workspace = (await workspace_factory())["workspace"]
    made = await build(database, workspace)
    async with database.connection() as connection:
        result = await queue_offline_processing(connection, workspace)
        jobs = await (await connection.execute(
            "select email_id,kind,payload from public.processing_jobs where workspace_id=%s and idempotency_key like 'offline:%%'",
            (workspace,),
        )).fetchall()
        flows = await (await connection.execute(
            "select email_id,state from public.email_workflows where workspace_id=%s", (workspace,)
        )).fetchall()
        again = await queue_offline_processing(connection, workspace)
    assert result == {"queued": 1, "skipped_failed": 0}
    assert [job["email_id"] for job in jobs] == [made["email_1"]]
    payload = jobs[0]["payload"]
    assert jobs[0]["kind"] == "extract"
    assert payload["prefer_ai"] is False  # the whole point: reading a mailbox never spends AI quota
    assert payload["workflow"] is True and payload["offline"] is True
    assert len(payload["attachment_ids"]) == 2 and payload["attachment_ids"] == sorted(payload["attachment_ids"])
    assert [(f["email_id"], f["state"]) for f in flows] == [(made["email_1"], "extracting")]
    assert again == {"queued": 0, "skipped_failed": 0}  # already in progress: nothing is queued twice


async def test_a_failed_request_is_not_silently_rerun(database, workspace_factory):
    workspace = (await workspace_factory())["workspace"]
    made = await build(database, workspace)
    async with database.connection() as connection:
        await queue_offline_processing(connection, workspace, made["email_1"])
        await connection.execute(
            "update public.processing_jobs set state='failed',error_code='X' where email_id=%s and idempotency_key like 'offline:%%'",
            (made["email_1"],),
        )
        result = await queue_offline_processing(connection, workspace, made["email_1"])
    assert result == {"queued": 0, "skipped_failed": 1}


def client(database, context, role):
    app = create_app(Settings(environment="test"))
    app.state.database = database
    app.dependency_overrides[principal] = lambda: Principal(context["user"], context["workspace"], role)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_progress_and_process_endpoints(database, workspace_factory):
    context = await workspace_factory()
    await build(database, context["workspace"])
    async with client(database, context, "viewer") as viewer:
        assert (await viewer.post("/api/v1/workspace/process")).status_code == 403
        before = (await viewer.get("/api/v1/workspace/processing")).json()
    # email_1, 2, 5 and 7 are comparison emails with files; only email_2 has been read.
    assert (before["eligible"], before["read"], before["compared"], before["failed"]) == (4, 1, 0, 0)
    assert before["active"] is True  # email_7 has a job running
    async with client(database, context, "operator") as operator:
        assert (await operator.post("/api/v1/workspace/process")).json() == {"queued": 1, "skipped_failed": 0}
    async with client(database, context, "viewer") as viewer:
        after = (await viewer.get("/api/v1/workspace/processing")).json()
    assert after["waiting"] == 1  # the held email is unread, not running, and is never queued
    assert (after["ai_extractions"], after["ai_classifications"]) == (0, 0)


VALUES = (
    "Shipper: Acme Export\nConsignee: Buyer Ltd\nNotify party: Buyer Ltd\nPort of Loading: Singapore\n"
    "Port of Discharge: Port Klang\nContainer Count: 2 x 40HC\nGross Weight (KG): 12000 KG\n"
)


def write_bundle(path):
    def email(number, subject, body, files=()):
        return json.dumps({
            "email_id": f"email_{number:03d}", "from": "ops@example.test", "subject": subject, "body": body,
            "attachments": [f"attachments/email_{number:03d}_{role}.txt" for role in files],
        })

    compare = "Please compare the SI and draft BL."
    with ZipFile(path, "w") as z:
        z.writestr("inbox/email_001.json", email(1, "Docs", compare, ("SI", "BL")))
        z.writestr("inbox/email_002.json", email(2, "Docs", compare, ("SI", "BL")))
        z.writestr("inbox/email_003.json", email(3, "Docs", compare, ("SI", "BL")))
        z.writestr("inbox/email_004.json", email(4, "Draft", "Please assist to send the draft BL for SIN1 for checking asap."))
        z.writestr("inbox/email_005.json", email(5, "Notice", "Our office resumes normal operations on 2 January."))
        # A comparison request whose BL is a truncated PDF: the job runs, but the file cannot be opened.
        z.writestr("inbox/email_006.json", json.dumps({
            "email_id": "email_006", "from": "ops@example.test", "subject": "Docs", "body": compare,
            "attachments": ["attachments/email_006_SI.txt", "attachments/email_006_BL.pdf"],
        }))
        z.writestr("attachments/email_006_SI.txt", "SHIPPING INSTRUCTIONS\n" + VALUES)
        z.writestr("attachments/email_006_BL.pdf", b"%PDF-1.4 this file is truncated")
        for number, bl_values in (
            (1, VALUES),                                                      # identical: checked
            (2, VALUES.replace("Buyer Ltd", "Other GmbH", 1)),                # a real difference
            (3, VALUES.replace("Buyer Ltd", "Other GmbH", 1).replace("Port Klang", "TBA")),  # difference + blank
        ):
            z.writestr(f"attachments/email_{number:03d}_SI.txt", "SHIPPING INSTRUCTIONS\n" + VALUES)
            z.writestr(f"attachments/email_{number:03d}_BL.txt", "BILL OF LADING (DRAFT)\n" + bl_values)


class CountingAI:
    """Any call to it fails the test: reading a mailbox must never spend AI quota."""

    def __init__(self):
        self.calls = 0

    async def classify(self, *args):
        self.calls += 1
        raise AssertionError("the offline pipeline called the AI classifier")

    async def extract(self, *args):
        self.calls += 1
        raise AssertionError("the offline pipeline called the AI extractor")


async def test_seeded_demo_is_read_and_compared_by_the_worker_with_no_ai(database, tmp_path):
    bundle = tmp_path / "mailbox.zip"
    write_bundle(bundle)
    settings = Settings(environment="test", demo_enabled=True, demo_dataset_path=str(bundle))
    app = create_app(settings)
    app.state.database = database
    ai = CountingAI()
    handlers = Handlers(database, Storage(settings), settings, ai)
    origin = {"Origin": "http://localhost:3000"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api:
        session = await api.post("/api/v1/demo/session", headers=origin)
        assert session.status_code == 201, session.text
        assert session.json()["queued_for_reading"] == 4  # the four comparison emails that have files
        headers = {**origin, "X-Demo-Mode": "true", "X-Workspace-Id": session.json()["workspace_id"]}

        before = (await api.get("/api/v1/workspace/processing", headers=headers)).json()
        assert (before["eligible"], before["read"], before["active"]) == (4, 0, True)

        for _ in range(30):  # extract -> case -> verify for each of the three emails
            async with database.connection() as connection:
                job = await claim(connection)
            if not job:
                break
            await execute_job(database, handlers, uuid4(), job)

        counts = (await api.get("/api/v1/emails/counts", headers=headers)).json()
        assert counts["by_state"] == {
            "spam": 0, "held": 0, "processing": 0, "needs_documents": 0, "waiting_for_draft": 1,
            "needs_review": 1, "mismatch_found": 2, "checked": 1, "classified": 1,
        }
        mismatches = (await api.get("/api/v1/emails?state=mismatch_found", headers=headers)).json()["items"]
        assert [(m["display_id"], m["reasons"][0]["fields"]) for m in mismatches] == [
            ("email_002", ["consignee"]), ("email_003", ["consignee"]),
        ]
        checked = (await api.get("/api/v1/emails?state=checked", headers=headers)).json()["items"]
        assert [c["display_id"] for c in checked] == ["email_001"]
        unreadable = (await api.get("/api/v1/emails?state=needs_review", headers=headers)).json()["items"]
        assert [(u["display_id"], u["reasons"][0]["code"], u["action"]["kind"]) for u in unreadable] == [
            ("email_006", "unreadable", "request_readable"),
        ]
        assert checked[0]["documents"] == {"count": 2, "si": True, "bl": True, "other": 0, "unread": 0}

        after = (await api.get("/api/v1/workspace/processing", headers=headers)).json()
        assert (after["eligible"], after["read"], after["compared"], after["failed"], after["active"]) == (4, 3, 3, 0, False)
        assert (after["unreadable"], after["waiting"]) == (1, 0)  # nothing more will happen for the truncated file
        assert (after["ai_extractions"], after["ai_classifications"]) == (0, 0)
    assert ai.calls == 0
    async with database.connection() as connection:
        failed = await (await connection.execute("select count(*) as n from public.processing_jobs where state='failed'")).fetchone()
    assert failed["n"] == 0
