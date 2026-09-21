-- Apply after schema.sql. Internal worker liveness; no browser access.
begin;
create table if not exists public.worker_heartbeats (
  id uuid primary key,
  last_seen timestamptz not null default now()
);
alter table public.worker_heartbeats enable row level security;
revoke all on public.worker_heartbeats from anon, authenticated;
grant select,insert,update,delete on public.worker_heartbeats to service_role;
commit;
