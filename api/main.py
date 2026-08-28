"""
AgentProbe API -- FastAPI

Endpoints:
  POST /audit            submit URL for audit
  GET  /audit/{id}       get audit status + report
  GET  /audit/{id}/events  SSE stream of live agent events
  GET  /audits           list recent audits
  GET  /leaderboard      top-scoring publicly audited sites
  GET  /compare          side-by-side two audits
  POST /audit/{id}/events  (internal) worker posts step events
  POST /audit/{id}/complete  (internal) worker posts final report
  GET  /health           health check
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import database as db
from .models import (
    AuditCreate,
    AuditRequest,
    AuditReport,
    AuditStatus,
    AuditSummary,
    TaskName,
)
from .scoring import INDUSTRY_BASELINES


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the DB pool
    await db.get_pool()
    yield
    await db.close_pool()


app = FastAPI(
    title="AgentProbe API",
    version="1.0.0",
    description="Agentic Readiness Score for any website.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKER_SECRET = os.environ.get("WORKER_SECRET", "dev-secret-change-me")
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")
GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "Aprameya05")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "agentprobe")
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def verify_worker(x_worker_secret: str = Header(default="")):
    if x_worker_secret != WORKER_SECRET:
        raise HTTPException(status_code=401, detail="Invalid worker secret")


# ---------------------------------------------------------------------------
# SSE event bus (in-memory, per audit_id)
# In production, back this with Redis pub/sub. For demo, memory is fine.
# ---------------------------------------------------------------------------

_sse_queues: dict[str, list[asyncio.Queue]] = {}


def _get_queues(audit_id: str) -> list[asyncio.Queue]:
    return _sse_queues.setdefault(audit_id, [])


async def _broadcast(audit_id: str, event: dict) -> None:
    """Broadcast an event to all SSE subscribers for this audit."""
    payload = json.dumps(event)
    for q in _get_queues(audit_id):
        await q.put(payload)
    # Also persist to DB for clients that connect late
    await db.append_event(audit_id, event)


async def _sse_generator(audit_id: str, request: Request) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    queues = _get_queues(audit_id)
    queues.append(queue)

    # Replay past events for late-joiners
    past = await db.get_events_since(audit_id, after_id=0)
    for ev in past:
        yield f"data: {json.dumps(ev)}\n\n"

    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=25.0)
                yield f"data: {msg}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"  # SSE heartbeat
    finally:
        queues.remove(queue)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/audit", response_model=dict)
async def submit_audit(body: AuditRequest, background: BackgroundTasks):
    audit = AuditCreate(
        url=body.url.rstrip("/"),
        label=body.label,
        tasks=[t.value for t in body.tasks],
    )
    await db.create_audit(
        audit_id=audit.audit_id,
        url=audit.url,
        tasks=audit.tasks,
        label=audit.label,
    )

    # Dispatch GitHub Actions workflow for compute
    background.add_task(_dispatch_worker, audit.audit_id, audit.url, audit.tasks)

    return {"audit_id": audit.audit_id, "status": "queued"}


@app.get("/audit/{audit_id}")
async def get_audit(audit_id: str):
    row = await db.get_audit(audit_id)
    if not row:
        raise HTTPException(status_code=404, detail="Audit not found")
    return _format_audit(row)


@app.get("/audit/{audit_id}/events")
async def stream_events(audit_id: str, request: Request):
    """SSE endpoint -- dashboard subscribes here for live agent steps."""
    row = await db.get_audit(audit_id)
    if not row:
        raise HTTPException(status_code=404, detail="Audit not found")
    return StreamingResponse(
        _sse_generator(audit_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# Internal: worker posts step events
@app.post("/audit/{audit_id}/events", dependencies=[Depends(verify_worker)])
async def receive_event(audit_id: str, event: dict):
    await _broadcast(audit_id, event)
    return {"ok": True}


# Internal: worker posts final report
@app.post("/audit/{audit_id}/complete", dependencies=[Depends(verify_worker)])
async def receive_complete(audit_id: str, report: dict):
    await db.complete_audit(audit_id, report)
    await _broadcast(audit_id, {"event_type": "audit_done", "report": report})
    return {"ok": True}


# Internal: worker signals failure
@app.post("/audit/{audit_id}/fail", dependencies=[Depends(verify_worker)])
async def receive_fail(audit_id: str, body: dict):
    await db.fail_audit(audit_id, body.get("error", "unknown error"))
    await _broadcast(audit_id, {"event_type": "error", "message": body.get("error")})
    return {"ok": True}


@app.get("/audits")
async def list_audits(limit: int = 20):
    rows = await db.list_audits(limit=min(limit, 50))
    return [_format_audit(r) for r in rows]


@app.get("/leaderboard")
async def leaderboard(limit: int = 25):
    """Top publicly completed audits ranked by composite ARS."""
    rows = await db.list_audits(limit=200)
    completed = [
        r for r in rows
        if r.get("status") == "completed" and r.get("report")
    ]
    ranked = []
    for r in completed:
        report = r["report"] if isinstance(r["report"], dict) else json.loads(r["report"])
        ars = report.get("ars", {})
        ranked.append({
            "audit_id": r["audit_id"],
            "url": r["url"],
            "label": r.get("label"),
            "composite": ars.get("composite", 0),
            "grade": ars.get("grade", "F"),
            "discoverability": ars.get("discoverability", 0),
            "parseability": ars.get("parseability", 0),
            "task_completion": ars.get("task_completion", 0),
            "friction": ars.get("friction", 0),
            "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
        })

    ranked.sort(key=lambda x: x["composite"], reverse=True)
    return {
        "leaderboard": ranked[:limit],
        "industry_baselines": INDUSTRY_BASELINES,
    }


@app.get("/audit/{audit_id}/events-poll")
async def poll_events(audit_id: str, after: int = 0):
    """Polling fallback for environments where SSE is unreliable (e.g. static export)."""
    row = await db.get_audit(audit_id)
    if not row:
        raise HTTPException(status_code=404, detail="Audit not found")
    events = await db.get_events_since(audit_id, after_id=after)
    return {
        "events": events,
        "status": row["status"],
        "last_id": events[-1].get("id", after) if events else after,
    }


# Internal: worker posts parseability score
@app.post("/internal/audit/{audit_id}/parseability", dependencies=[Depends(verify_worker)])
async def receive_parseability(audit_id: str, body: dict):
    score = body.get("score", 0)
    await _broadcast(audit_id, {"event_type": "parseability", "score": score, "signals": body.get("signals", [])})
    return {"ok": True}


# Internal: worker signals failure
@app.post("/internal/audit/{audit_id}/fail", dependencies=[Depends(verify_worker)])
async def internal_fail(audit_id: str, body: dict):
    await db.fail_audit(audit_id, body.get("error", "unknown error"))
    await _broadcast(audit_id, {"event_type": "error", "message": body.get("error")})
    return {"ok": True}


# Internal: worker posts final report
@app.post("/internal/audit/{audit_id}/complete", dependencies=[Depends(verify_worker)])
async def internal_complete(audit_id: str, report: dict):
    await db.complete_audit(audit_id, report)
    await _broadcast(audit_id, {"event_type": "audit_done", "report": report})
    return {"ok": True}


@app.get("/compare")
async def compare(a: str, b: str):
    """Side-by-side ARS comparison for two audit IDs."""
    row_a = await db.get_audit(a)
    row_b = await db.get_audit(b)
    if not row_a or not row_b:
        raise HTTPException(status_code=404, detail="One or both audit IDs not found")
    return {
        "a": _format_audit(row_a),
        "b": _format_audit(row_b),
        "delta": _compute_delta(row_a, row_b),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_audit(row: dict) -> dict:
    result = {
        "audit_id": row["audit_id"],
        "url": row["url"],
        "label": row.get("label"),
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if hasattr(row.get("created_at"), "isoformat") else str(row.get("created_at")),
    }
    if row.get("report"):
        report = row["report"] if isinstance(row["report"], dict) else json.loads(row["report"])
        result["report"] = report
    return result


def _compute_delta(a: dict, b: dict) -> dict:
    dims = ["discoverability", "parseability", "task_completion", "friction", "clarity", "resilience", "composite"]
    delta = {}
    try:
        ra = (a.get("report") or {})
        rb = (b.get("report") or {})
        if isinstance(ra, str):
            ra = json.loads(ra)
        if isinstance(rb, str):
            rb = json.loads(rb)
        ars_a = ra.get("ars", {})
        ars_b = rb.get("ars", {})
        for d in dims:
            delta[d] = round(ars_b.get(d, 0) - ars_a.get(d, 0), 1)
    except Exception:
        pass
    return delta


async def _dispatch_worker(audit_id: str, url: str, tasks: list[str]) -> None:
    """
    Trigger GitHub Actions workflow_dispatch.
    The workflow runs the Playwright agent and POSTs results back here.
    Falls back to in-process agent if GitHub dispatch fails.
    """
    if not GITHUB_PAT:
        # Run in-process (development mode)
        from .agent.runner import run_audit_inprocess
        await run_audit_inprocess(
            audit_id=audit_id,
            url=url,
            tasks=tasks,
            api_base=API_BASE_URL,
            worker_secret=WORKER_SECRET,
        )
        return

    payload = {
        "ref": "main",
        "inputs": {
            "audit_id": audit_id,
            "url": url,
            "tasks": ",".join(tasks),
            "api_url": API_BASE_URL,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/audit-worker.yml/dispatches",
                json=payload,
                headers={
                    "Authorization": f"Bearer {GITHUB_PAT}",
                    "Accept": "application/vnd.github+json",
                },
            )
            if resp.status_code not in (204, 200):
                raise ValueError(f"GitHub dispatch failed: {resp.status_code} {resp.text}")
    except Exception as e:
        # Fallback to in-process
        from .agent.runner import run_audit_inprocess
        await run_audit_inprocess(
            audit_id=audit_id,
            url=url,
            tasks=tasks,
            api_base=API_BASE_URL,
            worker_secret=WORKER_SECRET,
        )
