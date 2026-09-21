# Cross-page UI verification

Completed 2026-09-21.

## Fixed

- Dashboard access prompt and `/sign-in` now share a responsive branded layout, clear primary actions, legal navigation and readable mobile form controls. Existing authentication handlers are retained.
- Mobile workspace navigation uses a compact grid. Workspace content has a zero minimum grid width, consistent action spacing, and clearance below content for the assistant launcher.
- Long unbroken shipment references wrap within email content instead of widening the entire page.
- Rules and Analytics secondary text has sufficient contrast. The 404 page has a main landmark and readable status text.
- Sign-in confirmation no longer asserts an unverified ten-minute link expiry.

## Measured checks

- Production build: passed, 21 static pages generated.
- Playwright: **48 passed**. This includes the existing workflows and three new cross-page/authentication checks.
- Layout matrix: 21 page states at **390, 768 and 1440px**, no horizontal document overflow. Automated axe checks passed at mobile width for these page states.
- Public/access states: home, sign-in, signed-out dashboard, demo entry, pricing, workflow, privacy, terms, 404.
- Workspace states: dashboard, inbox, email detail with long shipment reference, case list, case detail, review, completed, alerts, rules, analytics unavailable state, Trash, mailbox settings.
- Sign-in failure and success responses mocked; no real sign-in email sent. Workspace data in these layout checks is mocked. These checks verify UI behavior, not every live integration or all possible record contents.
- Existing tests separately cover populated classifier results, inbox preview states, dashboard customization, evidence review, amendment actions, alerts and Trash.

## Evidence

Tests: `frontend/tests/page-layouts.spec.ts` and the existing browser suite.

Screenshots in `artifacts/ui/`: `sign-in-access-desktop.png`, `sign-in-access-mobile.png`, `dashboard-access-desktop.png`, `dashboard-access-mobile.png`, `dashboard-workspace-desktop.png`, `dashboard-workspace-mobile.png`.

Local frontend restarted on port 3000. No backend API or database changes were needed.
