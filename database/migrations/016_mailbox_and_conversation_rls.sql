-- Migration 016: lock down the tables from 006 and 009, which were created without row level security.
-- Only the API (service role) reads them. OAuth tokens in mailbox_connections are encrypted by the
-- API before they are written (see backend/app/infrastructure/token_crypto.py).
begin;
alter table public.mailbox_connections enable row level security;
alter table public.gmail_messages enable row level security;
alter table public.conversations enable row level security;
revoke all on public.mailbox_connections, public.gmail_messages, public.conversations from public, anon, authenticated;
grant select, insert, update, delete on public.mailbox_connections, public.gmail_messages, public.conversations to service_role;
comment on column public.mailbox_connections.access_token is 'Encrypted by the API (fernet:v1:...); empty when disconnected.';
comment on column public.mailbox_connections.refresh_token is 'Encrypted by the API (fernet:v1:...); revoked with Google and erased on disconnect.';
commit;
