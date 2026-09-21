# DraftWise product audit: 2026-09-20

> **Later status (2026-09-20, evening):** issues 1, 2, 5 and 6 below were fixed after this audit (assistant quota/citations, worker backoff, isolated tests, demo copy); the backend suite then passed (117, then 122 tests). A follow-up review found further problems that this audit did not cover: benchmark figures scored against the project's own output, placeholder benchmark metrics, hardcoded Analytics claims, stale worker processes and an incomplete Gmail sync/disconnect. See the corrected status in [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md).

Verdict: the core demo workflow works, but not every requested feature is complete or reliable. This audit is not a production-readiness or model-accuracy certification. Application code was not changed; the stalled local frontend was restarted.

## Measured checks

| Check | Result and scope |
| --- | --- |
| Backend/PostgreSQL regression suite | **103 passed, 2 failed**. Both failures reproduced in an isolated rerun. Commands: `TEST_POSTGRES_PORT=55453 node tools/postgres/run-tests.mjs`, then port 55454 with the two failing tests selected. These are environment-variable examples; use PowerShell syntax on Windows. |
| Playwright regression suite | **9 passed**. Includes accessibility and dashboard controls; mocked backend responses limit claims about live integrations. |
| Frontend production build | Passed. Does not prove all runtime flows or production deployment. |
| Live API readiness | `/ready`: ready, database OK, worker active, including the final check. |
| Fresh homepage check after frontend restart | HTTP 200, expected heading, no captured page errors, no horizontal overflow at 390px. |
| Public routes | `/demo`, `/pricing`, `/privacy`, `/terms`: 200. Unknown route: 404. |
| Fresh demo session | Entered dashboard; dashboard, inbox, cases, human review, alerts and completed pages returned 200 with expected headings. This verifies navigation, not every action on those pages. |
| Settings | Actual navigation target `/settings/connections` returns 200. `/settings` itself has no page and returns 404; the visible Settings link uses the correct target. |
| Live sample workflow evidence | `artifacts/quality/live-workflow.json`: `email_001` reached `checked`, classified `BL_COMPARISON` by Morpheus/deepseek-v4-pro in 11,343ms, linked SI and BL. **Both extraction calls timed out and used labelled rule fallback.** This is not evidence of successful live AI extraction. |

The first live homepage check timed out. A second check also timed out before DOMContentLoaded. Restarting the identified Next development server restored it. The audit ran a production build while development used the same `.next` directory; build interference is a plausible cause, not proven. Earlier logs contain `Image is not defined`, but the current source imports Image and the fresh homepage check did not reproduce that error.

The fresh demo navigation helper stopped on a test-script error (`Response.status` was called as a function in browser fetch code). Consequently that particular run did not verify Gmail's API response or session exit. Gmail unavailability below is verified by implementation inspection. The separate completed live workflow script includes case navigation and session exit.

## Issues to address

1. **High: assistant AI bypasses demo limits and lacks case citations.** `backend/app/api/chat.py` calls Morpheus directly instead of the bounded AI service. Every authenticated demo chat request can initiate another provider call outside the nine-call session limit. The AI response has an empty citations list and is labelled `ai_grounded` without validating its claims against the summary. The database connection remains checked out during the provider request. Use the application's injected settings and shared quota/timeout controls, release the DB connection before the network call, and support evidence-backed answers or explicit limits.
2. **High: worker can exit on a transient database disconnect.** A logged worker crash occurred during heartbeat after the database closed a connection. `backend/app/workers/runner.py` has no outer reconnect/backoff handling. A worker is currently active, but this does not demonstrate automatic recovery. Add bounded recovery and verify pending-job recovery across disconnects.
3. **High: live AI extraction remains unverified.** The supplied sample completed through deterministic fallback after two `AI_TIMEOUT` results. Preserve that truthful fallback; diagnose provider latency and validate successful extraction against source quotes before claiming the full AI path works.
4. **Medium: retained demo sessions eventually block all new demos.** `seed_session` counts every row, including expired sessions, and rejects provisioning at 20. The initial audit found 17 rows; a subsequent fresh demo added a session. Ending a session only expires it. Implement a safe retention/cleanup policy and concurrency tests; do not merely remove the provisioning bound.
5. **Medium: two backend tests fail because configuration is not isolated.** `test_demo_sessions_are_isolated_and_expire` reaches real AI through global `get_settings()` and receives variable wording instead of the expected deterministic summary. `test_demo_disabled_by_default` loads the configured backend `.env`, enabling the demo and resolving a relative bundle path from the wrong directory. Isolate test settings/provider clients and resolve configured paths consistently. The test wrapper returned exit zero despite pytest failures, so also verify failure propagation before relying on it in CI.
6. **Medium: demo explanation is inaccurate.** `frontend/app/demo/page.tsx` says the demo uses deterministic rules and live AI/persistent storage require sign-in. The demo now permits bounded workflow AI and stores a temporary workspace. Update the copy to explain actual behavior and retention.

## Feature coverage and remaining gaps

| Feature | Current assessment |
| --- | --- |
| No-sign-in demo and sample Gmail fetch | Implemented. Real sample workflow evidence exists; capacity/retention issue remains. Simulator does not connect Google. |
| Linked email, SI and BL; seven-field comparison | Implemented with quotes, review states and next actions. One live sample completed; wider format coverage is not established. |
| Five email categories and contextual WSD | AI/rule paths and targeted tests exist. Current-message precedence and shipping-term evidence are implemented. This is not a validated, comprehensively trained classifier or general WSD model. |
| AI demo review | Live AI classification observed. Live AI extraction timed out; fallback worked. Mocked provider tests cover success and failure behavior. |
| Dashboard counts and customization | Tenant-scoped counts, saved section visibility/order, permanent queue implemented; browser regression passes. Not an unrestricted dashboard designer. |
| Assistant | Responds from workspace summaries or rules; quota, citations and test isolation issues above remain. |
| Real Gmail OAuth/import/sync/disconnect | **Unavailable**, explicitly gated in `backend/app/api/gmail.py`. OAuth credentials alone would not finish these endpoints. User previously selected simulator work for now. |
| Spam/phishing review | Static suspicious-signal checks, holds and reviewer release implemented and tested. Not a validated phishing detector; no live Gmail security-header/URL analysis established. |
| Quality evaluation | Versioned synthetic development set and scorer exist. Ten-message rule result: 80% coverage/accuracy, 20% abstention; 14/14 extracted fields and 7/7 comparisons from one document pair. These are not real-world accuracy estimates. |
| Drift monitoring | Reviewed-baseline/two-window logic exists, but the live database contained **zero quality baselines**. It cannot currently assess reviewed error change for those workspaces. No confirmed concept drift claim is justified. |
| Human review and amendments | Existing workflow/regression coverage; direct editing of extracted field values remains unfinished. Complete human review cannot be claimed. |
| Tenant isolation | Automated checks cover isolation, but one demo test currently fails later on assistant output. This audit does not replace an independent security review. |
| Mobile and keyboard access | Automated accessibility coverage and a fresh 390px homepage overflow check pass. Not every live feature was manually exercised using keyboard/mobile. |
| Custom domain and deployment | Not verified by this localhost audit. A passing build is insufficient evidence. |

Recommended order: fix assistant limits/configuration and failing checks; make worker recovery reliable; resolve demo retention; verify successful live AI extraction; then complete review editing, real Gmail when requested, and representative held-out model/drift evaluation.
