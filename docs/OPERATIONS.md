# Operations and deployment

[Repository overview](../README.md) · [Implementation plan](../IMPLEMENTATION_PLAN.md)


## 1 Environment and secrets

```dotenv
# Frontend public configuration; no privileged secrets in NEXT_PUBLIC_*.
NEXT_PUBLIC_API_BASE_URL=https://backend.example/api/v1
NEXT_PUBLIC_SUPABASE_URL=https://project.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=configure-public-project-key

# Backend only.
ENVIRONMENT=production
SUPABASE_URL=https://project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=configure-server-secret
DATABASE_URL=configure-server-only-supabase-connection
SUPABASE_JWT_ISSUER=https://project.supabase.co/auth/v1
SUPABASE_JWT_AUDIENCE=authenticated
GEMINI_API_KEY=configure-server-secret
GEMINI_MODEL=gemini-3.1-flash-lite
AI_PROVIDER=gemini
FREE_ONLY=true
XAI_API_KEY=
XAI_MODEL=
ALLOWED_ORIGINS=https://frontend.example
WORKER_ENABLED=true
WORKER_CONCURRENCY=1
PROVIDER_CONCURRENCY=2
MAX_UPLOAD_BYTES=20971520
MAX_PDF_PAGES=20
OCR_LANGUAGES=eng+chi_sim
POLICY_VERSION=v1
PROMPT_VERSION=v1
ORIGINAL_RETENTION_DAYS=30
DERIVED_RETENTION_DAYS=7
LOG_LEVEL=INFO

# Local runner only; not a URL supplied by arbitrary API clients.
EVALUATOR_BASE_URL=http://localhost:8080
DATASET_ROOT=configure-extracted-participant-directory
```

These values are examples, not working credentials or deployment claims. Configure account-specific provider rate limits through protected settings after checking AI Studio. Validate required variables at startup, mask them in errors and rotate leaked credentials. Never accept provider keys from email text, document contents or query parameters. A Grok adapter is optional behind the same schema interface, but is disabled under the zero-cost baseline unless the account has verified applicable credits; its published API pricing is paid usage, not a guaranteed free alternative. [xAI model pricing](https://docs.x.ai/developers/models).

## 2 Deployment configuration

**Vercel:** project root `frontend/`; use native Next.js build output and committed lockfile; no Vite SPA rewrite. Configure public API URL and Supabase publishable settings per environment. Protect preview deployments containing private data, register explicit callback URLs, and avoid wildcard CORS for all preview origins. Keep extraction/OCR and long jobs off Vercel request functions.

**Railway:** build the monorepo Dockerfile with Python runtime, pinned Python dependencies and only needed OCR language packs. Run as a non-root user with a writable temporary directory. Start with a shell-expanded command `uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1`. The container working directory must be `backend/`. One worker loop is created in lifespan; do not use multiple Uvicorn workers with an unbounded loop per process. Health path `/api/v1/health`; readiness path `/api/v1/ready`; graceful SIGTERM and bounded restart policy. Database migrations run once as a deployment operation before traffic, never concurrently in each worker.

**Supabase:** apply SQL migrations with a migration-owner connection; create private buckets; configure allowed auth redirect origins; create first workspace/admin through an authenticated bootstrap script; disable open public signup if not needed. Use TLS and an appropriate regional endpoint close to Railway. Back up data independently within the prototype's allowed resources; do not assume free-tier managed backup/recovery guarantees. Test restore on a local project before claiming production readiness.

**Local profile:** same backend image, worker and frontend can run locally while using the configured Supabase project and Gemini account. This is a development/resource fallback, not a substitute for the required deployed cloud application. Cloud ingress and durable storage remain operational only while the selected providers' free allowances permit them.

## 3 Free-tier feasibility and operational controls

| Component | Verified constraint | Engineering response |
|---|---|---|
| Railway Free | $1/month resource credit; limited RAM and one replica | One lean service; bounded jobs; no resident large OCR model; measure memory; pause unavailable work and surface queue status |
| Supabase Free | 500 MB DB, 1 GB file storage, 5 GB egress plus 5 GB cached egress; inactive projects may pause after a week | Small metadata, private originals, expiring derivatives, quota-aware uploads and readiness checks |
| Vercel Hobby | Restricted to personal, non-commercial use; usage caps apply | Use only where this prototype qualifies; reassess commercial deployment eligibility rather than asserting free commercial production |
| Gemini | Model/account-specific free access and quotas; free-tier content may be used to improve products | Synthetic supplied data only by default; explicit data policy before real confidential shipping documents; bounded calls and cache |
| Grok | API usage has published prices; no universal free guarantee established | Optional adapter, off by default in `FREE_ONLY` mode |

Platform facts: [Railway plans](https://docs.railway.com/pricing/plans), [Supabase pricing](https://supabase.com/pricing), [Vercel Hobby](https://vercel.com/docs/plans/hobby), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [xAI pricing](https://docs.x.ai/developers/models). Recheck account eligibility and limits when deploying; no numeric RPM allowance is assumed here.

With 520 emails and 250 documents, calling an LLM once for every email and every attachment would require up to 770 initial calls before retries or semantic checks. This is a planning upper bound for that strategy, not a required usage estimate. High-precision rules and grounded deterministic parsing reduce calls, while AI remains meaningful for intent ambiguity, varied layouts and multimodal recovery. Benchmark mode reports actual call/token counts. Submit only relevant blocks/crops; do not resend entire inboxes. Avoid external search, embeddings and hosted tracing services in the baseline.

## 4 Caching and scaling

Extraction cache key = SHA-256 of workspace ID, source bytes hash, parser/preprocessing versions, model ID, prompt hash, schema version and normalization policy version. A human correction uses a distinct revision key including correction content; it never replaces the AI cache entry. Classification keys include the current body/subject/manifest hash and classifier version. Verification keys include exact SI/BL extraction IDs, pair selection and comparison policy version. Never reuse a report solely because filenames match.

Exact duplicate uploads may reuse parsing artifacts within the same workspace after authorization, but retain distinct email/source associations. Cache misses do not trigger simultaneous duplicate calls: use a unique job key and lock. TTL controls operational cache retention; immutable report evidence remains until its retention policy permits deletion.

Start with one parser and two provider network requests, then measure RSS, queue age and p95 latency before increasing concurrency. A split worker deployment can scale independently through PostgreSQL `SKIP LOCKED`; prioritize interactive review re-verification over bulk benchmarks without starving old jobs. Keep provider limits global across workers. Add connection pooling, read indexes and backpressure before extra infrastructure. Large archived artifacts belong in Storage, not PostgreSQL JSONB. Benchmark and user traffic have separate concurrency budgets.

## 5 Security and file validation

Enforce signature/MIME/extension agreement; reject executable or unsupported formats; check OOXML ZIP entry counts, expansion ratio and total uncompressed size before parsing. Reject traversal, absolute paths, alternate separators, symlinks and archive names outside a resolved import root. Browser uploads do not accept archives in the baseline. Set memory, CPU, wall-time, page and cell limits; run parsers without outbound network or shell command interpolation. Keep parser/OCR dependencies patched and locked.

Treat PDF links/actions, Office relationships, spreadsheet formulas, HTML email and model output as untrusted. Do not fetch external Office relationships or render raw HTML. Neutralize CSV formula-leading values on export. For email links, render safe text or explicit user navigation; processing never follows them. Document prompt injection cannot issue API calls: model clients have no tools, secrets or database capabilities. Validate role/schema/grounding before any output is persisted as an accepted extraction.

CORS lists explicit application origins. Use role-specific write permissions, CSRF protection where cookie-based mutation endpoints are introduced, and strict file/source authorization. Use signed URLs rather than public buckets; redact logs; cap request bodies at ingress and application layers. Benchmark endpoints accept configured datasets only to avoid SSRF. Keep the organizer harness on a local/private network; its endpoint/path validation is a reference contract, not a production security template.

## 6 Validation and completion criteria

The implementation is complete when a user can import the provided inbox, classify every email, process all supported attachment formats, inspect seven-field evidence, resolve incomplete cases, produce a new immutable report, and export a harness-valid submission with visible failures rather than silent defaults. Acceptance includes these concrete checks:

| Check | Expected result |
|---|---|
| SI says 3 containers, BL says 4, remaining six equal | Exactly `container_count` mismatched |
| 22,000 KG versus 22 MT | Weight matches after exact conversion |
| Same missing mandatory field on both sides | `NEEDS_REVIEW`, never a match |
| `_BL.txt` actually contains an invoice | Wrong-document review |
| SI request with complete fields in email body | `SI_REQUEST`; no automatic BL verification |
| Misleading subject with current invoice query | Current intent drives classification |
| Scanned but readable SI/BL | OCR/vision evidence path; compare if supported, otherwise review |
| Malformed PDF or absent attachment | Visible typed failure/review and replacement action |
| Duplicate submission and worker crash | One durable logical result, resumable execution |
| Two reviewers edit same queue item | One succeeds; stale update receives 409 |
| Workspace A requests Workspace B source | No data or signed URL returned |
| Provider quota exhausted | Persisted retry/deferred state; no false clean report or paid fallback |
| Automated benchmark after manual correction | Uses frozen automated revisions unless explicitly marked human-assisted |

Run migration syntax and execution checks against a fresh local Supabase/PostgreSQL instance, then authorization tests using real anon/authenticated/service roles. Validate all JSON examples against schemas, generate OpenAPI types, run Python unit/integration tests, frontend type/lint/build checks and browser flows. Inspect actual UI evidence highlights against source coordinates. Record software versions, dataset hash and measured results in benchmark artifacts. No part of this plan substitutes projected accuracy or quota assumptions for those implementation checks.
