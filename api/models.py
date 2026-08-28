"""
AgentProbe -- data models
All Pydantic v2. Every audit, step, and score lives here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AuditStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class TaskName(str, Enum):
    pricing_discovery = "PRICING_DISCOVERY"
    contact_extraction = "CONTACT_EXTRACTION"
    checkout_initiation = "CHECKOUT_INITIATION"
    demo_booking = "DEMO_BOOKING"
    policy_retrieval = "POLICY_RETRIEVAL"
    support_routing = "SUPPORT_ROUTING"
    api_discovery = "API_DISCOVERY"


class StepAction(str, Enum):
    navigate = "navigate"
    click = "click"
    type = "type"
    scroll = "scroll"
    done = "done"
    failed = "failed"
    wait = "wait"


# ---------------------------------------------------------------------------
# Step-level models
# ---------------------------------------------------------------------------

class AgentStep(BaseModel):
    step_id: str = Field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    step_index: int
    url: str
    action: StepAction
    target: Optional[str] = None
    value: Optional[str] = None
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    friction_note: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TaskResult(BaseModel):
    task_name: TaskName
    status: TaskStatus
    steps: list[AgentStep] = []
    steps_taken: int = 0
    duration_ms: float = 0.0
    failure_point: Optional[str] = None
    agent_summary: Optional[str] = None
    extracted_data: dict[str, Any] = {}

    # Per-task dimension scores (0-100)
    friction_score: float = 100.0
    clarity_score: float = 100.0
    completion_score: float = 0.0

    walls_hit: int = 0        # CAPTCHAs, login walls
    backtracks: int = 0
    avg_confidence: float = 1.0


# ---------------------------------------------------------------------------
# Parseability (static analysis)
# ---------------------------------------------------------------------------

class ParseabilitySignal(BaseModel):
    label: str
    present: bool
    points: int
    detail: Optional[str] = None


class ParseabilityResult(BaseModel):
    score: float = 0.0          # 0-100
    signals: list[ParseabilitySignal] = []
    json_ld_types: list[str] = []
    price_count: int = 0
    aria_coverage: float = 0.0  # 0-1
    form_label_coverage: float = 0.0


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

class ARSBreakdown(BaseModel):
    """Agentic Readiness Score -- 6-dimensional scoring."""
    discoverability: float = 0.0   # w=0.20  Can the agent find key pages?
    parseability: float = 0.0      # w=0.20  Is content machine-readable?
    task_completion: float = 0.0   # w=0.30  Can tasks be completed end-to-end?
    friction: float = 0.0          # w=0.15  How many walls / obstacles?
    clarity: float = 0.0           # w=0.10  Are decisions unambiguous?
    resilience: float = 0.0        # w=0.05  Can the agent recover from failures?

    composite: float = 0.0
    grade: str = "F"

    @staticmethod
    def compute_grade(score: float) -> str:
        if score >= 90:
            return "A+"
        if score >= 80:
            return "A"
        if score >= 70:
            return "B"
        if score >= 60:
            return "C"
        if score >= 50:
            return "D"
        return "F"


class Recommendation(BaseModel):
    severity: str   # "critical" | "warning" | "info"
    dimension: str  # which ARS dimension this addresses
    title: str
    detail: str
    estimated_impact: int  # +N points to ARS if fixed


# ---------------------------------------------------------------------------
# Audit request / response
# ---------------------------------------------------------------------------

class AuditRequest(BaseModel):
    url: str
    tasks: list[TaskName] = list(TaskName)
    label: Optional[str] = None    # optional human label, e.g. "Stripe pricing"


class AuditCreate(BaseModel):
    """What the API stores when it creates an audit."""
    audit_id: str = Field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:12]}")
    url: str
    label: Optional[str] = None
    tasks: list[str]
    status: AuditStatus = AuditStatus.queued
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditEvent(BaseModel):
    """Streamed event from the worker -> API -> dashboard polling."""
    audit_id: str
    event_type: str   # "task_start" | "step" | "task_done" | "audit_done" | "error"
    task_name: Optional[str] = None
    step: Optional[AgentStep] = None
    task_result: Optional[TaskResult] = None
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AuditReport(BaseModel):
    audit_id: str
    url: str
    label: Optional[str] = None
    status: AuditStatus
    ars: ARSBreakdown
    parseability: Optional[ParseabilityResult] = None
    tasks: list[TaskResult] = []
    recommendations: list[Recommendation] = []
    total_steps: int = 0
    total_duration_ms: float = 0.0
    created_at: datetime
    completed_at: Optional[datetime] = None

    # For the comparison endpoint
    vs_industry_avg: Optional[dict[str, float]] = None


class AuditSummary(BaseModel):
    """Lightweight version for list endpoints."""
    audit_id: str
    url: str
    label: Optional[str] = None
    status: AuditStatus
    composite_ars: float
    grade: str
    created_at: datetime
