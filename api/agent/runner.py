"""
AgentProbe -- browser agent runner

The Claude-powered decision loop. For each task the agent:
  1. Loads the page
  2. Extracts a concise page summary (links, buttons, inputs, headings, text)
  3. Asks Claude what to do next
  4. Executes the action
  5. Repeats until done / failed / max_steps

All events are streamed back to the API via HTTP POST so the
dashboard gets live updates via SSE.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Optional

import httpx

from ..models import (
    AgentStep,
    StepAction,
    TaskName,
    TaskResult,
    TaskStatus,
)
from ..scoring import compute_ars, generate_recommendations
from .browser import BrowserSession
from .claude_loop import claude_decide
from .parseability import analyze_parseability
from ..tasks.registry import TASK_REGISTRY


MAX_STEPS = 15
STEP_TIMEOUT = 30  # seconds per action


# ---------------------------------------------------------------------------
# In-process audit (used when GitHub Actions is not configured)
# ---------------------------------------------------------------------------

async def run_audit_inprocess(
    audit_id: str,
    url: str,
    tasks: list[str],
    api_base: str,
    worker_secret: str,
) -> None:
    """Full audit lifecycle. Runs as an asyncio background task."""
    client = _make_client(api_base, worker_secret)

    try:
        await _post_event(client, audit_id, {"event_type": "audit_start", "url": url})

        task_results: list[TaskResult] = []

        async with BrowserSession() as session:
            # Static parseability analysis on root URL
            await _post_event(client, audit_id, {"event_type": "parseability_start"})
            parseability = await analyze_parseability(session, url)
            await _post_event(client, audit_id, {
                "event_type": "parseability_done",
                "score": parseability.score,
                "signals": [s.model_dump() for s in parseability.signals],
            })

            # Run tasks sequentially (GitHub Actions runs them in parallel matrix)
            for task_name_str in tasks:
                try:
                    task_name = TaskName(task_name_str)
                except ValueError:
                    continue

                task_def = TASK_REGISTRY.get(task_name)
                if not task_def:
                    continue

                result = await run_task(
                    session=session,
                    audit_id=audit_id,
                    task_name=task_name,
                    task_description=task_def["description"],
                    start_url=url,
                    client=client,
                )
                task_results.append(result)

        ars = compute_ars(task_results, parseability)
        recs = generate_recommendations(ars, task_results, parseability)

        report = {
            "audit_id": audit_id,
            "url": url,
            "status": "completed",
            "ars": ars.model_dump(mode="json"),
            "parseability": parseability.model_dump(mode="json"),
            "tasks": [t.model_dump(mode="json") for t in task_results],
            "recommendations": [r.model_dump(mode="json") for r in recs],
            "total_steps": sum(t.steps_taken for t in task_results),
            "total_duration_ms": sum(t.duration_ms for t in task_results),
            "industry_vs": {
                dim: round(getattr(ars, dim) - baseline, 1)
                for dim, baseline in {
                    "discoverability": 68.0,
                    "parseability": 52.0,
                    "task_completion": 57.0,
                    "friction": 63.0,
                    "clarity": 61.0,
                    "resilience": 72.0,
                }.items()
            },
        }

        await client.post(f"{api_base}/audit/{audit_id}/complete", json=report)

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        try:
            await client.post(f"{api_base}/audit/{audit_id}/fail", json={"error": error_msg})
        except Exception:
            pass
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# Single-task runner
# ---------------------------------------------------------------------------

async def run_task(
    session: BrowserSession,
    audit_id: str,
    task_name: TaskName,
    task_description: str,
    start_url: str,
    client: httpx.AsyncClient,
) -> TaskResult:
    """Run one task, stream steps to the API, return TaskResult."""

    await _post_event(client, audit_id, {
        "event_type": "task_start",
        "task_name": task_name.value,
        "description": task_description,
    })

    steps: list[AgentStep] = []
    history: list[dict] = []
    walls_hit = 0
    backtracks = 0
    task_start = time.monotonic()

    # Navigate to the start URL fresh for each task
    try:
        await session.page.goto(start_url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(1)
    except Exception as e:
        return TaskResult(
            task_name=task_name,
            status=TaskStatus.failed,
            failure_point=f"Could not load start URL: {e}",
            steps_taken=0,
            duration_ms=0,
        )

    for step_idx in range(MAX_STEPS):
        step_start = time.monotonic()

        # Extract page state
        try:
            page_summary = await session.get_page_summary()
        except Exception:
            page_summary = {"error": "could not extract page state"}

        current_url = session.page.url

        # Claude decides what to do
        try:
            decision = await claude_decide(
                task_description=task_description,
                current_url=current_url,
                page_summary=page_summary,
                history=history[-4:],
                step_index=step_idx,
            )
        except Exception as e:
            decision = {
                "action": "failed",
                "target": None,
                "value": None,
                "reasoning": f"Claude API error: {e}",
                "confidence": 0.0,
                "friction_note": None,
            }

        action_str = decision.get("action", "failed")
        friction_note = decision.get("friction_note")

        # Track friction signals
        if friction_note and any(
            kw in friction_note.lower()
            for kw in ["captcha", "login required", "sign in to", "verify", "phone number"]
        ):
            walls_hit += 1

        step = AgentStep(
            step_index=step_idx,
            url=current_url,
            action=StepAction(action_str) if action_str in StepAction.__members__.values() else StepAction.failed,
            target=decision.get("target"),
            value=decision.get("value"),
            reasoning=decision.get("reasoning", ""),
            confidence=float(decision.get("confidence", 0.5)),
            friction_note=friction_note,
            duration_ms=round((time.monotonic() - step_start) * 1000, 1),
        )
        steps.append(step)

        # Stream step to API
        await _post_event(client, audit_id, {
            "event_type": "step",
            "task_name": task_name.value,
            "step": step.model_dump(mode="json"),
        })

        history.append({
            "step": step_idx,
            "url": current_url,
            "action": action_str,
            "target": decision.get("target"),
            "reasoning": decision.get("reasoning", ""),
        })

        # Terminal conditions
        if action_str == "done":
            duration = round((time.monotonic() - task_start) * 1000, 1)
            result = TaskResult(
                task_name=task_name,
                status=TaskStatus.completed,
                steps=steps,
                steps_taken=len(steps),
                duration_ms=duration,
                agent_summary=decision.get("reasoning"),
                walls_hit=walls_hit,
                backtracks=backtracks,
                avg_confidence=_avg_conf(steps),
                completion_score=100.0,
            )
            await _post_event(client, audit_id, {
                "event_type": "task_done",
                "task_name": task_name.value,
                "status": "completed",
                "steps_taken": len(steps),
                "duration_ms": duration,
            })
            return result

        if action_str == "failed":
            duration = round((time.monotonic() - task_start) * 1000, 1)
            result = TaskResult(
                task_name=task_name,
                status=TaskStatus.failed,
                steps=steps,
                steps_taken=len(steps),
                duration_ms=duration,
                failure_point=decision.get("reasoning"),
                walls_hit=walls_hit,
                backtracks=backtracks,
                avg_confidence=_avg_conf(steps),
            )
            await _post_event(client, audit_id, {
                "event_type": "task_done",
                "task_name": task_name.value,
                "status": "failed",
                "failure_point": decision.get("reasoning"),
                "steps_taken": len(steps),
            })
            return result

        # Execute the action
        try:
            went_back = await session.execute_action(
                action=action_str,
                target=decision.get("target"),
                value=decision.get("value"),
            )
            if went_back:
                backtracks += 1
        except Exception as e:
            # Action failed -- log and let the agent recover next step
            history.append({"step": step_idx, "error": str(e)})

        await asyncio.sleep(0.8)

    # Timeout
    duration = round((time.monotonic() - task_start) * 1000, 1)
    result = TaskResult(
        task_name=task_name,
        status=TaskStatus.failed,
        steps=steps,
        steps_taken=len(steps),
        duration_ms=duration,
        failure_point=f"Exceeded {MAX_STEPS} steps without completing task",
        walls_hit=walls_hit,
        backtracks=backtracks,
        avg_confidence=_avg_conf(steps),
    )
    await _post_event(client, audit_id, {
        "event_type": "task_done",
        "task_name": task_name.value,
        "status": "failed",
        "failure_point": "timeout",
        "steps_taken": len(steps),
    })
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(api_base: str, worker_secret: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=api_base,
        headers={"x-worker-secret": worker_secret},
        timeout=15.0,
    )


async def _post_event(client: httpx.AsyncClient, audit_id: str, event: dict) -> None:
    try:
        await client.post(f"/audit/{audit_id}/events", json=event)
    except Exception:
        pass  # non-fatal


def _avg_conf(steps: list[AgentStep]) -> float:
    if not steps:
        return 1.0
    return round(sum(s.confidence for s in steps) / len(steps), 3)
