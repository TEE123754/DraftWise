# Implementation checkpoint — 2026-09-19

Executable application code is present in separate files. This is a partial implementation, not a production-ready release.

## Local evidence

- 2026-09-20 reliability repair: homepage loop, case-list 404, schema-mismatched dashboard queries, unauthenticated assistant requests and false-success alerts are fixed. Redesigned business homepage and favicon/social assets load. **89 backend/PostgreSQL tests, eight browser tests and production build pass**; desktop/mobile homepage inspected.
- Hosted connectivity restored using the user-provided IPv4 Session pooler in ignored backend/.env. API readiness and worker heartbeat pass. Real Edge passed homepage/mobile, no-login demo summary, cases, assistant and exit with no page errors. Gmail is explicitly gated until secure import is implemented.

- Email-body and batch-pipeline update: **89 backend/PostgreSQL tests pass**, production frontend build passes, and the live API returns labelled email fields with exact evidence and quoted-history exclusion. See [local pipeline](LOCAL_PIPELINE.md) for scope and commands. Unlabelled prose, trained five-category classification, source promotion and benchmark submission remain pending.

- Latest checkpoint: **82 backend/PostgreSQL tests, four mocked-service browser tests and the production build pass**. Input manifests match across static and Docker archives (520 emails, 250 attachments, zero missing). Live Docker HTTP remains untested.
- Migration 004 is installed. The local no-login demo passed real API/worker extraction, source selection and report persistence; real Edge passed entry, inbox and exit. It uses isolated expiring sessions and local rules, with no anonymous provider calls. Advanced demo features, reset and cleanup remain incomplete.

- 82 backend/PostgreSQL tests pass. Coverage includes: units/numeric ambiguity, required-field gates, same-document notify dependencies, quote/label grounding, revision regressions, preview purity/expiry/version, scoped rule lifecycle, classification segmentation, TXT/Word/Excel parsing, API authentication boundary, first-login onboarding and shared-schema compatibility.
- Next.js production build and TypeScript checks pass.
- Four real-browser tests pass with mocked API responses: returned-draft preview, failed-check retry; keyboard navigation and axe checks for dashboard/case screens.
- One supplied input-only TXT SI/BL pair passed the subprocess CLI smoke test. This is not a benchmark score.

- Local PostgreSQL schema/migrations, tenant isolation/RLS, concurrent updates, atomic job publication, worker fencing and terminal failure projection pass. The full amendment API/worker/database journey passes with synthetic uploads and an overridden authenticated principal.
- The Supabase schema and migrations are installed in the configured project. The private bucket and signed-upload reservation passed. First login now creates a private admin workspace. Morpheus model discovery and a minimal structured inference passed with `deepseek-v4-pro`. Secrets live only in environment files excluded by `.gitignore`.
- The local frontend, Windows-safe API launcher and durable worker start together; `/health`, `/ready`, database connectivity and worker heartbeat pass against the configured live services.

## Implemented but not live-validated

JWT/JWKS authorization with a real signed-in user; complete Storage upload/download bytes; document-level Morpheus output quality; Docker/Railway deployment. Local PostgreSQL was exercised with minimal Supabase Auth/Storage schema scaffolding. The hosted schema and one synthetic provider request were exercised; no deployment or remote GitHub push occurred.

## Next work sequence

The September expansion request follows [the DraftWise roadmap](DRAFTWISE_EXPANSION_PLAN.md), covering anonymous demo, Gmail, overview dashboard, safety/drift, assistant and the public site. P0/P1 now have a tested initial local slice; remaining phases and full demo parity remain open. The items below remain technical gaps feeding those phases.

1. Sign in once to validate the hosted JWT/RLS/onboarding journey. Verify Storage byte immutability and orphan reservation cleanup. Add quotas/rate limits.
2. Complete mutation idempotency, graceful cancellation, job streaming and provider recovery. Guarded failure/retry projections are tested. Processing-job submission has idempotency; not every case/amendment mutation does yet.
3. Curated versioned port aliases, country/terminal contradictions, party/address qualifiers, multiline identities and container table totals. Current verifier uses exact normalization and review-gated fuzzy candidates. No general WSD model exists.
4. PDF hybrid-page recovery, pypdf fallback, Office image OCR, hidden row/column handling, formula-cache diagnostics and measured memory bounds. OCR and subprocess timeout adapters exist; Tesseract is not yet exercised here.
5. Document-level Morpheus/Gemini quality and quota tests, chunk reconciliation, schema repair retries and semantic identity assessment. Oversized prompts currently fail explicitly.
6. Evidence-supported review corrections, dependency persistence, customer/rule endpoints, historical rule evaluation and policy rechecks. Pure scoped rule functions/tests exist but rules are not yet applied by the running verifier.
7. Complete case issue/audit lineage and guided action decisions. Returned drafts currently require source selection after extraction. Custom correction wording is rejected until contradiction validation exists.
8. Inbox pagination/filters, PDF/image previews, generated API types, rule management and benchmark UI. Current evidence viewer shows exact parsed text and locations.
9. Input-only dataset runner and actual 520-email scorer measurement. Never import the private answer key into product code.
10. Real API/UI amendment journey, container/deployed smoke tests and quota/resource measurement before claiming production readiness.

## Live configuration required

Project URL, database URL, Supabase keys, JWT issuer and Morpheus credentials/model are configured locally. A minimal real inference passed, but document quality and free-tier eligibility are not established. Follow [local setup](LOCAL_SETUP.md).

The manifest distinguishes `implemented`, `partial` and `planned` modules. File existence is not feature acceptance. The checked/crossed master checklist is [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md).
