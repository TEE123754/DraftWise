# Product specification

[Implementation plan](../IMPLEMENTATION_PLAN.md) · [User experience](UX_SPECIFICATION.md) · [Feature contracts](FEATURE_CONTRACTS.md)

## Product direction

Build a shipping-document amendment workspace for an operations reviewer who must get a draft BL corrected before it is finalized. The central object is a shipment case with open issues and a next action. Emails and documents are evidence attached to the case.

The main product promise to test is: a reviewer can move from a problematic draft to a verified correction with fewer document searches, fewer repeated decisions, and no silent loss of a previously correct value. This is a product hypothesis, not a measured outcome.

Classification, OCR, seven-field extraction, comparison, confidence labels, history and benchmark scores are required capabilities. They do not, individually, establish differentiation. The distinctive implementation is the complete amendment cycle: identify the unresolved issue, gather the minimum missing evidence, preview a precise correction request, ingest the returned draft, and explain what was fixed or newly broken.

## Competitive evidence and limits

Reviewed on 18 September 2026. Public feature pages describe capabilities; they do not establish comparative quality or prove the absence of a feature.

| Publicly advertised capability | Source | Design consequence |
|---|---|---|
| Incoming-email BL recognition, shipment matching, SI comparison and amendment requests | [BuyCo AI](https://buyco.co/buyco-ai/) | Do not claim that comparing documents or generating amendment text is unique |
| Broad document ingestion and cross-document verification | [Pysar](https://www.pysar.ai/) | File-format coverage and a diff table are baseline expectations |

The differentiation is a focused workflow to validate through usability and accuracy tests, rather than an unsupported claim that competitors cannot offer it. The supplied hackathon data measures classification and defects; it does not measure the amendment experience. Add independent revision fixtures and user task measurements to evaluate that experience.

## Primary user and scope

Primary user: a shipping operations reviewer handling a queue of draft BLs and incoming corrections. Secondary user: a supervisor who confirms ambiguous instructions, manages approved equivalence rules, and checks quality. The seven mandatory fields remain the automatic verification scope. No screen implies legal, customs, cargo-release or whole-document compliance approval.

Baseline input is the supplied JSON inbox plus user uploads. The UI must not imply a live email synchronization connection until one is implemented. A case has one primary email; additional documents from other emails can be explicitly associated through a confirmed shipment relationship. A unique confirmed reference can assist matching, while conflicting matches require selection. The initial case API does not merge whole email threads automatically.

## Signature feature 1: Amendment cycle with regression detection

**User problem:** a corrected BL can fix one issue while changing a previously correct field. Rechecking every version from scratch is slow and easy to get wrong.

**Experience:** when a new draft is uploaded, display a concise change result such as “Consignee fixed; gross weight changed; one issue remains.” The reviewer can open the changed evidence directly. Unchanged, previously supported values are collapsed but still checked.

**Workflow:** pin the SI extraction, previous BL extraction, new BL extraction and policy version. Verify the entire new BL against the SI. Compare the old and new seven-field results to classify issues as `fixed`, `unchanged`, `new`, `regressed` or `unresolved`. A regressed field previously matched the SI and now differs. An unreadable replacement cannot inherit the old value or mark an issue fixed. A changed SI creates a new comparison baseline and invalidates outstanding correction previews.

**Backend:** `amendments.py`, `revision_analysis.py`, `verification.py`. Use a deterministic three-input comparison, not an LLM summary deciding what changed. AI extracts each document independently; optional narration uses a strict schema and can only refer to computed results.

**Database:** `cases`, `case_documents`, `amendment_rounds`, `case_issues`, `issue_events`, with references to immutable extraction/report IDs.

**Frontend:** amendment summary on the case page, changes-only view by default after a replacement, full seven-field view always available, and a visible SI version label.

**Acceptance:** fixing consignee while changing matching gross weight resolves only the consignee issue and opens a weight regression. Re-uploading the same file creates no new round. A new SI never silently closes an issue against the old baseline.

## Signature feature 2: Correction preview with exact scope

**User problem:** a generic error report still leaves the reviewer to decide which changes to ask for, write the message, and avoid copying incorrect values.

**Experience:** select confirmed issues and choose “Preview correction request.” Show each requested change as “Current BL → Required by SI”, with evidence and a concise editable message. Show the forecast explicitly as “If these changes are made, 2 issues would remain.” It is a preview, not proof that the carrier changed the document.

**Workflow:** generate deterministic patches for selected, supported mismatches. Apply them to a transient copy of the BL's normalized fields, run the same verifier, and show residual issues. Missing or disputed reference values cannot become requested replacement values. Persist the original selection, preview hash and edited message. On copy/download, recheck the case, SI, BL and policy versions; a stale draft must be refreshed.

**Backend:** `correction_previews.py`, `amendment_drafts.py`, the existing verifier. Use templates for factual text. Do not modify the original BL or transmit emails automatically.

**Database:** `correction_previews` and `amendment_drafts`, linked to case revision, source report, selected issue IDs and request fingerprint.

**Frontend:** a compact right panel containing change cards, remaining issues, message editor, and explicit copy/download. Export success says “Copied”; it does not say “Sent” or “Corrected.”

**AI involvement:** optional wording suggestions only. Numbers, parties and ports are filled from validated source values and never generated from memory.

**Acceptance:** a preview changing two fields leaves the actual case untouched; stale preview use returns 409; edited narrative cannot alter the machine-readable requested values without a new preview.

## Signature feature 3: One question that resolves several blockers

**User problem:** reviewing a case often means answering several versions of the same question, such as which SI is authoritative.

**Experience:** present the smallest useful next decision: “Which SI applies to this draft?” or “Confirm the marked gross-weight total.” Show why it matters: “This resolves the source choice for seven checks.” Ask one question at a time, with the relevant evidence already visible.

**Workflow:** represent dependencies explicitly: pair selection precedes field comparison; a required value depends on its source region; a notify-party reference may depend on the same document's consignee. Group blockers by their actual dependency. Order candidate actions by readiness prerequisite, number of affected unresolved checks, then age. No fabricated probability of operational impact or financial savings.

**Backend:** `action_planner.py`, `evidence_dependencies.py`, `review.py`. Persist known dependency edges and action reasons. Recompute available actions after each decision. Never auto-propagate a human answer across different shipments or different source revisions.

**Database:** `case_actions` and `evidence_dependencies`. A correction records actor, evidence and the exact version affected.

**Frontend:** “Next action” card with a short question, evidence, one primary button and an explicit “I cannot confirm” path. Hide advanced extraction settings from the operator's normal flow.

**AI involvement:** may suggest candidates from the current source; deterministic dependency rules select and apply actions. A model cannot decide a disputed authoritative SI on the operator's behalf.

**Acceptance:** selecting one authoritative SI resolves the pairing blocker and reruns seven checks, while leaving unsupported field values unresolved. Dismissing a question does not produce a clean result.

## Supporting feature 4: Approved equivalence memory with a preview

**User problem:** reviewers repeatedly confirm harmless, specific naming variations, but an overly broad rule could hide a real wrong party or port.

**Experience:** after confirming a supported alias, offer “Suggest this equivalence for future cases.” A supervisor sees its exact customer/field scope, evidence and affected-case preview before approval. Show a visible “Approved rule” badge on future matches, with a route to revoke it.

**Workflow:** human proposes a field-specific rule; server tests it against selected historical examples and a regression fixture set; admin approves an immutable rule version. Apply only to the selected workspace and explicitly identified customer. Numeric equality, missing values, countries, identity qualifiers and arbitrary substring matches cannot be overridden. A revocation marks affected reports stale for re-verification; original reports remain unchanged.

**Backend:** `equivalence_rules.py`, `rule_impact.py`, existing normalizer/verifier. No automatic model retraining or cross-customer learning.

**Database:** `equivalence_rules`, `rule_evaluations`, `report_rule_applications`.

**Frontend:** an opt-in action after supported human confirmation; approval and impact preview under supervisor settings. Queue an honest “recheck needed” state when a rule changes.

**AI involvement:** suggests a possible explanation for the alias, but cannot approve rules. Baseline benchmark mode freezes the policy and disables learning from evaluation outcomes.

**Acceptance:** an approved alias for Customer A never applies to Customer B. A rule cannot equate different gross weights or erase `ON BEHALF OF`. Rule previews disclose false matches in labelled test cases.

## Supporting feature 5: Attention queue with clear readiness

**User problem:** an inbox sorted by arrival time makes every email look equally actionable and hides the reason a case is blocked.

**Experience:** the dashboard answers “What should I do next?” with case rows grouped into `Needs you`, `Waiting for a draft`, `Checking`, and `Checked`. Each row shows the shipment reference, one reason, latest draft and a concrete next action. A row can say “New draft introduces a weight change” without requiring the user to open analytics.

**Workflow:** use deterministic, explainable ordering: confirmed regressions and blocking contradictions first, then unresolved evidence, then waiting. Optional deadlines affect ordering only if entered or confirmed by a user; the AI never invents a cutoff. Display operational state separately from verification status and job status.

**Backend:** `cases.py`, `action_planner.py`, `readiness.py`. Paginated projections are derived from authoritative issue/report state; no stale client-only readiness calculation.

**Database:** case projection, optimistic version, optional confirmed deadline and its provenance, and action records.

**Frontend:** the attention queue is the default page. Inbox is a secondary input view. Benchmark analytics lives under an admin workspace, not on the operator landing page.

**AI involvement:** classification and extraction underpin the case, but queue ordering remains inspectable and deterministic.

**Acceptance:** the same issues give the same priority order; unknown deadlines remain unknown; `Checked` means the scoped seven-field check is complete and does not mean shipment release is approved.

## Product boundaries

Maintain OCR, evidence links, human review, duplicate detection, version history and benchmark integration as shared infrastructure. Avoid a general-purpose chatbot, autonomous document editing, unexplained risk scores, unsupported cost-savings claims, live shipment tracking or additional paid data providers. These would distract from the amendment task and require evidence/integration beyond this use case.

## Outcome measurement

Measure reviewer completion time, document/page switches, repeated field decisions, correction request edits, percentage of amendment regressions caught and false clean reports. Instrument only necessary interaction metadata; no document body in analytics. Compare the same cases using a basic full diff and the guided workflow, counterbalance task order, and report the small sample size. Initial usability targets are in [UX specification](UX_SPECIFICATION.md); they are acceptance hypotheses, not achieved results.

For hackathon technical evaluation, preserve the provided category/defect export unchanged. Amendment rounds, previews and UX metrics are additional product evaluations and must not be mixed into the organizer's score.
