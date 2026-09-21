# Backend

Stack: Python FastAPI, asynchronous durable workers, Supabase PostgreSQL/Storage/Auth, Gemini structured outputs, deterministic field comparison.

Read [backend architecture](../docs/BACKEND_ARCHITECTURE.md), [core API contracts](../docs/API_CONTRACTS.md), [feature contracts](../docs/FEATURE_CONTRACTS.md), and [processing pipeline](../docs/PROCESSING_PIPELINE.md).

Generate each implementation module at its real path. Required route modules include `app/api/verify.py`, `app/api/cases.py`, `app/api/amendments.py`, and `app/api/rules.py`. Keep route validation/authorization separate from services and repositories. Do not combine all routes, provider calls and database access in a single file.

Application modules are implemented in separate files. See [implementation status](../docs/IMPLEMENTATION_STATUS.md) for completed checks and pending integration acceptance, and [local setup](../docs/LOCAL_SETUP.md) for credentials and database setup.

```bash
uv sync --frozen
uv run pytest -q
uv run uvicorn app.main:app --reload --loop asyncio:SelectorEventLoop
# Separate terminal after database setup:
uv run python -m app.workers.runner
```

Backend acceptance includes durable retry recovery, supported evidence for every accepted field, immutable report revisions, source/policy version checks, amendment regressions, stale preview rejection and cross-workspace denial. Credentials are unnecessary for pure unit tests; real integration requires the environment configuration in `.env.example`.
