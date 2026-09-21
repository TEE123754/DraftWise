begin;
create table if not exists public.demo_sessions (
  token_hash text primary key check(length(token_hash)=64),
  workspace_id uuid not null unique references public.workspaces(id),
  actor_id uuid not null references auth.users(id),
  manifest_sha256 text not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default now()+interval '8 hours'
);
alter table public.demo_sessions enable row level security;
revoke all on public.demo_sessions from public,anon,authenticated;
grant select,insert,update,delete on public.demo_sessions to service_role;
commit;
