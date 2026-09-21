-- Migration 014: AI budget, answer cache and classifier quality runs (P8 and the token policy).
begin;

-- Live AI calls made per workspace per day. The daily budget is enforced against this.
create table if not exists public.ai_usage (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  day date not null,
  calls integer not null default 0 check(calls>=0),
  primary key(workspace_id,day)
);

-- One provider answer per distinct input, so the same email or document is never sent twice.
create table if not exists public.ai_cache (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  cache_key text not null,
  kind text not null check(kind in ('classify','extract')),
  result jsonb not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  primary key(workspace_id,cache_key)
);

-- Measured accuracy of the AI classifier next to the rules, on a labelled sample.
create table if not exists public.quality_runs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  kind text not null check(kind in ('ai_classifier')),
  source text not null check(source in ('heldout_cached','heldout_live')),
  status text not null default 'complete' check(status in ('running','complete','failed')),
  sample_size integer not null default 0 check(sample_size>=0),
  calls_made integer not null default 0 check(calls_made>=0),
  metrics jsonb not null default '{}',
  error text,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  finished_at timestamptz
);
create index if not exists quality_runs_latest_idx on public.quality_runs(workspace_id,kind,created_at desc);

alter table public.ai_usage enable row level security;
alter table public.ai_cache enable row level security;
alter table public.quality_runs enable row level security;
revoke all on public.ai_usage, public.ai_cache, public.quality_runs from public,anon,authenticated;
grant select on public.ai_usage, public.quality_runs to authenticated;
grant select,insert,update,delete on public.ai_usage, public.ai_cache, public.quality_runs to service_role;
create policy ai_usage_member_read on public.ai_usage for select to authenticated
using(public.is_member(workspace_id));
create policy quality_runs_member_read on public.quality_runs for select to authenticated
using(public.is_member(workspace_id));
commit;
