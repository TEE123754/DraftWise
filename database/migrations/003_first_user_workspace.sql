-- Give every newly authenticated user a usable private workspace immediately.
begin;
create or replace function public.bootstrap_new_user_workspace() returns trigger
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
do $$
begin
  if not exists (
    select 1 from pg_trigger
    where tgname='create_initial_workspace' and tgrelid='auth.users'::regclass
  ) then
    create trigger create_initial_workspace
      after insert on auth.users
      for each row execute function public.bootstrap_new_user_workspace();
  end if;
end;
$$;
commit;
