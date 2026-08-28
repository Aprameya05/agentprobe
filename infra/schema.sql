-- AgentProbe -- Neon Postgres schema
-- Run once: psql $DATABASE_URL -f infra/schema.sql

-- ---------------------------------------------------------------------------
-- Core tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audits (
    audit_id     TEXT PRIMARY KEY,
    url          TEXT NOT NULL,
    label        TEXT,
    tasks        JSONB NOT NULL DEFAULT '[]',
    status       TEXT NOT NULL DEFAULT 'queued'
                 CHECK (status IN ('queued','running','completed','failed')),
    report       JSONB,
    error        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_events (
    id           BIGSERIAL PRIMARY KEY,
    audit_id     TEXT NOT NULL REFERENCES audits(audit_id) ON DELETE CASCADE,
    event_json   JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Security / access audit log (append-only)
CREATE TABLE IF NOT EXISTS security_events (
    id           BIGSERIAL PRIMARY KEY,
    event_type   TEXT NOT NULL,     -- rate_limited | auth_failure | oversized_request
    ip           TEXT,
    path         TEXT,
    detail       TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Indexes -- keep queries fast as the table grows
-- ---------------------------------------------------------------------------

-- Single-audit fetch (covered by PK, listed for documentation)
-- PRIMARY KEY on audits.audit_id

-- Leaderboard: completed audits by recency
CREATE INDEX IF NOT EXISTS idx_audits_status_created
    ON audits (status, created_at DESC)
    WHERE status = 'completed';

-- Recent audits list (used by /audits endpoint)
CREATE INDEX IF NOT EXISTS idx_audits_created_desc
    ON audits (created_at DESC);

-- SSE replay + polling: events for an audit in order
CREATE INDEX IF NOT EXISTS idx_events_audit_id
    ON audit_events (audit_id, id ASC);

-- Security event queries by IP (rate-limit analysis, abuse investigation)
CREATE INDEX IF NOT EXISTS idx_security_events_created
    ON security_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_security_events_ip
    ON security_events (ip, created_at DESC);

-- ---------------------------------------------------------------------------
-- Housekeeping
-- Neon free tier is 0.5 GB. Run this weekly via Neon scheduled queries:
--   DELETE FROM audit_events WHERE created_at < NOW() - INTERVAL '30 days';
--   DELETE FROM audits WHERE created_at < NOW() - INTERVAL '30 days';
-- ---------------------------------------------------------------------------
