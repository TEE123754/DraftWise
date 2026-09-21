import pytest

from app.api.health import worker_verdict
from app.infrastructure.hosting import hosting_kind

RAILWAY_VARIABLES = ("RAILWAY_SERVICE_ID", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in (*RAILWAY_VARIABLES, "WORKER_KIND"):
        monkeypatch.delenv(name, raising=False)


def test_a_developer_machine_is_local():
    assert hosting_kind() == "local"


@pytest.mark.parametrize("variable", RAILWAY_VARIABLES)
def test_railway_marks_the_process_as_hosted(monkeypatch, variable):
    monkeypatch.setenv(variable, "anything")
    assert hosting_kind() == "hosted"


def test_worker_kind_overrides_detection_but_ignores_nonsense(monkeypatch):
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "x")
    monkeypatch.setenv("WORKER_KIND", "local")
    assert hosting_kind() == "local"
    monkeypatch.setenv("WORKER_KIND", "cloud")  # not a kind: fall back to detection
    assert hosting_kind() == "hosted"


def test_no_worker_at_all_is_never_ready():
    assert worker_verdict("local", {}) == "The processing worker is not active"
    assert worker_verdict("hosted", {}) == "The processing worker is not active"


def test_a_local_api_accepts_any_worker():
    for counts in ({"local": 3}, {"hosted": 3}, {"unknown": 1}):
        assert worker_verdict("local", counts) is None


def test_a_hosted_api_is_not_ready_on_workers_from_other_machines():
    # The original outage: the deployed service had no worker, but a laptop sharing the database did.
    problem = worker_verdict("hosted", {"local": 3})
    assert problem and "deployed service" in problem
    assert worker_verdict("hosted", {"unknown": 3})  # a worker of unknown origin does not count either
    assert worker_verdict("hosted", {"hosted": 3, "local": 3}) is None
