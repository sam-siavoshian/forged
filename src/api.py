"""FastAPI backend for the Rocket Booster system."""

from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.orchestrator import RocketOrchestrator, ExecutionMode
from src.models import (
    RunRequest,
    CompareRequest,
    RunResponse,
    StatusResponse,
    TemplateResponse,
    ComparisonResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global state — initialized in lifespan
# ---------------------------------------------------------------------------

orchestrator: RocketOrchestrator | None = None
_results: dict[str, RunResponse] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared clients on startup, clean up on shutdown."""
    global orchestrator

    # Defensive: import DB/Anthropic clients with fallbacks
    try:
        from src.db.client import SupabaseClient

        supabase = SupabaseClient(
            url=os.environ["SUPABASE_URL"],
            key=os.environ["SUPABASE_KEY"],
        )
    except (ImportError, KeyError) as exc:
        logger.warning("Supabase not available (%s), using None", exc)
        supabase = None

    try:
        from anthropic import AsyncAnthropic

        anthropic = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    except ImportError:
        logger.warning("Anthropic SDK not available")
        anthropic = None

    browser_use_key = os.environ.get("BROWSER_USE_API_KEY", "")

    orchestrator = RocketOrchestrator(
        supabase_client=supabase,
        anthropic_client=anthropic,
        browser_use_api_key=browser_use_key,
    )
    logger.info("Orchestrator initialized")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Rocket Booster API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_orchestrator() -> RocketOrchestrator:
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    return orchestrator


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/run", response_model=RunResponse)
async def run_task(request: RunRequest) -> RunResponse:
    """Run a browser task in the specified mode."""
    orch = _require_orchestrator()

    try:
        mode = ExecutionMode(request.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")

    result = await orch.run_task(task=request.task, mode=mode)
    response = result.to_response()
    _results[response.session_id] = response
    return response


@app.post("/api/run-baseline", response_model=RunResponse)
async def run_baseline(request: RunRequest) -> RunResponse:
    """Convenience: always runs in baseline mode."""
    orch = _require_orchestrator()
    result = await orch.run_task(task=request.task, mode=ExecutionMode.BASELINE)
    response = result.to_response()
    _results[response.session_id] = response
    return response


@app.post("/api/run-rocket", response_model=RunResponse)
async def run_rocket(request: RunRequest) -> RunResponse:
    """Convenience: always runs in rocket mode (fails if no template)."""
    orch = _require_orchestrator()

    try:
        result = await orch.run_task(task=request.task, mode=ExecutionMode.ROCKET)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    response = result.to_response()
    _results[response.session_id] = response
    return response


@app.post("/api/learn", response_model=RunResponse)
async def learn_task(request: RunRequest) -> RunResponse:
    """Run baseline + extract template for future rocket runs."""
    orch = _require_orchestrator()
    result = await orch.run_task(task=request.task, mode=ExecutionMode.LEARN)
    response = result.to_response()
    _results[response.session_id] = response
    return response


@app.post("/api/compare", response_model=ComparisonResponse)
async def compare(request: CompareRequest) -> ComparisonResponse:
    """Run same task in baseline and rocket mode, return side-by-side comparison."""
    orch = _require_orchestrator()

    baseline_result = await orch.run_task(
        task=request.task, mode=ExecutionMode.BASELINE
    )
    rocket_result = await orch.run_task(
        task=request.task, mode=ExecutionMode.AUTO
    )

    baseline_resp = baseline_result.to_response()
    rocket_resp = rocket_result.to_response()

    _results[baseline_resp.session_id] = baseline_resp
    _results[rocket_resp.session_id] = rocket_resp

    baseline_ms = baseline_resp.timing.total_duration_ms
    rocket_ms = rocket_resp.timing.total_duration_ms

    speedup = baseline_ms / rocket_ms if rocket_ms > 0 else 0.0
    saved = baseline_ms - rocket_ms

    return ComparisonResponse(
        baseline=baseline_resp,
        rocket=rocket_resp,
        speedup_factor=round(speedup, 2),
        time_saved_ms=saved,
        steps_saved=baseline_resp.steps.total_steps - rocket_resp.steps.total_steps,
    )


@app.get("/api/status/{session_id}", response_model=StatusResponse)
async def get_status(session_id: str) -> StatusResponse:
    """Poll for real-time session status (frontend calls every 500ms)."""
    orch = _require_orchestrator()
    state = orch.get_session_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return StatusResponse(
        session_id=state.session_id,
        task=state.task,
        mode=state.mode,
        status=state.status,
        live_url=state.live_url,
        error=state.error,
    )


@app.get("/api/result/{session_id}", response_model=RunResponse)
async def get_result(session_id: str) -> RunResponse:
    """Retrieve a completed run result by session ID."""
    result = _results.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


@app.get("/api/templates", response_model=list[TemplateResponse])
async def list_templates() -> list[TemplateResponse]:
    """List all stored templates."""
    orch = _require_orchestrator()
    templates = await orch.list_templates()
    return [
        TemplateResponse(
            id=t.id,
            task_pattern=t.task_pattern,
            site_domain=t.site_domain,
            playwright_step_count=len(t.playwright_steps),
            parameter_names=list(t.parameter_schema.get("properties", {}).keys()),
            created_at=t.created_at,
            usage_count=t.usage_count,
        )
        for t in templates
    ]


@app.delete("/api/templates/{template_id}")
async def delete_template(template_id: str) -> dict:
    """Delete a stored template."""
    orch = _require_orchestrator()
    await orch.delete_template(template_id)
    return {"deleted": template_id}


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
