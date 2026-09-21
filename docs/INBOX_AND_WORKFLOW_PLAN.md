# Inbox and workflow: audit and implementation plan (2026-09-21)

Audit of the 20 requests against the running product, then a phased plan. The original audit below is historical; phase notes and the latest checkpoint record implementation progress.
Request IDs: **A1–A11** are the first list (inbox layout … AI score), **B1–B9** the second (IDs … reference codes).

## 1. Status of each request

| ID | Request | Status | Evidence and root cause |
|---|---|---|---|
| A1 | Inbox shows email → attachments (SI/BL) → classification → actions → extracted info (BL, SI, email match) | **Partial** | List rows show subject, sender, 2-line preview, an attachment *count* and a static action. The preview adds attachment names and labelled fields found in the email text. Missing: SI/BL roles, document extraction, email-vs-document match, classification method and evidence, state-specific actions (`frontend/app/inbox/page.tsx`). |
| A2 | Spam red | **Done for category only** | Red border and tint when `category === "SPAM"`. Emails held by the safety check (suspected phishing) but not categorised SPAM are not red. |
| A3 | Needs review yellow | **Wrong** | Yellow only when the email has *no category*. Missing SI/BL, wrong document, unreadable file, mismatch, held email: none are yellow (`getStatusColor`). |
| A4 | Checked / no problem green | **Wrong** | Every classified non-spam email is green, including all 220 BL comparisons whose documents were never read or compared. |
| A5 | Step-by-step workflow; boxed buttons; hover name + function | **Partial** | A 5-step workflow exists on the email page only. `Button`/`ActionButton` are boxes, but the sidebar nav, filter pills, alert buttons, "Show more", "End demo" are text/pills/inline styles (three button styles). Hints are native `title` attributes: no keyboard/touch support, no name+function format, none on nav or alerts. No tooltip component (only `@radix-ui/react-slot` installed). |
| A6 | Customizable dashboard | **Done, limited** | Toggle and drag-reorder of fixed panels, saved per workspace (`/dashboard/preferences`, covered by a Playwright test). No new state panels, no resizing, no date range. |
| A7 | Floating chatbot bubble bottom-right | **Done, limited** | Bubble, dialog, focus trap, suggestions exist (`app-shell.tsx`). Read-only workspace summaries chosen by keyword routing; unaware of the open page; cites cases only, never emails. |
| A8 | Update the workflow | **Partial** | In-app steps exist but describe a safety check for "sanctioned parties, restricted goods" that does not exist (only spam/phishing signals: `email_safety.py`). Public `/workflow` page still says mail is "imported from a connected Gmail inbox" (Gmail sync is a stub). |
| A9 | Extraction of email info not working | **Broken as expected** | (a) Demo seeding extracts documents for `email_001` only; the other ~250 attachments are never read (`demo_sessions.py`). (b) The "Extracted Info" panel shows only *labelled* fields found in the email text; these emails are prose, so it nearly always says "No fields extracted". (c) Nothing compares email details to the documents. |
| A10 | Something off in Quick Preview | **Bugs found** | See section 2. |
| A11 | Self-evaluation shows AI classifier score | **Not done** | `/analytics` shows the official rules-only score and a self-agreement figure. AI classifier results exist only in the CLI and docs. |
| B1 | Email_00N is the fetched email's own ID, not list position | **Bug confirmed** | Label is `Email_${index + 1}` from the row's position in the *current filtered list*; email_007 shows as Email_001 under a filter. Manual emails have random UUIDs as external ID. |
| B2 | Incomplete details / missing BL or SI / any problem = yellow | **Not done** | Same as A3. |
| B3 | Case lacking SI or BL shows it in the workflow | **Not done** | Case page shows "Not selected" for both tiles plus one generic sentence. The planner has a single `add_sources` action ("Add shipping instructions and a draft BL") whichever is missing. Email steps 3–4 say "Parsing begins after safety check…" with no missing-document state. |
| B4 | Check email classification | **Checked, findings below** | Sample: 520/520 by rules. Held-out: rules 48% (31 of 60 abstained), live AI 95%. The demo seed classifies by rules, then falls back to a git-ignored benchmark file (`artifacts/.../predictions.jsonl`); without that file, unresolved emails stay unclassified. |
| B5 | Classification looks messy (incomplete / checked / needs review) | **Root cause found** | The list API returns only category and attachment count; there is no single "review state" (see section 3). |
| B6 | Let users delete spam from the inbox | **Not done** | No delete endpoint or UI. |
| B7 | What can users do after an alert? | **Not done** | "Acknowledge" only sets a status flag. "Dismiss" saves the hard-coded reason "Dismissed after review" without asking. Sample emails appear as raw IDs, not links. No release / not-spam / delete / relabel / create-baseline action; the `investigated` state is unused. |
| B8 | Actions for emails without SI and BL | **Not done** | Nothing distinguishes "asked me to send the draft" from "claims attachments that never arrived" from "asks me to check documents that are missing". |
| B9 | Use reference codes to find SI/BL that aren't attached; local rules, no tokens | **Not done; data checked** | See section 4. |

## 2. Other issues found

1. **"Load more" drops the active filter.** It builds its query from `location.search` (empty), not from the category filter, so page 2 mixes categories. The list also loads 25 rows at a time and the search box filters only rows already loaded.
2. **Quick Preview.** Auto-selects the first email on load; keeps showing an email that is no longer in the list after a filter change (stale closure, eslint disabled); "Ref" shows a raw UUID for manual emails; recommended action is static per category and ignores missing documents; the SI-request action ("Create SI and open amendment case") describes the wrong task.
3. **Colour is the only signal** (border and dot). Needs text and icon for accessibility.
4. **AI cost is unbounded outside the demo.** "Review with AI" defaults to a live call; the per-session cap (9) applies to demo sessions only. The worker calls AI for any document with 3+ unread fields. The provider client does not back off on HTTP 429 (a burst of ~96 calls lost 54 answers) and ~5% of answers are unusable.
5. **Seed depends on an ignored artifact** (`predictions.jsonl`), which does not exist in a container image.
6. **Every BL email gets an empty case**, including those with no attachments, so the Cases page mixes real work with "waiting" items.
7. **Public workflow page** claims Gmail import that does not work yet.

## 3. Design decisions

### 3.1 One review state per email (computed on the server)

| State | Colour | When | Recommended action |
|---|---|---|---|
| Spam | Red | category SPAM, or safety says spam / suspected phishing | Confirm spam and delete, or mark not spam |
| Held for safety | Red | safety hold open | Inspect signals; release with a reason |
| Needs documents | Yellow | comparison request with SI and/or BL missing, or attachments claimed but absent | Ask sender for the missing document (draft reply), upload, or link an existing one |
| Waiting for draft | Yellow | asks for the draft BL to be sent; no files | Send/chase the draft; reopen when it arrives |
| Needs review | Yellow | unclassified, wrong document type, unreadable file, missing value, uncertain field | Open the case and confirm evidence |
| Mismatch found | Yellow | report status MISMATCH | Preview the correction request |
| Checked | Green | comparison with all seven fields matching | None |
| Classified, no check needed | Green (lighter) | SI request, invoice query or general mail, classified | Show the category-specific action |
| Processing | Grey | jobs queued or running | Wait |

Each row also carries **reason codes** (`missing_si`, `missing_bl`, `awaiting_draft`, `wrong_doc_type`, `unreadable`, `missing_value`, `mismatch:<fields>`, `unclassified`, `safety_hold`) rendered as text chips beside the colour.

### 3.2 Stable display ID
Show the email's own `external_id` (`email_007`) everywhere, sorted numerically. Manual emails get a short workspace sequence (`M-001`) at creation. The list position is never shown.

### 3.3 Token policy (default: no AI)
1. Rules first for classification, parsing, extraction, comparison and reference matching.
2. AI only when (a) rules abstain on classification, (b) a document has 3+ unread fields, or (c) the user clicks "Review with AI".
3. Every AI call is gated by a per-workspace daily budget, paced, retried with backoff on 429, and cached by content hash (never called twice for the same email or document).
4. Batch and seed jobs run with AI **off**. The UI shows "AI calls used: n / budget".

### 3.4 Actions when SI and/or BL are missing

| Situation | Detection (local rules) | Actions offered |
|---|---|---|
| Asks for the draft to be sent, no files | `requests_draft` and no attachment claim | "Waiting for draft"; copy a chaser message; reopen on arrival |
| Claims attachments, none arrived | `attachments_expected` and no files | "Ask sender to resend" (draft reply); upload manually |
| Only SI or only BL present | roles of attached documents | Name the missing one; ask sender; upload; link by code |
| Wrong document type in a slot | role detection | Ask for the correct document |
| Unreadable file | parse failure | Ask for a readable copy |
| Missing SI/BL found in another email | reference code match (section 4) | "Suggested link": confirm to attach |

## 4. Reference codes: what the data says

Checked on the supplied 520 emails with local rules only (no tokens):
- **0 of 94** attachment-less BL-comparison emails cite an SI/BL identifier (B/L no., booking ref, OC no.) that appears in any attachment. The one token they share with other emails is a *vessel voyage code*, not a document reference.
- **108 of 116** emails with attachments cite an identifier found in their *own* documents, so a cheap "email matches its documents" check is possible; **0** cite another email's identifier (no mix-ups).
- **0 identifiers** appear in more than one email's attachments, so there are no re-sent or revised drafts in this sample.

Consequence: local code matching is worth building (free, and it powers the email-vs-document match and thread linking in real mailboxes), but on this dataset it will not rescue attachment-less emails. For those, the right action is asking the sender (section 3.4). Rule: exact normalized match only, shown as a *suggestion* the user confirms; never auto-link.

## 5. Implementation plan

Effort is a rough estimate in working days for one developer.

### P0. Decisions (0.5 d) — see section 7

### P1. Review state and list API (2 d) — DONE 2026-09-21

Implemented: `backend/app/services/email_state.py` (`derive_state`, pure), `backend/app/repositories/emails.py` (one read-model query), `GET /emails` (state, reasons, documents, case, display ID; server-side `state`, `category`, `q`, paging with `total`), `GET /emails/counts`, and the same fields on `GET /emails/{id}`. Tests: 26 unit tests including an exhaustive invariant (nothing is green unless a BL comparison actually passed) and 2 PostgreSQL integration tests. Measured on the demo mailbox before P2: 520 emails, states spam 32, held 8, processing 1, needs_documents 3, waiting_for_draft 91, needs_review 125 (all "documents not read yet"), classified 260, checked 0, mismatch_found 0; counts in ~1 s (fine for hundreds of emails; P2 can store the state to make it constant-time). Not changed in P1: the inbox UI (P3) still colours by category, and the display ID fix is API-only until P3 uses `display_id`.

Original scope:
- New pure function `derive_state()` in `backend/app/services/email_state.py` implementing section 3.1 from: category, safety, attachments and roles, extraction status, latest report status, case readiness.
- `GET /emails` returns `state`, `state_reasons`, `documents {si, bl, other}`, `case {id, readiness}`, and accepts `state`, `q` (server-side search), numeric order by external ID. Add `GET /emails/counts` for filter badges. Fix pagination.
- Tests: table-driven unit test per state and reason; PostgreSQL API test.
- **Done when:** the counts of all states sum to the number of emails; no BL email without a compared report is green.

### P2. Automatic offline processing (2 d) — DONE 2026-09-21 (see the notes at the end of this section)

Implemented: `backend/app/services/offline_processing.py` (`queue_offline_processing`: one query finds comparison emails with unread documents, skipping held, already-active, non-comparison and unclassified mail; three statements create every job and workflow row; every job carries `prefer_ai: false`); the demo seed calls it and no longer reads the git-ignored predictions artifact or opens empty cases for emails with no files; `GET /workspace/processing` (eligible / read / compared / failed / waiting / active, plus the number of AI-produced extractions and classifications, which stays 0) and `POST /workspace/process` (operator). Switch: `DEMO_OFFLINE_PROCESSING` (default on). Worker: verify jobs run before extract jobs (each email finishes end to end), 3 concurrent slots, heartbeat and lease recovery throttled, demo-status check cached 30 s, source blocks and discrepancies inserted in one statement each.

Bug fixed along the way: a report with a real mismatch plus a blank value violated `verification_reports_check1`, so the worker's save failed. Migration `012_mismatch_reports_may_be_incomplete.sql` (also applied to the development database) replaces it with `verification_reports_status_consistency`; `database/schema.sql` matches.

Tests: end-to-end (seed → real worker handlers with an AI stub that fails on any call → inbox states, zero AI calls, mismatch-plus-blank saved, a truncated PDF reported as unreadable), queue eligibility and idempotency, progress endpoints, constraint regression (7 cases). 210 backend tests pass.

Measured on the real 520-email demo mailbox against the hosted database (~100 ms per statement): seed 7.2 s (was 43.8 s before batching the queue); all 126 comparison emails read and compared in **521 s** with 3 worker slots, 0 failed jobs, **0 AI extractions and 0 AI classifications**. Final states: mismatch found 46, checked 63, needs documents 13 (5 wrong document, 3 attachments dropped, 2 SI only, 3 unrecognised scans), needs review 7 (5 missing value, 2 unreadable files), waiting for draft 91, classified 260, spam 32, held 8. The 46 mismatches and the 5 / 5 / 5 / 5 review cases match the dataset's designed defects and edge cases. The time is dominated by database latency (about 45 round trips per email); a deployment next to its database should be roughly 20 times faster. If an instant demo is needed, precomputing a seed pack (extractions and reports stored with the dataset) is the next step; it was not done because it would duplicate the worker's persistence code.

Known limits: the queue does not prioritise the emails currently on screen (it works in ID order, so the first inbox page fills first); held emails are read only after release; emails whose job failed are not retried automatically.

Original scope:
- On demo seed and on import, enqueue classify → parse → role → extract → verify for every email with attachments, **AI off**. Priority to the currently visible page. `GET /workspace/processing` reports progress ("Reading documents 87/250").
- Seed classifies by rules only and no longer reads the ignored artifact; unresolved emails become "Needs review" until AI is used on demand.
- Cases created only for emails with something to compare or a real follow-up.
- **Done when:** after seeding, all 250 attachments are extracted without any provider call, and the states from P1 are populated (measure the time).

### P3. Inbox redesign (3 d) — DONE 2026-09-21

Implemented: rows show the email's own ID, a state chip (icon, text and colour), reason chips, SI/BL found/missing chips, sender, category and method (`frontend/components/inbox/`). The preview follows the requested order (Email, Attachments, Classification with method and evidence, Actions, Extracted info) with an SI | BL | Email table whose cells carry a text mark and a source quote; `GET /emails/{id}` gained `classification_summary` and `field_table` (`backend/app/services/email_preview.py`). Filters by status and type with server counts, server-side search, a working "Load more", no auto-selected row, filters kept in the URL (`/inbox?state=held`), and a multi-select mode that reads and compares without AI. Bugs found by the tests and fixed: a click within 300 ms of load lost its selection; polling stopped when a filter hid every processing row.

Also found and fixed: on the 520 supplied emails **all 128** ports the email extractor took from a subject line were wrong ("TO CONFIRM DOCS" gave a port of discharge of CONFIRM). A port is now taken from a subject only when explicitly labelled (`POL: SGSIN`); port of discharge dropped from 253 to 125 values, matching the 125 labelled loading ports and weights. Display only: no scored result depends on it.

- Row: stable ID, subject, state chip (text + icon + colour), reason chips, SI/BL chips (found / missing), sender, category, method.
- Preview panel in the requested order: **Email → Attachments (SI, BL) → Classification (method, evidence) → Actions → Extracted info** as a three-column table SI | BL | Email with match / mismatch / missing marks and evidence.
- Filters by state and category with counts; server-side search; working "Load more"; no auto-selecting the first row; multi-select mode.
- **Done when:** a Playwright test covers each state colour and reason, the filter counts, and that email_007 keeps its ID in every filter.

### P4. Case page and workflow (2 d) — IMPLEMENTED 2026-09-21
- Planner action kinds: `request_si`, `request_bl`, `request_both`, `await_draft`, `resend`, `upload`, `link_existing`, `close`. Case page names exactly which document is missing and offers the actions in section 3.4, including a copyable draft reply (template, no AI).
- Rebuild the email workflow as 6 steps: Intake → Classify → Documents (found/missing) → Extract → Compare → Decide/Reply; correct the safety-step copy to spam and phishing signals.
- **Done when:** a case with no SI, no BL, or neither shows that fact and the right action.

### P5. Reference matching (2 d) — DONE 2026-09-21
- `backend/app/services/references.py`: labelled identifiers (B/L no., booking, OC no.) plus generic codes from the email and from documents; table `document_references`; suggestions and the email-vs-documents check; chips in the preview.
- **Done when:** on the sample, 108/116 emails show "matches its documents", 8 are flagged, and no false link is offered.
- **Measured** (`scripts/measure_references.py`, all 520 emails and 250 attachments, offline): of the 126 emails with readable documents, labelled references match their own documents for **66**, 8 cite an identifier their documents lack, 52 cite none. Adding a wider generic code (two to five capitals then six to twelve digits, e.g. `SIN525534192`, used only for this advisory check, never to link) gives **75 matches, 3 flagged, 48 citing none**. The 108/116 of the earlier audit was not this implementation's result and is not reproduced. For the 94 attachment-less comparison emails it offers **0** link suggestions, so no false link is offered; no email cites another email's identifier. `GET /emails/{id}` returns `reference_check` and the preview shows each cited code as in / not in its documents.

### P6. Spam removal and alerts (2 d) — DONE 2026-09-21
- Soft delete (`deleted_at`, `deleted_by`, `deleted_reason`), `DELETE /emails/{id}`, bulk delete, restore, Trash view, purge after 30 days, audit trail. Non-spam deletion needs a reviewer and a reason.
- Alerts: per-type actions with a required reason. Safety alert → open email / not spam (relabel and release) / confirm spam and delete. Drift alert → review sample emails / create baseline / relabel. Sample emails become links; use the `investigated` state; remove the hard-coded dismiss reason.
- **Done when:** a spam email can be deleted and restored, and every alert offers at least one action beyond a status flag.
- **Physical storage cleanup** (migration 015, `services/storage_cleanup.py`): purging an email queues each uploaded object nothing else uses (a linked copy holds its source's key inside its own, so those are kept); the worker deletes queued objects, retrying with a growing pause up to 8 attempts, treating "already gone" as done, and re-checking before each delete in case a link appeared. Bundled demo files and link keys are never deleted. Tested with a fake storage and a `Storage.delete` unit test; not run against real Supabase Storage.

### P7. Design system (2 d) — DONE 2026-09-21

One `Button` (primary, secondary, ghost, danger, link; `default` and `outline` kept as old names) and a `Tooltip` showing a name and a one-line function on hover, keyboard focus and touch, dismissible with Esc, drawn in a portal so the sidebar cannot clip it (`frontend/components/ui/`). The sidebar, filters, alerts, rules, dashboard, demo and sign-in controls all use it; the sidebar destinations are boxed buttons. `tests/design-system.spec.ts` fails on any raw `<button>` outside `components/ui/`. Touch is tested with synthetic pointer events, not a real device.

- One `Button` (primary / secondary / ghost / danger) and a `Tooltip` component with **name + one-line function**, keyboard-focus and touch support. Sidebar, filters, alerts and all inline-styled buttons move to it. A test fails on new raw `<button>` elements outside the component.

### P8. AI classifier score in Analytics (1.5 d) — DONE 2026-09-21

Migration 014 (`ai_usage`, `ai_cache`, `quality_runs`); `GET/POST /quality/ai-classifier`, `GET /quality/ai-usage` (`backend/app/api/ai_quality.py`); the panel on `/analytics` shows rules, AI and rules-then-AI accuracy, the unusable-output rate, latency, per-category counts and the sample size. **Measured on the 60-email held-out set** (written independently of the supplied sample): rules 29/60 = 48.3% with 31 undecided, AI 57/60 = 95.0% with 3 unusable answers, rules then AI 58/60 = 96.7%, scored from AI answers saved earlier at **no new cost**. A live evaluation needs an administrator, the exact call count confirmed, enough budget and no run in progress; it runs paced in the background and waits out rate limits. It was exercised only with a stub provider: **no real provider call was made in this work.** The older Analytics section, which called agreement with this project's own report "ground-truth", is relabelled.

- Table `quality_runs`; an "AI classifier" panel next to the rules score showing rules, AI and combined accuracy, unusable-output rate and latency, with the sample size.
- A budgeted evaluation: a stratified sample (default 60 emails), paced calls with backoff, cached by content hash, confirmation showing the call count first. The held-out set results are linked.

### P9. Dashboard (1 d) — DONE 2026-09-21

New "Needs my attention" (most urgent first, `GET /emails?attention=true`) and "Emails by state" panels, each linking into the filtered inbox; panels have labelled checkboxes and keyboard "Move up / down" buttons (drag still works); the view is saved per user and workspace and comes back after a reload. This also fixed the `workflow-controls` test that had been failing on unnamed checkboxes.

- Add state-count panels and a "needs my attention" panel; keep the customization. Verify persistence across sessions.

### P10. Chat and documentation (1 d) — DONE 2026-09-21

The assistant sends the open page (email or case) with each question; rule-routed intents answer "this email / this case", "what needs my attention" and "which emails are missing documents" from the inbox, cite emails by their own ID as links, and never describe another workspace's email. The public `/workflow` page describes the six real steps, the colours and the token policy and no longer claims Gmail import; pricing lists the Gmail connection as not yet available. API contracts, `.env.example` and this plan are updated.

- Chat becomes aware of the current page and links answers to emails, not only cases; still rule-routed and free.
- Rewrite the public workflow page; remove the Gmail claim until it works; update the README and plan.

### Suggested order
P0 → **P1 → P2 → P3** (fixes A1–A5, A9, A10, B1, B2, B4, B5, about 7 days) → P4 → P6 → P5 → P7 → P8 → P9 → P10. Total about 18 working days.

## 6. Test and risk notes
- Regression gate after every phase: sample predictions identical to the 1.000 run (`organizer-eval-03`), `eval_heldout.py --no-calls` unchanged, backend suite and Playwright green.
- Migrations needed: soft delete columns, `document_references`, `quality_runs`, optional email sequence.
- Playwright tests use mocked API responses, so each phase also needs one live check (`smoke_demo`-style) through the real worker.
- The frontend runs a Next.js version that differs from common docs (`frontend/AGENTS.md`); verify new APIs by building, since `node_modules/next/dist/docs` is not present.

## 7. Decisions needed
1. Colour for classified mail that needs no document check (SI request, invoice, general): light green (recommended) or neutral grey?
2. Mismatch found (real defect): yellow "needs action" (recommended), or its own colour?
3. Spam deletion: soft delete with Trash and restore (recommended) or permanent?
4. AI budget default (proposal: 30 calls per workspace per day, AI off for batch and seed) and OK to spend about 60 calls once for the analytics AI score?
5. Should "waiting for draft" emails stay in the main inbox as yellow (recommended) or move to their own tab?


## P4–P6 checkpoint (2026-09-21)

Completed tasks:
- [x] ~~Name missing SI, BL, or both in the case and email workflow; provide a local, editable, copyable follow-up reply.~~ No email is sent automatically.
- [x] ~~Six workflow steps: Intake, Classify, Documents, Extract, Compare, Decide/Reply.~~ Safety copy describes implemented spam/phishing signals.
- [x] ~~Upload missing/readable documents and enqueue local review with AI off.~~ Document follow-up refreshes after processing.
- [x] ~~Exact labelled BL/booking/OC reference extraction, evidence cache, own-document checks and confirmed same-workspace suggestions.~~ Linked copies enter the normal offline worker. Held, spam and trashed sources are excluded. Voyage and fuzzy matches never auto-link.
- [x] ~~Reasoned single/bulk soft delete, Trash page, restore within 30 days, reviewer-only non-spam removal, audit records and job fencing.~~ Restore does not silently resume processing or change Gmail.
- [x] ~~Worker purges expired Trash database records after 30 days.~~ Uploaded object keys remain in audit records for administrator cleanup; physical storage deletion is not implemented.
- [x] ~~Alerts link source emails and record investigation reasons; safety actions relabel/release or confirm spam and move to Trash.~~ Drift alerts link samples and offer baseline creation using reviewed labels. Closed alerts reject repeat actions.
- [x] ~~Migration 013 applied to the development database; local API and worker restarted.~~

Verification checkpoint: full backend suite **239 passed** before final hardening; new browser suite **3 passed**, including mobile overflow and axe checks. Existing browser regression suite: **19 passed, 1 failed**; the failing dashboard-customization test concerns existing missing accessible control names/keyboard reorder (P9), outside P4–P6. Production build passed before final refresh/safety hardening. Final affected-test/build/live results are recorded below when available.

Remaining:
- [ ] Implement retriable physical uploaded-object cleanup after retention, preserving bytes still referenced by linked documents. Database purge is not a claim of full storage erasure.
- [ ] Measure this conservative labelled-reference implementation against all supplied records; the earlier 108/116 audit is not this implementation's measured result. Generic-code support and preview reference chips remain pending.
- [ ] Complete the P9 dashboard accessibility/customization regression separately.
- [ ] P7–P10 remain outside this implementation scope.


### Final verification, before usage limit

- Production build: **passed**, all 21 pages generated, including `/trash`.
- Final affected backend tests: **6 passed, 233 deselected**, including confirmed reference linking through the real offline worker and full compared-case database purge. An enum-comparison regression found during hardening was fixed and retested.
- Final targeted browser tests: **7 passed** (document follow-up, confirmed link, Trash restore, spam alert action, failed-alert retention, page reliability and assistant credentials).
- Live production frontend on localhost:3000 and API on localhost:8000 restarted; API health is `ok`. Fresh-demo live check passed missing-document replies, spam Trash/restore, alert investigation and mobile layout, with no browser errors and no AI requested; evidence: `artifacts/p4-p6-live.json`. The first attempt timed out against the old frontend process; restarting it with the new build resolved that.
- P5 full-sample acceptance and physical uploaded-storage deletion remain unchecked above. The existing dashboard test failure is not claimed fixed.


## Final checkpoint: all phases (2026-09-21)

Token policy (section 3.3) is implemented: rules first everywhere; every worker AI call goes through `BoundedAI`, which caches each distinct input per workspace, counts it and stops at `AI_DAILY_BUDGET` (default 30 a day; demo sessions keep their own allowance of 9), falling back to the rules; the email page and Analytics show "AI calls used: n / budget". The Morpheus client still fails fast on HTTP 429 with a retryable error, as its contract test requires: the durable worker chooses the retry time, and only the live evaluation, which has no durable retry, waits and retries itself.

Decisions taken (defaults): classified mail is light green; a mismatch is yellow; deleted spam goes to Trash with restore for 30 days; the AI budget is 30 calls per workspace per day with AI off for batch and seed jobs; "waiting for draft" stays in the main inbox as yellow.

Verification:
- Backend: **273 passed** in the full suite against an isolated PostgreSQL (including integration tests of `GET /emails/{id}`, budget and cache, evaluation gating, assistant, references, storage cleanup and tenant isolation).
- Frontend: type check clean; production build passes (21 pages); **41 browser tests**. The full run had 39 pass and 2 case-page tests time out on a cold dev-server compile; those passed 7 of 7 on two reruns, and the test timeout is now 60 s.
- Live, through the real API and worker against the hosted development database on a fresh demo session: 520 emails, every state count sums to 520, no email is green without a real SI and BL comparison, 0 AI calls; the dashboard panels, URL filters, reference chips, tooltip, assistant and the AI score panel were exercised on screen. Migrations 014 and 015 were applied to the development database.

Not verified, and not claimed:
- No live AI provider call was made, so the live-evaluation path is proven only with a stub; the cached scores are from answers saved earlier.
- Physical storage deletion has not run against real Supabase Storage; there is no administrator screen for `storage_cleanup` (rows in the database show state, attempts and last error).
- The sample-mailbox "Simulate Gmail fetch" still asks for AI; it is bounded by the demo allowance.
- The held-out and 520-email regression gates (`eval_heldout.py --no-calls`, the organizer scorer) were not rerun: nothing in classification, extraction or comparison was changed except subject-line port extraction, which no scored result uses.
- The API and worker already running on port 8000 were started before these changes; restart them (and apply migrations 014 and 015 to any other database) to use the new endpoints.

## Follow-up: open items closed (2026-09-21, later)

- **Services**: the API and worker on port 8000 were restarted on the current code (the old run had two duplicate workers), and the `next start` frontend on port 3000 was rebuilt.
- **Migrations**: `scripts/check_migrations.py` reports what each migration file creates that a database lacks. The development database was missing **006 (Gmail connections) and 009 (conversations)**; they were applied together with the new **016**, which enables row level security and revokes client access on those three tables. Development is now complete through 016. Test and CI databases apply every file in order. Run the script against any other database before use.
- **Demo sessions**: none were live. The session left open earlier had ended and been purged.
- **Git**: the project is a git repository with a baseline commit, so changes can be reviewed and rolled back.
- **AI only when asked**: `prefer_ai` now defaults to false for `POST /demo/gmail/fetch` and `POST /emails/{id}/process`, and "Simulate Gmail fetch" sends false.
- **Dashboard**: "Failed processing" counts non-trashed emails whose latest job failed, and links to `/inbox?failed=true`, a real filter (removable chip, kept in the URL). It no longer approximates this with "Needs review".
- **File deletion**: checked against real Supabase Storage (upload, delete, confirm gone, delete again). That found a real bug: Supabase reports a missing object as HTTP 400 with `statusCode: "404"`, which was treated as an error, so a retried delete could end as "failed". It is fixed and unit-tested with the recorded response. Administrators have a panel on `/trash` (`GET /storage-cleanup`, `POST /storage-cleanup/{id}/retry`) with counts, failed files and a retry button.
- **Read without AI**: exercised live in a demo workspace on an email whose SI and BL were unread, through the real button, API and worker, with no AI call.
- **Gmail tokens**: sealed with Fernet (`TOKEN_ENCRYPTION_KEY`; Gmail cannot be connected without it). Disconnect revokes the grant with Google and erases both tokens; if Google cannot be reached, the tokens are still erased and the user is told to remove access in their Google Account. The address is no longer put in the redirect URL, and the OAuth state no longer falls back to a fixed signing key. Real Gmail sync is still a stub.
- **Lint**: `ruff check backend` passes (was 38 errors).
- **Regression gates rerun offline**: organizer scorer 1.000 on the 520-email sample (`artifacts/benchmarks/organizer-eval-04`); held-out rules-only unchanged (classification 29/60, fields 224/224, 0 false alarms). `benchmark.py` no longer crashes on a cp1252 console before saving the scoreboard.

Still open: a fresh held-out set with new wording (rules-only classification is 48% on unfamiliar mail); a live AI evaluation (needs that new set, and costs provider calls); real-device touch testing; real Gmail sync; container runs and deployed smoke tests; an independently reviewed accuracy evaluation.
