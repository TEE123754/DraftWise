-- Initial Supabase schema. Apply once to a fresh project.
begin;
create extension if not exists pgcrypto;

create type public.email_category as enum
  ('BL_COMPARISON','SI_REQUEST','INVOICE_QUERY','GENERAL','SPAM');
create type public.document_role as enum
  ('SI','BL','INVOICE','PACKING_LIST','CERTIFICATE','UNKNOWN','EMAIL_BODY');
create type public.field_name as enum
  ('shipper','consignee','notify_party','port_of_loading',
   'port_of_discharge','container_count','gross_weight_kg');
create type public.field_state as enum ('present','missing','ambiguous','unreadable');
create type public.report_status as enum ('OK','MISMATCH','NEEDS_REVIEW');
create type public.job_status as enum
  ('queued','running','retry_wait','succeeded','needs_review','failed','cancelled');
create type public.review_status as enum ('open','claimed','resolved','dismissed');

create table public.workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null check (length(name) between 1 and 120),
  settings jsonb not null default '{}' check (jsonb_typeof(settings)='object'),
  settings_version integer not null default 1 check(settings_version>0),
  created_at timestamptz not null default now()
);
create table public.memberships (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('viewer','operator','reviewer','admin')),
  primary key (workspace_id,user_id)
);
create index memberships_user_idx on public.memberships(user_id,workspace_id);

create table public.emails (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id),
  source_namespace text not null,
  external_id text not null,
  sender text not null,
  subject text not null default '',
  body text not null default '',
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  segments jsonb not null default '[]' check (jsonb_typeof(segments)='array'),
  received_at timestamptz,
  created_at timestamptz not null default now(),
  unique(workspace_id,id),
  unique(workspace_id,source_namespace,external_id)
);
create index emails_list_idx on public.emails(workspace_id,created_at desc,id);

create table public.email_classifications (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  email_id uuid not null,
  revision integer not null check(revision>0),
  category public.email_category not null,
  ambiguous boolean not null default false,
  confidence numeric(5,4) not null check(confidence between 0 and 1),
  decided_by text not null check(decided_by in ('rule','ai','human')),
  evidence jsonb not null default '[]',
  run_metadata jsonb not null,
  created_at timestamptz not null default now(),
  unique(workspace_id,id), unique(workspace_id,email_id,revision),
  foreign key(workspace_id,email_id) references public.emails(workspace_id,id)
);
create index classifications_category_idx
  on public.email_classifications(workspace_id,category,email_id,revision desc);

create table public.attachments (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  email_id uuid not null,
  original_name text not null,
  storage_key text not null,
  mime_type text not null,
  byte_size bigint not null check(byte_size>=0 and byte_size<=20971520),
  sha256 text check(sha256 ~ '^[0-9a-f]{64}$'),
  role public.document_role not null default 'UNKNOWN',
  state text not null default 'pending'
    check(state in ('pending','validated','quarantined','deleted')),
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique(workspace_id,id), unique(storage_key),
  foreign key(workspace_id,email_id) references public.emails(workspace_id,id)
);
create index attachments_email_idx on public.attachments(workspace_id,email_id);
create index attachments_hash_idx on public.attachments(workspace_id,sha256);

create table public.source_blocks (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  attachment_id uuid not null,
  parser_version text not null,
  ordinal integer not null check(ordinal>=0),
  text_content text not null,
  locator jsonb not null check(jsonb_typeof(locator)='object'),
  quality numeric(5,4) check(quality between 0 and 1),
  unique(workspace_id,id),
  unique(workspace_id,attachment_id,parser_version,ordinal),
  foreign key(workspace_id,attachment_id) references public.attachments(workspace_id,id)
);

create table public.document_extractions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  attachment_id uuid not null,
  parent_id uuid,
  revision integer not null check(revision>0),
  document_type public.document_role not null,
  schema_version text not null,
  cache_key text not null,
  output jsonb not null check(jsonb_typeof(output)='object'),
  run_metadata jsonb not null,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  unique(workspace_id,id), unique(workspace_id,attachment_id,revision),
  unique(workspace_id,attachment_id,cache_key),
  foreign key(workspace_id,attachment_id) references public.attachments(workspace_id,id),
  foreign key(workspace_id,parent_id) references public.document_extractions(workspace_id,id)
);

create table public.normalized_fields (
  workspace_id uuid not null,
  extraction_id uuid not null,
  field public.field_name not null,
  state public.field_state not null,
  raw_value text,
  text_value text,
  numeric_value numeric(20,6),
  confidence numeric(5,4) not null check(confidence between 0 and 1),
  evidence jsonb not null default '[]' check(jsonb_typeof(evidence)='array'),
  normalization jsonb not null default '{}',
  primary key(workspace_id,extraction_id,field),
  foreign key(workspace_id,extraction_id) references public.document_extractions(workspace_id,id),
  check(state <> 'present' or raw_value is not null),
  check(state <> 'present' or
    (field in ('container_count','gross_weight_kg') and numeric_value is not null and text_value is null) or
    (field not in ('container_count','gross_weight_kg') and text_value is not null and numeric_value is null)),
  check(numeric_value is null or numeric_value>=0),
  check(field<>'container_count' or numeric_value is null or
    (numeric_value>=1 and numeric_value=trunc(numeric_value)))
);

create table public.shipments (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id),
  reference text not null,
  references_json jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique(workspace_id,id)
);
create index shipments_reference_idx on public.shipments(workspace_id,reference);
create table public.document_links (
  workspace_id uuid not null,
  shipment_id uuid not null,
  attachment_id uuid not null,
  role public.document_role not null,
  version_number integer not null check(version_number>0),
  confirmed boolean not null default false,
  evidence jsonb not null default '{}',
  primary key(workspace_id,shipment_id,attachment_id),
  foreign key(workspace_id,shipment_id) references public.shipments(workspace_id,id),
  foreign key(workspace_id,attachment_id) references public.attachments(workspace_id,id)
);

create table public.verification_reports (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  email_id uuid not null,
  si_extraction_id uuid,
  bl_extraction_id uuid,
  supersedes_id uuid,
  revision integer not null check(revision>0),
  status public.report_status not null,
  complete boolean not null,
  confidence numeric(5,4) not null check(confidence between 0 and 1),
  comparison_version text not null,
  input_fingerprint text not null,
  review_reasons text[] not null default '{}',
  report jsonb not null check(jsonb_typeof(report)='object'),
  created_at timestamptz not null default now(),
  unique(workspace_id,id), unique(workspace_id,email_id,revision),
  unique(workspace_id,email_id,input_fingerprint),
  foreign key(workspace_id,email_id) references public.emails(workspace_id,id),
  foreign key(workspace_id,si_extraction_id) references public.document_extractions(workspace_id,id),
  foreign key(workspace_id,bl_extraction_id) references public.document_extractions(workspace_id,id),
  foreign key(workspace_id,supersedes_id) references public.verification_reports(workspace_id,id),
  check(si_extraction_id is null or bl_extraction_id is null or si_extraction_id<>bl_extraction_id),
  -- A MISMATCH may still list unresolved fields (a real difference plus a blank value), so it is
  -- complete exactly when nothing is unresolved; OK requires both. See migration 012.
  constraint verification_reports_status_consistency check(
    (status='NEEDS_REVIEW' and not complete and cardinality(review_reasons)>0)
    or (status='OK' and complete and cardinality(review_reasons)=0
        and si_extraction_id is not null and bl_extraction_id is not null)
    or (status='MISMATCH' and complete=(cardinality(review_reasons)=0)
        and si_extraction_id is not null and bl_extraction_id is not null))
);
create index reports_email_idx on public.verification_reports(workspace_id,email_id,revision desc);
create index reports_status_idx on public.verification_reports(workspace_id,status,created_at desc);

create table public.discrepancies (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  report_id uuid not null,
  field public.field_name not null,
  decision text not null check(decision in ('mismatch','missing','partial_match','uncertain')),
  severity text not null check(severity in ('low','medium','high')),
  confidence numeric(5,4) not null check(confidence between 0 and 1),
  details jsonb not null,
  unique(workspace_id,report_id,field),
  foreign key(workspace_id,report_id) references public.verification_reports(workspace_id,id)
);

create table public.review_queue (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  email_id uuid not null,
  report_id uuid,
  reason text not null,
  priority smallint not null default 50 check(priority between 0 and 100),
  state public.review_status not null default 'open',
  assigned_to uuid references auth.users(id),
  version integer not null default 1 check(version>0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(workspace_id,id),
  foreign key(workspace_id,email_id) references public.emails(workspace_id,id),
  foreign key(workspace_id,report_id) references public.verification_reports(workspace_id,id)
);
create unique index one_open_review_idx on public.review_queue(workspace_id,email_id)
  where state in ('open','claimed');
create index review_work_idx on public.review_queue(workspace_id,state,priority desc,created_at,id);

create table public.review_actions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  review_id uuid not null,
  actor_id uuid not null references auth.users(id),
  action text not null check(action in ('claim','correct','confirm','replace','dismiss','reopen','reclassify')),
  rationale text not null check(length(rationale) between 1 and 2000),
  patch jsonb not null,
  created_at timestamptz not null default now(),
  foreign key(workspace_id,review_id) references public.review_queue(workspace_id,id)
);

create table public.processing_jobs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id),
  email_id uuid,
  kind text not null check(kind in ('ingest','classify','extract','verify','benchmark','purge')),
  idempotency_key text not null,
  request_sha256 text not null,
  state public.job_status not null default 'queued',
  payload jsonb not null,
  result jsonb,
  attempt integer not null default 0 check(attempt>=0),
  max_attempts integer not null default 3 check(max_attempts between 1 and 10),
  available_at timestamptz not null default now(),
  leased_until timestamptz,
  lease_token uuid,
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(workspace_id,id), unique(workspace_id,kind,idempotency_key),
  foreign key(workspace_id,email_id) references public.emails(workspace_id,id)
);
create index jobs_due_idx on public.processing_jobs(available_at,created_at)
  where state in ('queued','retry_wait');
create index jobs_lease_idx on public.processing_jobs(leased_until) where state='running';

create table public.job_events (
  id bigint generated always as identity primary key,
  workspace_id uuid not null,
  job_id uuid not null,
  stage text not null,
  event jsonb not null,
  created_at timestamptz not null default now(),
  foreign key(workspace_id,job_id) references public.processing_jobs(workspace_id,id)
);
create index job_events_cursor_idx on public.job_events(workspace_id,job_id,id);

create table public.anomalies (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  extraction_id uuid not null,
  rule text not null,
  severity text not null check(severity in ('low','medium','high')),
  evidence jsonb not null,
  acknowledged_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  foreign key(workspace_id,extraction_id) references public.document_extractions(workspace_id,id)
);

create table public.benchmark_runs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id),
  state public.job_status not null default 'queued',
  dataset_sha256 text not null,
  config_sha256 text not null,
  git_commit text not null,
  manifest_key text not null,
  submission_key text,
  mode text not null check(mode in ('automated','human_assisted')),
  metrics jsonb,
  diagnostics jsonb not null default '{}',
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  unique(workspace_id,id)
);
create index benchmark_runs_list_idx on public.benchmark_runs(workspace_id,created_at desc);
create table public.benchmark_predictions (
  workspace_id uuid not null,
  run_id uuid not null,
  external_email_id text not null,
  prediction jsonb not null,
  latency_ms integer check(latency_ms>=0),
  diagnostics jsonb not null default '{}',
  primary key(workspace_id,run_id,external_email_id),
  foreign key(workspace_id,run_id) references public.benchmark_runs(workspace_id,id)
);

create table public.audit_logs (
  id bigint generated always as identity primary key,
  workspace_id uuid not null references public.workspaces(id),
  actor_id uuid references auth.users(id),
  actor_type text not null check(actor_type in ('user','worker','system')),
  action text not null,
  entity_type text not null,
  entity_id uuid,
  request_id uuid not null,
  details jsonb not null default '{}',
  created_at timestamptz not null default now()
);
create index audit_entity_idx on public.audit_logs(workspace_id,entity_type,entity_id,created_at);

create function public.reject_audit_mutation() returns trigger
language plpgsql set search_path=public as $$
begin
  raise exception 'audit records are append-only';
end;
$$;
create trigger audit_append_only before update or delete on public.audit_logs
  for each row execute function public.reject_audit_mutation();

-- Definer helper avoids membership-policy recursion. Its owner must be the
-- migration owner, not a browser-accessible or application-created role.
create function public.is_member(target_workspace uuid) returns boolean
language sql stable security definer set search_path='' as $$
  select exists(select 1 from public.memberships m
    where m.workspace_id=target_workspace and m.user_id=(select auth.uid()));
$$;
revoke all on function public.is_member(uuid) from public,anon;
grant execute on function public.is_member(uuid) to authenticated,service_role;

alter table public.workspaces enable row level security;
alter table public.memberships enable row level security;
revoke all on public.workspaces,public.memberships from anon,authenticated;
grant select on public.workspaces,public.memberships to authenticated;
create policy workspace_read on public.workspaces for select to authenticated
  using(public.is_member(id));
create policy membership_read on public.memberships for select to authenticated
  using(user_id=(select auth.uid()));

do $$
declare t text;
begin
  foreach t in array array['emails','email_classifications','attachments','source_blocks',
    'document_extractions','normalized_fields','shipments','document_links',
    'verification_reports','discrepancies','review_queue','review_actions',
    'processing_jobs','job_events','anomalies','benchmark_runs','benchmark_predictions','audit_logs']
  loop
    execute format('alter table public.%I enable row level security',t);
    execute format('revoke all on public.%I from anon,authenticated',t);
    -- Data is read through FastAPI by default. This read policy is defense in
    -- depth if selective authenticated grants are added in a later migration.
    execute format('create policy member_read on public.%I for select to authenticated using (public.is_member(workspace_id))',t);
    execute format('grant select,insert,update,delete on public.%I to service_role',t);
  end loop;
end;
$$;
grant select,insert,update,delete on public.workspaces,public.memberships to service_role;
grant usage,select on sequence public.job_events_id_seq,public.audit_logs_id_seq to service_role;

-- A first login must not lead to an empty, unusable application shell.
create function public.bootstrap_new_user_workspace() returns trigger
language plpgsql security definer set search_path='' as $$
declare workspace_id uuid;
begin
  insert into public.workspaces(name) values('My shipping team')
  returning id into workspace_id;
  insert into public.memberships(workspace_id,user_id,role)
  values(workspace_id,new.id,'admin');
  return new;
end;
$$;
revoke all on function public.bootstrap_new_user_workspace() from public,anon,authenticated;
create trigger create_initial_workspace
  after insert on auth.users
  for each row execute function public.bootstrap_new_user_workspace();

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values
 ('shipping-originals','shipping-originals',false,20971520,
  array['text/plain','application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']),
 ('shipping-derived','shipping-derived',false,20971520,
  array['application/json','text/plain','image/png','image/webp']),
 ('benchmark-artifacts','benchmark-artifacts',false,20971520,
  array['application/json','text/csv']);
commit;


-- Amendment workspace extension.
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
