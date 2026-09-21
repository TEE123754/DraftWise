# Backend architecture

[Repository overview](../README.md) · [Implementation plan](../IMPLEMENTATION_PLAN.md)


## 1 Layering and components

```text
backend/app/
  main.py                     # app factory, lifespan and router registration
  config.py                   # validated pydantic-settings configuration
  api/
    dependencies.py           # verified principal, workspace, roles, request ID
    errors.py                 # consistent Problem response mapping
    # Individual route modules below live directly in api/
      emails.py uploads.py classify.py extract.py verify.py
      review.py jobs.py benchmarks.py health.py settings.py
  schemas/                    # Pydantic request/result/evidence contracts
  domain/                     # enums, immutable value objects, policy rules
  services/
    ingestion.py classification.py pairing.py extraction.py
    normalization.py verification.py review.py exports.py
  parsers/
    base.py registry.py text.py pdf.py docx.py xlsx.py ocr.py
  ai/
    base.py gemini.py grok.py capabilities.py limiter.py grounding.py
  repositories/
    emails.py documents.py reports.py jobs.py reviews.py benchmarks.py
  workers/
    runner.py claim.py handlers.py heartbeat.py recovery.py
  benchmark/
    dataset.py manifest.py export.py scorer_client.py metrics.py
  infrastructure/
    database.py storage.py auth.py logging.py subprocesses.py
```

Routers deserialize and authorize; services implement business transitions; repositories perform scoped persistence; parsers/providers implement replaceable adapters. No router directly constructs prompts or compares strings. Pydantic schemas are the source of truth for OpenAPI and generated frontend types. Domain policy functions remain pure and independently testable.

## 2 Durable job claim protocol

The worker claims one due job in a short transaction. The lease token fences stale workers; all output commits must verify ownership before inserting artifacts. Heartbeat renews every 20 seconds while a job is running; initial lease 90 seconds. A separate bounded recovery tick requeues expired leases below the attempt ceiling or marks them failed with `WORKER_LEASE_EXHAUSTED`.

See [the job claim query](../database/queries/claim_job.sql).

Before final commit: lock the job row and require matching `lease_token`, state `running`, and an unexpired lease; then insert artifacts, enqueue downstream work with deterministic idempotency key, append event, and mark succeeded atomically. An expired worker discards its result. Stage outputs already committed are reusable after restart. Unique input fingerprints prevent duplicate extraction/report versions across retries. Deleting a job is never the acknowledgment mechanism.

Use `asyncio` for network/database I/O, a bounded subprocess for CPU and untrusted parsers, and semaphores for resource limits. Do not run durable processing solely through FastAPI `BackgroundTasks`, which is suitable for small same-process follow-up work and does not provide a persistent queue. [FastAPI background task guidance](https://fastapi.tiangolo.com/tutorial/background-tasks/).

Shutdown stops claims, signals parser children, lets current transactions finish within the configured grace period, then relinquishes the lease or allows expiration. Job cancellation is cooperative: after a provider response and before commit, check cancellation/lease state. A late response cannot create a new current report for a cancelled job.

## 3 Failure, quota and observability behavior

Error taxonomy: `VALIDATION_ERROR`, `FILE_UNSUPPORTED`, `FILE_CORRUPT`, `FILE_LIMIT_EXCEEDED`, `DOCUMENT_ROLE_INVALID`, `EVIDENCE_INCOMPLETE`, `PROVIDER_RATE_LIMITED`, `PROVIDER_UNAVAILABLE`, `PROVIDER_OUTPUT_INVALID`, `AUTH_REQUIRED`, `FORBIDDEN`, `STALE_REVIEW`, `IDEMPOTENCY_CONFLICT`, `SCORER_UNAVAILABLE`. Distinguish a valid business review result from a job exception.

Initial limits: 20 MB/file, 20 attachments/email, 20 PDF pages/file, 100,000 populated XLSX cells, 100,000 body characters, 50,000 prompt-input characters per text chunk, one parser/OCR process, two provider requests at a time, and three total attempts per stage. These are configurable safeguards, not provider limits. Global provider RPM/TPM/daily limits come from the actual account and are reserved centrally when multiple workers run. Reduce input/crop size before increasing tokens. Persist `available_at` on 429 so restarts do not create retry storms.

Structured logs contain request/job/workspace IDs, stage, model version, elapsed time, retry reason and sizes; no email bodies, raw documents, API keys or signed URLs. Log raw provider payloads only as private, access-controlled diagnostic artifacts with retention, not console output. Counters: queue age, completion/review/failure counts, parser errors by format, provider quota events, evidence failures, peak RSS, cache hit rate, p50/p95 latency. Expose dependency readiness separately from liveness; external AI unavailability should not make the API process unhealthy and repeatedly restart it.

Initial per-user API limits: 60 reads/minute, 10 processing submissions/minute and 2 active benchmark runs per workspace, adjusted through settings. Single-process limiter is acceptable only while one replica is enforced; distributed deployments use atomic PostgreSQL counters/reservations. Authorization and quota errors are JSON, never HTML provider error pages.

Settings changes increment `workspaces.settings_version` atomically using the requested prior version. Multi-worker provider quotas use a separate migration for `provider_budget_windows(provider,model,window_start,window_seconds,requests_reserved,tokens_reserved)` with a unique window key; reserve capacity in a locked transaction before each call. Until that shared limiter is implemented and tested, enforce one worker deployment rather than claiming distributed quota correctness.


## New case services and job dispatch

Use the exact route/service destinations in [Feature contracts](FEATURE_CONTRACTS.md) and the manifest. The canonical route location is `app/api/verify.py`; a separate `routers` directory is not required.

The baseline `processing_jobs.kind` enum-like constraint remains unchanged: dispatch amendment/revision/action recomputation under `kind=verify` with a validated `payload.operation` enum (`compare`, `analyze_revision`, `recompute_actions`, `rebaseline`, `recheck_rule`). Rule evaluations run under `kind=benchmark` with operation `evaluate_rule`. Payload schemas must forbid arbitrary function names and enforce each operation's required IDs. This avoids silently introducing job kinds rejected by the SQL constraint.

Module tests cover pure revision classification, source-pinned previews, dependency action selection and customer-scoped rule application. Repository tests cover locking, stale versions, matching case/report references and worker fencing.
