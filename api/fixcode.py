"""
AgentProbe -- AI-generated fix code

For each recommendation, calls Groq (llama-3.3-70b) to generate the exact
copy-paste code that would fix the issue on the audited site.

Results are added to the report's recommendations list as `fix_code`.
"""

from __future__ import annotations

import os
from typing import Optional

try:
    from groq import AsyncGroq
    _groq_available = True
except ImportError:
    _groq_available = False

from .models import Recommendation

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


_SYSTEM = """You are an expert web developer helping a site become AI-agent-friendly.
Given a specific issue found by AgentProbe, output ONLY the minimal code snippet
that fixes it. No explanations, no markdown prose, just the code block.
Be concise. Use real-world best-practice patterns.
If the fix is a JSON-LD script tag, output that. If it's aria-label additions,
output a diff-style snippet. If it's a robots.txt line, output just that line.
Max 30 lines of code."""


async def generate_fix_code(
    rec: Recommendation,
    site_url: str,
) -> Optional[str]:
    """Return a code snippet string or None if Groq is unavailable / fails."""
    if not _groq_available or not GROQ_API_KEY:
        return None

    try:
        client = AsyncGroq(api_key=GROQ_API_KEY)
        prompt = (
            f"Site URL: {site_url}\n"
            f"Dimension: {rec.dimension}\n"
            f"Issue: {rec.title}\n"
            f"Detail: {rec.detail}\n\n"
            "Generate the exact code snippet to fix this issue."
        )
        resp = await client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.1,
        )
        code = resp.choices[0].message.content.strip()
        return code if code else None
    except Exception:
        return None


async def enrich_recommendations_with_fixes(
    recs: list[Recommendation],
    site_url: str,
) -> list[dict]:
    """
    Return serializable dicts of recommendations with fix_code added.
    Runs all Groq calls concurrently.
    """
    import asyncio
    tasks = [generate_fix_code(r, site_url) for r in recs]
    codes = await asyncio.gather(*tasks, return_exceptions=True)

    result = []
    for rec, code in zip(recs, codes):
        d = rec.model_dump(mode="json")
        if isinstance(code, str):
            d["fix_code"] = code
        result.append(d)
    return result
