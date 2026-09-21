# Data architecture

[Repository overview](../README.md) · [Implementation plan](../IMPLEMENTATION_PLAN.md)


## 1 Migration and ownership model

Use Supabase Auth for identities and workspace membership for access. Business writes pass through FastAPI; authenticated clients have only explicitly granted workspace-scoped reads. Browser access to raw bodies/evidence is optional; the baseline frontend reads through FastAPI. Service-role Storage/API credentials stay server-side and bypass RLS, so every backend repository method requires a verified workspace context. A transaction must never infer workspace from an untrusted request field without checking membership.

The following is an initial migration for a fresh Supabase project. Run once through migrations, not at every application startup. Composite foreign keys enforce tenant consistency even if application code is wrong. Business objects are immutable revisions except operational statuses, memberships and review queue state. JSONB stores schema-versioned evidence/results; normalized searchable fields remain typed.

See the executable initial DDL in [database/schema.sql](../database/schema.sql).

## 2 Transaction rules and access checks

Use a server-only SQL connection for multi-row transactions, via SQLAlchemy async and an appropriate Supabase connection endpoint. A privileged SQL connection can bypass RLS just like the service key; enforce workspace predicates in every query and composite FK constraints. Never expose it to Next.js client code. Repositories use bound parameters and reject unrestricted queries. Transaction pooling requires driver configuration compatible with the pooler, including disabling unsupported prepared-statement caching where applicable; keep connection pool size initially 2–3.

Implement transaction-level validations beyond DDL: seven distinct normalized field rows for a completed extraction; report extraction roles really SI/BL; both extractions belong to the email or a confirmed shipment link; parent extraction belongs to the same attachment; report supersession belongs to the same email; assignee is a workspace reviewer; JSON status agrees with typed columns; `OK` has seven matches and zero discrepancy rows; `MISMATCH` has at least one mismatch and no unresolved rows. Acquire an email/extraction row lock before assigning `max(revision)+1`; unique constraints are the final guard.

Storage has no public buckets and no broad client policies. Backend creates exact-path signed uploads/reads only after membership checks. Storage service-role operations are server-only. Signed reads expire after 60 seconds; authorized clients can refresh them. Pending uploads cannot be viewed as trusted documents. Client JWTs have no ability to insert audit rows or edit evidence directly. Supabase RLS and grants both matter, and service keys bypass RLS. [Supabase RLS guidance](https://supabase.com/docs/guides/database/postgres/row-level-security).

Application transactions append audit entries for imports, classification overrides, pair changes, report creation, review decisions, and deletion requests. The append-only trigger prevents ordinary update/delete; it is not tamper-proof against a database administrator. Retention of audit records uses a separately controlled maintenance migration/process and redacted minimal metadata, rather than blocking legitimate deletion of sensitive file content indefinitely.

JSONB GIN indexes are optional: add only after query profiling demonstrates need, for example on `shipments.references_json`. Do not index large raw extraction payloads by default. Use keyset pagination on `(created_at,id)` and `(priority,created_at,id)`; aggregate benchmark metrics in stored run JSON rather than recomputing on every page load.


## Case and amendment entities

The complete fresh-install schema includes the new amendment entities: customers, cases, case documents, amendment rounds, issues/events, next actions/dependencies, correction previews, amendment drafts and scoped equivalence rules/evaluations/applications. See [database instructions](../database/README.md) for fresh versus upgrade application.

Case writes lock the row and compare `version`; report/source relationships are validated in the same transaction. `checked` requires a complete current `OK` report against the active source IDs and policy. The DDL's foreign keys alone do not prove semantic compatibility. Dependencies must form an acyclic graph within one case; source references cannot cross extraction boundaries. Preserve rule content snapshots and audit state transitions. Numeric fields and missing values cannot be overridden by equivalence rules.
