# Shipping amendment workspace

A shipping amendment workspace that helps operators resolve draft Bill of Lading issues and verify returned corrections against pinned Shipping Instructions.

**Current status:** partial implementation. FastAPI services, PostgreSQL repositories/worker, parsers, CLI and Next.js UI are present. Local tests and frontend build pass. Live integrations and deployment acceptance are pending; this is not yet production ready. See [implementation status](docs/IMPLEMENTATION_STATUS.md) and [local setup](docs/LOCAL_SETUP.md).

## Start here

- [Implementation plan](IMPLEMENTATION_PLAN.md): concise decisions and navigation.
- [Product specification](docs/PRODUCT_SPECIFICATION.md): amendment regression checks, correction previews, guided decisions and approved equivalence memory.
- [UX specification](docs/UX_SPECIFICATION.md): focused attention queue and one case workspace.
- [Repository structure](docs/REPOSITORY_STRUCTURE.md): actual artifacts and planned application paths.
- [Delivery contract](docs/DELIVERY_CONTRACT.md): requirements for generating the application as separate files.

## Validate this repository

Python 3.10 or newer is sufficient for the specification checks; no secrets or dependencies are required.

```bash
python scripts/validate_repository.py
```

The validator checks file inventory, local Markdown links, JSON syntax, schema examples and SQL inventory. Backend tests and frontend build/browser tests are separate checks described in the setup guide.

## Technical artifacts

- [database/schema.sql](database/schema.sql): complete initial Supabase schema.
- [database/amendment_workspace.sql](database/amendment_workspace.sql): upgrade from the earlier base schema only; do not apply after the complete fresh schema.
- [Shared schemas](shared/schemas/verification.schema.json) and [feature contracts](docs/FEATURE_CONTRACTS.md): typed domain and API behavior.
- [Backend environment example](backend/.env.example) and [frontend environment example](frontend/.env.example): safe configuration names.
- [Benchmark integration](docs/BENCHMARKING.md): actual supplied harness and documented annotation limitations.

## Stack and implementation

Next.js App Router, TypeScript, Tailwind and Shadcn UI on Vercel; FastAPI and durable asynchronous work on Railway; Supabase PostgreSQL/Storage/Auth; Gemini structured outputs and local document/OCR tools. Free allowances are bounded; see [operations](docs/OPERATIONS.md) for quotas and deployment limitations.

Use the [machine-readable manifest](repository.manifest.json) to generate each planned module at its proper path. Keep routes, services, repositories, components, schemas, prompts and tests in separate files. Source materials and private local analysis are ignored by Git and are not deliverable application code. No remote GitHub repository has been created or pushed.
