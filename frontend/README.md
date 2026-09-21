# Frontend

Stack: Next.js App Router, TypeScript, Tailwind CSS, Shadcn UI, Vercel.

Read [UX specification](../docs/UX_SPECIFICATION.md) before implementing components, then [frontend architecture](../docs/FRONTEND_ARCHITECTURE.md) and [feature contracts](../docs/FEATURE_CONTRACTS.md).

Generate actual modules separately: `app/dashboard/page.tsx` owns the work queue; `app/cases/[caseId]/page.tsx` owns the complete amendment workflow. Related evidence, next action, preview and history components live under `components/cases/`. The operator should not navigate across separate extraction/review/confidence pages to resolve one case.

The source modules are implemented, and the production build and mocked browser tests pass. Live API/Supabase integration remains pending. See [local setup](../docs/LOCAL_SETUP.md) and [implementation status](../docs/IMPLEMENTATION_STATUS.md).

```bash
pnpm install --frozen-lockfile
pnpm dev
pnpm build
pnpm test:e2e
```

Use generated API types and server-authoritative case state. Keep privileged API keys out of browser code. Test actual decision flows, concurrency errors and keyboard operation rather than only screenshots.
