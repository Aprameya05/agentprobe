"""
AgentProbe -- Agentic Readiness Score (ARS) engine

Six-dimensional composite score that measures how well a website
serves AI agent traffic. Each dimension maps to a concrete failure
mode that costs real agent conversions.

Dimension weights (sum to 1.0):
  discoverability  0.20 -- can the agent find key pages?
  parseability     0.20 -- is content machine-readable?
  task_completion  0.30 -- can tasks finish end-to-end?
  friction         0.15 -- how many walls / dead ends?
  clarity          0.10 -- are decisions unambiguous?
  resilience       0.05 -- can the agent recover from errors?

ARS = weighted sum, 0-100.
Grade: A+ (>=90), A (>=80), B (>=70), C (>=60), D (>=50), F (<50).

Industry baseline (derived from pilot audits):
  SaaS pricing pages:  avg ARS 61
  E-commerce checkout: avg ARS 54
  B2B lead gen:        avg ARS 47
"""

from __future__ import annotations

import math
from typing import Optional

from .models import (
    ARSBreakdown,
    AuditReport,
    ParseabilityResult,
    Recommendation,
    TaskResult,
    TaskStatus,
)

# Industry averages for comparison panel
INDUSTRY_BASELINES: dict[str, float] = {
    "discoverability": 68.0,
    "parseability": 52.0,
    "task_completion": 57.0,
    "friction": 63.0,
    "clarity": 61.0,
    "resilience": 72.0,
    "composite": 60.5,
}

WEIGHTS = {
    "discoverability": 0.20,
    "parseability": 0.20,
    "task_completion": 0.30,
    "friction": 0.15,
    "clarity": 0.10,
    "resilience": 0.05,
}


# ---------------------------------------------------------------------------
# Individual dimension scorers
# ---------------------------------------------------------------------------

def score_discoverability(tasks: list[TaskResult]) -> float:
    """
    Measures how quickly the agent reaches key pages.

    scoring per task:
      found in 1 hop:  100
      found in 2 hops: 75
      found in 3 hops: 55
      4+ hops:         35
      not found:       0

    Partial completion (agent reached a related page but not the goal) gives 40.
    """
    if not tasks:
        return 0.0

    scores: list[float] = []
    for t in tasks:
        if t.status == TaskStatus.completed:
            hops = t.steps_taken
            if hops <= 1:
                scores.append(100.0)
            elif hops == 2:
                scores.append(75.0)
            elif hops == 3:
                scores.append(55.0)
            else:
                scores.append(max(35.0, 55.0 - (hops - 3) * 5))
        elif t.status == TaskStatus.failed:
            # partial credit if agent made real progress
            progress = min(t.steps_taken / 8.0, 1.0)
            scores.append(40.0 * progress)
        else:
            scores.append(0.0)

    return sum(scores) / len(scores)


def score_parseability(result: Optional[ParseabilityResult]) -> float:
    """Raw parseability score from the static analyzer."""
    if result is None:
        return 50.0  # unknown, give benefit of doubt
    return result.score


def score_task_completion(tasks: list[TaskResult]) -> float:
    """
    Binary completion with partial credit.

    completed:         100
    failed with steps: 20 * (steps / max_steps), capped at 40
    skipped:           0
    """
    if not tasks:
        return 0.0

    scores: list[float] = []
    for t in tasks:
        if t.status == TaskStatus.completed:
            scores.append(100.0)
        elif t.status == TaskStatus.failed:
            partial = min(t.steps_taken / 15.0, 1.0) * 40.0
            scores.append(partial)
        elif t.status == TaskStatus.skipped:
            scores.append(0.0)
        else:
            scores.append(0.0)

    return sum(scores) / len(scores)


def score_friction(tasks: list[TaskResult]) -> float:
    """
    Friction Index -- higher = less friction = better.

    Starts at 100. Deductions:
      -25 per CAPTCHA or bot-detection wall
      -20 per mandatory login wall blocking a public task
      -10 per required field that blocks agent (phone, SSN, etc.)
      -8  per dead end requiring backtrack
      -4  per step where agent confidence < 0.4 (ambiguous UI)
    """
    score = 100.0

    for t in tasks:
        score -= t.walls_hit * 25
        score -= t.backtracks * 8

        for step in t.steps:
            if step.confidence < 0.4:
                score -= 4
            if step.friction_note and any(
                kw in step.friction_note.lower()
                for kw in ["captcha", "login required", "sign in", "verify", "phone"]
            ):
                score -= 10

    return max(score, 0.0)


def score_clarity(tasks: list[TaskResult]) -> float:
    """
    Decision clarity -- inverse of average agent uncertainty.

    clarity = 100 * mean(confidence across all steps)
    Penalize extra for steps where agent had to backtrack after low-confidence action.
    """
    all_confidences: list[float] = []

    for t in tasks:
        for step in t.steps:
            all_confidences.append(step.confidence)

    if not all_confidences:
        return 70.0  # neutral default

    avg_conf = sum(all_confidences) / len(all_confidences)
    base = avg_conf * 100

    # additional penalty for high variance (inconsistent clarity across site)
    if len(all_confidences) >= 3:
        mean = avg_conf
        variance = sum((c - mean) ** 2 for c in all_confidences) / len(all_confidences)
        std = math.sqrt(variance)
        base -= std * 20  # high variance = confusing site

    return max(0.0, min(100.0, base))


def score_resilience(tasks: list[TaskResult]) -> float:
    """
    Measures agent's ability to recover from errors.

    If no failures occurred: 100 (no resilience needed)
    Otherwise: (successful_recoveries / total_failure_moments) * 100

    A backtrack that led to task completion counts as successful recovery.
    """
    total_failures = sum(t.backtracks + t.walls_hit for t in tasks)

    if total_failures == 0:
        return 100.0

    recoveries = sum(
        1 for t in tasks
        if t.status == TaskStatus.completed and (t.backtracks + t.walls_hit) > 0
    )

    return min(100.0, (recoveries / max(total_failures, 1)) * 100)


# ---------------------------------------------------------------------------
# Composite ARS
# ---------------------------------------------------------------------------

def compute_ars(
    tasks: list[TaskResult],
    parseability: Optional[ParseabilityResult] = None,
) -> ARSBreakdown:
    d = score_discoverability(tasks)
    p = score_parseability(parseability)
    t = score_task_completion(tasks)
    f = score_friction(tasks)
    c = score_clarity(tasks)
    r = score_resilience(tasks)

    composite = (
        WEIGHTS["discoverability"] * d
        + WEIGHTS["parseability"] * p
        + WEIGHTS["task_completion"] * t
        + WEIGHTS["friction"] * f
        + WEIGHTS["clarity"] * c
        + WEIGHTS["resilience"] * r
    )

    composite = round(min(100.0, max(0.0, composite)), 1)

    return ARSBreakdown(
        discoverability=round(d, 1),
        parseability=round(p, 1),
        task_completion=round(t, 1),
        friction=round(f, 1),
        clarity=round(c, 1),
        resilience=round(r, 1),
        composite=composite,
        grade=ARSBreakdown.compute_grade(composite),
    )


# ---------------------------------------------------------------------------
# Recommendation generator
# ---------------------------------------------------------------------------

def generate_recommendations(
    ars: ARSBreakdown,
    tasks: list[TaskResult],
    parseability: Optional[ParseabilityResult] = None,
) -> list[Recommendation]:
    recs: list[Recommendation] = []

    # Parseability
    if ars.parseability < 60:
        recs.append(Recommendation(
            severity="critical",
            dimension="parseability",
            title="Add JSON-LD structured data to key pages",
            detail=(
                "Pricing, product, and contact pages lack machine-readable markup. "
                "Add Schema.org JSON-LD so agents can extract prices, contact info, "
                "and availability without fragile DOM scraping."
            ),
            estimated_impact=12,
        ))

    if parseability and parseability.aria_coverage < 0.5:
        recs.append(Recommendation(
            severity="warning",
            dimension="parseability",
            title=f"ARIA label coverage is {parseability.aria_coverage:.0%} -- under 50%",
            detail=(
                "More than half of interactive elements have no ARIA label. "
                "Agents rely on accessible names to identify buttons and links. "
                "Without them, the agent must guess from surrounding text and fails often."
            ),
            estimated_impact=8,
        ))

    # Friction
    wall_tasks = [t for t in tasks if t.walls_hit > 0]
    if wall_tasks:
        recs.append(Recommendation(
            severity="critical",
            dimension="friction",
            title=f"{sum(t.walls_hit for t in wall_tasks)} login/CAPTCHA wall(s) block agent tasks",
            detail=(
                "Tasks that should be publicly accessible are gated behind login or "
                "CAPTCHA challenges. AI agents cannot pass these. Any agent trying to "
                "retrieve your pricing or book a demo will fail before reaching its goal."
            ),
            estimated_impact=18,
        ))

    backtrack_tasks = [t for t in tasks if t.backtracks > 2]
    if backtrack_tasks:
        recs.append(Recommendation(
            severity="warning",
            dimension="friction",
            title="Navigation structure forces excessive backtracking",
            detail=(
                "The agent had to backtrack more than twice per task on average. "
                "Add consistent nav labels, breadcrumbs, and direct deep-links to "
                "pricing, checkout, and contact pages."
            ),
            estimated_impact=7,
        ))

    # Task completion
    failed = [t for t in tasks if t.status == TaskStatus.failed]
    if failed:
        names = ", ".join(t.task_name.value for t in failed)
        recs.append(Recommendation(
            severity="critical",
            dimension="task_completion",
            title=f"Agent failed to complete: {names}",
            detail=(
                f"These tasks failed outright. For each: audit the page flow manually, "
                f"identify the exact step where the agent could not proceed, and either "
                f"remove the blocker or add machine-readable affordances."
            ),
            estimated_impact=20,
        ))

    # Discoverability
    if ars.discoverability < 65:
        recs.append(Recommendation(
            severity="warning",
            dimension="discoverability",
            title="Key pages take 3+ hops to reach from the homepage",
            detail=(
                "Pricing, contact, and support pages should be reachable within 2 clicks "
                "from the root. Add footer links, nav shortcuts, and sitemap.xml entries "
                "for these destinations."
            ),
            estimated_impact=9,
        ))

    # Clarity
    if ars.clarity < 60:
        recs.append(Recommendation(
            severity="warning",
            dimension="clarity",
            title="Agent confidence averaged below 60% -- site has ambiguous UI patterns",
            detail=(
                "Buttons with generic labels ('Click here', 'Submit'), prices rendered as "
                "images or SVGs, and overlapping CTAs all reduce agent confidence. "
                "Use descriptive, unique button text and plain-text prices."
            ),
            estimated_impact=6,
        ))

    # Sort: critical first, then by estimated_impact desc
    recs.sort(key=lambda r: (0 if r.severity == "critical" else 1, -r.estimated_impact))
    return recs
