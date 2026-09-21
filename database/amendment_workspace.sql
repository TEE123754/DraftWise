-- Apply after the initial schema, once. Also included in schema.sql for a fresh project.
begin;

create table public.customers (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id),
  display_name text not null check(length(display_name) between 1 and 240),
  created_at timestamptz not null default now(),
  unique(workspace_id,id)
);

create table public.cases (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  email_id uuid not null,
  customer_id uuid,
  reference text not null check(length(reference) between 1 and 120),
  version integer not null default 1 check(version>0),
  baseline_version integer not null default 1 check(baseline_version>0),
  readiness text not null default 'needs_source' check(readiness in
    ('needs_source','checking','needs_decision','changes_required','awaiting_revision','checked','failed')),
  active_si_id uuid,
  active_bl_id uuid,
  latest_report_id uuid,
  policy_version text not null default 'v1',
  confirmed_deadline timestamptz,
  deadline_confirmed_by uuid references auth.users(id),
  deadline_evidence jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(workspace_id,id),
  unique(workspace_id,email_id),
  foreign key(workspace_id,email_id) references public.emails(workspace_id,id),
  foreign key(workspace_id,customer_id) references public.customers(workspace_id,id),
  foreign key(workspace_id,active_si_id) references public.document_extractions(workspace_id,id),
  foreign key(workspace_id,active_bl_id) references public.document_extractions(workspace_id,id),
  foreign key(workspace_id,latest_report_id) references public.verification_reports(workspace_id,id),
  check(confirmed_deadline is null or (deadline_confirmed_by is not null and deadline_evidence is not null)),
  check(readiness<>'checked' or (active_si_id is not null and active_bl_id is not null and latest_report_id is not null))
);
create index cases_queue_idx on public.cases(workspace_id,readiness,updated_at desc,id);
create index cases_customer_idx on public.cases(workspace_id,customer_id);

create table public.case_documents (
  workspace_id uuid not null,
  case_id uuid not null,
  attachment_id uuid not null,
  confirmed_by uuid references auth.users(id),
  relationship_evidence jsonb not null default '{}',
  created_at timestamptz not null default now(),
  primary key(workspace_id,case_id,attachment_id),
  foreign key(workspace_id,case_id) references public.cases(workspace_id,id),
  foreign key(workspace_id,attachment_id) references public.attachments(workspace_id,id)
);

create table public.amendment_rounds (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  case_id uuid not null,
  baseline_version integer not null check(baseline_version>0),
  round_number integer not null check(round_number>0),
  si_extraction_id uuid not null,
  previous_bl_id uuid,
  new_bl_id uuid not null,
  previous_report_id uuid,
  new_report_id uuid not null,
  policy_version text not null,
  summary jsonb not null check(jsonb_typeof(summary)='object'),
  created_at timestamptz not null default now(),
  unique(workspace_id,id), unique(workspace_id,case_id,round_number),
  unique(workspace_id,case_id,baseline_version,new_bl_id,policy_version),
  foreign key(workspace_id,case_id) references public.cases(workspace_id,id),
  foreign key(workspace_id,si_extraction_id) references public.document_extractions(workspace_id,id),
  foreign key(workspace_id,previous_bl_id) references public.document_extractions(workspace_id,id),
  foreign key(workspace_id,new_bl_id) references public.document_extractions(workspace_id,id),
  foreign key(workspace_id,previous_report_id) references public.verification_reports(workspace_id,id),
  foreign key(workspace_id,new_report_id) references public.verification_reports(workspace_id,id),
  check(previous_bl_id is null or previous_bl_id<>new_bl_id)
);

create table public.case_issues (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  case_id uuid not null,
  baseline_version integer not null check(baseline_version>0),
  field public.field_name not null,
  state text not null default 'open' check(state in ('open','resolved','superseded')),
  kind text not null check(kind in ('mismatch','missing','ambiguous','regressed')),
  source_report_id uuid not null,
  resolved_report_id uuid,
  prior_issue_id uuid,
  evidence jsonb not null default '[]',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(workspace_id,id),
  foreign key(workspace_id,case_id) references public.cases(workspace_id,id),
  foreign key(workspace_id,source_report_id) references public.verification_reports(workspace_id,id),
  foreign key(workspace_id,resolved_report_id) references public.verification_reports(workspace_id,id),
  foreign key(workspace_id,prior_issue_id) references public.case_issues(workspace_id,id),
  check(state<>'resolved' or resolved_report_id is not null)
);
create unique index one_open_field_issue_idx on public.case_issues(workspace_id,case_id,baseline_version,field)
  where state='open';
create index issues_case_idx on public.case_issues(workspace_id,case_id,state);

create table public.issue_events (
  id bigint generated always as identity primary key,
  workspace_id uuid not null,
  issue_id uuid not null,
  actor_id uuid references auth.users(id),
  event_type text not null check(event_type in ('opened','acknowledged','resolved','superseded','rechecked')),
  details jsonb not null,
  created_at timestamptz not null default now(),
  foreign key(workspace_id,issue_id) references public.case_issues(workspace_id,id)
);
create index issue_events_cursor_idx on public.issue_events(workspace_id,issue_id,id);

create table public.case_actions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  case_id uuid not null,
  case_version integer not null check(case_version>0),
  kind text not null check(kind in ('choose_source','add_draft','confirm_value','review_regression','preview_request','retry')),
  state text not null default 'open' check(state in ('open','answered','declined','stale')),
  question text not null,
  affected_fields public.field_name[] not null default '{}',
  evidence jsonb not null default '[]',
  decision jsonb,
  priority integer not null default 50 check(priority between 0 and 100),
  created_at timestamptz not null default now(),
  unique(workspace_id,id),
  foreign key(workspace_id,case_id) references public.cases(workspace_id,id)
);
create index case_actions_open_idx on public.case_actions(workspace_id,case_id,priority desc) where state='open';

create table public.evidence_dependencies (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  case_id uuid not null,
  extraction_id uuid,
  parent_action_id uuid,
  parent_field public.field_name,
  child_field public.field_name not null,
  kind text not null check(kind in ('source_selection','same_document_reference','source_region')),
  evidence jsonb not null,
  foreign key(workspace_id,case_id) references public.cases(workspace_id,id),
  foreign key(workspace_id,extraction_id) references public.document_extractions(workspace_id,id),
  foreign key(workspace_id,parent_action_id) references public.case_actions(workspace_id,id),
  check(parent_field is null or parent_field<>child_field),
  check(kind<>'same_document_reference' or (extraction_id is not null and parent_field is not null)),
  check(kind<>'source_selection' or parent_action_id is not null)
);

create table public.correction_previews (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  case_id uuid not null,
  case_version integer not null check(case_version>0),
  report_id uuid not null,
  fingerprint text not null check(fingerprint ~ '^[0-9a-f]{64}$'),
  payload jsonb not null check(jsonb_typeof(payload)='object'),
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  unique(workspace_id,id),
  foreign key(workspace_id,case_id) references public.cases(workspace_id,id),
  foreign key(workspace_id,report_id) references public.verification_reports(workspace_id,id),
  check(expires_at>created_at and expires_at<=created_at+interval '30 minutes')
);
create index previews_case_idx on public.correction_previews(workspace_id,case_id,case_version);

create table public.amendment_drafts (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  case_id uuid not null,
  preview_id uuid not null,
  case_version integer not null check(case_version>0),
  state text not null default 'draft' check(state in ('draft','marked_shared','stale')),
  message text not null check(length(message) between 1 and 8000),
  requested_changes jsonb not null check(jsonb_typeof(requested_changes)='array'),
  created_by uuid not null references auth.users(id),
  shared_note text,
  shared_at timestamptz,
  created_at timestamptz not null default now(),
  unique(workspace_id,id),
  foreign key(workspace_id,case_id) references public.cases(workspace_id,id),
  foreign key(workspace_id,preview_id) references public.correction_previews(workspace_id,id),
  check(state<>'marked_shared' or (shared_at is not null and shared_note is not null))
);

create table public.equivalence_rules (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  customer_id uuid not null,
  field public.field_name not null check(field not in ('container_count','gross_weight_kg')),
  left_value text not null check(length(left_value) between 1 and 4000),
  right_value text not null check(length(right_value) between 1 and 4000),
  version integer not null default 1 check(version>0),
  state text not null default 'proposed' check(state in ('proposed','approved','revoked')),
  content_sha256 text not null check(content_sha256 ~ '^[0-9a-f]{64}$'),
  evidence jsonb not null,
  proposed_by uuid not null references auth.users(id),
  approved_by uuid references auth.users(id),
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  unique(workspace_id,id),
  foreign key(workspace_id,customer_id) references public.customers(workspace_id,id),
  check(left_value<>right_value),
  check(state<>'approved' or (approved_by is not null and approved_at is not null))
);
create index rules_scope_idx on public.equivalence_rules(workspace_id,customer_id,field) where state='approved';

create table public.rule_evaluations (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  rule_id uuid not null,
  rule_version integer not null check(rule_version>0),
  rule_content_sha256 text not null,
  manifest_sha256 text not null,
  state text not null check(state in ('queued','running','passed','failed','insufficient_validation')),
  metrics jsonb,
  created_at timestamptz not null default now(),
  unique(workspace_id,id),
  foreign key(workspace_id,rule_id) references public.equivalence_rules(workspace_id,id)
);

create table public.report_rule_applications (
  workspace_id uuid not null,
  report_id uuid not null,
  rule_id uuid not null,
  rule_version integer not null check(rule_version>0),
  rule_snapshot jsonb not null,
  primary key(workspace_id,report_id,rule_id),
  foreign key(workspace_id,report_id) references public.verification_reports(workspace_id,id),
  foreign key(workspace_id,rule_id) references public.equivalence_rules(workspace_id,id)
);

do $$
declare t text;
begin
  foreach t in array array['customers','cases','case_documents','amendment_rounds','case_issues',
    'issue_events','case_actions','evidence_dependencies','correction_previews','amendment_drafts',
    'equivalence_rules','rule_evaluations','report_rule_applications']
  loop
    execute format('alter table public.%I enable row level security',t);
    execute format('revoke all on public.%I from anon,authenticated',t);
    execute format('grant select,insert,update,delete on public.%I to service_role',t);
    execute format('create policy member_read on public.%I for select to authenticated using (public.is_member(workspace_id))',t);
  end loop;
end;
$$;
grant usage,select on sequence public.issue_events_id_seq to service_role;
commit;
