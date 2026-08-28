"""
Aggregate worker job.
Runs after all task jobs finish (GitHub Actions `needs` dependency).
Reads all task results from the API, computes ARS, and posts the final report.
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
WORKER_SECRET = os.environ["WORKER_SECRET"]

HEADERS = {"X-Worker-Secret": WORKER_SECRET, "Content-Type": "application/json"}


async def main() -> None:
    print(f"[aggregate] computing final ARS for audit {AUDIT_ID}")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{API_URL}/audit/{AUDIT_ID}", headers=HEADERS)
        r.raise_for_status()
        audit_data = r.json()

    report = audit_data.get("report") or {}
    raw_tasks = report.get("tasks") or []
    task_results = [TaskResult(**t) for t in raw_tasks]

    if not task_results:
        print("[aggregate] no task results found -- marking audit failed")
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(
                f"{API_URL}/internal/audit/{AUDIT_ID}/fail",
                json={"error": "no task results received"},
                headers=HEADERS,
            )
        return

    parseability_score: float = report.get("parseability_score", 50.0)
    # compute_ars expects None or ParseabilityResult; pass None to use score fallback
    ars = compute_ars(task_results, None)

    payload = ars.model_dump()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{API_URL}/internal/audit/{AUDIT_ID}/complete",
            json=payload,
            headers=HEADERS,
        )
        r.raise_for_status()

    print(f"[aggregate] ARS {ars.composite:.1f} ({ars.grade}) -- audit complete")


if __name__ == "__main__":
    asyncio.run(main())
