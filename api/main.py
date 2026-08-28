"""
AgentProbe API -- FastAPI

Public routes:
  POST /audit                    Submit URL for audit (rate-limited: 10/min/IP)
  GET  /audit/{id}               Get audit status + report (cached 5 min when done)
  GET  /audit/{id}/events        SSE live agent step stream
  GET  /audit/{id}/events-poll   Polling fallback for environments without SSE
  GET  /audits                   List recent audits
  GET  /leaderboard              Top ARS rankings (cached 60 s)
  GET  /compare                  Side-by-side diff for two audits
  GET  /badge/{audit_id}.svg     Live SVG badge for README embeds
  GET  /site/{domain}            All audits for a domain (history + trend)
  GET  /health                   Liveness probe

  POST /monitor                  Register a domain for scheduled re-audits
  GET  /monitor/{domain}         Get monitor config for a domain
  DELETE /monitor/{monitor_id}   Remove a monitor

Internal routes (X-Worker-Secret required):
  POST /audit/{id}/events        Worker posts a step event
  POST /audit/{id}/complete      Worker posts the final report
  POST /audit/{id}/fail          Worker signals failure
  POST /internal/audit/{id}/parseability   Parseability job result
  POST /internal/audit/{id}/complete       Aggregate job final result
  POST /internal/audit/{id}/fail           Aggregate job failure
  POST /internal/monitor/tick              Scheduled monitor sweep
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional
from urllib.parse import urlparse

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from . import database as db
from .cache import cache, cached_json
from .middleware import SecurityMiddleware
from .models import AuditCreate, AuditRequest, AuditStatus, TaskName
from .scoring import INDUSTRY_BASELINES

logger = logging.getLogger("agentprobe.api")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WORKER_SECRET = os.environ.get("WORKER_SECRET", "dev-secret-change-me")
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")
GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "Aprameya05")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "agentprobe")
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "https://agentprobe.pages.dev,http://localhost:3000",
).split(",")


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.get_pool()
    yield
    await db.close_pool()
    await cache.close()


app = FastAPI(
    title="AgentProbe API",
    version="1.0.0",
    description="Agentic Readiness Score for any website.",
    lifespan=lifespan,
    # Don't expose internal error details in production
    openapi_url="/openapi.json" if os.environ.get("DEBUG") else None,
)

# Security middleware first (runs outermost)
app.add_middleware(SecurityMiddleware)

# CORS -- lock to known origins, not *
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Worker-Secret"],
    max_age=600,
)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def verify_worker(x_worker_secret: str = Header(default="")):
    if x_worker_secret != WORKER_SECRET:
        logger.warning("invalid_worker_secret")
        raise HTTPException(status_code=401, detail="Unauthorised")


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

_PRIVATE_IP_RE = re.compile(
    r"^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)"
)

def _validate_url(raw: str) -> str:
    """Reject local/private URLs (SSRF guard) and non-http(s) schemes."""
    try:
        p = urlparse(raw)
    except Exception:
        raise HTTPException(400, "Invalid URL")
    if p.scheme not in ("http", "https"):
        raise HTTPException(400, "URL must start with http:// or https://")
    host = (p.hostname or "").lower()
    if _PRIVATE_IP_RE.match(host) or host == "":
        raise HTTPException(400, "Private / local URLs are not allowed")
    return raw.rstrip("/")


# ---------------------------------------------------------------------------
# SSE event bus (in-memory per audit_id)
# For horizontal scaling: swap _broadcast() to publish on a Redis channel
# and subscribe in _sse_generator(). The rest of the code stays the same.
# ---------------------------------------------------------------------------

_sse_queues: dict[str, list[asyncio.Queue]] = {}


def _get_queues(audit_id: str) -> list[asyncio.Queue]:
    return _sse_queues.setdefault(audit_id, [])


async def _broadcast(audit_id: str, event: dict) -> None:
    payload = json.dumps(event)
    for q in _get_queues(audit_id):
        await q.put(payload)
    await db.append_event(audit_id, event)
    # Bust any cached events-poll responses for this audit
    await cache.delete(f"audit:{audit_id}:events")
    # Bust the audit report cache when the audit completes/fails
    if event.get("event_type") in ("audit_done", "error"):
        await cache.invalidate_audit(audit_id)
        await cache.delete("leaderboard:25")


async def _sse_generator(audit_id: str, request: Request) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
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
                yield ": keepalive\n\n"
    finally:
        try:
            queues.remove(queue)
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Routes -- public
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/audit", response_model=dict)
async def submit_audit(body: AuditRequest, background: BackgroundTasks, request: Request):
    """Submit a URL for an ARS audit. Rate-limited to 10 requests/min/IP."""
    url = _validate_url(str(body.url))
    audit = AuditCreate(
        url=url,
        label=body.label,
        tasks=[t.value for t in body.tasks],
    )
    await db.create_audit(
        audit_id=audit.audit_id,
        url=audit.url,
        tasks=audit.tasks,
        label=audit.label,
    )
    background.add_task(_dispatch_worker, audit.audit_id, audit.url, audit.tasks)
    # Invalidate leaderboard cache so new audits appear when completed
    await cache.delete("leaderboard:25")
    return {"audit_id": audit.audit_id, "status": "queued"}


@app.get("/audit/{audit_id}")
async def get_audit(audit_id: str):
    # Return cached version for completed audits (saves DB round-trip)
    async def _fetch():
        row = await db.get_audit(audit_id)
        if not row:
            return None
        return _format_audit(row)

    cache_key = f"audit:{audit_id}"
    row = await db.get_audit(audit_id)
    if not row:
        raise HTTPException(status_code=404, detail="Audit not found")

    formatted = _format_audit(row)

    # Only cache completed/failed audits -- in-progress audits must stay live
    if row["status"] in ("completed", "failed"):
        await cache.set(cache_key, json.dumps(formatted, default=str), ttl=300)

    return formatted


@app.get("/audit/{audit_id}/events")
async def stream_events(audit_id: str, request: Request):
    """SSE stream of live agent steps. The dashboard connects here."""
    row = await db.get_audit(audit_id)
    if not row:
        raise HTTPException(status_code=404, detail="Audit not found")
    return StreamingResponse(
        _sse_generator(audit_id, request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/audit/{audit_id}/events-poll")
async def poll_events(audit_id: str, after: int = 0):
    """
    Polling fallback for clients where SSE is unreliable.
    Returns up to 50 events with id > `after`, plus current audit status.
    Cached for 2 s to absorb burst polling from the dashboard.
    """
    cache_key = f"audit:{audit_id}:events:{after}"
    cached = await cache.get(cache_key)
    if cached:
        return json.loads(cached)

    row = await db.get_audit(audit_id)
    if not row:
        raise HTTPException(status_code=404, detail="Audit not found")

    events = await db.get_events_since(audit_id, after_id=after)
    result = {
        "events": events,
        "status": row["status"],
        "last_id": events[-1].get("id", after) if events else after,
    }
    # Short TTL -- the dashboard polls every ~1.8 s anyway
    await cache.set(cache_key, json.dumps(result, default=str), ttl=2)
    return result


@app.get("/audits")
async def list_audits(limit: int = 20):
    rows = await db.list_audits(limit=min(limit, 50))
    return [_format_audit(r) for r in rows]


@app.get("/leaderboard")
async def leaderboard(limit: int = 25):
    """Top publicly completed audits ranked by ARS. Cached 60 s."""
    async def _build():
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
                "created_at": (
                    r["created_at"].isoformat()
                    if hasattr(r["created_at"], "isoformat")
                    else str(r["created_at"])
                ),
            })
        ranked.sort(key=lambda x: x["composite"], reverse=True)
        return {
            "leaderboard": ranked[: min(limit, 50)],
            "industry_baselines": INDUSTRY_BASELINES,
        }

    return await cached_json(f"leaderboard:{limit}", ttl=60, factory=_build)


@app.get("/badge/{audit_id}.svg")
async def badge(audit_id: str):
    """Live SVG badge for README embeds. Cache 5 min for completed audits."""
    GRADE_COLORS = {
        "A+": "#10b981", "A": "#34d399", "B": "#60a5fa",
        "C": "#fbbf24", "D": "#f97316", "F": "#ef4444",
    }
    row = await db.get_audit(audit_id)
    if not row or not row.get("report"):
        grade, score, color = "?", "--", "#6b7280"
    else:
        report = row["report"] if isinstance(row["report"], dict) else json.loads(row["report"])
        ars = report.get("ars", {})
        grade = ars.get("grade", "F")
        score = str(int(ars.get("composite", 0)))
        color = GRADE_COLORS.get(grade, "#6b7280")

    label = "AgentProbe ARS"
    label_w = 110
    val_w = 52
    total_w = label_w + val_w

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="20">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total_w}" height="20" rx="3"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_w}" height="20" fill="#555"/>
    <rect x="{label_w}" width="{val_w}" height="20" fill="{color}"/>
    <rect width="{total_w}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{label_w//2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_w//2}" y="14">{label}</text>
    <text x="{label_w + val_w//2}" y="15" fill="#010101" fill-opacity=".3">{grade} {score}</text>
    <text x="{label_w + val_w//2}" y="14">{grade} {score}</text>
  </g>
</svg>"""

    headers = {"Cache-Control": "max-age=300, s-maxage=300"}
    return Response(content=svg, media_type="image/svg+xml", headers=headers)


@app.get("/site/{domain}")
async def site_history(domain: str, limit: int = 20):
    """All audits for a domain, newest first. Used for domain history + trend pages."""
    # Normalize domain
    domain = domain.lower().lstrip("www.")
    rows = await db.list_audits(limit=200)
    matched = []
    for r in rows:
        host = (urlparse(r["url"]).hostname or "").lower().lstrip("www.")
        if host == domain or host.endswith(f".{domain}"):
            report = None
            if r.get("report"):
                rpt = r["report"] if isinstance(r["report"], dict) else json.loads(r["report"])
                ars = rpt.get("ars", {})
                report = {
                    "composite": ars.get("composite", 0),
                    "grade": ars.get("grade", "F"),
                    "discoverability": ars.get("discoverability", 0),
                    "parseability": ars.get("parseability", 0),
                    "task_completion": ars.get("task_completion", 0),
                    "friction": ars.get("friction", 0),
                    "clarity": ars.get("clarity", 0),
                    "resilience": ars.get("resilience", 0),
                }
            matched.append({
                "audit_id": r["audit_id"],
                "url": r["url"],
                "label": r.get("label"),
                "status": r["status"],
                "created_at": (
                    r["created_at"].isoformat()
                    if hasattr(r.get("created_at"), "isoformat")
                    else str(r.get("created_at"))
                ),
                "ars": report,
            })
        if len(matched) >= limit:
            break
    return {"domain": domain, "audits": matched}


@app.post("/monitor")
async def create_monitor(body: dict, background: BackgroundTasks):
    """Register a domain for scheduled monitoring. Fires webhook on ARS drop."""
    url = _validate_url(body.get("url", ""))
    webhook_url = body.get("webhook_url", "")
    threshold_drop = float(body.get("threshold_drop", 5.0))  # alert if ARS drops by this much
    monitor_id = await db.create_monitor(url=url, webhook_url=webhook_url, threshold_drop=threshold_drop)
    return {"monitor_id": monitor_id, "url": url, "status": "active"}


@app.get("/monitor/{domain}")
async def get_monitor(domain: str):
    """Get monitor config for a domain."""
    monitors = await db.list_monitors(domain=domain)
    return {"domain": domain, "monitors": monitors}


@app.delete("/monitor/{monitor_id}")
async def delete_monitor(monitor_id: str):
    """Remove a monitor."""
    await db.delete_monitor(monitor_id)
    return {"ok": True}


@app.post("/internal/monitor/tick", dependencies=[Depends(verify_worker)])
async def monitor_tick(background: BackgroundTasks):
    """Called by the scheduled GitHub Actions workflow. Re-audits all active monitors."""
    monitors = await db.list_monitors()
    for m in monitors:
        background.add_task(_run_monitor_check, m)
    return {"ok": True, "monitors_checked": len(monitors)}


async def _run_monitor_check(monitor: dict) -> None:
    """Re-audit a monitored URL and fire webhook if ARS dropped enough."""
    url = monitor["url"]
    webhook_url = monitor.get("webhook_url", "")
    threshold_drop = float(monitor.get("threshold_drop", 5.0))
    last_score = float(monitor.get("last_score") or 0)
    monitor_id = monitor["monitor_id"]

    # Create a new audit
    from .models import AuditCreate
    audit = AuditCreate(url=url, tasks=[t.value for t in TaskName])
    await db.create_audit(audit_id=audit.audit_id, url=url, tasks=audit.tasks)
    await _dispatch_worker(audit.audit_id, url, audit.tasks)

    # Update monitor's last_audit_id (score will be updated when audit completes)
    await db.update_monitor(monitor_id, last_audit_id=audit.audit_id)

    # Webhook fired from complete_audit_and_notify after audit finishes


@app.get("/compare")
async def compare(a: str, b: str):
    """Side-by-side ARS diff for two audit IDs."""
    row_a, row_b = await asyncio.gather(db.get_audit(a), db.get_audit(b))
    if not row_a or not row_b:
        raise HTTPException(status_code=404, detail="One or both audit IDs not found")
    return {
        "a": _format_audit(row_a),
        "b": _format_audit(row_b),
        "delta": _compute_delta(row_a, row_b),
    }


# ---------------------------------------------------------------------------
# Routes -- internal (worker → API callbacks)
# ---------------------------------------------------------------------------

@app.post("/audit/{audit_id}/events", dependencies=[Depends(verify_worker)])
async def receive_event(audit_id: str, event: dict):
    await _broadcast(audit_id, event)
    return {"ok": True}


@app.post("/audit/{audit_id}/complete", dependencies=[Depends(verify_worker)])
async def receive_complete(audit_id: str, report: dict):
    await db.complete_audit(audit_id, report)
    await _broadcast(audit_id, {"event_type": "audit_done", "report": report})
    return {"ok": True}


@app.post("/audit/{audit_id}/fail", dependencies=[Depends(verify_worker)])
async def receive_fail(audit_id: str, body: dict):
    await db.fail_audit(audit_id, body.get("error", "unknown error"))
    await _broadcast(audit_id, {"event_type": "error", "message": body.get("error")})
    return {"ok": True}


@app.post("/internal/audit/{audit_id}/parseability", dependencies=[Depends(verify_worker)])
async def internal_parseability(audit_id: str, body: dict):
    await _broadcast(audit_id, {
        "event_type": "parseability_done",
        "score": body.get("score", 0),
        "signals": body.get("signals", []),
    })
    return {"ok": True}


@app.post("/internal/audit/{audit_id}/complete", dependencies=[Depends(verify_worker)])
async def internal_complete(audit_id: str, report: dict):
    await db.complete_audit(audit_id, report)
    await _broadcast(audit_id, {"event_type": "audit_done", "report": report})
    return {"ok": True}


@app.post("/internal/audit/{audit_id}/fail", dependencies=[Depends(verify_worker)])
async def internal_fail(audit_id: str, body: dict):
    await db.fail_audit(audit_id, body.get("error", "unknown error"))
    await _broadcast(audit_id, {"event_type": "error", "message": body.get("error")})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_audit(row: dict) -> dict:
    """
    Trim the audit row to only the fields the client needs.
    Never expose internal fields (error stack traces, DB ids, etc.) in prod.
    """
    result: dict = {
        "audit_id": row["audit_id"],
        "url": row["url"],
        "label": row.get("label"),
        "status": row["status"],
        "created_at": (
            row["created_at"].isoformat()
            if hasattr(row.get("created_at"), "isoformat")
            else str(row.get("created_at"))
        ),
    }
    if row.get("report"):
        report = (
            row["report"] if isinstance(row["report"], dict)
            else json.loads(row["report"])
        )
        result["report"] = report

    # Surface error only in debug mode -- no stack traces in production
    if row.get("error") and os.environ.get("DEBUG"):
        result["error"] = row["error"]

    return result


def _compute_delta(a: dict, b: dict) -> dict:
    dims = ["discoverability", "parseability", "task_completion",
            "friction", "clarity", "resilience", "composite"]
    delta: dict = {}
    try:
        ra = a.get("report") or {}
        rb = b.get("report") or {}
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
    Async fire-and-forget: trigger GitHub Actions workflow_dispatch.
    Falls back to in-process agent (useful for local dev or if GitHub fails).
    The worker posts events back here via the internal routes.
    """
    if not GITHUB_PAT:
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
                f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
                f"/actions/workflows/audit-worker.yml/dispatches",
                json=payload,
                headers={
                    "Authorization": f"Bearer {GITHUB_PAT}",
                    "Accept": "application/vnd.github+json",
                },
            )
            if resp.status_code not in (204, 200):
                raise ValueError(f"dispatch failed: {resp.status_code}")
    except Exception as exc:
        logger.warning("GitHub dispatch failed (%s), falling back to in-process", exc)
        from .agent.runner import run_audit_inprocess
        await run_audit_inprocess(
            audit_id=audit_id,
            url=url,
            tasks=tasks,
            api_base=API_BASE_URL,
            worker_secret=WORKER_SECRET,
        )
