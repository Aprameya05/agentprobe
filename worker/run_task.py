"""
AgentProbe worker -- runs a single task in GitHub Actions.
Called by audit-worker.yml in the task matrix.

Reads env: AUDIT_ID, TARGET_URL, TASK_NAME, API_URL, WORKER_SECRET, GROQ_API_KEY
"""

import asyncio
import os
import sys

# Make api package importable from worker/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.agent.browser import BrowserSession
from api.agent.runner import run_task, _make_client, _post_event
from api.models import TaskName
from api.tasks.registry import TASK_REGISTRY


async def main():
    audit_id = os.environ["AUDIT_ID"]
    url = os.environ["TARGET_URL"]
    task_name_str = os.environ["TASK_NAME"]
    api_url = os.environ["API_URL"]
    worker_secret = os.environ["WORKER_SECRET"]

    try:
        task_name = TaskName(task_name_str)
    except ValueError:
        print(f"Unknown task: {task_name_str}", file=sys.stderr)
        sys.exit(1)

    task_def = TASK_REGISTRY.get(task_name)
    if not task_def:
        print(f"No definition for task: {task_name}", file=sys.stderr)
        sys.exit(1)

    client = _make_client(api_url, worker_secret)

    try:
        async with BrowserSession() as session:
            result = await run_task(
                session=session,
                audit_id=audit_id,
                task_name=task_name,
                task_description=task_def["description"],
                start_url=url,
                client=client,
            )

        # Save result as a GitHub Actions output for the aggregation step
        result_json = result.json()
        output_file = os.environ.get("GITHUB_OUTPUT", "/tmp/task_output")
        with open(output_file, "a") as f:
            # Escape newlines for GitHub Actions output
            escaped = result_json.replace("\n", "%0A").replace("\r", "%0D")
            f.write(f"task_result={escaped}\n")
            f.write(f"task_name={task_name_str}\n")
            f.write(f"task_status={result.status.value}\n")

        print(f"Task {task_name_str}: {result.status.value} in {result.steps_taken} steps")

    except Exception as e:
        await _post_event(client, audit_id, {
            "event_type": "task_error",
            "task_name": task_name_str,
            "message": str(e),
        })
        print(f"Task {task_name_str} crashed: {e}", file=sys.stderr)
        raise
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
