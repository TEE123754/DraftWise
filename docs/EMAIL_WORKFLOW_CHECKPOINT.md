# Email workflow and demo checkpoint

## Implemented

The supplied email attachment manifest is the linkage source. Sample fetch reuses the seeded email identity and attachment records. It calls the same durable classification, extraction and verification handlers used by the application. Automatic source selection occurs only when one SI and one BL are identified and no existing verified case baseline would be replaced; other cases need source confirmation.

The email screen shows classification, method/fallback reason, contextual acronym evidence, document fields and exact source quotes, processing status, recommended action and a case link. The case retains its seven-field comparison, correction previews and revision history.

Demo inference is capped at nine provider calls per session with a 25-second timeout per call by default. AI is attempted on explicit review; provider failures, invalid structured output and allowance exhaustion fall back to grounded rules. Unresolved intent abstains. Numeric comparison and action planning remain deterministic. No benchmark answer key is sent to inference or used by rules.

Safety assessment is independent of intent. Corroborated credential pressure and executable attachments produce a hold; a reviewer must supply a release reason. Messages render as text, with no URL fetching. The detector is a limited static signal system, not an assurance of safety or a trained phishing model.

Dashboard metrics reconcile with tenant-scoped latest classifications, reports, cases, jobs and safety assessments. The user can save supporting section visibility/order; the case action queue remains visible. Quality monitoring requires a baseline from at least 20 distinct human-reviewed email labels and two separate windows of 20 new classifications. Sustained shifts create evidence-bearing alerts. Error changes are reported only when reviewed labels exist. No default fabricated baseline or confirmed concept-drift claim is made.

Real Gmail remains disabled. The user chose the labelled simulator for this checkpoint; OAuth credentials and real-account acceptance remain pending.

## Verification

- 97 backend tests pass against isolated PostgreSQL, including chained workflow, AI success/failure/quota, citations, sample deduplication, safety hold/release, preferences and drift state calculations.
- Eight existing browser tests and one new dashboard customization/accessibility test pass.
- Production Next.js build passes.
- Development Supabase migrations 008 and 010 applied. New application tables have RLS enabled and direct anon/authenticated grants revoked.
- Synthetic development evaluation: 10 messages, 80% rule accuracy/coverage, 20% abstention, 14/14 extraction checks and 7/7 comparison checks on one pair. `artifacts/quality/report-v1.json` includes the confusion matrix, per-class metrics and measured latency. This tiny development set does not estimate real-world accuracy.

## Remaining

- Finish live UI/provider acceptance and record actual methods and fallbacks.
- Independent held-out real-message labels, provider evaluation across all supported formats, calibrated confidence/drift thresholds and broader contextual disambiguation.
- Real Gmail OAuth, read-only import, incremental sync, disconnect, encrypted token handling and end-to-end consent testing.
- Richer phishing signals from trusted mail metadata, alert ownership/assignment and sustained reviewed-label concept-drift validation.
- Demo retention cleanup/reset and a fully processed sample library. Existing sessions created before this migration acquire safety assessments when processed; their unassessed count remains visible.

## Local use

Start the demo, open Inbox, and select **Simulate Gmail fetch** with `email_001`. Follow processing in the email page, inspect SI/BL field values and quotes, then open the document comparison. **Use local rules** explicitly selects deterministic review. A later re-run of a case with an existing report asks for source confirmation instead of overwriting the verified baseline. Dashboard preferences are saved for the current workspace and user.
