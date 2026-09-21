# Frontend architecture

[UX specification](UX_SPECIFICATION.md) defines the experience; [API contracts](API_CONTRACTS.md) and [feature contracts](FEATURE_CONTRACTS.md) define server behavior.

Use Next.js App Router, TypeScript, Tailwind CSS and Shadcn UI on Vercel. Use Supabase Auth with server/client session separation. FastAPI verifies every token and workspace membership independently.

## Exact implementation paths

```text
frontend/
  app/
    layout.tsx
    page.tsx                           # redirect authenticated users to /dashboard
    globals.css
    dashboard/page.tsx                 # default attention queue
    cases/[caseId]/page.tsx             # one case resolution workspace
    inbox/page.tsx
    inbox/[emailId]/page.tsx
    completed/page.tsx
    settings/rules/page.tsx
    settings/workspace/page.tsx
    quality/benchmarks/page.tsx
    login/page.tsx
    error.tsx
    not-found.tsx
  components/
    ui/                                # Shadcn primitives
    layout/app-shell.tsx
    queue/case-table.tsx
    queue/next-action-cell.tsx
    cases/case-header.tsx
    cases/issue-list.tsx
    cases/next-action-card.tsx
    cases/field-comparison.tsx
    cases/evidence-viewer.tsx
    cases/correction-preview.tsx
    cases/amendment-timeline.tsx
    cases/returned-draft-summary.tsx
    cases/upload-sheet.tsx
    rules/equivalence-rule-form.tsx
    rules/rule-impact-preview.tsx
  lib/
    api/client.ts                      # auth, errors, request IDs and aborts
    api/generated.ts                   # generated from OpenAPI
    auth/client.ts
    auth/server.ts
    queries/cases.ts
    queries/jobs.ts
    queries/rules.ts
    evidence/coordinates.ts
  tests/
    case-resolution.spec.ts
    amendment-regression.spec.ts
    accessibility.spec.ts
  components.json
  package.json
  pnpm-lock.yaml
  next.config.ts
  tsconfig.json
```

## State ownership

Server Components own the shell and authorized initial load. Interactive case components are Client Components. TanStack Query owns remote state with keys containing workspace ID, entity ID and revision. URL parameters retain queue filters and selected immutable report; local state holds panel width, selected field and unsaved message text. Do not persist original document content in localStorage.

The server is authoritative for readiness, next actions, issue state and preview validity. Poll active jobs at a bounded interval with backoff; fetch SSE can enhance this later. Revalidate case state after every mutation. Clearing a browser query cache must not lose durable work. Workspace switch/logout cancels requests and removes cached private data.

## Integration rules

Only `lib/api/client.ts` constructs API requests. Components never call Gemini or use Supabase service credentials. API-generated types and schemas define payloads; UI-facing model adapters supply readable labels without duplicating domain decisions. Error responses render inline recovery actions tied to typed error codes.

PDF evidence uses lazily rendered PDF.js pages with matching worker assets and verified coordinate transforms. DOCX/XLSX use application-rendered paragraphs/tables/cells; they do not pretend to have verified page numbers. Signed URLs are short-lived and refreshed through the backend. Office/HTML input cannot render executable content.

Use cache control `private, no-store` for sensitive server fetches. Verify workspace access before rendering pages, and again on FastAPI. The public landing/login page can be accessible without exposing documents. A read-only sample workspace contains synthetic data and a clearly labelled sample banner.

## Test focus

Playwright scenarios must cover the main amendment journey, a stale preview, a concurrent reviewer update, provider delay, missing evidence, a weight regression and keyboard navigation. Assert user-visible outcomes and source values rather than internal component structure. Do not substitute screenshot-only tests for workflow correctness.
