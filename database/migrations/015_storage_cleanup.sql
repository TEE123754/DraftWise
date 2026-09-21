-- Migration 015: physical deletion of uploaded objects after Trash retention (P6).
begin;
create table if not exists public.storage_cleanup (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  storage_key text not null,
  -- pending: to delete (or retry); deleted: gone; skipped: a linked document still uses the bytes;
  -- failed: gave up after repeated errors, for an administrator to look at.
  state text not null default 'pending' check(state in ('pending','deleted','skipped','failed')),
  attempts integer not null default 0 check(attempts>=0),
  last_error text,
  next_attempt_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  finished_at timestamptz,
  unique(workspace_id,storage_key)
);
create index if not exists storage_cleanup_due_idx on public.storage_cleanup(next_attempt_at) where state='pending';
alter table public.storage_cleanup enable row level security;
revoke all on public.storage_cleanup from public,anon,authenticated;
grant select,insert,update,delete on public.storage_cleanup to service_role;
commit;
