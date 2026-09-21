# Repository structure

[Delivery contract](DELIVERY_CONTRACT.md) · [Machine-readable manifest](../repository.manifest.json)

## Files delivered in this plan revision

```text
/
  README.md
  IMPLEMENTATION_PLAN.md
  repository.manifest.json
  .editorconfig
  .gitignore
  .github/workflows/validate-specification.yml
  backend/
    README.md
    .env.example
  frontend/
    README.md
    .env.example
  database/
    README.md
    schema.sql
    amendment_workspace.sql
    queries/claim_job.sql
  shared/
    schemas/
      extraction.schema.json
      verification.schema.json
      submission.schema.json
      case.schema.json
      correction-preview.schema.json
      revision-summary.schema.json
    examples/
      verification.json
      submission.json
      case.json
      correction-preview.json
      revision-summary.json
    fixtures/amendment-scenarios.json
  prompts/
    classify.v1.txt
    extract.v1.txt
    equivalence.v1.txt
  scripts/validate_repository.py
  docker/README.md
  docs/
    PRODUCT_SPECIFICATION.md
    UX_SPECIFICATION.md
    FEATURE_CONTRACTS.md
    SYSTEM_ARCHITECTURE.md
    PROCESSING_PIPELINE.md
    AI_EXTRACTION.md
    DOCUMENT_PARSING.md
    VERIFICATION_ENGINE.md
    DATA_ARCHITECTURE.md
    BACKEND_ARCHITECTURE.md
    FRONTEND_ARCHITECTURE.md
    API_CONTRACTS.md
    BENCHMARKING.md
    OPERATIONS.md
    ACCEPTANCE_CRITERIA.md
    REFERENCES.md
    REPOSITORY_STRUCTURE.md
    DELIVERY_CONTRACT.md
```

## Application file generation

The manifest distinguishes actual delivered artifacts from planned application modules. Generate planned files at their exact paths when implementing the app; do not paste source into a single document or create empty files merely to match this tree. Detailed backend and frontend module responsibilities are in their architecture documents.

Route naming is now canonical under `backend/app/api/`. Earlier references to `api/routers/verify.py` are superseded by `api/verify.py`. The operator landing page is `frontend/app/dashboard/page.tsx`; case resolution is `frontend/app/cases/[caseId]/page.tsx`. Historical report deep links redirect into the case workspace while retaining immutable report selection.

Source materials, reference checkout, private organizer labels and analysis scripts remain local outside the deliverable manifest and are ignored by Git. Do not publish a GitHub repository until its actual intended destination is provided.
