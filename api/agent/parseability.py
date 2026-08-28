"""
AgentProbe -- static parseability analyzer

Runs on the homepage HTML without the agent loop.
Fast (<2s), deterministic, gives reliable baseline scores
even before any agent tasks run.

Parseability = how machine-readable is this page for an AI agent?
Six signals, max 100 points.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from bs4 import BeautifulSoup

from ..models import ParseabilityResult, ParseabilitySignal


async def analyze_parseability(session, url: str) -> ParseabilityResult:
    """
    Load the URL and run static analysis.
    Returns ParseabilityResult with score 0-100.
    """
    try:
        await session.page.goto(url, wait_until="domcontentloaded", timeout=20000)
        html = await session.page.content()
    except Exception as e:
        return ParseabilityResult(score=0.0, signals=[
            ParseabilitySignal(label="Page load failed", present=False, points=0, detail=str(e))
        ])

    return _analyze_html(html)


def _analyze_html(html: str) -> ParseabilityResult:
    soup = BeautifulSoup(html, "lxml")
    signals: list[ParseabilitySignal] = []
    total_points = 0

    # 1. JSON-LD structured data (20 points)
    jsonld_scripts = soup.find_all("script", type="application/ld+json")
    jsonld_types: list[str] = []
    if jsonld_scripts:
        for script in jsonld_scripts:
            try:
                data = json.loads(script.string or "{}")
                t = data.get("@type", "")
                if t:
                    jsonld_types.append(t)
            except Exception:
                pass
        pts = 20
        total_points += pts
        signals.append(ParseabilitySignal(
            label="JSON-LD structured data",
            present=True,
            points=pts,
            detail=f"Types found: {', '.join(jsonld_types) or 'present'}",
        ))
    else:
        signals.append(ParseabilitySignal(
            label="JSON-LD structured data",
            present=False,
            points=0,
            detail="No JSON-LD found. Add Schema.org markup for Product, Organization, FAQPage.",
        ))

    # 2. Schema.org microdata (10 points)
    microdata = soup.find(attrs={"itemtype": True})
    if microdata:
        total_points += 10
        signals.append(ParseabilitySignal(
            label="Schema.org microdata",
            present=True,
            points=10,
            detail=microdata.get("itemtype", ""),
        ))
    else:
        signals.append(ParseabilitySignal(label="Schema.org microdata", present=False, points=0))

    # 3. ARIA label coverage on interactive elements (20 points, proportional)
    interactive = soup.find_all(["button", "input", "select", "textarea", "a"])
    if interactive:
        aria_labeled = [
            el for el in interactive
            if el.get("aria-label") or el.get("aria-labelledby") or el.get("title")
        ]
        coverage = len(aria_labeled) / len(interactive)
        pts = round(20 * coverage)
        total_points += pts
        signals.append(ParseabilitySignal(
            label="ARIA label coverage",
            present=coverage > 0.5,
            points=pts,
            detail=f"{coverage:.0%} of interactive elements labelled ({len(aria_labeled)}/{len(interactive)})",
        ))
    else:
        signals.append(ParseabilitySignal(
            label="ARIA label coverage",
            present=False,
            points=0,
            detail="No interactive elements found",
        ))
        coverage = 0.0

    # 4. Form label coverage (15 points, proportional)
    inputs = [i for i in soup.find_all("input") if i.get("type", "") not in ("hidden", "submit", "button")]
    form_label_coverage = 0.0
    if inputs:
        labeled = [
            i for i in inputs
            if (
                soup.find("label", attrs={"for": i.get("id", "__none__")})
                or i.get("aria-label")
                or i.get("placeholder")
            )
        ]
        form_label_coverage = len(labeled) / len(inputs)
        pts = round(15 * form_label_coverage)
        total_points += pts
        signals.append(ParseabilitySignal(
            label="Form input labels",
            present=form_label_coverage > 0.5,
            points=pts,
            detail=f"{form_label_coverage:.0%} of inputs have labels/placeholders",
        ))
    else:
        signals.append(ParseabilitySignal(label="Form input labels", present=True, points=15, detail="No forms on homepage"))
        total_points += 15
        form_label_coverage = 1.0

    # 5. Machine-readable prices (20 points)
    price_pattern = re.compile(
        r'[\$€£¥₹]\s*[\d,]+\.?\d*|[\d,]+\.?\d*\s*(USD|EUR|GBP|INR|per\s+month|\/mo)',
        re.IGNORECASE,
    )
    body_text = soup.get_text()
    prices = price_pattern.findall(body_text)
    price_count = len(prices)
    if prices:
        pts = min(20, 10 + price_count * 2)
        total_points += pts
        signals.append(ParseabilitySignal(
            label="Machine-readable prices",
            present=True,
            points=pts,
            detail=f"{price_count} price indicator(s) found as plain text",
        ))
    else:
        # Check for price-like elements that might be SVG/image (bad for agents)
        price_class_els = soup.find_all(
            attrs={"class": re.compile(r"price|cost|amount", re.I)}
        )
        if price_class_els:
            signals.append(ParseabilitySignal(
                label="Machine-readable prices",
                present=False,
                points=0,
                detail=f"Price containers exist but no parseable text values found -- likely rendered as images or CSS",
            ))
        else:
            signals.append(ParseabilitySignal(label="Machine-readable prices", present=False, points=0))

    # 6. Open Graph + meta description (15 points)
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    meta_desc = soup.find("meta", attrs={"name": "description"})
    has_og = bool(og_title and og_desc)
    has_meta = bool(meta_desc)

    if has_og and has_meta:
        total_points += 15
        signals.append(ParseabilitySignal(
            label="Open Graph + meta description",
            present=True,
            points=15,
            detail="Full OG tags and meta description present",
        ))
    elif has_meta:
        total_points += 8
        signals.append(ParseabilitySignal(
            label="Open Graph + meta description",
            present=True,
            points=8,
            detail="Meta description present, OG tags missing",
        ))
    else:
        signals.append(ParseabilitySignal(
            label="Open Graph + meta description",
            present=False,
            points=0,
            detail="No meta description or OG tags",
        ))

    return ParseabilityResult(
        score=min(float(total_points), 100.0),
        signals=signals,
        json_ld_types=jsonld_types,
        price_count=price_count,
        aria_coverage=coverage if interactive else 1.0,
        form_label_coverage=form_label_coverage,
    )
