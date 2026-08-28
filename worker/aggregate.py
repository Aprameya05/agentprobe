"""
Aggregate worker job.
Runs after all task jobs finish (GitHub Actions `needs` dependency).
Reads task_done events from the API event stream, computes ARS, and posts
the final report.
"""
import asyncio
import json
import os
import sys
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.models import TaskResult, TaskStatus
from api.scoring import compute_ars

API_URL = os.environ["API_URL"]
AUDIT_ID = os.environ["AUDIT_ID"]
TARGET_URL = os.environ.get("TARGET_URL", "")
WORKER_SECRET = os.environ["WORKER_SECRET"]

HEADERS = {"X-Worker-Secret": WORKER_SECRET, "Content-Type": "application/json"}


async def main() -> None:
    print(f"[aggregate] computing final ARS for audit {AUDIT_ID}")

    async with httpx.AsyncClient(timeout=30, base_url=API_URL, headers=HEADERS) as client:
        # Pull all stored events for this audit
        r = await client.get(f"/audit/{AUDIT_ID}/events-poll?after=0")
        r.raise_for_status()
        data = r.json()

    events = data.get("events") or []
    print(f"[aggregate] found {len(events)} events")

    # Reconstruct task results from task_done events
    task_results: list[TaskResult] = []
    parseability_score: float = 50.0

    for ev in events:
        if ev.get("event_type") == "task_done" and ev.get("task_result"):
            try:
                tr = TaskResult(**ev["task_result"])
                task_results.append(tr)
                print(f"[aggregate] task {tr.task_name}: {tr.status.value}")
            except Exception as e:
                print(f"[aggregate] failed to parse task_result: {e}", file=sys.stderr)
        elif ev.get("event_type") == "parseability_done":
            parseability_score = float(ev.get("score", 50.0))

    if not task_results:
        print("[aggregate] no task results found in events -- marking audit failed")
        async with httpx.AsyncClient(timeout=30, base_url=API_URL, headers=HEADERS) as client:
            await client.post(
                f"/internal/audit/{AUDIT_ID}/fail",
                json={"error": "no task results received from workers"},
            )
        return

    ars = compute_ars(task_results, None)
    from api.scoring import generate_recommendations
    recs = generate_recommendations(ars, task_results, None)

    report = {
        "audit_id": AUDIT_ID,
        "url": TARGET_URL,
        "ars": ars.model_dump(mode="json"),
        "tasks": [t.model_dump(mode="json") for t in task_results],
        "recommendations": [r.model_dump(mode="json") for r in recs],
        "total_steps": sum(t.steps_taken for t in task_results),
        "total_duration_ms": sum(t.duration_ms for t in task_results),
        "parseability_score": parseability_score,
    }

    async with httpx.AsyncClient(timeout=30, base_url=API_URL, headers=HEADERS) as client:
        r = await client.post(f"/internal/audit/{AUDIT_ID}/complete", json=report)
        r.raise_for_status()

    print(f"[aggregate] ARS {ars.composite:.1f} ({ars.grade}) -- audit complete")


if __name__ == "__main__":
    asyncio.run(main())
