begin;
alter table public.emails add column if not exists deleted_at timestamptz;
alter table public.emails add column if not exists deleted_by uuid references auth.users(id);
alter table public.emails add column if not exists deleted_reason text;
create index if not exists emails_trash_idx on public.emails(workspace_id,deleted_at);
alter table public.drift_alerts add column if not exists investigation_note text;
create table if not exists public.document_references (
  workspace_id uuid not null,
  attachment_id uuid not null,
  kind text not null,
  code text not null,
  quote text not null,
  block_id uuid not null,
  primary key(workspace_id,attachment_id,kind,code,block_id),
  foreign key(workspace_id,attachment_id) references public.attachments(workspace_id,id) on delete cascade
);
alter table public.document_references enable row level security;
revoke all on public.document_references from public,anon,authenticated;
grant select on public.document_references to authenticated;
grant select,insert,update,delete on public.document_references to service_role;
create policy reference_member_read on public.document_references for select to authenticated
using(public.is_member(workspace_id));
commit;
