# Database artifacts

`schema.sql` is the complete fresh-project Supabase schema, including the amendment workspace. Apply it once. It is executable SQL rather than Markdown pseudocode. It relies on Supabase's `auth`, `storage`, `anon`, `authenticated` and `service_role` objects.

For an existing installation of the original base schema, apply `amendment_workspace.sql` once instead of rerunning `schema.sql`. Do not apply both to a fresh project: the full schema includes the same amendment DDL. This repository has no production database migration execution record; validate in an isolated Supabase project before deployment.

`queries/claim_job.sql` contains the bounded, fenced worker claim operation. Use the returned lease token in the final commit transaction.

All application tables use RLS and explicit grants. Business access goes through the authorized FastAPI service by default. Composite foreign keys enforce workspace consistency. Backend services must additionally check case/attachment/report relationships, source roles and optimistic versions; RLS is bypassed by privileged server credentials.

The case projection is derived, never an operator-editable status. A `checked` transition requires a current complete `OK` report for the pinned SI/BL/policy in the same transaction. A preview cannot change that state. Rule activation/revocation and SI re-baselining must stale previews and schedule dependent recomputation.

Use a migration tool to record application when implementation starts. Subsequent changes are additive versioned migrations; regenerate the fresh-install snapshot from those migrations. Do not edit an already-applied migration or treat `CREATE TABLE IF NOT EXISTS` as a schema upgrade.
