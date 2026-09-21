-- Preserve immutable audit history and anonymous session metadata while removing
-- expired sample payloads. No real workspace or uploaded object is purged.
alter table public.demo_sessions add column if not exists purged_at timestamptz;
create index if not exists demo_cleanup_idx on public.demo_sessions(expires_at)
    where purged_at is null;
