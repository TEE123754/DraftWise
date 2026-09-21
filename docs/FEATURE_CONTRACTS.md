# Amendment workspace contracts

[Product specification](PRODUCT_SPECIFICATION.md) · [API contracts](API_CONTRACTS.md) · [Database schema](../database/schema.sql)

The existing classification, extraction and seven-field verification contracts remain. These contracts add case-level workflow and never change the organizer's submission schema. All endpoints are under `/api/v1`, require a verified bearer token and workspace membership, and use the shared error envelope. Reads hide inaccessible IDs with 404. Operator/reviewer/admin permissions are checked for each mutation. Processing POSTs require an idempotency key and return a durable job.

## Domain vocabulary and state

`case.version` is an optimistic concurrency number incremented whenever an active source, issue decision, rule policy or amendment selection changes. A preview is bound to this version plus exact report/extraction IDs. A case's `readiness` is a computed projection, never an editable client field.

| State | Meaning | Primary action |
|---|---|---|
| `needs_source` | A required source is absent or authority is ambiguous | Add/choose source |
| `checking` | A durable extraction/verification job is active | Inspect progress |
| `needs_decision` | Evidence or role ambiguity needs a reviewer | Answer the next question |
| `changes_required` | Complete comparison has supported mismatches | Preview request |
| `awaiting_revision` | Reviewer explicitly marked a request as shared or is waiting for a draft | Add returned draft |
| `checked` | All seven fields match against the pinned reference | View checks |
| `failed` | Processing failed and no current valid outcome is available | Retry/replace |

`awaiting_revision` is a workflow state and can coexist with a stored `MISMATCH` report. Copying a request alone never transitions to `awaiting_revision`; provide a separate **Mark as shared** action with an audit record. No case state means cargo release or legal clearance.

Issue transitions: `open` → `resolved` only after supported re-verification or an explicitly approved evidence correction; `open` → `superseded` when the SI baseline changes; a newly broken field is a new issue linked to its prior resolved/matched field. Acknowledgment records that a reviewer saw the issue and does not resolve it. Unreadable new evidence keeps the issue `unresolved` in the round summary.

## Data dependencies and revision analysis

The following algorithm is mandatory for each field `f`:

```text
old = compare(pinned_si[f], old_bl[f], pinned_policy)
new = compare(pinned_si[f], new_bl[f], pinned_policy)

if old or new cannot be resolved: summary[f] = unresolved
elif old is mismatch and new is match: summary[f] = fixed
elif old is match and new is mismatch: summary[f] = regressed
elif old is mismatch and new is mismatch: summary[f] = unchanged
else: summary[f] = unchanged_match
```

For a first draft, a mismatch is `new`, a match is `unchanged_match`, and missing/ambiguous evidence is `unresolved`. A changed SI invalidates this old/new calculation; create a new baseline with all previous issues `superseded`, rerun all seven checks, and clearly label the resulting differences. Distinct policy versions also require an explicit re-baseline or recalculation under one frozen policy, not a comparison of differently normalized values.

Issue identity uses case, field and baseline rather than a transient PDF coordinate. Evidence remains attached to exact extraction IDs. `SAME AS CONSIGNEE` uses a dependency within the same document; a changed consignee invalidates its dependent notify-party decision. A case-level pair choice is a parent dependency of the seven checks. Model output may suggest dependencies but only whitelisted relationship types can enter the graph.

## New endpoint contracts

All mutation examples assume a UUID case ID and a valid workspace header. Domain errors are 422; stale version/source/preview is 409; invalid roles are 403; invalid/inaccessible IDs are 404; quotas are 429; unavailable durable storage is 503. No mutation succeeds partially.

### GET `/cases`

Query: `readiness` enum above, `limit` 1–100 (default 25), opaque `cursor`, `search` up to 120 characters. Return `{items:CaseSummary[],next_cursor:string|null}`. Summary fields: UUID `id`, string `reference`, integer `version`, readiness enum, `latest_report_id:uuid|null`, integer `open_issue_count`, nullable `next_action`, nullable confirmed deadline and last activity. The backend owns sorting and projections. Search uses indexed metadata, not raw private document content by default.

### GET `/cases/{id}`

Return `{case:CaseSummary,active_sources:{si_extraction_id,bl_extraction_id},issues:Issue[],actions:CaseAction[],rounds:AmendmentRound[],latest_report:VerificationReport|null}`. Include evidence IDs and typed locators; fetch full artifacts separately. Support `ETag`/conditional GET for the case version. Data from another workspace is never included through a related record.

### POST `/cases`

Request `{email_id:uuid,reference:string[1..120]}`. Operator. Atomically create or reuse the case association, append audit event and create initial action planning job. Return 201 `{id:uuid,version:1}`. Repeated same idempotency key returns the same case; different request hash returns 409. An email may be associated with only one active case in the baseline implementation. More complex multi-shipment emails require an explicit split before automatic verification.

### POST `/cases/{id}/sources`

Request `{expected_version:integer,si_extraction_id:uuid,bl_extraction_id:uuid|null,reason:string}`. Reviewer. Verify role, workspace and confirmed shipment link. Pin sources and enqueue re-verification. Return 202 `{job_id,case_id,case_version}`. Changing the SI or policy stales previews and supersedes the current issue baseline in the same transaction. An SI role cannot be inferred from an uploaded filename alone.

### POST `/cases/{id}/drafts`

Request `{expected_version:integer,attachment_id:uuid}`. Operator. Attachment must be finalized, belong to the case's email or confirmed shipment relationship, and not be an unrelated document. Return 202 `{job_id,case_id,case_version}`. Role validation may finish in the job and produce `needs_decision`; do not mark the new draft active until its identity and relationship are supported. Exact duplicate content returns the existing round/job association.

### POST `/cases/{id}/previews`

Request `{expected_version:integer,report_id:uuid,issue_ids:uuid[1..7]}`. Reviewer. Report must be the current immutable report. Reject unresolved/missing-value issues or unsupported SI values. Return 201 `CorrectionPreview` matching [the schema](../shared/schemas/correction-preview.schema.json), including changed fields, remaining blockers, source fingerprint and expiry. Preview calculation is deterministic and bounded; it can be synchronous after authorization because it performs no OCR or LLM calls.

### POST `/cases/{id}/requests`

Request `{expected_version:integer,preview_id:uuid,message:string[1..8000]}`. Reviewer. Revalidate preview fingerprint and unchanged source/policy state. Return 201 `{id:uuid,state:"draft",case_version:integer,requested_changes:Patch[],message:string}`. Store machine-readable changes separately from editable wording. User edits that contradict a source value require a new preview, not silent alteration of the patch.

### POST `/cases/{id}/requests/{request_id}/shared`

Request `{expected_version:integer,note:string[1..1000]}`. Reviewer. Explicitly record the user's assertion that the request was shared outside the product; no email is sent. Return 200 `{request_id,state:"marked_shared",case_version,readiness:"awaiting_revision"}`. A stale request receives 409.

### PATCH `/cases/{id}/actions/{action_id}`

Request `{expected_version:integer,decision:"confirm"|"cannot_confirm",evidence_ids:string[],value:string|null,rationale:string}`. Reviewer. The action type controls permissible values; choosing SI uses `/sources` rather than arbitrary `value`. Atomically persist action decision/correction, add issue event, increment case version and enqueue dependent recomputation. Return 202 `{job_id,case_id,case_version}`. The previous report remains available while recalculation runs. A declined action remains blocked and has a visible reason.

### GET and POST `/customers`

GET accepts a bounded `search` and `limit` and returns `{items:[{id:uuid,display_name:string}],next_cursor:string|null}`. Operator or higher. POST accepts `{display_name:string[1..240]}` and returns 201 `{id:uuid,display_name:string}`; admin only and idempotent. A case customer association is confirmed by a reviewer through `PATCH /cases/{id}` with `{expected_version:integer,customer_id:uuid|null}`. It increments the case version and re-verifies if scoped rules change. Never derive a customer scope solely from fuzzy matching of an extracted party name.

### POST `/rules/equivalences`

Request `{customer_id:uuid,field:"shipper"|"consignee"|"notify_party"|"port_of_loading"|"port_of_discharge",left:string,right:string,evidence_ids:string[],rationale:string}`. Reviewer proposes a rule in `proposed` state. Ports require authoritative same-port identity; country/terminal contradictions cannot be waived. Return 201 `{id,version:1,state:"proposed"}`. Numeric/missing-value rules are rejected.

### POST `/rules/equivalences/{id}/evaluate`

Request `{expected_version:integer,case_ids:uuid[]}`. Admin. Bounded authorized historical sample plus the fixed regression suite; no hidden evaluation labels. Return 202 `{job_id,evaluation_id}`. Result includes changed decision counts, newly cleared fields and fixture false-match count, with input manifest hash. An empty labelled fixture set is `insufficient_validation`, not a passing result.

### PATCH `/rules/equivalences/{id}`

Request `{expected_version:integer,action:"approve"|"revoke",evaluation_id:uuid|null,rationale:string}`. Admin. Approval requires a current completed evaluation, matching rule/content hash and zero invariant violations; revocation requires a reason. Return 200 `{id,version,state,affected_report_count,recheck_job_id:uuid|null}`. Activation/revocation creates a new policy version and queues affected-case checks. No original report is rewritten.

## Correction preview invariants

Patch values always come from supported SI normalized fields. Apply to a temporary in-memory representation of a BL extraction; original storage/DB extraction rows are immutable. Preview fingerprints cover workspace, case version, SI extraction, BL extraction, report, selected issues and policy version. Expiry is at most 30 minutes. Acceptance also requires unchanged dependencies even if the expiry time has not passed.

`remaining_blocker_count` counts unresolved/mismatched required fields under the preview and must correspond to the returned field list. A preview with zero blockers is labelled “Would match if applied,” never `OK` on the real case. Preview values do not appear in the organizer benchmark submission.

## Concurrency and audit

Serialize case mutations with `SELECT ... FOR UPDATE` and the supplied version. Validate all linked objects in the same workspace, using composite foreign keys and scoped queries. Append audit rows and enqueue jobs in that transaction. Increment the version only on an actual semantic change. A worker finalization checks lease token and the case/source fingerprint; a stale job can retain its historical artifact but cannot replace the current projection. The `cases.py` router owns customer lookup/create and case-customer assignment; it enforces the stronger admin role on customer creation.

No operator can submit arbitrary normalized fields directly to make a report match. All value corrections use the review service, evidence and immutable revisions. Request copy/export is logged separately from a supported new-document fix.

## Implementation file ownership

| Path | Responsibility |
|---|---|
| `backend/app/api/verify.py` | Existing verification request/response and auth checks |
| `backend/app/api/cases.py` | Case queries, creation and source selection |
| `backend/app/api/amendments.py` | Draft intake, previews and correction requests |
| `backend/app/api/rules.py` | Rule proposal, evaluation, approval and revocation |
| `backend/app/services/revision_analysis.py` | Pure old/new/SI comparison and regression labels |
| `backend/app/services/correction_previews.py` | Pure proposed patch evaluation and residual blockers |
| `backend/app/services/action_planner.py` | Dependency-aware next action selection |
| `backend/app/services/equivalence_rules.py` | Scoped and versioned approved aliases |
| `backend/app/repositories/cases.py` | Scoped transactional persistence/version locks |
| `frontend/app/dashboard/page.tsx` | Case attention queue |
| `frontend/app/cases/[caseId]/page.tsx` | Complete operator workflow |
| `database/schema.sql` | Complete fresh-project schema including amendment entities |

These paths are application implementation destinations. Specification documents do not imply that the modules already execute; runnable code must be generated and validated in the application implementation phase.
