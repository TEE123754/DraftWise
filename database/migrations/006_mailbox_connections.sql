-- Migration 006: Gmail mailbox connections
-- Run after migration 005 (or 004 if 005 does not exist)

CREATE TABLE IF NOT EXISTS public.mailbox_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    owner_user_id   UUID,                   -- the user who authorised this connection
    email           TEXT NOT NULL,          -- Gmail address
    state           TEXT NOT NULL DEFAULT 'active'
                        CHECK (state IN ('active','syncing','disconnected','error')),
    -- Tokens stored plaintext in prototype; encrypt in production
    access_token    TEXT NOT NULL DEFAULT '',
    refresh_token   TEXT NOT NULL DEFAULT '',
    history_cursor  TEXT,                   -- Gmail history ID for incremental sync
    messages_imported INTEGER NOT NULL DEFAULT 0,
    last_sync_at    TIMESTAMPTZ,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, email)
);

CREATE TABLE IF NOT EXISTS public.gmail_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL,
    connection_id   UUID NOT NULL REFERENCES public.mailbox_connections(id) ON DELETE CASCADE,
    gmail_message_id TEXT NOT NULL,          -- provider message ID for deduplication
    email_id        UUID REFERENCES public.emails(id) ON DELETE SET NULL,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (connection_id, gmail_message_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mailbox_connections_workspace ON public.mailbox_connections(workspace_id);
CREATE INDEX IF NOT EXISTS idx_gmail_messages_connection ON public.gmail_messages(connection_id);

COMMENT ON TABLE public.mailbox_connections IS
    'Gmail OAuth connections per workspace. Tokens are encrypted in production. '
    'Disconnect revokes access; imported emails are retained separately.';

COMMENT ON TABLE public.gmail_messages IS
    'Deduplication table linking Gmail message IDs to imported email records.';
