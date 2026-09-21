begin;
alter table public.demo_sessions add column if not exists ai_calls integer not null default 0;
create table if not exists public.email_workflows (
  workspace_id uuid not null,
  email_id uuid not null,
  state text not null default 'queued',
  job_id uuid,
  case_id uuid,
  details jsonb not null default '{}',
  updated_at timestamptz not null default now(),
  primary key(workspace_id,email_id),
  foreign key(workspace_id,email_id) references public.emails(workspace_id,id)
);
create table if not exists public.quality_baselines (
  workspace_id uuid primary key references public.workspaces(id),
  version text not null,
  reference_data jsonb not null,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);
create table if not exists public.quality_windows (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id),
  baseline_version text not null,
  fingerprint text not null,
  result jsonb not null,
  created_at timestamptz not null default now(),
  unique(workspace_id,baseline_version,fingerprint)
);
-- All access goes through the authenticated, tenant-scoped backend.
alter table public.email_safety enable row level security;
alter table public.drift_alerts enable row level security;
alter table public.dashboard_preferences enable row level security;
alter table public.email_workflows enable row level security;
alter table public.quality_baselines enable row level security;
alter table public.quality_windows enable row level security;
revoke all on public.email_safety,public.drift_alerts,public.dashboard_preferences,
  public.email_workflows,public.quality_baselines,public.quality_windows from public,anon,authenticated;
grant select,insert,update,delete on public.email_safety,public.drift_alerts,public.dashboard_preferences,
  public.email_workflows,public.quality_baselines,public.quality_windows to service_role;
alter table public.email_safety add constraint email_safety_tenant_fk
  foreign key(workspace_id,email_id) references public.emails(workspace_id,id);
commit;
