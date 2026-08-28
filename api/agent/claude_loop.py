"""
AgentProbe -- LLM decision loop (Groq, free tier)

Model priority:
  1. llama-3.3-70b-versatile  (best reasoning, free on Groq)
  2. llama-3.1-8b-instant     (fallback if 70b rate-limited)

Groq free tier: 14,400 requests/day, 6000 tokens/min per model.
Each decision step uses ~400-600 tokens. Well within limits.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from groq import AsyncGroq

_groq = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY", ""))

PRIMARY_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct-fp8"
FALLBACK_MODEL = "llama-3.1-70b-versatile"
FAST_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are an AI agent browsing a website. Complete the assigned task efficiently.

ALWAYS respond with ONLY a JSON object -- no markdown, no explanation, just the JSON:
{
  "action": "navigate | click | type | scroll | done | failed",
  "target": "CSS selector, exact link/button text, or full URL (for navigate)",
  "value": "text to type (only if action=type, else null)",
  "reasoning": "one sentence",
  "confidence": 0.85,
  "friction_note": "optional: CAPTCHA, login wall, broken element, or ambiguous UI"
}

Rules:
- Use "done" immediately when the task goal is clearly achieved
- Use "failed" if you hit a hard blocker (CAPTCHA, mandatory login, no path forward)
- Prefer clicking visible elements over navigating to URLs directly
- confidence: 1.0 = certain this action leads toward goal, 0.0 = guessing"""


async def claude_decide(
    task_description: str,
    current_url: str,
    page_summary: dict[str, Any],
    history: list[dict],
    step_index: int,
) -> dict[str, Any]:
    """
    Ask Groq/Llama what to do next given the current page state.
    Returns parsed action dict.
    """
    history_text = "\n".join(
        f"  Step {h.get('step', '?')}: {h.get('action')} -> {h.get('target', 'n/a')} | {h.get('reasoning', '')}"
        for h in history
    ) or "  (none yet)"

    page_text = json.dumps(page_summary, ensure_ascii=False)
    if len(page_text) > 5000:
        page_text = page_text[:5000] + "..."

    user_message = f"""Task: {task_description}

URL: {current_url}
Step: {step_index + 1} / 15

Recent actions:
{history_text}

Page state:
{page_text}

Decide the next action (respond with JSON only):"""

    for model in [PRIMARY_MODEL, FALLBACK_MODEL, FAST_MODEL]:
        try:
            resp = await _groq.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=350,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            text = resp.choices[0].message.content.strip()
            return _parse_response(text)
        except Exception as e:
            err = str(e)
            if any(x in err.lower() for x in ["rate_limit", "model_not_found", "404", "does not exist"]):
                continue  # try next model
            return _error_decision(err)

    return _error_decision("All models failed")


def _parse_response(text: str) -> dict[str, Any]:
    # Strip fences if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(l for l in lines if not l.startswith("```"))

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
            except Exception:
                return _error_decision(f"Unparseable response: {text[:100]}")
        else:
            return _error_decision(f"No JSON found in response: {text[:100]}")

    valid_actions = {"navigate", "click", "type", "scroll", "done", "failed", "wait"}
    if parsed.get("action") not in valid_actions:
        parsed["action"] = "failed"
        parsed["reasoning"] = f"Model returned invalid action: {parsed.get('action')}"

    # Ensure all expected keys are present
    parsed.setdefault("target", None)
    parsed.setdefault("value", None)
    parsed.setdefault("reasoning", "")
    parsed.setdefault("confidence", 0.5)
    parsed.setdefault("friction_note", None)

    return parsed


def _error_decision(error: str) -> dict[str, Any]:
    return {
        "action": "failed",
        "target": None,
        "value": None,
        "reasoning": f"LLM error: {error}",
        "confidence": 0.0,
        "friction_note": None,
    }
