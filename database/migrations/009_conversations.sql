-- Migration 009: Chat conversations

CREATE TABLE IF NOT EXISTS public.conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL,
    actor_id        UUID NOT NULL,
    -- JSONB array of {role, content, citations, timestamp}
    messages        JSONB NOT NULL DEFAULT '[]',
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- One conversation per workspace+user (extend later to support threads)
    UNIQUE (workspace_id, actor_id)
);

CREATE INDEX IF NOT EXISTS idx_conversations_workspace ON public.conversations(workspace_id, actor_id);

COMMENT ON TABLE public.conversations IS
    'Chat conversation history per workspace+user. '
    'Token count is tracked for budget enforcement. '
    'Deletion of a workspace cascades here. '
    'Content is scoped to the workspace and must not cross tenant boundaries.';
