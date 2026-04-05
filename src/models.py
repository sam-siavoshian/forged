"""Shared types for the Rocket Booster system."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


@dataclass
class TemplateStep:
    """A single step in a task template."""

    index: int
    type: str  # "fixed", "parameterized", "dynamic"
    action: str | None = None  # e.g., "navigate", "click", "fill", "input"
    url: str | None = None
    selector: str | None = None
    fallback_selectors: list[str] = field(default_factory=list)
    param: str | None = None  # for parameterized steps
    value: str | None = None  # for fixed fill steps
    key: str | None = None  # for press actions
    modifiers: list[str] = field(default_factory=list)
    direction: str | None = None  # for scroll
    amount: int | None = None  # for scroll
    ms: int | None = None  # for wait_time
    description: str | None = None  # for dynamic steps
    agent_needed: bool = False
    context_hint: str | None = None
    verify: dict[str, Any] | None = None
    timeout_ms: int = 5000
    on_failure: str = "abort"  # "abort", "try_fallback", "continue", "retry"
    clear_first: bool = True  # for fill actions
    state: str = "visible"  # for wait_for


@dataclass
class TemplateParameter:
    """A parameter that a template accepts."""

    name: str
    type: str  # "string", "number", etc.
    description: str = ""


@dataclass
class TaskTemplate:
    """A reusable browser automation template."""

    id: str
    domain: str
    action_type: str
    task_pattern: str
    parameters: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    handoff_index: int
    confidence: float
    success_count: int
    failure_count: int
    avg_rocket_duration_ms: int | None = None
    avg_agent_duration_ms: int | None = None
    avg_total_duration_ms: int | None = None
    avg_baseline_duration_ms: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class ExecutionTrace:
    """A record of a single task execution."""

    id: str
    template_id: str | None
    task_description: str
    mode: str  # "rocket" or "baseline"
    steps_executed: list[dict[str, Any]]
    rocket_steps_count: int | None
    agent_steps_count: int | None
    total_duration_ms: int
    rocket_duration_ms: int | None
    agent_duration_ms: int | None
    success: bool
    error_message: str | None = None
    error_step_index: int | None = None
    created_at: str | None = None


@dataclass
class SiteKnowledge:
    """Cached knowledge about a specific website."""

    id: str
    domain: str
    selector_map: dict[str, list[str]] = field(default_factory=dict)
    navigation_patterns: dict[str, list[str]] = field(default_factory=dict)
    page_load_signals: dict[str, str] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


# --- Browser Architecture Layer Models ---


@dataclass
class RocketResult:
    """Outcome of the Playwright rocket phase."""

    steps_completed: int
    total_steps: int
    duration_seconds: float
    aborted: bool
    abort_reason: str | None = None
    current_url: str | None = None
    step_timings: list[float] = field(default_factory=list)
    skipped_steps: list[int] = field(default_factory=list)
    step_outcomes: list[tuple[str, str | None]] = field(default_factory=list)
    page_content: str | None = None  # visible text extracted via page.evaluate() before disconnect
    # step_outcomes entries: ("completed", None), ("skipped", reason), ("aborted", reason),
    # ("completed_after_retry", None), ("fallback_failed", reason)


@dataclass
class AgentResult:
    """Outcome of the browser-use agent phase."""

    action_names: list[str] = field(default_factory=list)
    model_actions: list[dict] = field(default_factory=list)
    model_thoughts: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    final_result: str | None = None


@dataclass
class ExecutionResult:
    """Combined result of rocket + agent phases."""

    success: bool
    rocket_result: RocketResult | None = None
    agent_result: AgentResult | None = None
    total_duration_seconds: float = 0.0
    error: str | None = None


@dataclass
class CloudBrowserSession:
    """Metadata for an active BaaS browser session."""

    browser_id: str
    cdp_url: str
    live_url: str
    status: str


@dataclass
class SessionState:
    """Tracks the lifecycle state of a browser session through handoff."""

    browser_session: CloudBrowserSession | None = None
    rocket_result: RocketResult | None = None
    agent_result: AgentResult | None = None
    phase: str = "idle"  # idle, browser_created, rocket_running, rocket_done, agent_running, agent_done, stopped


# --- Orchestrator Layer Models ---


@dataclass
class Template:
    """A reusable task template with parameterized Playwright steps (orchestrator view)."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_pattern: str = ""
    site_domain: str = ""
    embedding: list[float] = field(default_factory=list)
    playwright_steps: list[dict] = field(default_factory=list)
    parameter_schema: dict = field(default_factory=dict)
    agent_handoff_prompt: str = ""
    created_at: str = ""
    usage_count: int = 0
    similarity_score: float = 0.0  # Populated during matching, not stored


@dataclass
class OrchestratorResult:
    """Full execution result with all timing and trace data (orchestrator level)."""

    session_id: str
    task: str
    mode: str  # "baseline" or "rocket"
    success: bool
    total_duration_ms: int
    browser_creation_ms: int
    playwright_steps: int
    agent_steps: int
    total_steps: int
    model: str

    template_lookup_ms: int | None = None
    parameter_extraction_ms: int | None = None
    playwright_duration_ms: int | None = None
    agent_duration_ms: int | None = None
    template_extraction_ms: int | None = None

    output: str | None = None
    error: str | None = None
    live_url: str | None = None
    llm_cost_usd: float | None = None
    trace: Any = None  # AgentHistory -- not serialized to API

    def to_response(self) -> RunResponse:
        return RunResponse(
            session_id=self.session_id,
            task=self.task,
            mode=self.mode,
            success=self.success,
            timing=TimingBreakdown(
                total_duration_ms=self.total_duration_ms,
                template_lookup_ms=self.template_lookup_ms,
                parameter_extraction_ms=self.parameter_extraction_ms,
                browser_creation_ms=self.browser_creation_ms,
                playwright_duration_ms=self.playwright_duration_ms,
                agent_duration_ms=self.agent_duration_ms,
                template_extraction_ms=self.template_extraction_ms,
            ),
            steps=StepCounts(
                playwright_steps=self.playwright_steps,
                agent_steps=self.agent_steps,
                total_steps=self.total_steps,
            ),
            output=self.output,
            error=self.error,
            live_url=self.live_url,
            model=self.model,
            llm_cost_usd=self.llm_cost_usd,
        )


@dataclass
class OrchestratorSessionState:
    """Mutable session state for real-time frontend polling."""

    session_id: str
    task: str
    mode: str
    status: str = "starting"
    live_url: str | None = None
    error: str | None = None


# --- API Request/Response Models (Pydantic) ---


class RunRequest(BaseModel):
    """Request body for /api/run, /api/run-baseline, /api/run-rocket."""

    task: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Natural-language task description",
        examples=["Search for wireless mouse under $50 on Amazon"],
    )
    mode: str = Field(
        default="auto",
        pattern="^(auto|baseline|rocket|learn)$",
        description="Execution mode",
    )


class CompareRequest(BaseModel):
    """Request body for batch comparison runs."""

    task: str = Field(..., min_length=5, max_length=2000)
    runs_per_mode: int = Field(default=1, ge=1, le=5)


class TimingBreakdown(BaseModel):
    """Millisecond-level timing for every execution phase."""

    total_duration_ms: int
    template_lookup_ms: int | None = None
    parameter_extraction_ms: int | None = None
    browser_creation_ms: int
    playwright_duration_ms: int | None = None
    agent_duration_ms: int | None = None
    template_extraction_ms: int | None = None


class StepCounts(BaseModel):
    playwright_steps: int
    agent_steps: int
    total_steps: int


class RunResponse(BaseModel):
    """Response from a single task execution."""

    session_id: str
    task: str
    mode: str
    success: bool
    timing: TimingBreakdown
    steps: StepCounts
    output: str | None = None
    error: str | None = None
    live_url: str | None = None
    model: str
    llm_cost_usd: float | None = None


class StatusResponse(BaseModel):
    """Polling response for real-time session tracking."""

    session_id: str
    task: str
    mode: str
    status: str
    live_url: str | None = None
    error: str | None = None


class TemplateResponse(BaseModel):
    """Summary of a stored template."""

    id: str
    task_pattern: str
    site_domain: str
    playwright_step_count: int
    parameter_names: list[str]
    created_at: str
    usage_count: int


class ComparisonResponse(BaseModel):
    """Side-by-side comparison of two execution results."""

    baseline: RunResponse
    rocket: RunResponse
    speedup_factor: float
    time_saved_ms: int
    steps_saved: int
