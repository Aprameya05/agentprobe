"""
Parseability-only worker job.
Called by GitHub Actions as a fast static analysis step (< 5 seconds).
"""
import asyncio
import os
import sys
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.agent.browser import BrowserSession
from api.agent.parseability import analyze_parseability


API_URL = os.environ["API_URL"]
AUDIT_ID = os.environ["AUDIT_ID"]
TARGET_URL = os.environ["TARGET_URL"]
WORKER_SECRET = os.environ["WORKER_SECRET"]

HEADERS = {"X-Worker-Secret": WORKER_SECRET, "Content-Type": "application/json"}


async def main() -> None:
    print(f"[parseability] starting static analysis for {TARGET_URL}")
    async with BrowserSession() as session:
        result = await analyze_parseability(session, TARGET_URL)

    payload = result.model_dump()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{API_URL}/internal/audit/{AUDIT_ID}/parseability",
            json=payload,
            headers=HEADERS,
        )
        r.raise_for_status()

    print(f"[parseability] done -- score {result.score:.0f}")


if __name__ == "__main__":
    asyncio.run(main())
