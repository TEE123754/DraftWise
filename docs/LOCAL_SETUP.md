# Local setup

Requirements: Python 3.12, uv, Node.js 22+, pnpm 10.15, and Tesseract for scanned PDFs. Pure tests and the local labelled-document CLI need no API keys.

## Backend

Copy `backend/.env.example` to `backend/.env`. Configure `DATABASE_URL` for an isolated Supabase project, `SUPABASE_URL`, backend-only `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_JWT_ISSUER` (project URL plus `/auth/v1`). The database connection needs the schema's service privileges. Use TLS. `STORAGE_BUCKET=shipping-originals` matches the supplied SQL.

Set `GEMINI_API_KEY` to enable AI fallback. Verify `GEMINI_MODEL` availability, structured-output compatibility and account quota before relying on it. No live provider calls have been tested yet.

Apply [schema.sql](../database/schema.sql) once to a fresh Supabase project, followed by every numbered file in [database/migrations](../database/migrations/). Do not separately reapply the amendment extension, which is already included in the fresh schema. A new authenticated user automatically receives a private admin workspace.

Authentication uses Supabase asymmetric signing keys, ES256 or RS256, through the project JWKS. Legacy HS256 verification is unsupported. Configure permitted email sign-in redirects, including `http://localhost:3000/dashboard` for local use.

From `backend`:

```bash
uv sync --frozen
uv run pytest -q
uv run shipping-api
# Separate terminal:
uv run python -m app.workers.runner
```

Public `/health` checks liveness. `/ready` checks PostgreSQL and worker heartbeat. Business endpoints require a bearer token and `X-Workspace-Id`. OpenAPI is at `/docs`.

Local verification without credentials:

```bash
uv run shipping-verify --si /path/instructions.txt --bl /path/draft.txt --output /path/report.json
```

The CLI uses conservative labelled extraction and includes original source text in its output. Keep report artifacts private. Complex layouts may require AI or review.

## Frontend

### Morpheus alternative

Set `AI_PROVIDER=morpheus`, `MORPHEUS_API_KEY`, `MORPHEUS_BASE_URL=https://api.mor.org/api/v1` and `MORPHEUS_MODEL=deepseek-v4-pro` in `backend/.env`. Gemini remains available with `AI_PROVIDER=gemini`. The Morpheus adapter validates JSON and source grounding locally; provider-side schema enforcement is not assumed. It uses the [Morpheus chat API](https://api.mor.org/docs). Authentication, model discovery and a minimal structured inference are verified; document quality and free-tier eligibility still require acceptance. `FREE_ONLY` is not yet a billing enforcement mechanism.

The Supabase backend variable `SUPABASE_SERVICE_ROLE_KEY` accepts either a legacy service-role JWT or a modern secret key. Modern keys use only the `apikey` header, following [Supabase key guidance](https://supabase.com/docs/guides/getting-started/api-keys). The frontend anonymous-key variable also accepts the modern publishable key. Use the project root URL without `/rest/v1/`. A separate PostgreSQL `DATABASE_URL` remains required.

### Local database integration tests

CI starts PostgreSQL and runs the real SQL schema, tenant isolation, concurrency, lease recovery and amendment workflow tests. For a machine without PostgreSQL, from `tools/postgres` run `npm ci` then `node run-tests.mjs`. The helper starts an isolated loopback database, runs backend tests and stops it; local cluster files remain in ignored `tools/postgres/data`. Tests use minimal Auth/Storage schema scaffolding and synthetic documents, so they do not replace live Supabase acceptance.

Copy `frontend/.env.example` to `frontend/.env.local`. Configure the Supabase project URL and public/anonymous key, plus `NEXT_PUBLIC_API_URL=http://localhost:8000`. Never expose the service-role key through frontend variables.

From `frontend`:

```bash
pnpm install --frozen-lockfile
pnpm dev
pnpm build
pnpm test:e2e
```

Browser tests start a local frontend and intercept API/Supabase calls with synthetic fixtures. They require no real keys and do not establish live integration correctness. Windows uses installed Edge. On Linux, first run `pnpm exec playwright install --with-deps chromium`.

Sign in, select a workspace, add an email and documents, then confirm SI/BL sources in the case. Returned drafts require reviewer source confirmation after extraction. Correction requests are copied; the product does not send email.

## Local no-login demo

Apply `database/migrations/004_demo_sessions.sql` after earlier migrations before starting API/worker. In `backend/.env`, set `DEMO_ENABLED=true` and `DEMO_DATASET_PATH=../sdoc-hackathon-bundle.zip`. Start services from their documented working directories. Open `http://localhost:3000/demo` and select **Start the demo**. No account is needed.

Open `email_001` in Inbox, review its request, enter a shipment reference and choose **Open amendment case**, then **Continue to case**. Its sample documents are extracted automatically; select the SI and BL to check them. Other documents can be processed with **Read documents**. Uncertain classification remains unresolved. Gmail, assistant, drift and the expanded dashboard are not implemented yet.

Sessions expire after eight hours. **End demo** revokes access but retains the isolated sample records. This initial local version caps provisioning at 20 retained sessions; reset/cleanup is pending. Production demo access is explicitly disabled. No paid inference is invoked by demo jobs.

Optional live checks, with all services running: from root run `backend/.venv/Scripts/python.exe scripts/smoke_demo.py`; from frontend run `node tests/live-demo.cjs` (installed Edge). Each creates one isolated sample session and ends it. The normal mocked browser suite runs on port 3100 with `.next-test`, preserving the interactive frontend on 3000.

## Containers and repository validation commands

From the repository root:

```bash
python scripts/validate_repository.py
docker compose -f docker/compose.dev.yml up --build
```

Compose runs API and worker against the configured Supabase project; it does not emulate Supabase Auth or Storage. Docker execution is not yet validated on this host.

Store secrets only in the ignored environment files. See [implementation status](IMPLEMENTATION_STATUS.md) for remaining acceptance work.
