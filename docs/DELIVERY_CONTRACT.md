# Repository delivery contract

[Implementation plan](../IMPLEMENTATION_PLAN.md) · [File manifest](../repository.manifest.json)

## Current artifact and application generation

This revision is an implementation-specification repository. Database DDL, shared JSON schemas, examples, prompt templates and a repository validator are actual files. Application modules are listed separately as planned destinations. This status is deliberate and must remain visible; no document implies that an unimplemented API, UI or cloud deployment is already working.

When generating the application from this plan, deliver a clean multi-file GitHub repository. Write each file separately at its proper path; never return one giant Markdown file containing all source code. Examples of required real paths are `backend/app/api/verify.py`, `frontend/app/dashboard/page.tsx`, `database/schema.sql` and `docs/SYSTEM_ARCHITECTURE.md`.

## File and module rules

- Use `backend/`, `frontend/`, `database/`, `shared/`, `prompts/`, `scripts/`, `docker/`, `docs/` and `.github/` as the root boundaries.
- Each backend router delegates to services and repositories. Domain comparison, revision analysis and correction previews are pure functions with typed inputs and deterministic outputs.
- Each frontend route composes focused components. Dashboard and case pages do not contain provider calls, normalization policies or inline database queries.
- Keep schemas as JSON files and SQL as executable `.sql` files; docs link to their authoritative locations.
- Generate TypeScript API types from FastAPI OpenAPI; do not maintain competing category/field enums by hand.
- Commit tested dependency lockfiles and meaningful configuration. Never invent lockfile integrity hashes or publish a container configuration that has not been built as if it was tested.
- Avoid empty stubs, `pass`, fake metrics and success responses for unimplemented operations. Unsupported optional integrations must be explicitly unavailable, with a typed recoverable state.
- Do not copy the organizer answer key, reference repository code without permission, or local source materials into the application tree.
- Do not create an application license on the user's behalf. Retain required third-party notices and document unresolved code licensing before incorporating external code.

## Required implementation completeness

The application must implement the authorized flow end to end: import inputs → classify → resolve sources → extract → compare → show evidence → support review → create correction preview → accept a revised draft → detect fixes and regressions. All user-facing actions in the shipped UI must call real validated code or be clearly unavailable.

Produce actual tests alongside the modules. Test supported normalization and missing evidence, regression detection, preview purity, stale versions, cross-workspace access, durable job restart and the critical browser journey. Run appropriate checks once the code exists. The current plan validator cannot substitute for those checks.

## Repository acceptance

1. A fresh clone has one clear setup entry point in `README.md`.
2. The tree matches `repository.manifest.json`; implemented and planned files are distinguished.
3. Secrets are absent and `.env.example` contains only variable names/defaults.
4. SQL applies to a fresh isolated Supabase project before deployment is described as ready.
5. Frontend build/type checks, backend tests, tenant authorization tests and browser flows pass.
6. The deployed environment has real provider/DB configuration or an explicit unavailable state; no test fixture is masquerading as a live result.
7. The final delivery reports actual commands/checks run and remaining configuration or validation limits.

Publishing to GitHub is a separate operation requiring the destination repository/account. A GitHub-ready directory does not imply a repository has been created or pushed.
