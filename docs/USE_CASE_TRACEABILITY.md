# Shipping use-case requirements and acceptance

Source: all four pages of `Shipping Document Verification Use Case.pdf` in the workspace. The actual source resides in `Downloads/[!] Problem Statement`, with a directory separator after `Downloads`. No dataset README instructions were used. This document records required behavior, not a claim that implementation is finished.

## PDF requirements

| ID / page | Source requirement | Existing evidence / gap | Completion gate |
|---|---|---|---|
| PDF-01 / 1 | Start from an inbox and produce a clear result for each email | Manual intake exists; bulk import absent | P0/P1/P3: import all 520 IDs; every email shows classification, pending, failed or review state; no silent omissions |
| PDF-02 / 1 | Classify comparison requests, new SI requests, invoice queries, general messages and spam | Five-class model/rules exist; domain accuracy unmeasured | P2: held-out five-class confusion matrix, per-class metrics and review coverage; misleading subjects/quoted intent tested |
| PDF-03 / 1 | Only comparison requests continue to checking; other classes need classification only | Existing classification and verification jobs need orchestration acceptance | P2: noncomparison emails do not launch SI/BL verification automatically; ambiguous intent escalates |
| PDF-04 / 1 | Read corresponding SI/BL attachment fields; SI is the intended reference | Labelled parsing, role checks and source selection exist | P2: confirm document roles/shipment relationship, retain evidence; cannot silently swap SI and BL or mix shipments |
| PDF-05 / 1 | Recognize equivalent field labels such as Port of Loading and Load Port | Label aliases exist; complex context incomplete | P2: WSD/label fixture suite includes aliases, port direction, gross/net, package/container and conflicting headings |
| PDF-06 / 1–2 | Compare exactly seven fields | Seven-field domain/report models implemented | P2/P8: shipper, consignee, notify party, loading port, discharge port, container count, gross weight kg each present exactly once with traceable decisions |
| PDF-07 / 2 | Identify the checked email, mismatch and fields needing attention; side-by-side values | Case report and evidence viewer exist | P4/P8: email identity, pinned source versions and SI/BL values visible; normalized meaning and original units remain explainable |
| PDF-08 / 2 | All seven match: display “No mismatch detected” | OK state exists; exact UX wording needs check | P2/P8: wording only for complete supported matches; absent values, preview-only changes and failed reads never clear the case |
| PDF-09 / 2 | Example: SI 3 containers, BL 4; equal weight 22,000 kg | Numeric comparison and synthetic amendment test exist | P2/P8: flag only container count; show SI 3 / BL 4; no false weight discrepancy |
| PDF-10 / 2 | PDF and Word tables and varied page layouts | Parsers exist; advanced layout acceptance incomplete | P2: evaluate supplied PDF/DOCX plus table fixtures with correct field locations and selective escalation |
| PDF-11 / 2 | Scanned/image-only pages using OCR/vision | OCR adapter exists; live recovery incomplete | P2: image-only and hybrid-page tests, evidence coordinates and quality gates; unreadable pages become review cases |
| PDF-12 / 2 | Messy formatting/labels, misleading subjects and missing attachments; distinguish mismatch from read issue | Some conservative gates exist | P2: formatting-only differences do not create false mismatches; missing attachment is a review reason, not a guessed value |
| PDF-13 / 1–2 | Ask a person with source evidence and reason; allow confirmation/correction and update report | Review display exists; correction persistence/recompute incomplete | P2: reviewer changes a grounded field, an immutable revision is created, dependent fields/report recompute and old report remains auditable |
| PDF-14 / 2 | Fail visibly and permit retries | Worker/failure projection/retry implemented and tested locally | P8: live quota/timeout/OCR failure visible; retry is bounded and idempotent; stale worker cannot overwrite a newer case |
| PDF-15 / 3 | JSON inbox + referenced attachments; static bundle or Docker access | Local CLI and input data present | P0: adapters agree on IDs/bytes, safe missing-reference handling and import progress; neither README nor private answer key enters processing |
| PDF-16 / 4 | Optional evaluation: one JSON object keyed by every email_id, agreed sample shape, `/submit` | Export exists; full runner/score unmeasured | P8: schema-validated all-email export and reproducible run; call only evaluator endpoint; preserve review states internally even if scorer format is narrower |
| PDF-17 / 4 | Score is developmental, not a complete assessment; inspect evidence for disagreement | Documented, not measured | P8: publish scoreboard separately from review quality, format slices, regression failures and source-supported disagreement notes |

XLSX is supported because 22 supplied inputs use it and it is in the existing scope; it is an additional format, not a fabricated explicit PDF requirement. Gmail, chatbot, drift, phishing detection, pricing and the landing page are the user's extensions. The PDF encourages advanced reliability, but does not require supervised training or Gmail integration.

## Eleven requested extensions

| Request | Delivery slice | Acceptance evidence |
|---|---|---|
| 1. No-login demo from supplied data, every feature accessible | P1 and parity checks in P8 | Fresh browser enters seeded isolated workspace; all completed workflows exercised; real external credentials are never bypassed |
| 2. Gmail fetching via Google login | P3 | Explicit mailbox permission, bounded real import, incremental sync, disconnect and duplicate protection |
| 3. Clean/customizable dashboard with summary/progress | P4 | Saved layouts; counts reconcile; every widget drills down; mobile/keyboard tests |
| 4. Progress/query chatbot | P6 | Authorized tool results, timestamps/citations, unknown-answer handling and injection/isolation tests |
| 5. Concept drift with human escalation | P5 | Stable/shift replay, insufficient-data state, labelled error evidence, owner/acknowledgement/resolution |
| 6. Phishing/spam identification | P2/P5 | Five-class spam metrics plus independent suspected-phishing signals; malicious/benign fixture evaluation |
| 7. Landing/workflow/pricing/consent/terms/privacy with generated visuals | P7 | Public routes render without auth; truthful content/consent records; assets generated and inspected |
| 8. DraftWise brand, logo, slogan and UI exclusions | P1/P7 | Brand/design checklist and 360px/desktop visual review; feature help and evidence-first actions |
| 9. Domain/routes/404/SEO/metadata/assets/performance | P7/P8 | Each item in the site brief checked; private/demo pages excluded from indexing; domain verified after supplied |
| 10. Trained classification, WSD and no hallucinated claims | P2/P6 | Versioned labelled corpus, held-out scores, contextual ambiguity tests, grounding and abstention; no absolute accuracy guarantee |
| 11. Every source PDF capability | P0/P2/P8 | All PDF rows above have passing tests or explicit release blockers, not merely implementation files |

## Release evidence ledger

Create a validation record per gate with commit/source manifest, model/prompt/parser versions, environment, command, output, timestamp, reviewer and remaining limitation. Treat mocked browser APIs, local PostgreSQL scaffolding and live Supabase checks as different evidence categories.

Do not repeat the earlier broad claim that signed uploads “all pass”: reserving a signed URL does not prove byte upload, download, immutability or tenant isolation. Each receives its own live acceptance check. Similarly a one-object LLM smoke response does not demonstrate document extraction accuracy.
