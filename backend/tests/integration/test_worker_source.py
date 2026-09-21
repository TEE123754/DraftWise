from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from app.workers.runner import heartbeat


def client(database):
    app = create_app(Settings(environment="test"))
    app.state.database = database
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def beat(database, monkeypatch, *, hosted: bool, slots: int):
    if hosted:
        monkeypatch.setenv("RAILWAY_SERVICE_ID", "service")
    else:
        monkeypatch.delenv("RAILWAY_SERVICE_ID", raising=False)
    for _ in range(slots):
        await heartbeat(database, uuid4())


async def test_a_worker_records_where_it_runs(database, monkeypatch):
    monkeypatch.delenv("WORKER_KIND", raising=False)
    await beat(database, monkeypatch, hosted=True, slots=2)
    await beat(database, monkeypatch, hosted=False, slots=1)
    async with database.connection() as connection:
        rows = await (
            await connection.execute("select kind,count(*) as n from public.worker_heartbeats group by kind")
        ).fetchall()
    assert {row["kind"]: row["n"] for row in rows} == {"hosted": 2, "local": 1}


async def test_a_worker_from_before_the_migration_counts_as_unknown(database):
    async with database.connection() as connection:
        await connection.execute(
            "insert into public.worker_heartbeats(id,last_seen) values(%s,now())", (uuid4(),)
        )
        kind = (await (await connection.execute("select kind from public.worker_heartbeats")).fetchone())["kind"]
    assert kind == "unknown"


async def test_ready_says_where_the_workers_are(database, monkeypatch):
    monkeypatch.delenv("WORKER_KIND", raising=False)
    monkeypatch.delenv("RAILWAY_SERVICE_ID", raising=False)  # this API runs locally
    await beat(database, monkeypatch, hosted=False, slots=3)
    monkeypatch.delenv("RAILWAY_SERVICE_ID", raising=False)
    async with client(database) as api:
        response = await api.get("/ready")
    assert response.status_code == 200
    assert response.json()["workers"] == {"hosted": 0, "local": 3, "unknown": 0}


async def test_a_hosted_api_is_not_ready_when_only_other_machines_have_workers(database, monkeypatch):
    monkeypatch.delenv("WORKER_KIND", raising=False)
    await beat(database, monkeypatch, hosted=False, slots=3)  # a laptop sharing the database
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "service")  # the API is the deployed service
    async with client(database) as api:
        before = await api.get("/ready")
        assert before.status_code == 503
        assert before.json()["error"]["code"] == "WORKER_UNAVAILABLE"
        assert "deployed service" in before.json()["error"]["message"]
        await beat(database, monkeypatch, hosted=True, slots=3)  # the deployed worker starts
        after = await api.get("/ready")
    assert after.status_code == 200
    assert after.json()["workers"] == {"hosted": 3, "local": 3, "unknown": 0}
