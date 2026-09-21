# Acceptance criteria

[Product specification](PRODUCT_SPECIFICATION.md) · [UX specification](UX_SPECIFICATION.md) · [Benchmarking](BENCHMARKING.md)

## Required product behavior

| ID | Input or action | Required outcome | Implementation destination |
|---|---|---|---|
| CORE-01 | All seven fields match with supported evidence | `OK`; scope explicitly seven fields | `backend/app/services/verification.py` |
| CORE-02 | SI count 3, BL count 4; remaining fields match | Exactly count mismatched | `backend/app/services/verification.py` |
| CORE-03 | Required field missing on both sides | Review; no clean clearance | `backend/app/services/verification.py` |
| CORE-04 | SI request body includes complete shipment data | Classify SI request; no automatic comparison | `backend/app/services/classification.py` |
| CORE-05 | Invoice named as BL | Wrong-document review | `backend/app/services/pairing.py` |
| CORE-06 | Valid image-only PDF | Bounded OCR/vision and evidence checks | `backend/app/parsers/ocr.py` |
| CORE-07 | Malformed or oversized file | Typed failure, no API crash | `backend/app/parsers/registry.py` |
| AMEND-01 | New draft fixes consignee but breaks weight | Fixed consignee + weight regression | `backend/app/services/revision_analysis.py` |
| AMEND-02 | New draft has unreadable weight | Unresolved; do not inherit old value | `backend/app/services/revision_analysis.py` |
| AMEND-03 | Same bytes uploaded twice | Existing logical draft/round reused | `backend/app/services/amendments.py` |
| AMEND-04 | Authoritative SI changes | New baseline, stale previews, recheck seven fields | `backend/app/services/cases.py` |
| PREVIEW-01 | Simulate a supported SI-value replacement | Correct residual blockers; originals unchanged | `backend/app/services/correction_previews.py` |
| PREVIEW-02 | Copy request after source changed | 409; draft text retained in UI | `backend/app/api/amendments.py` |
| PREVIEW-03 | Copy request | Mark copied, not sent/corrected | `frontend/components/cases/correction-preview.tsx` |
| ACTION-01 | Choose one authoritative SI | Recompute dependencies; preserve unresolved values | `backend/app/services/action_planner.py` |
| ACTION-02 | Reviewer cannot confirm | Case remains blocked with reason | `backend/app/services/review.py` |
| RULE-01 | Customer-specific approved alias | No cross-customer/workspace application | `backend/app/services/equivalence_rules.py` |
| RULE-02 | Attempt numeric or qualifier-erasing rule | Reject | `backend/app/services/equivalence_rules.py` |
| RULE-03 | Revoke rule used by reports | Original reports unchanged; affected cases rechecked | `backend/app/services/rule_impact.py` |
| UX-01 | Open an issue | Both source regions accessible in one click | `frontend/components/cases/evidence-viewer.tsx` |
| UX-02 | Complete review | Stay on case; preserve source context | `frontend/app/cases/[caseId]/page.tsx` |
| UX-03 | First login with no cases | Clear import/upload path, no fake metrics | `frontend/app/dashboard/page.tsx` |
| UX-04 | Keyboard-only operator | Complete the same supported workflow | `frontend/tests/accessibility.spec.ts` |
| SAFE-01 | Cross-workspace entity ID | No data, mutation or signed URL | `backend/tests/integration/test_tenant_isolation.py` |
| SAFE-02 | Two reviewers save same version | One succeeds; other gets 409 without partial writes | `backend/tests/integration/test_review_concurrency.py` |
| SAFE-03 | Worker dies around commit | Recover with no duplicated logical result | `backend/tests/integration/test_worker_recovery.py` |
| EVAL-01 | Export supplied dataset predictions | Every email present, strict harness schema | `backend/app/benchmark/export.py` |

## Evaluation separation

The organizer score evaluates categories and defects. Amendment detection and user task results are separate reported measures. Manually corrected runs must be labelled human-assisted. Approved alias memory is frozen before an automated evaluation; no hidden-label outcomes feed its proposals.

Use independent synthetic fixtures for fix-plus-regression, unreadable replacement, SI re-baselining, stale correction preview, revoked rules and duplicate uploads. The supplied dataset does not establish performance for these scenarios by itself.

## Measured outcomes

Record: exact regression detection, false fixed-issue rate, false clearance count, residual-preview correctness, operator completion time, page switches and repeated decisions. Publish denominator/sample size with every accuracy or usability result. Proposed time/click targets in the UX specification are not achieved metrics until tested.

## Implementation exit condition

The repository is production deployable only after migrations execute, core and feature tests pass, UI actions use real endpoints, credentials are configured, resource fit is measured and recoverability is exercised. This plan provides the design and acceptance requirements; it does not claim that those implementation checks have already passed.
