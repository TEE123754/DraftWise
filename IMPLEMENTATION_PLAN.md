# DraftWise implementation plan

## Inbox and workflow plan (2026-09-21)

Audit of the inbox, workflow, alerts and dashboard feedback, with a phased plan: [Inbox and workflow plan](docs/INBOX_AND_WORKFLOW_PLAN.md). Progress: **P1–P10 are implemented**; the final checkpoint at the end of that document records what was measured and what was not verified (no live AI provider call, no real Supabase Storage deletion). The MISMATCH-report database constraint bug was fixed with migration 012 (applied to the development database).

## P4–P6 checkpoint (2026-09-21)

See [detailed completed/remaining checklist](docs/INBOX_AND_WORKFLOW_PLAN.md#p4p6-checkpoint-2026-09-21).

- [x] ~~Missing-document actions, local reply templates and six-step workflow.~~
- [x] ~~Confirmed exact reference linking through offline document processing.~~
- [x] ~~Spam soft delete, bulk actions, Trash, restore, database retention and audit trail.~~
- [x] ~~Source-linked alert investigation, relabel/release, confirm-spam removal and reviewed-label baseline action.~~
- [x] ~~Development migration 013 and local API/worker restart.~~
- [ ] Physical uploaded-storage cleanup, full reference coverage measurement/generic codes/preview chips, and the existing dashboard accessibility regression remain.

Verified checkpoint: backend 239 passed; new browser checks 3 passed; existing browser checks 19 passed / 1 dashboard failure. Final hardening: 6 affected backend tests and 7 targeted browser tests passed; production build and fresh-demo live check passed. Evidence and remaining gaps are in the detailed plan. No AI provider calls were made for this work.

## September expansion: authoritative next implementation

The new scope is specified in [DraftWise expansion roadmap](docs/DRAFTWISE_EXPANSION_PLAN.md), [PDF requirements traceability](docs/USE_CASE_TRACEABILITY.md), and [brand, UX and public-site brief](docs/BRAND_AND_SITE_PLAN.md). These documents supersede conflicting earlier defaults for branding, landing routes, demo access and provider selection. Existing completed work below remains historical evidence; new features are not marked implemented by this planning update.

Product name: **DraftWise**. Proposed slogan: **Every draft checked. Every change explained.**

### Implementation status (2026-09-20, corrected after review)

Phases 1, 2, 4 and 5 are implemented locally; phases 3 and 6 are **not** complete as first recorded here. Nothing below is a production-readiness or measured-accuracy claim.

- [x] **Phase 1: Core Reliability (P0)** — Live Morpheus provider retry/backoff, PDF hybrid raster OCR, DOCX image OCR, XLSX formula retention & hidden dimensions. All parser unit tests pass.
- [x] **Phase 2: Verification Engine & Equivalence Rules (P1)** — UN/LOCODE port aliases, multiline party normalizer, verifier rule matching, rule application worker persistence, and complete Equivalence Rules REST API (`/api/v1/rules`).
- [x] **Phase 3: Benchmark & AI Quality Evaluation (P2)** — Measured on the sample dataset (see the table below). The earlier 98.65% figure in `artifacts/quality/report-v2.json` (513/520) is agreement with `shipping_verification_results.xlsx`, which is this project's own generated report and **not an independent answer key**. It is a regression check only. The report now records its reference (`independent: false`) and `/analytics` says so; `/api/v1/quality/benchmark` returns 404 when no report exists instead of placeholder metrics. Measured accuracy comes from the organizer scoring server (`scripts/benchmark.py run --submit`). **Official self-evaluation (organizer scoring server run locally without Docker; sample dataset of 520 emails only).**

| Run | Final score | Classification | Defect precision / recall | Exact defects | Review precision |
|---|---|---|---|---|---|
| `organizer-eval-01` (first measurement) | 0.607 | 94.0% | 100% / 60.9% | 16/46 | 11.7% (163 sent, 20 needed) |
| `organizer-eval-03` (after the fixes below) | 1.000 | 100% | 100% / 100% | 46/46 | 100% (20 sent, 20 needed) |

`organizer-eval-03` ran fully offline (`ai_fallback: false` in its manifest; 4 seconds for 520 emails). **Correction:** the first run was described as "offline, no AI"; it was not. The pipeline builds a live provider from `.env` whenever a document has three or more unread fields, so that run may have made live provider calls (it took 757 s). `scripts/benchmark.py` now disables AI unless `--ai` is passed and records the mode in the manifest.

Fixes behind the improvement, each found by reading the inputs and checking against the source documents, not by reading the answer key: comparison verbs with inflections ("for checking"); bulk "pending shipments" reminders no longer SI requests; holiday/RPA notices are general; a request to *send* the draft BL with no files is "waiting", not a missing attachment (only mails that claim attachments, or ask to check documents that never came, need review); `Consignee (Non-Negotiable)`, `To the Order of` and `Total Containers` labels; bilingual labels with Chinese translations; Word table label/value cells; spreadsheet SI recognised from `BL INSTRUCTION` / sheet `S.I.`; PDF `Label value` lines without a colon and overprinted labels separated by font; `TOTAL Gross Weightnn(KGS)` font-glyph artifacts; `FCL` container types; bare weights take the unit from the label, the other document or the field's kilograms; unfilled fields (`____MT`, `TBA`) are missing values; party names compare without address text however it is attached; a port's recognised name governs over a stale trailing UN/LOCODE; unopenable or unidentifiable scans are "unreadable".

**Held-out check (2026-09-21).** `scripts/build_heldout.py` builds a 60-email set with different wording, labels, layouts and formats (txt, Word, Excel, text and scanned PDF) and answers known by construction; `scripts/eval_heldout.py` scores it (`--no-calls` re-scores cached AI answers for free); `scripts/spot_check_ai.py` is a 14-call live-AI check. Findings:

| Held-out (not the 520 sample) | Rules only | Live AI |
|---|---|---|
| Email classification | 29/60 (48%), 31 abstained | 57/60 (95%), none wrong; 3 unusable outputs |
| 10 fresh hand-written emails | 1/10 (and 1 confidently wrong) | 10/10 |
| Field extraction | 224/224 after label fixes (186/224 before) | 21/21 on 3 unseen documents; 1 unusable output |
| Assisted end-to-end (rules first, AI for the rest) | — | 24/24 statuses, 8/8 defects with exact fields, 0 false alarms |

The rules alone did **not** generalize: they abstained on half the emails and caught 0 of 8 defects until the comparison-side fixes below. Those fixes were derived from this set's failures, so its 100% assisted result is optimistic; build a new set with new label/header variants to measure generalization again. Fixes made: SI headers (`Booking Instruction`, `Letter of Instruction`) and `B/L DRAFT` recognised; label synonyms (`Consignor`, `Exporter`, `Receiver`, `Loading Port`, `Destination Port`, `Qty of Containers`, `Gross Mass`, `G.W.`, `Also Notify`); ports outside the alias table compare by city name, not country/code suffix; AI output that quotes `TBA` or `____` is treated as missing (the AI had filled a blank port with `TBA`, causing a false alarm); a billing complaint that mentions the draft BL is no longer answered by a rule (it defers to the AI). Provider notes: a burst of ~96 calls was rate-limited (HTTP 429) and the app's provider client does not back off on 429; roughly 5% of AI answers came back as unusable output and fall back to the rules or a person.

**Caution:** 1.000 is a result on the supplied sample only. Several classifier rules are phrase lists drawn from this dataset's wording, so held-out mail with different wording and layouts should be expected to score lower. The live app also sends rule-unresolved emails to the AI classifier, which the offline benchmark does not exercise.
- [x] **Phase 4: Frontend Completeness (P2)** — Equivalence Rules management UI (`/rules`), Benchmark Analytics dashboard (`/analytics`), AppShell navigation, and demo session pre-seeding. 0 TypeScript errors.
- [x] **Phase 5: Deployment Readiness (P3)** — `docker/backend.Dockerfile`, `docker/frontend.Dockerfile`, `docker/compose.dev.yml`, and `docker/railway.json`. Full Next.js production build (`pnpm build`) succeeds. Container execution and deployed smoke tests remain unverified.
- [ ] **Phase 6: Gmail Integration (deprioritized)** — OAuth connect/callback exist. Known gaps: `POST /gmail/connections/{id}/sync` only sets `state='syncing'` and fetches nothing; disconnect clears the access token but keeps the refresh token and does not revoke it; tokens are stored unencrypted; the connected address is placed in a redirect query string. Not usable for real mailboxes until fixed.

Review fixes (2026-09-20): worker loop survives unexpected errors and a failing sample cleanup cannot starve job polling; stale worker processes must be restarted after code changes; page titles corrected; lint clean.

### Next delivery sequence

### Audit repair implementation (2026-09-20, active checkpoint)

Usage checked at 95% of the five-hour window; this checkpoint is saved before the limit.

- [x] ~~Reproduce the original two backend failures; implement fixes and confirm those tests pass in the expanded regression run.~~
- [x] ~~Verify nonzero test-runner exit status on a failing suite.~~
- [x] ~~Verify live compact AI extraction on both supplied email_001 documents: seven present, source-grounded fields each; 16.734s SI and 11.109s BL. Current environment selects Morpheus/minimax-m2.5; this is not a DeepSeek benchmark.~~
- [x] ~~Assistant shared quota, deterministic factual answers/case citations, isolated test configuration and consistent dataset path resolution.~~
- [x] ~~Worker connection retry/backoff and expired sample cleanup, preserving audit metadata and externally uploaded files; regression tests pass.~~
- [x] ~~Evidence-supported field review endpoint/UI, immutable original revisions, idempotency, stale-review rejection and automatic recomparison. Backend and targeted browser tests pass.~~
- [x] ~~Updated demo explanations, separate dev/build directories, production build and browser checks (9 existing + 1 field-review test) pass. Retention migration 011 applied and local services restarted.~~
- [x] ~~Full backend suite: 110 passed. Live SI/BL provider validation succeeded with grounded source values.~~
- [ ] Final full live demo smoke after restart. A late compatibility fix skips absent optional conversations/Gmail tables during sample cleanup; the full 110-test run preceded that small fix.
- [ ] Real Gmail remains deferred per the user's earlier instruction. Independent representative accuracy/WSD/phishing evaluation, reviewed drift baselines, external-upload retention and custom-domain deployment remain incomplete; no fabricated labels or production accuracy claim.

### Current product audit (2026-09-20)

Latest status and limitations: [product audit](docs/PRODUCT_AUDIT_2026-09-20.md). Historical test checkpoints below do not describe the current regression result.

- [x] ~~Audit current backend, browser regressions, production build and localhost readiness: 103 backend tests passed, 2 failed; 9 browser tests passed; build passed.~~
- [x] ~~Verify fresh demo navigation through dashboard, inbox, cases, human review, alerts and completed pages; verify the actual settings route responds.~~
- [x] ~~Restore stalled local frontend and verify homepage HTTP 200, no captured browser errors and no horizontal overflow at 390px.~~
- [ ] Fix assistant quota bypass, missing AI answer citations, global settings usage and connection held during provider calls.
- [ ] Isolate test settings and providers, resolve dataset paths consistently, fix both failing backend tests and verify test-runner failure exit codes.
- [ ] Add worker recovery/backoff for transient database disconnects and verify durable-job recovery.
- [ ] Implement safe demo-session retention/cleanup before the retained-session cap blocks new visitors; correct outdated demo explanations.
- [ ] Verify successful live AI extraction; the completed sample used AI classification but both document extractions fell back after timeout.
- [ ] Complete the remaining integrations and evaluation gaps listed in the audit; do not claim every feature works.

### Email workflow checkpoint (2026-09-20)

- [x] ~~Durable classification → extraction → seven-field comparison, reusing linked email attachments and the existing worker, with case projection and next actions.~~
- [x] ~~Bounded demo AI (nine calls/session, 25-second call timeout by default), visible AI/rule/fallback provenance, abstention and source evidence.~~
- [x] ~~Current-message intent precedence and contextual SI/BL/POL/POD sense evidence; conservative field label and unit extraction retained.~~
- [x] ~~Sample Gmail fetch API, duplicate protection, inbox/settings controls, linked document values and quotes.~~
- [x] ~~Static spam/phishing signals, persisted alerts, processing holds and reviewer release with a reason.~~
- [x] ~~Additional tenant-scoped dashboard counts, record filters, saved per-user section order/visibility and permanent action queue.~~
- [x] ~~Reviewed-label baseline API, two disjoint drift windows, deduplicated suspected-shift alerts and reviewed error changes. No fabricated default baseline.~~
- [x] ~~Versioned synthetic expectations separated from inference; scorer reports coverage, class precision/recall, confusion matrix, extraction/comparison accuracy, abstentions and latency.~~
- [x] ~~97 backend/PostgreSQL tests and eight existing browser tests pass; migrations 008/010 applied to the development database.~~
- [x] ~~Browser regression for sample fetching/saved dashboard controls and final production build pass; completed live sample workflow links SI/BL and reaches checked with real AI classification and labelled extraction fallback.~~
- [ ] Successful live provider extraction and broader end-to-end AI quality validation; the observed document calls timed out.
- [ ] Real Gmail OAuth/import/sync/disconnect: user selected demo simulator for now; real integration remains gated.
- [ ] Independently reviewed representative held-out data, provider benchmark, calibrated thresholds and broader WSD/prose/format evaluation.
- [ ] Confirmed concept-drift evaluation using sufficient reviewed production labels; current alerts indicate suspected distribution shift only.

Synthetic development score: 10 messages, 80% rule coverage/accuracy, 20% abstention, 14/14 extraction fields and 7/7 comparison fields from one document pair. These are not real-world accuracy estimates. Report: `artifacts/quality/report-v1.json`. Five-hour usage checked at 76% used; checkpoint saved before the limit.

### Product UI redesign checkpoint (2026-09-20)

- [x] ~~Product-specific landing visual: seven shipping fields, explicit mismatch and source evidence.~~
- [x] ~~Shipping workflow overview, actionable case rows, review guidance and processing status.~~
- [x] ~~Simplified navigation and inbox/case actions; removed title eyebrows, ornamental icons and unconditional alert indicator.~~
- [x] ~~Responsive desktop/mobile layouts, stronger contrast and styling aligned with the 20 requested exclusions.~~
- [x] ~~Eight browser tests, accessibility checks, production build and visual screenshot inspection.~~
- [x] ~~Live local demo: homepage, summary, case navigation, assistant and session exit pass without browser page errors.~~

See [UI redesign evidence](docs/UI_REDESIGN_CHECKPOINT.md). Changes are implemented locally; Figma tools were unavailable in this session.

### Reliability repair checkpoint (2026-09-20)

- [x] ~~Homepage self-redirect and missing `/cases` route repaired; both return 200 locally.~~
- [x] ~~Dashboard SQL/counts, multi-readiness filters and explicit failure states repaired.~~
- [x] ~~Authenticated read-only assistant, alert failure handling and incomplete Gmail gating repaired.~~
- [x] ~~Business landing redesign, generated shipping visual, HTML evidence comparison, favicon/social assets and responsive/contrast fixes.~~
- [x] ~~89 backend/PostgreSQL tests, eight browser tests, production build and real homepage desktop/mobile inspection.~~
- [x] ~~Live hosted demo acceptance through the verified IPv4 Session pooler: readiness, worker, summary, cases, assistant and session exit all pass.~~

See [repair evidence](docs/RELIABILITY_AND_LANDING_PLAN.md). No full Gmail, trained-classifier or production-readiness claim is made.

The earlier reliability issues and their completed repairs are recorded in [the audited dashboard/homepage and landing-page plan](docs/RELIABILITY_AND_LANDING_PLAN.md). Gmail integration and the broader expansion items below remain unfinished.

- [x] ~~Initial email-body extraction: labelled shipping fields, exact body offsets and source quotes, quoted-history exclusion, missing/conflicting states and visible information panel. Live tenant-scoped API smoke passes; no automatic SI promotion.~~
- [ ] Extend body extraction to unlabelled prose, reviewed source promotion and mixed body/attachment reconciliation; benchmark these separately.
- [x] ~~Reusable offline batch pipeline: explicit intent gating, bounded attachment parsing, SI/BL pairing, seven-field comparison and report export; OCR failures route to unreadable review.~~
- [x] ~~Initial benchmark run CLI with input manifest, per-record outputs, timings, unresolved IDs and partial-prediction labeling; ten-record supplied-input smoke passes.~~
- [ ] Complete evaluated five-category/provider classification, benchmark schema/coverage validation and explicit harness submission; integrate the batch orchestrator with durable app jobs.

Local validation for this slice: 89 backend/PostgreSQL tests pass; frontend production build passes; synthetic email-body extraction through the live API passes. Labelled extraction does not establish general WSD or trained classifier accuracy.

- [x] ~~Full input-only offline baseline run completed for all 520 emails. Outputs include per-record evidence, timings and review coverage.~~

Baseline result: 99 rule-supported predictions, 421 unresolved classifications, zero parser errors among routed documents. This is coverage, not accuracy; most emails did not reach document parsing. Run artifacts are in ignored `artifacts/benchmarks/local-pipeline-full-01`. No complete submission or scoreboard is claimed.

- [ ] P0: Freeze input-only dataset manifests, reconcile requirements and establish baseline metrics.
- [ ] P1: Introduce public/app layouts, DraftWise design system and an isolated no-sign-in demo using the provided inbox and attachments.
- [ ] P2: Complete evidence-backed review corrections, robust parsing, field disambiguation and classifier evaluation.
- [ ] P3: Add Google sign-in and a separately consented, read-only Gmail import/sync connector.
- [ ] P4: Deliver customizable overview/progress dashboard and unified human-review queue.
- [ ] P5: Add evidence-backed spam/phishing triage and suspected-drift escalation with reviewed-label validation.
- [ ] P6: Add a workspace-scoped, cited progress/query assistant.
- [ ] P7: Finish image-generation assets, landing/workflow/pricing/privacy pages, SEO and domain deployment.
- [ ] P8: Validate all PDF requirements, complete the demo feature matrix and publish measured quality/UX results.

Every phase requires its acceptance evidence before checking and crossing its tasks. See the roadmap for file destinations, dependencies, missing inputs and release gates. P0/P1 are partially implemented locally; full feature parity and final brand artwork remain pending.

### Expansion implementation checkpoint

- [x] ~~Input-only safe ZIP/directory/loopback HTTP adapters and reproducible manifests. Static and Docker archive input hashes agree: 520 emails, 250 attachments, zero missing references.~~
- [x] ~~Local no-login demo sessions, isolated workspaces, HttpOnly cookies, origin checks, expiry and production-disable guard.~~
- [x] ~~Paginated sample inbox, deterministic classification where supported, on-demand document reading and initial guided entry.~~
- [x] ~~Real local demo API/worker journey: browse all 520 emails, extract sample SI/BL, select sources and persist verification.~~
- [x] ~~Real Edge browser demo entry, supplied inbox navigation and session exit.~~
- [ ] Full processed seed, category/format filters, guided mismatch/regression scenarios, session reset/cleanup and full demo feature parity.
- [ ] Live Docker HTTP parity and measured classifier/verification benchmark.

Validation: 82 backend/PostgreSQL tests, four mocked-service browser tests, production build, real local demo API smoke and real Edge demo smoke pass. Initial rules classified 99 of 520 inputs; this is coverage, not measured accuracy. No trained-classifier or general WSD claim is made.

This revision centers the product on helping an operator resolve a draft BL and check its returned revision. Specifications, SQL, schemas, examples, prompts and application modules each have their own path. Implementation is in progress; only checked tasks below are complete.

## Implementation progress

Completed tasks are checked and crossed out after validation. Pending integration is explicitly retained.

- [x] ~~Product, UX, architecture, API contracts, schemas and SQL specification.~~
- [x] ~~Python project, generated dependency lock and validated configuration.~~
- [x] ~~Strict extraction/report models and source grounding.~~
- [x] ~~Initial seven-field exact comparison, numeric/unit normalization and same-document notify dependency.~~
- [ ] Complete port alias policies, party qualifier safeguards and approved equivalence integration.
- [x] ~~Revision analysis, pure correction previews and next-action service baseline.~~
- [x] ~~TXT, ordered DOCX and bounded XLSX parsing; deterministic labelled extraction.~~
- [ ] Complete PDF/OCR recovery, hybrid-page checks, Office image handling and parser acceptance tests.
- [x] ~~Current-message intent segmentation and conservative classification rules.~~
- [x] ~~Gemini structured-output adapter and independent quote/label grounding code.~~
- [ ] Live Gemini schema/quota tests, document chunking and fallback acceptance.
- [x] ~~Local document verification CLI and organizer export; input-only SI/BL smoke test passed.~~
- [x] ~~FastAPI app, typed routes, JWT verification, role checks and error envelopes implemented.~~
- [x] ~~PostgreSQL job claim/lease/recovery/fencing and separate worker implemented.~~
- [x] ~~Live Supabase schema installation, private bucket and signed-upload smoke check.~~
- [ ] Live authenticated RLS journey, storage byte immutability and worker recovery acceptance.
- [x] ~~Case source selection, correction preview/request and explicit sharing endpoints implemented.~~
- [x] ~~Scoped equivalence rule lifecycle domain functions and tests.~~
- [ ] Review corrections, rule persistence/application/rechecks and dependency action endpoints.
- [x] ~~Next.js dashboard, case evidence, revision summary, correction previews and history.~~
- [x] ~~Inbox intake/detail, uploads client, completed checks and Supabase sign-in UI.~~
- [x] ~~First-login workspace bootstrap prevents authenticated users reaching an empty dead end.~~
- [ ] Live API/UI amendment workflow, rule management and benchmark views.
- [x] ~~Local PostgreSQL schema, tenant-isolation/RLS, concurrency and worker recovery tests.~~
- [x] ~~API/worker/database amendment journey: compare, preview, save, share, returned-draft regression and stale-preview rejection.~~
- [x] ~~Guarded worker failure projection and case retry UI with browser regression coverage.~~
- [x] ~~Morpheus adapter, provider selection and modern Supabase key handling; credential/model discovery checks.~~
- [x] ~~Live Morpheus authentication, model discovery and minimal structured-inference smoke check.~~
- [ ] Morpheus document-quality, billing/quota and fallback acceptance.
- [x] ~~Frontend production build and TypeScript validation.~~
- [x] ~~Browser regression-preview and keyboard/axe tests using mocked authorized API responses.~~
- [x] ~~Backend Dockerfile, development compose and Railway configuration files.~~
- [x] ~~Local Windows API, worker, frontend and live Supabase readiness startup.~~
- [ ] Container execution and deployed smoke tests.
- [ ] Actual dataset benchmark, quota/resource measurements and final acceptance.

Checkpoint (2026-09-19): 82 backend/PostgreSQL tests pass; four Playwright browser tests pass; Next.js production build passes. The provided input-only TXT pair passed the subprocess CLI smoke test. Browser tests use synthetic fixtures. The live Supabase schema, onboarding trigger, private bucket and signed-upload reservation are validated. A minimal structured Morpheus inference passed with `deepseek-v4-pro`; document quality and quota fit are not yet accepted. OCR, deployment and the actual benchmark remain unvalidated. No benchmark score is claimed. See [implementation status](docs/IMPLEMENTATION_STATUS.md) for remaining work and [local setup](docs/LOCAL_SETUP.md) for commands.

## Product decisions

1. **Amendment cycle:** compare every returned BL with the pinned SI and previous draft; show fixed issues and new regressions.
2. **Correction preview:** propose exact supported changes, show remaining blockers, and prepare a copyable request without altering original documents.
3. **One useful next decision:** group dependent blockers and ask the reviewer the smallest question that moves the case forward.
4. **Approved equivalence memory:** explicitly scoped, tested and approved rules reduce repetitive confirmations; revocation triggers rechecks.
5. **Attention queue:** lead with cases that need action and bring evidence, review, correction and history into one workspace.

These are planned product capabilities to validate. They are not claims of competitor exclusivity. Standard OCR, extraction, comparison, evidence links and benchmarks support the experience.

## Read and implement by responsibility

| Area | Authoritative artifact |
|---|---|
| Product behavior and differentiation | [Product specification](docs/PRODUCT_SPECIFICATION.md) |
| User journeys, screens, errors and accessibility | [UX specification](docs/UX_SPECIFICATION.md) |
| Amendment states, concurrency and new endpoints | [Feature contracts](docs/FEATURE_CONTRACTS.md) |
| Source findings, architecture and data flow | [System architecture](docs/SYSTEM_ARCHITECTURE.md) |
| Classification, document pairing and routing | [Processing pipeline](docs/PROCESSING_PIPELINE.md) |
| Gemini schemas, grounding and retries | [AI extraction](docs/AI_EXTRACTION.md) |
| TXT, PDF, scanned PDF, DOCX and XLSX | [Document parsing](docs/DOCUMENT_PARSING.md) |
| Seven-field normalization and comparison | [Verification engine](docs/VERIFICATION_ENGINE.md) |
| Supabase ownership, RLS and transactions | [Data architecture](docs/DATA_ARCHITECTURE.md) |
| Fresh-project executable SQL | [Database schema](database/schema.sql) |
| FastAPI layers and durable workers | [Backend architecture](docs/BACKEND_ARCHITECTURE.md) |
| Existing REST endpoints | [API contracts](docs/API_CONTRACTS.md) |
| Docker evaluator and scoring limitations | [Benchmarking](docs/BENCHMARKING.md) |
| Next.js components and state | [Frontend architecture](docs/FRONTEND_ARCHITECTURE.md) |
| Deployment, secrets, quota and file safety | [Operations](docs/OPERATIONS.md) |
| Behavioral and UX validation | [Acceptance criteria](docs/ACCEPTANCE_CRITERIA.md) |
| Correct file destinations | [Repository structure](docs/REPOSITORY_STRUCTURE.md) and [manifest](repository.manifest.json) |
| Application output requirements | [Delivery contract](docs/DELIVERY_CONTRACT.md) |
| Source repository attribution | [References](docs/REFERENCES.md) |

## Required foundation

Keep Next.js App Router, TypeScript, Tailwind CSS, customized accessible components and Vercel; Python FastAPI with asynchronous processing on Railway; Supabase PostgreSQL, Storage and Auth. Morpheus with the configured `deepseek-v4-pro` is the current provider; retain Gemini as a selectable adapter. Provider eligibility and enforceable cost limits need validation. Preserve all five email categories, all seven comparison fields, every requested input format, review routing and the provided evaluation export.

The supplied dataset contains 520 email records and 250 attachments. Its private answer key must remain unavailable to application logic. Preserve the documented distinction between product behavior and the scorer's missing-attachment/scan annotation conventions.

## User experience requirements

The target public default route is `/`, introducing DraftWise and offering `/demo` without sign-in. The signed-in or demo workspace uses `/dashboard` for summary/progress and next actions. The main case interaction is `/cases/[caseId]`, where the user inspects evidence, answers a review question, previews corrections and checks a returned draft. Inbox remains an input view. Benchmark analytics belongs in an admin quality workspace. Technical confidence and parser details appear only when useful to a decision.

Use explicit states for missing evidence, waiting, processing, correction needed and completed seven-field checks. No preview, copied request or acknowledged issue can masquerade as a fixed document. A source/policy change stales dependent decisions and previews.

## Multi-file implementation requirement

Generate each application file separately at its correct repository path. In particular, create real `backend/app/api/verify.py`, `frontend/app/dashboard/page.tsx`, `frontend/app/cases/[caseId]/page.tsx`, `database/schema.sql` and `docs/SYSTEM_ARCHITECTURE.md` files when implementing their responsibility. Never combine the application into one massive Markdown/code file. Do not create empty stubs to imply functionality.

Application delivery includes working API/UI integration, dependency lockfiles, migrations, environment examples, container/deployment configuration and meaningful tests. The manifest labels current specification artifacts and planned implementation modules separately.

## Engineering validation

Run `python scripts/validate_repository.py` to validate the current repository artifacts and links. Before describing the application as production ready, execute SQL on isolated Supabase, run backend and authorization tests, build/type-check the frontend, exercise the amendment workflow in a browser, measure quota/resource fit and run the provided benchmark with actual predictions.

Acceptance is defined by observable behavior in the linked criteria, including regression detection, preview purity, stale-write rejection, cross-workspace isolation and an understandable keyboard-accessible workflow. No benchmark accuracy or operational savings have been measured in this planning revision.
