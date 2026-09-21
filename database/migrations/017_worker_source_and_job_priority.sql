-- Migration 017: say where each worker runs, and let jobs be ordered by how soon a person needs them.
--
-- worker_heartbeats.kind: 'hosted' (the deployed service), 'local' (any other machine) or
-- 'unknown' (a worker started before this migration). /ready uses it so that a worker left running on
-- a laptop that shares the database can no longer make a hosted API with no worker look healthy.
--
-- processing_jobs.priority: smaller runs sooner. 10 is work a person asked for (the default), 20 is
-- the first emails of a bulk read, 30 is the rest of it. Additive and backward compatible: code that
-- predates this migration simply never sets or reads either column.
begin;
alter table public.worker_heartbeats add column if not exists kind text not null default 'unknown'
  check (kind in ('hosted', 'local', 'unknown'));
alter table public.processing_jobs add column if not exists priority smallint not null default 10
  check (priority between 0 and 100);
commit;
