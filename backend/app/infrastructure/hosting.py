import os

# Railway sets these on every service it runs; none of them exist on a developer machine.
_HOSTED_MARKERS = ("RAILWAY_SERVICE_ID", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID")


def hosting_kind() -> str:
    """'hosted' when running as the deployed service, otherwise 'local'.

    Anything that shares the database can run a worker, so a worker's heartbeat is not proof that the
    deployed service can process jobs. WORKER_KIND=hosted|local overrides the detection.
    """
    explicit = os.environ.get("WORKER_KIND", "").strip().lower()
    if explicit in {"hosted", "local"}:
        return explicit
    return "hosted" if any(os.environ.get(name) for name in _HOSTED_MARKERS) else "local"
