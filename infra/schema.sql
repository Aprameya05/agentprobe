-- AgentProbe -- Neon Postgres schema
-- Run once against your Neon DB to initialize.

CREATE TABLE IF NOT EXISTS audits (
    audit_id     TEXT PRIMARY KEY,
    url          TEXT NOT NULL,
    label        TEXT,
    tasks        JSONB NOT NULL DEFAULT '[]',
    status       TEXT NOT NULL DEFAULT 'queued',
    report       JSONB,
    error        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_audits_status ON audits (status);
CREATE INDEX IF NOT EXISTS idx_audits_created ON audits (created_at DESC);

-- Live event log (used by SSE late-joiners)
CREATE TABLE IF NOT EXISTS audit_events (
    id          BIGSERIAL PRIMARY KEY,
    audit_id    TEXT NOT NULL REFERENCES audits(audit_id) ON DELETE CASCADE,
    event_json  JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_audit ON audit_events (audit_id, id);

-- Auto-expire events older than 24h (keeps the table lean)
-- In production: set up pg_cron or a cleanup job.
-- For Neon free tier: manual cleanup is fine.
