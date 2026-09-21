# DraftWise expansion roadmap

Status: P0/P1 partially implemented; remaining phases planned. This is the implementation contract for the user's eleven requested areas. Track completion in [the master plan](../IMPLEMENTATION_PLAN.md). Do not mark a feature complete merely because a route or file exists.

## 1. Evidence and scope

Reviewed all four pages of `Shipping Document Verification Use Case.pdf`, the existing application modules and test checkpoint, archive file inventories, and input-only email records. Dataset README content was not used. Never read the answer key, generation rules or scorer internals to build classifications or demo predictions.

Verified local input inventory: **520 JSON emails, 250 attachments: 192 TXT, 28 PDF, 8 DOCX, 22 XLSX**. These counts do not imply all records are comparisons or every attachment is readable. Use the static bundle as the default import source, with the Docker HTTP service as an alternative adapter. Compare input hashes before claiming the adapters are equivalent.

Existing assets to retain: seven-field comparison, strict schemas and grounding, immutable reports, preview fingerprints, amendment regression analysis, job fencing, Supabase workspace authorization and local startup. Last recorded checks: 82 backend/PostgreSQL tests, four mocked-service browser tests and a frontend production build. They do not validate the proposed features or prove production readiness.

Current gaps: manual live intake; initial local demo only; queue-only dashboard; no chatbot/Gmail/drift system; no separately evaluated phishing detector; no trained domain classifier or general WSD evaluation; incomplete human correction and parser recovery; public homepage redirects to the app.

### Product promise

**DraftWise: Every draft checked. Every change explained.**

Prioritize the complete loop: find the request, identify sources, compare, resolve uncertainty, request supported changes, and verify the returned draft. Gmail, the dashboard and assistant should make that loop easier. Position it through demonstrable revision regression checks, correction impact previews, source evidence and a unified review workflow. Do not claim competitor exclusivity or unmeasured time savings.

## 2. P0: baseline and foundation

- [x] ~~Create an input-only manifest of email IDs, safe relative attachment paths, checksums, formats and import counts. Reject path traversal and archive bombs; report missing referenced files.~~
- [x] ~~Add directory/static ZIP and loopback Docker HTTP source adapters with inbox/attachment allowlists, excluding README, answer keys and generator/scorer source. Unit-tested HTTP and static/Docker archive hash parity.~~
- [ ] Validate parity against a running Docker HTTP service; add bounded ingestion replay acceptance.
- [ ] Keep the organizer evaluator in a separate process/service; application code receives only a scoreboard, never reference labels.
- [ ] Reconcile older specifications, route naming, configured Morpheus provider, test evidence and the manifest. Fix stale launch/lockfile instructions before adding features.
- [ ] Complete mutation idempotency, runtime config validation and versioned migrations. Do not rerun the initial schema against the populated hosted project.

Acceptance: reproducible manifest counts; no hidden-label access; duplicate imports do not create duplicate emails/jobs; a baseline run records failures, review rate, latency and cost without invented accuracy. Signed-in routes still work.

## 3. P1: no-sign-in demo and shared application shell

Entry: landing page **Try the demo** -> `/demo` -> isolated sandbox dashboard. No email, password or Google account is required. Keep demo state distinct from any signed-in session.

Implemented first slice: `/demo` provides local-only sessions and all 520 input emails/250 attachment references. Sessions have origin checks, dedicated workspaces, hashed cookie credentials and eight-hour expiry; provisioning is capped at 20 retained sessions. Two-session isolation tests pass. All emails paginate; 99 receive explicit-rule classifications, with others left unresolved. Real API/worker source selection and verification plus real Edge entry/inbox/exit pass. No anonymous paid inference is performed. Reset/cleanup, processed seed cache, advanced scenarios and full feature parity remain pending. Migration `004_demo_sessions.sql` is required before starting the updated API/worker.

Use the same APIs, verification services and UI components as the real product. A server-issued, short-lived HttpOnly demo session maps to a dedicated sandbox workspace. A demo principal can access all product features within that sandbox, including rule workflows, review, assistant, settings, dashboard customization and benchmark views once implemented. It cannot grant itself access to a real tenant or platform administration.

- [ ] Build a versioned seed snapshot from actual supplied inputs processed by the pipeline. Preserve exact source evidence and provenance. Cache results with input, parser, model, prompt and policy fingerprints; invalidate when these change.
- [ ] Make all 520 email records available through pagination and format/category filters. Precompute expensive processing once; copy session-specific mutable state instead of reprocessing all documents per visitor. Show snapshot timestamp and seed version.
- [ ] Provide a short guided route through a real mismatch, a clean comparison, a missing/unreadable input and a returned-draft regression. Where the bundle lacks a scenario, add a separately labelled synthetic fixture derived from a sample; never describe it as organizer-provided data.
- [ ] Allow editing review decisions, trying rules, asking questions, uploading bounded temporary test files and resetting the sandbox. Separate a staged Gmail connection simulator from real Gmail OAuth.
- [ ] Show **Sample inbox** for simulated fetching and **Demo scenario** for injected phishing/drift examples. A Gmail connection to an actual mailbox requires Google authorization; a demo account cannot bypass it.
- [ ] Isolate uploads, conversations, metrics and resets per session. Use CSRF protection, request limits, file quotas, inference budgets, expiry and a cleanup worker. A reset affects only that session.
- [ ] For public deployment, confirm permission to republish supplied documents and contact details. Keep the provided originals local until rights are confirmed; provide transparently redacted public seeds if necessary.

Acceptance: in a clean browser, reach a populated demo without sign-in; execute the amendment workflow and every completed feature; reset safely; two visitors cannot observe or modify each other's changes. Requests with forged workspace IDs never read real customer data. Feature parity tests fail for unavailable or dead-end demo controls. Simulated integrations are clearly labelled.

## 4. P2: dependable classification, WSD, extraction and human review

Calling a pretrained model does not mean DraftWise has a trained shipping classifier. Build and measure a domain-specific system first. Keep five output classes: `BL_COMPARISON`, `SI_REQUEST`, `INVOICE_QUERY`, `GENERAL`, `SPAM`. Only comparison requests continue to SI/BL checks, with a separate uncertainty/review state.

- [ ] Create independently human-labelled development and held-out sets from permitted input content, plus adversarial examples. Split by shipment/thread/template family; remove near-duplicate leakage. Record annotator, rationale and disagreements. Keep the final holdout inaccessible to prompt tuning.
- [ ] Compare current rules+LLM with a supervised TF-IDF/linear classification baseline; calibrate thresholds on validation data. Promote the measured winner or cascade. Consider fine-tuning only after enough independent labelled examples and a demonstrated benefit. Never train on the private organizer answers.
- [ ] Add intent negation, misleading subjects, quoted-history separation, mixed requests and attachment-role evidence. Preserve original text and source spans. A document role must not come only from its filename.
- [ ] Implement contextual disambiguation with candidate sense, selected sense, span and rationale: preparing an SI versus checking a BL; loading versus discharge port; gross versus net weight; packages versus containers; consignee versus notify party; shipment instructions versus invoice billing. Use surrounding labels, table structure, units and document role. This is testable task-specific WSD, not a blanket claim of general language understanding.
- [ ] Ground every extracted value in the cited document. Unsupported or conflicting senses yield `needs_review`; schema-valid JSON is insufficient evidence.
- [ ] Finish PDF/Word tables, hybrid/scanned pages, OCR quality gates, XLSX hidden/formula-cell rules, unit ambiguity and multilingual label cases where samples support them. Explicitly separate read failures from mismatches.
- [ ] Implement reviewer confirmation/correction against source locations. Preserve original extraction, write an immutable corrected revision and rationale, recompute dependencies and report, invalidate stale previews, and audit actor/time.
- [ ] Persist scoped equivalence rules with independently labelled positive and negative evaluations, approval, revocation and rechecks. Avoid general fuzzy matches overriding country, terminal, address or numeric contradictions.

Provisional release targets, to validate against sample size: macro-F1 >= 0.90 across the five classes, comparison-request recall >= 0.95, automatic comparison-route precision >= 0.95; publish per-class counts/confusion matrix and uncertainty intervals. On the approved critical regression suite, zero unsupported automatic field matches and 100% escalation for required missing/unreadable values. These are acceptance targets, not achieved scores or universal guarantees. Include review rate and automation coverage so abstaining on everything cannot appear successful.

WSD acceptance: held-out ambiguous minimal pairs resolve from evidence or escalate; publish the slice score and errors. All seven fields need sufficient evidence before **No mismatch detected**. An unavailable model or invalid output yields a visible retry/review state. Attachments and emails are untrusted data, including apparent instructions addressed to the AI.

## 5. P3: Google sign-in and Gmail fetching

Use two distinct flows: **Continue with Google** establishes a DraftWise user session; **Connect Gmail** grants explicitly described mailbox access. Bind OAuth state to the signed-in user and selected workspace; use authorization-code flow with PKCE and verified callback/state handling. A Google email address alone is not permission to read its mailbox.

- [ ] Configure Supabase Google sign-in and a server-side Gmail OAuth connector. Keep provider tokens out of frontend storage/logs; encrypt refresh tokens at rest with a separately managed rotation key.
- [ ] Request `gmail.readonly` for user-authorized message/body/attachment import. Do not request send/delete/modify scope for this feature.
- [ ] Before first import show account, date range, label/query, limit, imported fields, retention and AI-processing disclosure. Preview the selection, then **Import selected emails**; default to a bounded recent period.
- [ ] Paginate Gmail listing; decode MIME bodies/base64url and nested attachments safely; retain provider message/thread IDs, hashes and trusted header provenance.
- [ ] Idempotency key: workspace + mailbox connection + Gmail message ID. Preserve connection ownership; another member cannot silently attach their token to somebody else's mailbox.
- [ ] Manual **Sync now** first, durable periodic sync second. Advance history cursor only after successful ingestion; restart interrupted pages safely. Handle expired history cursor with a bounded full sync. Add watch/Pub/Sub later only if needed.
- [ ] Show sync progress, duplicates skipped, failures, last success, quota delay and reconnect state. Disconnect revokes credentials/stops jobs; separately explain and implement deletion or retention of already imported data.
- [ ] Preserve manual upload/import for non-Gmail users. Linking emails to a shipment uses confirmed shipment/source evidence, not Gmail thread identity alone.

Acceptance: authorized test Google account imports a bounded real message set and attachments once; repeated sync creates no duplicates; revocation, interrupted sync, token refresh, history expiry and cross-tenant access tests pass.

External dependency: Google categorizes Gmail read access as restricted. Public rollout may require OAuth verification and a security assessment according to deployment and data handling. Test-user setup is a development path, not proof of public approval. See [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes), [restricted-scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification), and [incremental sync](https://developers.google.com/workspace/gmail/api/guides/sync).

## 6. P4: clean, customizable overview

Default dashboard answers: What arrived? What needs my decision? What is waiting on someone else? What was verified?

- [ ] Provide imported/classified/checked/review-required/awaiting-revision/failed counts, processing progress and a prioritized action queue. Show separate spam/security and drift summaries without overwhelming the main workflow.
- [ ] Define denominators and time scopes: an email is not a case; a noncomparison email is classified but not verified; previewing/copying a request never increases completed checks. Use distinct latest cases to avoid double counting revisions.
- [ ] Every summary links to the corresponding filtered records; persist filters in URLs and saved views. Show timezone, last refresh and data-unavailable versus actual zero.
- [ ] Let users hide/show/reorder/resize bounded widgets, save named layouts, select date ranges and reset to default. Store a versioned per-user/workspace configuration. Include keyboard controls alongside drag-and-drop.
- [ ] Show sync/job progress using completed stages and real counters. Use indeterminate progress when total work is unknown; do not fake percentages or savings estimates.
- [ ] Complete review queue with reason, severity, assignee, source context, age, decision and retry. Introduce escalation ownership and acknowledgement without automatic dismissal.

Acceptance: sums reconcile with underlying filtered records; customization survives reload; empty/loading/error/stale states are usable; layout works at 360px and desktop and is operable by keyboard.

## 7. P5: spam, phishing and concept-drift escalation

### Email safety

Keep intent classification separate from safety assessment. Spam is one of the five categories; phishing can masquerade as any category. Add `risk_state`, severity, observed signals and a review reason without changing organizer category labels.

- [ ] Combine Gmail spam labels and trustworthy authentication-header evidence with sender/reply-to mismatch, deceptive URL host, credential/payment requests and suspicious attachment signals. Store provenance; a sender-supplied header is not verified authentication.
- [ ] Never fetch links, tracking pixels or execute attachments to classify them. Sanitize email HTML, display URLs as text by default and explain each flag.
- [ ] Use **Suspected phishing** and **Insufficient evidence** rather than claiming maliciousness or safety from model confidence alone. Bundle inputs may not contain enough headers for spoofing checks; mark unavailable signals explicitly.
- [ ] High-risk content goes to a human safety queue before automatic downstream AI processing. Authorized reviewer can release with a reason. Preserve originals; do not automatically delete/move Gmail messages.
- [ ] Evaluate legitimate urgency/invoice requests as false-positive challenges and separate labelled phishing fixtures from the organizer corpus. Train only on consented/appropriate data; don't assert a phishing accuracy score from the shipping dataset.

Acceptance: obvious credential-harvest fixtures escalate, ordinary shipping payment discussions are not automatically called phishing, HTML is inert, and dismiss/release decisions are auditable.

### Drift monitoring

An unfamiliar email is an out-of-distribution signal. A changing distribution is suspected drift. Confirming concept drift requires evidence that the relationship between inputs and labels has changed, usually through reviewed labels. Do not declare verified concept drift from novelty alone.

- [ ] Version a reference distribution from reviewed development/training data: intent mix, representation distances, vocabulary/templates, confidence calibration, review rates and corrected-label errors. Keep demo and production baselines separate.
- [ ] Compare recent workspace windows to the reference; aggregate small workspaces cautiously. Start with configurable minimum 100-email windows and at least 20 reviewed outcomes for error-trend evaluation, then calibrate window sizes/thresholds on replay data. Low volume displays **Insufficient data**.
- [ ] Detect individual novel inputs for immediate review and sustained shifts for alerts. Separate traffic mix/seasonality, parser failures and provider-version changes from classification degradation. Require persistence or corroborating signals to limit alert noise.
- [ ] Alert includes affected window, baseline version, changed features, sample emails, reviewer disagreement, severity and recommended action. Route affected uncertain records into human review; preserve reliable unrelated processing.
- [ ] Alert lifecycle: open -> acknowledged/assigned -> investigated -> resolved or dismissed with reason. Cooldown/deduplication groups related alerts. Never silently retrain or replace the baseline from incoming predictions.
- [ ] A proposed replacement classifier/baseline uses reviewed labels, shadow evaluation, versioned approval and rollback. Resolve the alert only with recorded evidence.

Acceptance: replay a stable stream with no persistent false alert, then a documented distribution/label shift that produces an actionable escalation. Report detection delay and false-alert rate; thresholds remain tunable, not universal constants.

## 8. P6: progress and query chatbot

Expose **Ask DraftWise** beside the workspace and on case pages. Suggested questions: “What needs my attention?”, “Which drafts are waiting?”, “Why did this case fail?”, “What changed in the returned BL?” and “How do I correct this field?”

- [ ] Use a small allowlisted set of read-only tools: workspace summary, case/report details, issue timeline, job status and documented feature help. Tool arguments and queries are scoped server-side to the authorized workspace/session.
- [ ] Calculate counts/status with database queries, then let the model explain the results. Cite case/report IDs, field evidence and data timestamp; links open the relevant filtered page or evidence panel.
- [ ] Treat retrieved email/document content as untrusted quotations. Prevent arbitrary SQL, arbitrary URL fetching, cross-workspace search and model-initiated approval/sending.
- [ ] Clarify ambiguous case references, admit unavailable evidence and state when a job is still processing. Refuse unsupported claims about whether goods shipped or a BL was legally finalized.
- [ ] Respect retention/deletion for conversation data, cap tokens/context and expose provider outage as a recoverable state. Demo chat uses the demo workspace and its own budget.

Acceptance: a fixed query suite reproduces database counts, cites factual shipment statements and abstains on unknowns; prompt-injection and cross-tenant tests pass. No guarantee of zero hallucinations: enforce grounding and measure unsupported-answer rates.

## 9. P7: public site, branding and release engineering

Implement [the brand/site brief](BRAND_AND_SITE_PLAN.md), including every visual exclusion, image-generation asset, public/legal route and requested SEO item. Extract auth/app shell from the root layout so public pages render without session dependencies. Finish end-to-end demos before advertising an implemented feature.

Pricing: publish a genuinely available free sample demo; show team/pilot pricing as “Contact us” or “Coming soon” until the owner approves amounts, limits and billing. Do not invent a discount, customer testimonial, compliance certification or operational saving.

Domain: implement a configurable canonical origin now; final hostname and DNS deployment require the user's owned domain/hosting access. No fabricated hostname or localhost production canonical. Legal/operator facts and public Gmail consent verification are launch gates, not reasons to block local development.

## 10. P8: acceptance and measurement

- [ ] Meet every row in [PDF traceability](USE_CASE_TRACEABILITY.md), including basic classifications, seven-field reports, difficult formats, human corrections and retries.
- [ ] Run input-only predictions for all 520 emails; export exact organizer format; optionally submit only through documented `/submit`. Report scoreboard separately from human-review reliability and final holdout metrics.
- [ ] Run real browser flows for anonymous demo and a signed-in Google test user, Gmail import, verification, correction, returned revision, dashboard customization, safety/drift queue and grounded chat.
- [ ] Validate RLS, demo isolation, OAuth CSRF/replay, upload parser bounds, secret redaction, cost limits, injection handling, idempotency and stale-write rejection.
- [ ] Validate keyboard navigation, screen reader names, focus/dialog handling, contrast, 200% zoom and reduced motion. Target WCAG 2.2 AA through automated and manual checks, not an automated-only accessibility claim.
- [ ] Measure production build payload and route performance. Target public LCP <=2.5s, INP <=200ms and CLS <=0.1 under a documented representative device/network, then measure field data when available. Budgets are goals, not current performance claims.
- [ ] Refresh the manifest and docs after each phase; check/cross only evidence-backed tasks. Save known limitations, run IDs, fixture hashes and reproducible commands before a usage-window handoff.

## 11. Delivery order, effort and missing inputs

Suggested order: **P0 -> P1 -> P2 -> P3 -> P4 -> P5 -> P6 -> P7 -> P8**. Brand design can start alongside P1; public launch waits for P8. Core reliability takes priority over additional charts or marketing polish.

Rough engineering effort, not a Codex usage estimate: P0 1–2 days; P1 2–4; P2 4–8; P3 3–5; P4 2–4; P5 4–7; P6 2–4; P7 3–5; P8 3–5. Total 24–44 engineering days before external approval delays, with scope and labelled-data quality driving the range. Re-estimate after P0 and the first demo slice. Five-hour allowance consumption cannot be reliably converted to engineering days or guaranteed session counts.

Needed later, not blocking this plan or local demo:

| Input | Purpose | When needed |
|---|---|---|
| Google Cloud OAuth client ID/secret, Gmail API enabled, consent-screen test users | Real Google sign-in and mailbox import | P3; secrets in environment files |
| Owned domain and hosting/DNS access | HTTPS, canonical URLs and production OAuth callbacks | P7 |
| Legal operator name/contact, operating jurisdiction, retention/subprocessor decisions | Accurate privacy/terms and Google consent disclosures | Before public launch |
| Approved pricing, currency and usage limits | Honest paid-plan presentation | Before paid-plan publication |
| Dataset public redistribution permission or approved redactions | Public anonymous seed data | Before public demo launch |
| Reviewed classification/phishing samples and annotation time | Measured training/calibration and drift baseline | P2/P5 |
| AI spending cap and Gmail-data AI-processing policy | Provider budget enforcement and consent | Before real mailbox processing |

No additional password or API key should be pasted into chat. Existing credentials remain local and must be rotated before a public release because they were shared earlier.

## 12. Multi-file implementation destinations

These are planned files, not empty scaffolds to create now. Reuse existing modules where appropriate and regenerate OpenAPI-derived frontend types. All new tables carry workspace scoping, restricted grants and retention rules; apply numbered migrations to hosted deployments.

| Slice | Separate target files |
|---|---|
| Demo/import | `backend/app/api/demo.py`, `backend/app/services/demo_sessions.py`, `backend/app/services/dataset_import.py`, `backend/app/repositories/demo.py`, `scripts/build_demo_seed.py`, `database/migrations/004_demo_sessions.sql` |
| Review/quality | `backend/app/api/review.py`, `backend/app/services/review.py`, `backend/app/services/disambiguation.py`, `backend/app/benchmark/runner.py`, `scripts/train_classifier.py`, `scripts/evaluate_classifier.py`, `database/migrations/005_review_and_model_versions.sql` |
| Gmail | `backend/app/api/gmail.py`, `backend/app/integrations/gmail.py`, `backend/app/services/gmail_sync.py`, `backend/app/repositories/mailboxes.py`, `database/migrations/006_mailbox_connections.sql` |
| Overview | `backend/app/api/dashboard.py`, `backend/app/services/dashboard.py`, `frontend/components/dashboard/widget-layout.tsx`, `database/migrations/007_dashboard_preferences.sql` |
| Safety/drift | `backend/app/services/email_safety.py`, `backend/app/services/drift_detection.py`, `backend/app/api/alerts.py`, `database/migrations/008_safety_and_drift.sql` |
| Chat | `backend/app/api/chat.py`, `backend/app/services/chat.py`, `backend/app/services/chat_tools.py`, `frontend/components/assistant/assistant-panel.tsx`, `database/migrations/009_conversations.sql` |
| Public pages | `frontend/app/(marketing)/page.tsx`, `frontend/app/(marketing)/workflow/page.tsx`, `frontend/app/(marketing)/pricing/page.tsx`, `frontend/app/(marketing)/privacy/page.tsx`, `frontend/app/(marketing)/terms/page.tsx` |
| Application routes | `frontend/app/(workspace)/dashboard/page.tsx`, `frontend/app/(workspace)/inbox/page.tsx`, `frontend/app/(workspace)/review/page.tsx`, `frontend/app/(workspace)/alerts/page.tsx`, `frontend/app/(workspace)/settings/connections/page.tsx`, `frontend/app/demo/page.tsx` |
| Shared UI/metadata | `frontend/components/brand/wordmark.tsx`, `frontend/components/navigation/breadcrumbs.tsx`, `frontend/app/not-found.tsx`, `frontend/app/sitemap.ts`, `frontend/app/robots.ts`, `frontend/public/llms.txt`, `frontend/app/icon.png`, `frontend/app/opengraph-image.png` |
| Tests/docs | `backend/tests/integration/test_demo_isolation.py`, `backend/tests/integration/test_gmail_sync.py`, `backend/tests/unit/test_disambiguation.py`, `backend/tests/unit/test_drift_detection.py`, `backend/tests/integration/test_chat_grounding.py`, `frontend/tests/demo-journey.spec.ts`, `frontend/tests/gmail-import.spec.ts`, `docs/MODEL_CARD.md`, `docs/DEMO_DATA.md` |

Route groups preserve clean browser URLs. Move existing pages into the workspace group instead of leaving conflicting duplicate routes. Existing server/client contracts and migration numbering must be reconciled at implementation time.

## 13. Optional improvements after the requested release

Prefer **Why this needs review** evidence cards over raw confidence numbers; a daily priority summary over more widgets; saved team views over a complex dashboard builder; shadow evaluation over automatic retraining; and a short replayable demo over a static tour. Add team assignments and acknowledgement timers once the core queue is sound. Defer email sending, CRM integrations, billing automation and legal-release decisions to separately scoped work.
