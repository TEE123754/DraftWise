# DraftWise UI redesign

Date: 2026-09-20

The design now centers on shipping instructions, draft bills of lading, field evidence and returned revisions. Figma was explicitly requested, but no Figma connector tools were exposed in this session after tool discovery. This checkpoint describes the local implementation, not a Figma file.

- [x] Landing hero shows an accessible seven-field comparison with a highlighted weight difference and supporting source quote. All values are labelled illustrative.
- [x] Existing generated shipping photo supports the product story below the comparison.
- [x] Overview uses real API counts in a four-stage document workflow, actionable case rows, a review checklist and processing status.
- [x] Navigation, inbox and case queue use clear text actions; decorative icons and the unconditional alert indicator are removed.
- [x] Source quotes and revision history use neutral borders. Title eyebrows are removed, spacing is standardized and secondary text contrast is increased.
- [x] Source Sans 3, solid teal, dark ink, white paper and warm neutral backgrounds follow the requested exclusions. No gradients, glass effects, cursor effects, entrance fades, hover-hidden controls, serif italics or grain were added.
- [x] Eight browser tests pass, including accessibility checks, demo entry, case review, assistant credentials, failure handling and responsive overflow checks.
- [x] Production build passes. Desktop and mobile screenshots were visually inspected.
- [x] Live local Edge smoke passes: homepage/mobile, hosted demo summary, case navigation, authenticated assistant response and session exit. No browser page errors were reported. Frontend, API and worker are running locally.

Primary files: `frontend/app/document-design.css`, `frontend/components/brand/document-preview.tsx`, `frontend/app/(marketing)/page.tsx`, `frontend/app/dashboard/page.tsx`, `frontend/components/app-shell.tsx`.

Screenshots: `artifacts/ui/landing-redesign-desktop.png`, `landing-redesign-mobile.png`, `overview-redesign-desktop.png`, `overview-redesign-mobile.png`. Overview captures use browser test fixtures; they are not evidence of live classifier accuracy.

Gmail importing, trained classification, automatic drift monitoring and dashboard customization remain separate unfinished implementation work. The redesign does not imply these capabilities are complete.
