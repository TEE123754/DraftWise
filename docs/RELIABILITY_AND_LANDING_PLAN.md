# DraftWise reliability and business landing-page implementation plan

Status: core fixes implemented and verified locally on 2026-09-20. The findings below preserve the original audit; the checklist below records the repair evidence.

## Repair checkpoint

- [x] ~~Remove homepage self-redirect and duplicate route ownership.~~ Live `/` returns 200.
- [x] ~~Restore case-list route, readiness links, open-case filter and multi-state API filter.~~ Live case-list URLs return 200; database and browser regressions pass.
- [x] ~~Replace invented dashboard fallback counts with explicit unavailable states; correct schema queries and job-state counts.~~
- [x] ~~Send authenticated workspace headers for assistant requests; return read-only summaries with scoped case citations.~~ No provider inference is used for these answers.
- [x] ~~Remove fabricated alert fallbacks and false-success mutations; display failed operations and validate affected rows.~~
- [x] ~~Gate incomplete Gmail OAuth/import endpoints and UI.~~ This fixes the broken action, not the missing Gmail feature; secure live import remains pending.
- [x] ~~Redesign the landing page with generated shipping artwork, an HTML comparison example, responsive business layout and clearer capability boundaries.~~ Hero WebP is 187,908 bytes.
- [x] ~~Export existing SVG logo as legacy favicon; supply social-share image.~~ Both previously missing URLs return 200.
- [x] ~~Fix contrast, link-button styling, mobile overflow, assistant Escape/focus handling and misleading review/demo copy.~~
- [x] ~~Run 89 backend/PostgreSQL tests, eight browser regressions and production build.~~ Browser checks include homepage/demo/case accessibility, mobile widths, failed dashboard/alert calls, assistant headers and amendment regressions.
- [x] ~~Inspect real desktop/mobile homepage screenshots.~~ Saved under ignored `artifacts/ui/`.
- [x] ~~Finish real demo/dashboard/assistant end-to-end check against hosted Supabase.~~ User-provided IPv4 Session pooler verified and saved in ignored backend/.env. API readiness 200, database connected and worker active. Real Edge passed homepage/mobile, demo summary, cases, cited assistant, Escape/focus and End demo with no page errors. Next development badge disabled because it overlapped End demo.
- [ ] Complete secure Gmail import, calibrated detection, direct extraction corrections and dashboard customization in their roadmap phases.

Unknown routes still return 404 with recovery UI. No deployment or domain changes occurred. Generated hero source/prompt is documented in [the asset record](LANDING_ASSETS.md).

## Verified findings

| Priority | Finding | Evidence and effect |
|---|---|---|
| P0 | Homepage redirects to itself | Live `GET /` returns HTTP 307 with `Location: /`. `frontend/app/page.tsx` calls `redirect("/")`; `(marketing)/page.tsx` also claims `/`. The browser cannot reach a stable homepage. |
| P0 | Case-list route missing | Live `/cases` and `/cases?readiness=awaiting_revision` return 404. Sidebar Cases, Cases open, Awaiting revision and View all cases target this route. Only `cases/[caseId]/page.tsx` exists. |
| P0 | Failed dashboard requests become fabricated statistics | Dashboard catches requests individually, suppressing the outer error handler, then displays hard-coded totals including checked cases, spam and drift. Failure can look like success or an empty queue. |
| P0 | Dashboard/chat queries disagree with repository schema | They read `emails.category`, although classification lives in `email_classifications`. Dashboard and Gmail also reference `public.jobs`, while the established queue is `processing_jobs`. Verify deployed schema before migrations; do not invent duplicate tables to accommodate broken queries. |
| P0 | Assistant bypasses authenticated API client | Raw chat fetch sends no workspace, demo-mode or bearer headers. The endpoint requires the authenticated workspace principal. Citation mapping also assumes `caseId`; verify the actual response contract. |
| P0 | Alert actions falsely report success | Failed acknowledge requests still change local state; dismiss hides alerts even if resolution fails. Fetch errors silently load invented alerts, including outside explicitly selected simulation mode. |
| P1 | Action-queue filter contract mismatch | Dashboard repeats the `readiness` query parameter, but the API accepts one scalar readiness. It does not implement the intended union of needs-decision and changes-required cases. |
| P1 | Gmail workflow incomplete | Browser connect navigation cannot supply required auth/workspace headers. Callback URL uses the frontend origin, callback assigns a random workspace, token writes may fail silently, tokens are plaintext, and sync targets the wrong queue. Disconnect omits auth headers and does not check HTTP success. |
| P1 | Broken public assets | Live `/opengraph-image.png` and `/favicon.ico` return 404; metadata references both. `/icon.svg` and `/llms.txt` return 200. |
| P1 | Responsive and dialog risks | Workspace shell hardcodes a 240px sidebar, assistant a 380px panel, and marketing navigation has no compact layout. Check narrow-screen overflow, focus trapping and focus restoration. These are source findings, not measured visual results yet. |
| P1 | Misleading copy | Demo says no data is saved although sessions retain records. Review copy promises correction/recompute beyond currently accepted functionality. Reconcile all marketing, help and retention statements with tested behavior. |
| P1 | Existing browser tests are stale | Accessibility test still expects an Attention queue heading at `/dashboard`, while the current screen is Overview. Earlier green tests do not validate this version. |
| P2 | Landing page lacks substantive product visuals | Hero contains a dashed Workflow illustration placeholder. The current root loop prevents its normal display. |

Live `/dashboard`, `/review`, `/alerts`, `/settings/connections`, `/workflow` and `/pricing` return 200; this proves route availability only. The local API OpenAPI endpoint responds and lists dashboard/chat/alerts/Gmail routes. Authenticated success of those endpoints was not established in this audit.

Browser limitation: `agent-browser` was unavailable, and the browser automation runtime failed to initialize because of a filesystem permission configuration. Findings above use live HTTP checks and source inspection; screenshot, console and visual claims remain unverified.

## 1. Restore reliable routes and loading behavior

- [ ] Remove the self-redirecting root page and retain exactly one `/` owner, preferably `app/(marketing)/page.tsx`.
- [ ] Separate public layout from authenticated workspace layout so landing pages do not wait on workspace initialization.
- [ ] Create `frontend/app/cases/page.tsx` using the existing case queue. Support URL-based readiness/search filters and pagination. Preserve direct case-detail links.
- [ ] Centralize route constants and inventory every sidebar link, summary tile, breadcrumb, footer and CTA. Use real destinations; unavailable features need an explanatory state rather than an enabled broken action.
- [ ] Define loading, unauthenticated, expired-demo, empty, unavailable, retry and forbidden states separately. Ensure auth failures cannot leave indefinite loading indicators. Cancel stale fetches when workspace or route changes.
- [ ] Remove the unconditional immutable cache header for `/_next/static` and let Next manage development/production caching. Check a fresh browser and existing browser storage after correcting the loop.

Files: `frontend/app/page.tsx`, `frontend/app/(marketing)/layout.tsx`, `frontend/app/layout.tsx`, `frontend/app/cases/page.tsx`, `frontend/components/app-shell.tsx`, `frontend/components/auth-provider.tsx`, `frontend/components/cases/case-queue.tsx`, `frontend/next.config.ts`.

Acceptance: `/` returns 200 without a redirect; direct visit, refresh, Back/Forward and navigation settle without repeated document requests. Every advertised case-list link returns 200 and applies its visible filter. Unknown URLs show the custom 404 with working recovery links.

## 2. Correct dashboard, assistant and alert behavior

- [ ] Reconcile summary queries against the real schema. Count the latest classification per email without double counting revisions. Use the existing processing-job states. Distinguish unavailable metrics from a genuine zero.
- [ ] Remove automatic sample-stat and sample-alert fallbacks. Only show simulation data behind an explicit, labelled demo-scenario mechanism.
- [ ] Define a supported multi-readiness filter contract and use it consistently in summary links, action queue and case lists.
- [ ] Use the shared API client for chat, Gmail disconnect and other workspace calls. Handle session expiry and authorization failure explicitly.
- [ ] Validate assistant request/response types and citation URLs. Show supported read-only help honestly; do not claim implemented safety or correction behavior without evidence.
- [ ] Commit alert state changes only after backend success. Failed requests retain the alert and show a recoverable error. Require review rationale where the contract needs it.
- [ ] Remove broad database exception swallowing. Missing migrations produce an explicit unavailable/configuration state; handle transaction rollback correctly before subsequent queries.
- [ ] Reconcile counts with the exact lists they link to; add last-successful-refresh and stale-data states.

Files: `backend/app/api/dashboard.py`, `backend/app/api/chat.py`, `backend/app/api/alerts.py`, `backend/app/api/cases.py`, `frontend/app/dashboard/page.tsx`, `frontend/app/alerts/page.tsx`, `frontend/app/review/page.tsx`, `frontend/components/app-shell.tsx`, `frontend/lib/api/client.ts`, `frontend/lib/api/types.ts`.

Acceptance: simulated 401/403/404/500/network failures never produce fabricated success, invented counts or false empty queues. Real authenticated/demo responses match stored records. Cross-workspace requests fail. Every cited case opens the correct permitted case.

## 3. Repair or clearly gate incomplete integrations

- [ ] Keep Gmail connection unavailable with an accurate configuration explanation until its full path works.
- [ ] Initiate OAuth through an authenticated request; bind state server-side to user, workspace, expiry and approved return path. Use an explicit backend callback URL, PKCE, replay prevention and encrypted provider tokens.
- [ ] Remove random workspace assignment, swallowed persistence failures and unrestricted return redirects. Use the durable queue and implement/validate its Gmail handler before claiming sync is available.
- [ ] Confirm read-only import consent, bounded selection, refresh/reconnect, deduplication, disconnect and retention behavior using an authorized test account.
- [ ] Audit demo expiry/end-session handling and replace the inaccurate no-data-saved text. Check the newly added email-body evidence panel still works after navigation/layout changes.

Files: `backend/app/api/gmail.py`, `backend/app/config.py`, `backend/app/workers/handlers.py`, relevant versioned migrations, `frontend/app/settings/connections/page.tsx`, `frontend/components/app-shell.tsx`, `frontend/components/email-detail.tsx`.

Dependency: Google OAuth application configuration and test-account consent are needed for live Gmail acceptance. Core routing, error handling and landing redesign can proceed independently.

## 4. Redesign the landing page for business users

Visual direction: an editorial operations workspace with warm white, dark ink and restrained teal; Source Sans 3, clear typography, generous consistent spacing and readable tables. Preserve all earlier design exclusions: no purple/blue gradients, gradient titles, title emoji, glass cards, badges above headings, grain, scroll fades, icon-box filler or invented performance claims.

- [ ] Hero: direct headline such as **Check shipping drafts before mistakes travel further.** Supporting copy explains SI-versus-BL evidence and revision checks. Keep **Every draft checked. Every change explained.** as the brand line. Primary CTA: **Try the demo**; secondary: **See the workflow**.
- [ ] Pair hero copy with an accurate product visual: SI and draft BL beside a highlighted discrepancy and its source quote. Clearly identify illustrative sample values. Use a real accepted screen capture when possible.
- [ ] Replace the dashed placeholder with original generated logistics/workflow artwork, then assemble labels and diagram meaning in accessible HTML. Generate separate optimized assets and inspect them before use. Never render functional controls as an image.
- [ ] Present the workflow as a continuous sequence: receive request, inspect evidence, review differences, check returned draft. Follow with a larger before/after amendment example and concise capability explanations.
- [ ] Add a factual trust section: evidence links, human review, tenant boundaries and current data handling. Distinguish implemented features, demo simulations and upcoming integrations. No fictional logos, customer quotes or quantified savings.
- [ ] Show clear demo/pilot pricing status without inventing commercial commitments. Verify contact ownership, legal text and retention statements before publishing.
- [ ] Refine the existing logo for small-size legibility, add usable mobile navigation and a consistent footer. Keep buttons visible and high contrast.
- [ ] Supply missing social-share and favicon assets; preserve individual page titles/descriptions, canonical configuration, sitemap, robots, llms and alt text. Never invent business address or domain ownership.

Files: `frontend/app/(marketing)/page.tsx`, `frontend/app/(marketing)/layout.tsx`, related workflow/pricing pages, `frontend/components/brand/wordmark.tsx`, `frontend/app/globals.css`, `frontend/public/images/`, `frontend/public/opengraph-image.png`, favicon/metadata files.

Acceptance: no placeholder illustration; primary CTA reaches a functioning demo; desktop and 360/390/768px layouts have no horizontal overflow; keyboard and contrast checks pass; visuals explain the product and all claims match accepted functionality.

## 5. Regression and release checklist

- [ ] Add route smoke tests for all rendered internal links, dynamic case details, query strings and genuine unknown routes.
- [ ] Add homepage regression: one navigation settles on a 200 page, with no self-redirect, hydration loop or repeated navigation.
- [ ] Test dashboard/list reconciliation, multi-filter behavior, empty data and unavailable services.
- [ ] Test chat credentials/citations and alert failures that must not mutate displayed state.
- [ ] Test logged-out, signed-in, fresh demo and expired-demo navigation separately. Include sign-in return paths, account/demo switching and refresh.
- [ ] Run existing email intake, body evidence, attachment extraction, source selection and amendment regression journeys; update stale UI expectations without weakening behavioral checks.
- [ ] Run backend/database tests, TypeScript/production build and real browser verification against API + worker. Capture console errors, failed requests and desktop/mobile screenshots.
- [ ] Check sitemap/canonical/social/favicon status codes; inspect production bundle size and loading behavior, image sizing and source-map settings.
- [ ] Update the master implementation checklist only after acceptance evidence exists. Record unresolved external dependencies separately.

Delivery order: routing/loop first, truthful dashboard and action behavior second, integration gating third, landing redesign fourth, then full regression and visual acceptance. No domain purchase, deployment or Google authorization is required to start the local fixes.
