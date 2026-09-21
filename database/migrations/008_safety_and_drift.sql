-- Migration 008: Email safety assessment and concept drift alerts

-- Email safety: one row per email with safety assessment results
CREATE TABLE IF NOT EXISTS public.email_safety (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id        UUID NOT NULL REFERENCES public.emails(id) ON DELETE CASCADE,
    workspace_id    UUID NOT NULL,
    risk_state      TEXT NOT NULL DEFAULT 'clear'
                        CHECK (risk_state IN ('clear','suspected_phishing','spam','insufficient_evidence')),
    severity        TEXT NOT NULL DEFAULT 'none'
                        CHECK (severity IN ('none','low','medium','high','critical')),
    -- JSON array of signal objects: {type, description, evidence}
    signals         JSONB NOT NULL DEFAULT '[]',
    -- Held for human review before AI processing
    held_for_review BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_by     UUID,
    released_at     TIMESTAMPTZ,
    release_reason  TEXT,
    assessed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (email_id)
);

-- Concept drift alerts: one row per detected drift event
CREATE TABLE IF NOT EXISTS public.drift_alerts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id            UUID NOT NULL,
    alert_type              TEXT NOT NULL DEFAULT 'drift'
                                CHECK (alert_type IN ('drift','phishing','spam')),
    severity                TEXT NOT NULL DEFAULT 'medium'
                                CHECK (severity IN ('low','medium','high','critical')),
    title                   TEXT NOT NULL,
    description             TEXT NOT NULL,
    -- Window of emails affected
    affected_window_start   TIMESTAMPTZ,
    affected_window_end     TIMESTAMPTZ,
    -- Baseline the comparison was made against
    baseline_version        TEXT,
    -- Sample email IDs as a JSON array of strings
    sample_email_ids        JSONB NOT NULL DEFAULT '[]',
    -- Changed features: JSON array of {feature, baseline_value, current_value}
    changed_features        JSONB NOT NULL DEFAULT '[]',
    -- Lifecycle: open → acknowledged → investigated → resolved or dismissed
    lifecycle               TEXT NOT NULL DEFAULT 'open'
                                CHECK (lifecycle IN ('open','acknowledged','investigated','resolved','dismissed')),
    acknowledged_by         UUID,
    acknowledged_at         TIMESTAMPTZ,
    resolved_by             UUID,
    resolved_at             TIMESTAMPTZ,
    resolved_reason         TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Dashboard preferences: per workspace+user widget layout
CREATE TABLE IF NOT EXISTS public.dashboard_preferences (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL,
    user_id         UUID NOT NULL,
    -- Versioned widget configuration JSON
    widget_config   JSONB NOT NULL DEFAULT '{}',
    schema_version  INTEGER NOT NULL DEFAULT 1,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, user_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_email_safety_workspace ON public.email_safety(workspace_id);
CREATE INDEX IF NOT EXISTS idx_email_safety_email ON public.email_safety(email_id);
CREATE INDEX IF NOT EXISTS idx_email_safety_risk ON public.email_safety(workspace_id, risk_state) WHERE held_for_review = TRUE;
CREATE INDEX IF NOT EXISTS idx_drift_alerts_workspace ON public.drift_alerts(workspace_id, lifecycle);
CREATE INDEX IF NOT EXISTS idx_drift_alerts_open ON public.drift_alerts(workspace_id) WHERE lifecycle = 'open';

COMMENT ON TABLE public.email_safety IS
    'Safety assessment result per email. High-risk emails are held before AI processing. '
    'Signals are static (no external link fetching). HTML is sanitised separately.';

COMMENT ON TABLE public.drift_alerts IS
    'Concept drift and safety escalation alerts. '
    'Lifecycle must reach resolved/dismissed with a recorded reason. '
    'Never silently close alerts without evidence.';

COMMENT ON TABLE public.dashboard_preferences IS
    'Per-user dashboard widget configuration. Versioned JSON schema.';
