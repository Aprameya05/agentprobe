"""
AgentProbe -- Neon Postgres via asyncpg
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=os.environ["DATABASE_URL"],
            min_size=1,
            max_size=5,
            command_timeout=30,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def acquire() -> AsyncGenerator[asyncpg.Connection, None]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


# ---------------------------------------------------------------------------
# Audit CRUD
# ---------------------------------------------------------------------------

async def create_audit(
    audit_id: str,
    url: str,
    tasks: list[str],
    label: Optional[str] = None,
) -> None:
    async with acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audits (audit_id, url, label, tasks, status, created_at)
            VALUES ($1, $2, $3, $4, 'queued', NOW())
            """,
            audit_id, url, label, json.dumps(tasks),
        )


async def set_audit_running(audit_id: str) -> None:
    async with acquire() as conn:
        await conn.execute(
            "UPDATE audits SET status='running', started_at=NOW() WHERE audit_id=$1",
            audit_id,
        )


async def complete_audit(
    audit_id: str,
    report_json: dict[str, Any],
) -> None:
    async with acquire() as conn:
        await conn.execute(
            """
            UPDATE audits
            SET status='completed',
                completed_at=NOW(),
                report=$1
            WHERE audit_id=$2
            """,
            json.dumps(report_json), audit_id,
        )


async def fail_audit(audit_id: str, error: str) -> None:
    async with acquire() as conn:
        await conn.execute(
            "UPDATE audits SET status='failed', error=$1, completed_at=NOW() WHERE audit_id=$2",
            error, audit_id,
        )


async def get_audit(audit_id: str) -> Optional[dict[str, Any]]:
    async with acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM audits WHERE audit_id=$1", audit_id
        )
        if not row:
            return None
        return dict(row)


async def list_audits(limit: int = 20) -> list[dict[str, Any]]:
    async with acquire() as conn:
        rows = await conn.fetch(
            "SELECT audit_id, url, label, status, created_at, completed_at, report FROM audits ORDER BY created_at DESC LIMIT $1",
            limit,
        )
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Event log (live feed for dashboard polling)
# ---------------------------------------------------------------------------

async def append_event(audit_id: str, event: dict[str, Any]) -> None:
    async with acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audit_events (audit_id, event_json, created_at)
            VALUES ($1, $2, NOW())
            """,
            audit_id, json.dumps(event),
        )


async def get_events_since(audit_id: str, after_id: int = 0) -> list[dict[str, Any]]:
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, event_json, created_at
            FROM audit_events
            WHERE audit_id=$1 AND id > $2
            ORDER BY id ASC
            LIMIT 50
            """,
            audit_id, after_id,
        )
        return [
            {"id": r["id"], "created_at": r["created_at"].isoformat(), **json.loads(r["event_json"])}
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Monitors (scheduled re-audit + webhook alerts)
# ---------------------------------------------------------------------------

async def ensure_monitors_table(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS monitors (
            monitor_id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            webhook_url TEXT DEFAULT '',
            threshold_drop REAL DEFAULT 5.0,
            last_score REAL,
            last_audit_id TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            active BOOLEAN DEFAULT TRUE
        )
    """)


async def create_monitor(url: str, webhook_url: str = "", threshold_drop: float = 5.0) -> str:
    import uuid
    monitor_id = f"mon_{uuid.uuid4().hex[:12]}"
    async with acquire() as conn:
        await ensure_monitors_table(conn)
        await conn.execute(
            """
            INSERT INTO monitors (monitor_id, url, webhook_url, threshold_drop)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (monitor_id) DO NOTHING
            """,
            monitor_id, url, webhook_url, threshold_drop,
        )
    return monitor_id


async def list_monitors(domain: Optional[str] = None) -> list[dict[str, Any]]:
    async with acquire() as conn:
        await ensure_monitors_table(conn)
        if domain:
            rows = await conn.fetch(
                "SELECT * FROM monitors WHERE active=TRUE AND url ILIKE $1 ORDER BY created_at DESC",
                f"%{domain}%",
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM monitors WHERE active=TRUE ORDER BY created_at DESC",
            )
        return [dict(r) for r in rows]


async def update_monitor(monitor_id: str, last_audit_id: Optional[str] = None, last_score: Optional[float] = None) -> None:
    async with acquire() as conn:
        await ensure_monitors_table(conn)
        if last_audit_id is not None:
            await conn.execute(
                "UPDATE monitors SET last_audit_id=$1 WHERE monitor_id=$2",
                last_audit_id, monitor_id,
            )
        if last_score is not None:
            await conn.execute(
                "UPDATE monitors SET last_score=$1 WHERE monitor_id=$2",
                last_score, monitor_id,
            )


async def delete_monitor(monitor_id: str) -> None:
    async with acquire() as conn:
        await ensure_monitors_table(conn)
        await conn.execute(
            "UPDATE monitors SET active=FALSE WHERE monitor_id=$1",
            monitor_id,
        )
