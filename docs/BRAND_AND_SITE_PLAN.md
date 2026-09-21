# DraftWise brand, experience and public-site plan

Status: design/implementation brief only. No final artwork or redesigned screens were generated during this planning turn. Follow [the expansion roadmap](DRAFTWISE_EXPANSION_PLAN.md) for dependency order and acceptance.

## Brand direction

Exact name: **DraftWise**, including navigation, metadata, login emails controlled by the app, documentation, social images and screenshots. Proposed slogan: **Every draft checked. Every change explained.** It describes the intended workflow; never pair it with an unsupported “100% accurate” claim.

Logo direction: two aligned document edges forming a compact D/W relationship, with one precise comparison mark. Develop recognizable monochrome and dark-on-light versions and test at favicon size. Avoid a generic robot, brain, sparkle or shield implying a security certification. The wordmark remains editable text so spelling and accessibility are reliable.

Visual direction: warm white background, deep ink text, restrained teal for primary actions, neutral dividers and status colors only where they convey information. Use a consistent 4/8px spacing scale, readable density, clear headings and predictable alignment. Proposed typography: Source Sans 3 across the product, with tabular numerals for counts. Interpret “no: use inter font for all” as an instruction not to use Inter everywhere. Avoid adding decorative serif pairings. Validate locally available/font-licensed assets during implementation.

### Explicit visual exclusions

- [ ] No purplish-blue gradients or gradient hero text.
- [ ] No emoji in titles or badge placed above the title.
- [ ] No Inter-everywhere styling, Space Grotesk/Instrument Serif pairing or emphatic serif italics.
- [ ] No colorful left-edge card borders or glassmorphism.
- [ ] No low-contrast dark mode; ship a polished accessible light mode first.
- [ ] No three-icon-box row as the primary feature layout; use an annotated real workflow instead.
- [ ] No Lucide icons everywhere; reserve icons for useful controls and use clear text labels.
- [ ] No unchanged default shadcn look; reusable components receive DraftWise typography, sizes, spacing, focus and interaction states.
- [ ] No scroll-to-fade reveals, cursor-following line or buttons hidden/revealed through hover fades.
- [ ] No inconsistent spacing, habitual em dashes, hollow buzzwords or grain textures.

## Image-generation work package

Use the built-in image-generation tool during P1/P7; no extra OpenAI API key is required for that tool. Save selected assets into the repository, record prompts/versions in `docs/ASSET_PROVENANCE.md`, inspect output and compress delivery copies. Generated artwork must never substitute for genuine product screenshots or source-document evidence.

| Asset | Generation brief | Final destination and acceptance |
|---|---|---|
| Logo exploration | `logo-brand`: compact paired-document symbol for DraftWise; flat monochrome/teal, no gradient/shield/brain/sparkles; strong silhouette on plain background | `frontend/public/brand/logo-concept.png`; refine approved production mark, verify 16/32/64px and exact wordmark |
| Workflow illustration | `infographic-diagram`: inbox enters document comparison, evidence review and returned-draft check; warm white, ink and teal; space for accessible HTML labels; no decorative dashboard metrics | `frontend/public/images/workflow.webp`; logical arrows verified against actual workflow and meaningful alt text |
| Landing editorial image | `illustration-story`: shipping documents and a clear side-by-side review in an orderly operations desk setting; restrained palette, no logos/customer text, no invented screenshot | `frontend/public/images/document-review.webp`; useful composition, mobile crop, descriptive alt text |
| Social preview | Reuse approved image-generation art with deterministic DraftWise wordmark and slogan overlay; 1200x630, strong contrast | `frontend/app/opengraph-image.png`; safe crop, readable title, correct spelling |

Compose headings, labels and explanatory copy in HTML rather than burying essential text in generated pixels. Provide reduced-size WebP/AVIF variants with explicit dimensions. Suggested image budgets: <=200KB for the main visual and <=100KB for secondary illustrations where fidelity permits. Keep source artwork outside hot route payloads.

## Main experiences

Public entry: **Try the demo** is the primary action; **Connect your inbox** leads to sign-in and explicit Gmail consent. A visible link returns from demo to product information. Do not place a login wall around marketing or legal pages.

Inside the app: one consistent navigation model for Overview, Inbox, Cases, Review, Alerts and Settings. Ask DraftWise is a contextual side panel rather than a second disconnected product. Keep low-frequency benchmark/rule admin actions discoverable under Quality/Settings with explicit explanations.

Each screen needs an explanatory one-sentence introduction, purposeful empty state, primary next action, loading/error/retry states and keyboard-visible focus. Each case shows the authoritative SI, current BL, review blockers and latest verified outcome. Differentiate **Unreadable**, **Missing**, **Mismatch** and **Matched** in words as well as colors.

Use progressive disclosure: show the operational answer first, then evidence, then technical extraction details. Let users open original page/table evidence beside the field without losing place. Preserve filters and scroll position on return. Define meaningful completion confirmations and recovery after network interruptions. Avoid excessive confirmation dialogs for reversible local choices.

## Route and content map

| Browser route | Content | Indexing |
|---|---|---|
| `/` | Product promise, real workflow, illustrated explanation, demo entry, feature boundaries | Public canonical |
| `/workflow` | Inbox -> classification -> evidence comparison -> human correction -> returned draft; text alternative to visual | Public canonical |
| `/pricing` | Available demo and accurately described pilot/team options; transparent usage limits | Public canonical; no invented paid offers |
| `/privacy` | Data categories, Gmail scope, AI subprocessors, retention/deletion, contact, effective date | Public canonical |
| `/terms` | Actual operator, service limitations, acceptable use, account responsibilities, support/contact | Public canonical |
| `/sign-in` and `/auth/callback` | Google/magic-link login and OAuth outcomes | Noindex; callback secrets excluded from logs/analytics |
| `/demo` | No-sign-in sandbox entry | Noindex |
| `/dashboard`, `/inbox`, `/cases/[caseId]` | Shared real/demo product workflow based on server-authenticated session mode | Noindex |
| `/review`, `/alerts` | Human decisions, safety/drift escalation with evidence | Noindex |
| `/settings/connections`, `/settings/privacy`, `/settings/workspace` | Gmail scope/sync, retention/export/deletion, workspace settings | Noindex |
| `/quality` and `/rules` | Versioned evaluation/rules with role controls; available within demo sandbox | Noindex |

Use `(marketing)` and `(workspace)` route groups without exposing group names in URLs. Remove conflicting old page definitions when moving them; preserve existing deep links. Application labels reference “case” or “email,” not UUIDs. Breadcrumb example: Overview > Cases > shipment reference. Breadcrumbs are links, keyboard accessible and announce the current page.

## Consent, privacy and pricing behavior

Explain Google sign-in separately from mailbox permissions, and distinguish connecting a mailbox from importing messages or sending imported content to an AI provider. Record the accepted disclosure version, actor and timestamp. Never infer email access consent from visiting a demo or signing in.

Use necessary session cookies for authentication. Only add analytics/marketing scripts after an explicit nonessential preference where applicable; reject and revoke choices must work. Publish processor names and actual retention/deletion behavior, including demo uploads, chat history, revoked mailbox connections and backups. Confirm business/jurisdiction details before claiming legal compliance. A template legal page is not a completed legal review.

The pricing page can ship with **Free sample demo** and **Pilot access: contact us** if that matches the real offering. Paid amounts, currencies, refund language, commitments and quotas require owner-approved facts. Expose usage and limits in-product; never advertise unlimited inference over a bounded budget.

## Requested site/SEO checklist

- [ ] **Custom domain:** user-owned domain, DNS records, TLS, host verification, one canonical host, redirect alternate hosts, deploy provider callbacks and permitted origins. Domain purchase/availability is not assumed.
- [ ] **Clean routes:** meaningful stable public paths; preserve application links and sanitize return URLs.
- [ ] **Custom 404:** correct 404 status, helpful DraftWise wording and public navigation; no fake successful page or leaked private IDs. Add application error boundaries.
- [ ] **Unique title/description:** server-defined metadata per public route; contextual private titles without exposing sensitive shipment data in share metadata.
- [ ] **Canonical tags:** absolute public canonical built from validated `SITE_URL`; no localhost production fallback; filter/query variants canonicalize correctly.
- [ ] **Sitemap:** `app/sitemap.ts` includes only public canonical routes, honest last-modified dates and excludes auth/demo/workspaces.
- [ ] **Robots:** `app/robots.ts`, sitemap URL, private/auth/demo exclusions and noindex metadata/headers on protected routes. Robots rules are not authorization.
- [ ] **llms.txt:** curated public product/workflow/help links, current capability boundaries and no private sources. This is informational, not a guarantee of crawler behavior or search ranking.
- [ ] **Favicon:** approved brand mark in favicon/browser/app icon sizes; test on light/dark browser chrome.
- [ ] **Internal links:** product -> workflow -> demo/pricing/help; footer privacy/terms; avoid orphan pages and broken links.
- [ ] **Breadcrumbs:** appropriate workspace hierarchy and `BreadcrumbList` on genuine public hierarchical pages.
- [ ] **Structured data:** truthful `Organization`, `WebSite` and `SoftwareApplication` JSON-LD; only include offer/review fields with verified facts.
- [ ] **Local business schema:** conditional checklist item. Use `LocalBusiness` only if DraftWise has a real applicable business location and the required public facts. Otherwise use Organization/SoftwareApplication and record “not applicable”; never invent an address, opening hours or rating to satisfy a checklist.
- [ ] **Social share images:** Open Graph/Twitter metadata, absolute image URLs, 1200x630 artwork, correct image description and share-preview validation.
- [ ] **Image alt text:** meaningful alternatives for workflow/content imagery; empty alt for purely decorative art; logo accessible name; charts include textual/table alternatives.
- [ ] **Production source maps:** disable public browser maps explicitly, verify no reachable `*.map` files; if private error-reporting maps are used, upload privately and exclude public artifacts. Never remove server diagnostics needed for support blindly.
- [ ] **Bundle size/compression:** production build analysis; server-render public content; lazy-load assistant, OCR/evidence viewers and charts; subset fonts; use targeted imports; gzip/Brotli at hosting; cache hashed assets and optimize images. Inspect actual network payload instead of claiming a tiny bundle from configuration alone.

Source guidance: [Google Organization markup](https://developers.google.com/search/docs/appearance/structured-data/organization) and [LocalBusiness eligibility/fields](https://developers.google.com/search/docs/appearance/structured-data/local-business). Correct metadata does not guarantee rich results.

## Acceptance and handoff

Visual review at mobile/tablet/desktop, no prohibited patterns, keyboard/zoom/contrast validation, valid structured data, public metadata checks, private-route indexing exclusions and measured production payloads. Test the anonymous landing-to-demo journey and the signed-in Gmail-to-case journey separately. Persist chosen typography/colors/assets and their rationale so later screens remain consistent.
