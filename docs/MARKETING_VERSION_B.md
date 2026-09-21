# DraftWise marketing Version B

## Latest reference refinement

The carrier section has now been removed entirely, along with rules-first / optional-AI promotional wording. The shorter layout uses a cohesive robot-and-ship scene, compact workflow and feature cards, and a shorter footer. Copy and metadata describe the actual SI/BL seven-field review and follow-up workflow. Generic social homepage links and unsupported forwarding, instant-result and vessel-validation claims were removed. Five browser checks and the production build passed; localhost was refreshed.

New asset: `frontend/public/images/shipping-assistant-v3.png`, generated with built-in imagegen, copied into the workspace, and optimized via Next Image. Generation prompt:

Create a polished 3D business website hero illustration for DraftWise shipping email document verification. Wide 3:2 landscape, pale icy blue seamless background. A friendly white and navy AI robot with glowing cyan smiling eyes and rounded head, blue headset, small orange accent, upright torso and one hand gesturing, prominently center-right, behind a sleek navy container cargo ship with blue and orange containers and stylized gentle blue waves. The robot and ship are a single cohesive scene, with generous empty pale blue space in upper left and upper right for HTML floating cards. Light clouds, soft daylight, refined clean 3D rendering, professional and approachable. Main scene fills frame, clean edges, no circular badge or round border. No text, no wordmark, no logos, no interface cards, no UI, no purple, no grain. Not a photo; polished stylized 3D illustration matching a friendly logistics assistant.

The earlier notes below describe the previous iteration and are superseded by this refinement where they differ.

Implemented 2026-09-21 in the existing `(marketing)` route group. This brief supersedes the earlier no-glass/no-badge restrictions for marketing pages only.

- [x] Sticky glass navigation, mobile menu, existing route links and navy footer.
- [x] Existing horizontal/full logos and mascot; bespoke maritime illustration.
- [x] Native pointer parallax and card tilt/spotlight, with reduced-motion and coarse-pointer opt-outs.
- [x] Four-step workflow, four feature cards, reusable Card/Badge primitives and existing Button/Tooltip components.
- [x] Clearly labelled illustrative status cards, optional-AI copy and sample demo links.
- [x] Production build; browser reliability/design-system checks (8 passed) plus final marketing check (1 passed). Automated axe check passed; 390/768/1440px checks found no horizontal overflow. Image loading, keyboard tips, Escape dismissal, reduced motion and six existing routes verified.
- [x] Existing API, auth, forms, database and workspace business logic left unchanged.

Accuracy decisions: no unmeasured promise of completion in seconds, no automated sending or forwarding claim, no guarantee of fraud detection, and no claim of packing-list/invoice field verification. Carrier names are explicitly industry context, not endorsements or integrations. Official social/contact URLs were not supplied, so no invented links were added. No modal was needed: all primary actions retain `/demo` navigation.

Asset: `frontend/public/images/maritime-hero-v2.png`. Generated with the built-in imagegen tool and copied into the repository; served with responsive Next Image optimization. Existing supplied logos and mascot were reused without alteration.

## Generation prompt

Use case: stylized-concept. Production website hero illustration for DraftWise, a shipping document review product. Wide 3:2 composition, polished 3D isometric container vessel pointing right cutting through stylized ocean waves. Deep maritime navy #0B2A5C hull, royal blue #0D63DD and a few orange #F97316 shipping containers, white bridge. Vessel occupies lower half with generous pale icy blue negative space above for a separate robot mascot overlay and floating UI cards. Seamless soft pale blue #EBF3FC backdrop, gentle daylight, clean business illustration, crisp silhouettes. No text, no logos, no people, no robot, no UI cards, no grain or purple. High quality finished illustration, not a mockup.

## Files

Layout, page and scoped stylesheet: `frontend/app/(marketing)/`.
Interactive visual and sections: `frontend/components/marketing/`.
Verification: `frontend/tests/marketing.spec.ts`, `frontend/tests/reliability.spec.ts`, `frontend/tests/design-system.spec.ts`.
Screenshots: `artifacts/ui/landing-redesign-desktop.png`, `artifacts/ui/landing-redesign-mobile.png`, `artifacts/ui/marketing-workflow-mobile.png`.
