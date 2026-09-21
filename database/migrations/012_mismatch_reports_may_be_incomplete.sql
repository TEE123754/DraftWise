-- A verification report with a real MISMATCH and an unresolved field (a difference plus a blank
-- value) is valid: verify() returns status MISMATCH with complete=false and the unresolved fields
-- in review_reasons. The old CHECK required every MISMATCH to be complete, so the worker's insert
-- failed and the job ended as PROCESSING_FAILED.
--
-- New rule: OK is complete with no reasons; NEEDS_REVIEW is incomplete with reasons; MISMATCH is
-- complete exactly when nothing is unresolved. Relaxing a check cannot invalidate existing rows.
-- Idempotent: safe to run more than once.
alter table public.verification_reports
  drop constraint if exists verification_reports_check1;
alter table public.verification_reports
  drop constraint if exists verification_reports_status_consistency;
alter table public.verification_reports
  add constraint verification_reports_status_consistency check(
    (status='NEEDS_REVIEW' and not complete and cardinality(review_reasons)>0)
    or (status='OK' and complete and cardinality(review_reasons)=0
        and si_extraction_id is not null and bl_extraction_id is not null)
    or (status='MISMATCH' and complete=(cardinality(review_reasons)=0)
        and si_extraction_id is not null and bl_extraction_id is not null));
