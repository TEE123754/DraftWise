# User experience specification

[Product specification](PRODUCT_SPECIFICATION.md) · [Frontend architecture](FRONTEND_ARCHITECTURE.md) · [Feature contracts](FEATURE_CONTRACTS.md)

## Experience principles

The default screen tells the operator what needs a decision, why, and what action moves the case forward. All technical details must support that decision. The first usable screen must not be an empty analytics dashboard, a chat prompt, or an upload form with unexplained configuration.

One case page owns the correction workflow. An operator should not move between independent extraction, confidence, review and report pages to resolve one issue. Those views become panels on the same page, preserving selected field, source scroll positions and unsaved edits.

## Navigation

Primary navigation: **Work queue**, **Inbox**, **Completed**. A clearly visible **Add documents** action opens an upload sheet in context. **Settings** contains supervisor rules and account options. **Quality lab** is admin-only and contains benchmarks; it is not part of the everyday task flow.

Route contract:

| URL | Purpose |
|---|---|
| `/dashboard` | Actionable case queue, default authenticated landing page |
| `/cases/[caseId]` | Resolve issues, view sources, preview request and inspect revisions |
| `/inbox` | Classified input emails and import controls |
| `/inbox/[emailId]` | Original message, attachments and link to its case |
| `/completed` | Searchable verified case history; clear seven-field scope |
| `/settings/rules` | Approved equivalence rules and impact review |
| `/settings/workspace` | Roles, supported limits and retention |
| `/quality/benchmarks` | Admin evaluation runs |
| `/login` | Authenticated workspace access |

Legacy `/verification/[reportId]` and `/review/[reviewId]` become redirects to the associated case with a selected report/issue. Deep links preserve immutable report access. Report cards never invent a case relationship for an unrelated document.

## Work queue

Above the list: page title, workspace selector, search, Add documents. Four tabs: **Needs you**, **Waiting**, **Checking**, **Checked**. Counts distinguish cases from emails. The initial tab is Needs you when nonempty, otherwise the first nonempty group.

Each case row shows: shipment/reference, customer when confirmed, concise blocker, latest draft label, last activity and the next action. Severity icons include text; no traffic-light score without an explanation. Optional confirmed deadline appears in local time with a timezone tooltip. Missing deadlines show nothing rather than an artificial countdown.

Examples of primary action labels: **Choose SI**, **Confirm weight**, **Review returned draft**, **Preview request**, **View checks**. “Process”, “Execute agent” and “Resolve confidence” are not operator-facing labels.

Selecting a row opens its case at the highest-priority unresolved issue. Shift-click/multi-select is limited to harmless administrative operations. Bulk clearance and bulk acceptance of ambiguous values are unavailable.

## Case workspace

```text
Work queue / Booking ABC123             Draft 3 · SI 2      Add new draft
----------------------------------------------------------------------
Needs review: 1 new weight change       5 matched · 1 fixed · 1 unresolved

[Issues and next action]     [Evidence and comparison]
Weight changed in draft 3   SI reference        Latest BL
Consignee fixed             22,000 KG           24,000 KG
                            [highlighted source regions]
Next action:
Confirm the required        How this was checked ▾
weight from SI 2.           All seven fields ▾

[Confirm source value]      [Preview correction request]
----------------------------------------------------------------------
Amendment history: Draft 1 → request → Draft 2 → Draft 3
```

This is a content hierarchy, not a fixed pixel layout. Wide layouts use an issue rail plus resizable evidence panels; smaller screens stack the decision above tabbed sources. The primary action remains visible without covering source values. Evidence opens at the actual cited page/cell; if coordinates are unavailable, show a text/table locator and explain the limitation.

Default issue view contains only unresolved/new/regressed items; a matched-fields disclosure exposes all seven checks. The summary always shows coverage so collapsing matches does not hide an incomplete comparison. Display raw values first and normalized values under “How this was checked.” Never show a model confidence percentage as the main conclusion.

## Guided resolution

1. Operator opens a case and sees one next decision.
2. Relevant SI/BL evidence is already selected.
3. Operator confirms a supported interpretation, enters a correction with evidence, or selects “I cannot confirm.”
4. Save creates a durable revision and shows a pending state without claiming success prematurely.
5. When checks finish, the same workspace displays the updated issue list and next action. Focus moves to the status announcement, not unexpectedly to another field.

Keyboard controls: arrow keys traverse issue rows when the list is focused; Enter opens evidence; Escape closes a sheet; standard Tab order remains complete. Optional letter shortcuts are disabled in text inputs and discoverable in a help dialog. No destructive or approval action has a one-key shortcut.

## Correction preview

The preview panel contains selected changes, resulting remaining blockers, a source-version badge, and an editable message. Mismatches with uncertain SI evidence are disabled with a specific reason. The button says **Copy request** or **Download request**; no sending integration is implied.

A preview is visually labelled “Proposed changes.” It cannot change the official check status. If the source changes during editing, preserve the user's draft text but show “A newer document is available. Refresh the proposed changes.” An unchanged message can be copied only after refreshing its evidence/version association.

## Returned-draft review

Uploading a new draft from the case automatically associates it only after a supported reference/role check. Show **Fixed**, **Still open**, **New change**, and **Could not verify** groups. A regression gets an explanation: “This matched SI 2 in Draft 2 and differs in Draft 3.” Do not say a carrier made a mistake when the source could not be read.

The complete seven-field verifier runs for every new draft. Caching may reuse unchanged source parsing, but the UI cannot equate file similarity with verification. Changing the authoritative SI clearly starts a new baseline and requires rechecking outstanding requests.

## Empty, loading and failure states

| State | Operator-facing text/action | Behavior |
|---|---|---|
| No data | “Add an email or a document pair to start.” | Offer supplied synthetic dataset import to authorized admins; label it as sample data |
| Uploading | Per-file byte progress and cancellation | Keep successful uploads if one fails |
| Parsing | “Reading the shipping instruction” | Do not invent completion percentages; show stage and elapsed time |
| Missing BL | “The draft BL is missing.” / Add draft | Preserve classification; never show matched |
| Wrong file | “This file appears to be an invoice.” / Replace or choose another | Show document-type evidence |
| OCR uncertainty | “The highlighted weight is hard to read.” / Confirm or replace | Show crop and source, not a generic AI error |
| Provider unavailable | “Checks are waiting for the service to recover.” / Retry when available | Persist work; show last known state |
| Stale review | “Another reviewer updated this case.” / Review changes | Preserve local draft; reject partial save |
| New document while editing | “A newer draft needs checking.” / Refresh comparison | Prevent stale correction export |
| Rule revoked | “A previous equivalence rule changed.” / Recheck | Preserve old report and mark it superseded/stale |
| Complete match | “No mismatch detected in the seven checked fields.” | Do not imply release/compliance approval |

## Visual system

Use Next.js, Tailwind and Shadcn UI primitives. Calm neutral background, high-contrast text, one primary action color, and limited status colors paired with labels/icons. Use a tabular numeral style for counts/weights. Keep party names selectable and wrap full names; truncation has an accessible expand action. Use ample spacing around source evidence rather than dashboard decoration.

Use `Dialog`/`Sheet` for uploads and previews, `ResizablePanel` for evidence panes, `Tabs` for narrow screens, `Table` for cases, `Alert` for blocking changes, `Badge` for state, `Tooltip` only for optional detail, and `Sonner` for transient acknowledgments. Critical failures remain inline and do not disappear as a toast.

Loading skeletons reserve layout and are hidden from assistive technology. Announce stage completion with a polite live region. Maintain focus traps in dialogs, visible focus indicators, WCAG AA contrast and a complete keyboard path. Support 200% zoom and 360px screens without making horizontal scrolling necessary for decisions; document canvases can pan separately.

## Usability acceptance tests

Targets below are hypotheses to measure with representative tasks, not product claims. Use synthetic documents and counterbalance test order.

| Task | Acceptance target |
|---|---|
| Find the next actionable case | A first-time reviewer selects an appropriate case within 15 seconds without assistance |
| Inspect a field's proof | At most one click from the issue to both source regions |
| Resolve a missing value | No navigation away from the case; exact changed value and source visible before commit |
| Prepare a correction request | Supported changes and remaining blockers visible before copy; no manual retyping of verified values |
| Review a returned draft | Reviewer correctly identifies a fixed issue and a newly introduced regression |
| Understand a clean outcome | Reviewer can state the seven-field scope and distinguish a preview from a completed check |
| Handle concurrent edit | User draft survives a 409 and can be compared with the saved version |
| Keyboard-only operation | Complete upload, evidence inspection and review without a pointer |

Instrument `case_opened`, `evidence_opened`, `decision_saved`, `preview_created`, `request_copied`, and `revision_reviewed` with case/version IDs and timestamps. Do not collect document content, keys or clipboard text. Report median task time, task completion, error count and evidence-open actions along with sample size.
