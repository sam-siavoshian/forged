"""FastAPI backend for the Rocket Booster system.

Three flows:
  LEARN: Agent runs task → extract template → store in Supabase
  RACE:  Baseline (full agent) vs Rocket (Playwright + agent handoff)
  RUN:   Single execution (auto/baseline/rocket mode)

Frontend polling model:
  POST /api/learn or /api/compare → returns session IDs immediately
  GET /api/status/{id} → polled every 500ms for real-time progress
"""

from __future__ import annotations

import asyncio
import copy
import os
import time
import uuid
import logging
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.models import TemplateStep

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session state — what the frontend polls
# ---------------------------------------------------------------------------


class StepInfo(BaseModel):
    id: str
    description: str
    type: str  # "playwright" or "agent"
    timestamp: float
    durationMs: float | None = None


class SessionStatus(BaseModel):
    session_id: str
    status: str  # "pending", "running", "complete", "error"
    phase: str  # "idle", "rocket", "agent", "complete", "error", "learning"
    current_step: str
    steps: list[StepInfo]
    live_url: str | None = None
    duration_ms: float
    error: str | None = None


sessions: dict[str, SessionStatus] = {}


def _create_session() -> str:
    sid = str(uuid.uuid4())
    sessions[sid] = SessionStatus(
        session_id=sid,
        status="pending",
        phase="idle",
        current_step="Initializing...",
        steps=[],
        duration_ms=0,
    )
    return sid


def _update(sid: str, **kwargs: Any) -> None:
    s = sessions.get(sid)
    if s is None:
        return
    for k, v in kwargs.items():
        if hasattr(s, k):
            setattr(s, k, v)


def _step(sid: str, desc: str, stype: str, dur_ms: float | None = None) -> None:
    s = sessions.get(sid)
    if s is None:
        return
    s.steps.append(StepInfo(
        id=f"step_{len(s.steps)}",
        description=desc,
        type=stype,
        timestamp=time.time() * 1000,
        durationMs=dur_ms,
    ))
    s.current_step = desc


# ---------------------------------------------------------------------------
# Parameter filling — the critical bridge between templates and Playwright
# ---------------------------------------------------------------------------


def _fill_parameters(
    steps: list[dict[str, Any]],
    params: dict[str, str | None],
    handoff_index: int,
) -> list[TemplateStep]:
    """Convert DB step dicts to TemplateStep objects with parameter values filled.

    For parameterized steps (e.g., type="parameterized", param="query"),
    the extracted parameter value replaces the step's `value` field.
    Only returns steps up to and including handoff_index (the Playwright portion).
    """
    filled: list[TemplateStep] = []
    for s in steps[: handoff_index + 1]:
        step = TemplateStep(
            index=s.get("index", len(filled)),
            type=s.get("type", "fixed"),
            action=s.get("action"),
            url=s.get("url"),
            selector=s.get("selector"),
            fallback_selectors=s.get("fallback_selectors", []),
            param=s.get("param"),
            value=s.get("value"),
            key=s.get("key"),
            direction=s.get("direction"),
            amount=s.get("amount"),
            description=s.get("description"),
            agent_needed=s.get("agent_needed", False),
            timeout_ms=s.get("timeout_ms", 5000),
            on_failure=s.get("on_failure", "abort"),
        )
        # THE CRITICAL PIECE: fill parameterized values from extracted params
        if step.param and step.param in params and params[step.param] is not None:
            step.value = params[step.param]
        filled.append(step)
    return filled


# ---------------------------------------------------------------------------
# Shared: create cloud browser
# ---------------------------------------------------------------------------


async def _create_browser(session_id: str):
    """Create a BaaS cloud browser and return (manager, session, cdp_url)."""
    from src.browser.cloud import CloudBrowserManager

    api_key = os.environ.get("BROWSER_USE_API_KEY", "")
    if not api_key:
        raise RuntimeError("BROWSER_USE_API_KEY not set")

    _step(session_id, "Creating cloud browser...", "agent")
    mgr = CloudBrowserManager(api_key)
    browser = await mgr.create()
    _update(session_id, live_url=browser.live_url)
    _step(session_id, "Browser ready", "agent", 500)
    return mgr, browser, browser.cdp_url


# ---------------------------------------------------------------------------
# Shared: run browser-use agent
# ---------------------------------------------------------------------------


async def _run_agent(session_id: str, task: str, cdp_url: str, rocket_steps_done: int = 0):
    """Run the browser-use agent on the cloud browser. Returns history object."""
    from browser_use import Agent, BrowserSession as BUSession

    try:
        from browser_use import ChatAnthropic as BUChat
        llm = BUChat(model="claude-sonnet-4-6", temperature=0, max_tokens=8096)
    except ImportError:
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0, max_tokens=8096)

    bu_session = BUSession(cdp_url=cdp_url, keep_alive=True)

    agent_task = task
    if rocket_steps_done > 0:
        agent_task = (
            f"Continue this task: {task}\n\n"
            f"The browser has already completed {rocket_steps_done} steps via Playwright automation. "
            f"The page shows the result of those actions. "
            f"Pick up from the current state and complete the remaining work."
        )

    _step(session_id, "Agent starting...", "agent")
    agent = Agent(
        task=agent_task,
        llm=llm,
        browser_session=bu_session,
        max_failures=5,
        max_actions_per_step=5,
    )
    history = await agent.run()

    # Log agent actions as steps
    for name in history.action_names():
        _step(session_id, f"Agent: {name}", "agent")

    return history


# ---------------------------------------------------------------------------
# LEARN flow: agent runs → extract template → store in Supabase
# ---------------------------------------------------------------------------


async def _run_learn(session_id: str, task: str) -> None:
    """Full learn flow: run agent, extract template, store in DB."""
    start_ms = time.monotonic() * 1000
    mgr = browser = None

    try:
        _update(session_id, status="running", phase="agent")
        mgr, browser, cdp_url = await _create_browser(session_id)

        # Run agent (full, no rocket)
        history = await _run_agent(session_id, task, cdp_url)

        # Extract template
        _update(session_id, phase="learning")
        _step(session_id, "Extracting template from agent trace...", "agent")

        from src.template.extractor import extract_template_from_trace
        from src.template.generator import template_to_db_format
        from src.db.templates import create_template

        template = await extract_template_from_trace(history, task)

        fixed_count = len([s for s in template.steps if s.classification != "DYNAMIC"])
        total_count = len(template.steps)
        _step(
            session_id,
            f"Learned {total_count} steps: {fixed_count} replayable by Playwright, "
            f"handoff at step {template.handoff_index}",
            "agent",
        )

        # Store in Supabase
        _step(session_id, "Storing template in Supabase...", "agent")
        db_dict = template_to_db_format(template)
        template_id = await create_template(**db_dict)
        _step(session_id, f"Template saved! ID: {template_id[:8]}...", "agent")

        elapsed = time.monotonic() * 1000 - start_ms
        _update(session_id, status="complete", phase="complete", duration_ms=elapsed, current_step="Done! Template ready for racing.")

    except Exception as e:
        elapsed = time.monotonic() * 1000 - start_ms
        logger.exception("Learn failed: %s", e)
        _update(session_id, status="error", phase="error", duration_ms=elapsed, error=str(e), current_step=f"Error: {e}")

    finally:
        if mgr and browser:
            try:
                await mgr.stop(browser.browser_id)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# BASELINE flow: full agent, no template, no rocket
# ---------------------------------------------------------------------------


async def _run_baseline(session_id: str, task: str) -> None:
    """Run task with full agent only (for comparison)."""
    start_ms = time.monotonic() * 1000
    mgr = browser = None

    try:
        _update(session_id, status="running", phase="agent")
        mgr, browser, cdp_url = await _create_browser(session_id)
        await _run_agent(session_id, task, cdp_url)

        elapsed = time.monotonic() * 1000 - start_ms
        _update(session_id, status="complete", phase="complete", duration_ms=elapsed, current_step="Done")

    except Exception as e:
        elapsed = time.monotonic() * 1000 - start_ms
        logger.exception("Baseline failed: %s", e)
        _update(session_id, status="error", phase="error", duration_ms=elapsed, error=str(e), current_step=f"Error: {e}")

    finally:
        if mgr and browser:
            try:
                await mgr.stop(browser.browser_id)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# ROCKET flow: template match → Playwright → agent handoff
# ---------------------------------------------------------------------------


async def _run_rocket(session_id: str, task: str) -> None:
    """Run task using rocket booster: Playwright for known steps, agent for the rest."""
    start_ms = time.monotonic() * 1000
    mgr = browser = None

    try:
        _update(session_id, status="running", phase="rocket")

        # Step 1: Find matching template
        _step(session_id, "Searching for matching template...", "playwright")

        from src.matching.matcher import find_matching_template
        match = await find_matching_template(task)

        if match is None or match.similarity < 0.75:
            _step(session_id, "No matching template found. Learn this task first!", "agent")
            elapsed = time.monotonic() * 1000 - start_ms
            _update(session_id, status="error", phase="error", duration_ms=elapsed, error="No matching template. Run Learn first.")
            return

        _step(session_id, f"Template matched! {match.similarity:.0%} similarity to '{match.task_pattern}'", "playwright")

        # Step 2: Extract parameters
        _step(session_id, "Extracting parameters from task...", "playwright")

        from src.template.extractor import extract_parameters
        params = await extract_parameters(task, {
            "task_pattern": match.task_pattern,
            "parameters": match.parameters,
        })
        param_summary = ", ".join(f"{k}={v}" for k, v in params.items() if v)
        _step(session_id, f"Parameters: {param_summary}", "playwright")

        # Step 3: Fill parameters into template steps
        filled_steps = _fill_parameters(match.steps, params, match.handoff_index)
        _step(session_id, f"Prepared {len(filled_steps)} Playwright steps", "playwright")

        # Step 4: Create browser
        mgr, browser, cdp_url = await _create_browser(session_id)

        # Step 5: ROCKET — Playwright executes known steps
        _step(session_id, "Launching Playwright rocket...", "playwright")

        from src.browser.rocket import PlaywrightRocket
        rocket = PlaywrightRocket()
        rocket_result = await rocket.execute(cdp_url, filled_steps)

        # Log individual step timings
        for i, timing in enumerate(rocket_result.step_timings):
            if i < len(filled_steps):
                desc = filled_steps[i].description or filled_steps[i].action or f"Step {i}"
                _step(session_id, desc, "playwright", timing * 1000)

        if rocket_result.aborted:
            _step(session_id, f"Rocket aborted at step {rocket_result.steps_completed}: {rocket_result.abort_reason}", "playwright")
        else:
            _step(
                session_id,
                f"Rocket complete! {rocket_result.steps_completed} steps in {rocket_result.duration_seconds:.1f}s",
                "playwright",
            )

        # Step 6: Agent handoff for remaining dynamic steps
        _update(session_id, phase="agent")
        _step(session_id, "Handing off to agent for dynamic steps...", "agent")
        await _run_agent(session_id, task, cdp_url, rocket_result.steps_completed)

        elapsed = time.monotonic() * 1000 - start_ms
        _update(session_id, status="complete", phase="complete", duration_ms=elapsed, current_step="Done")

    except Exception as e:
        elapsed = time.monotonic() * 1000 - start_ms
        logger.exception("Rocket failed: %s", e)
        _update(session_id, status="error", phase="error", duration_ms=elapsed, error=str(e), current_step=f"Error: {e}")

    finally:
        if mgr and browser:
            try:
                await mgr.stop(browser.browser_id)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


app = FastAPI(title="Rocket Booster API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskRequest(BaseModel):
    task: str = Field(..., min_length=3, max_length=2000)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/learn")
async def learn(request: TaskRequest) -> dict:
    """Learn a task: run agent, extract template, store for future rockets."""
    sid = _create_session()
    asyncio.create_task(_run_learn(sid, request.task))
    return {"session_id": sid}


@app.post("/api/search-template")
async def search_template(request: TaskRequest) -> dict:
    """Search for a matching template WITHOUT starting a run.

    Returns match info so the frontend can show the search phase
    before deciding to race.
    """
    try:
        from src.matching.matcher import find_matching_template
        match = await find_matching_template(request.task)
        if match and match.similarity >= 0.75:
            return {
                "found": True,
                "template_id": match.template_id,
                "task_pattern": match.task_pattern,
                "similarity": round(match.similarity, 3),
                "confidence": round(match.confidence, 3),
                "domain": match.domain,
                "action_type": match.action_type,
                "playwright_steps": match.handoff_index + 1,
                "total_steps": len(match.steps),
            }
        return {"found": False}
    except Exception as e:
        logger.warning("Template search failed: %s", e)
        return {"found": False, "error": str(e)}


@app.post("/api/compare")
async def compare(request: TaskRequest) -> dict:
    """Start baseline + rocket runs in parallel. Returns session IDs immediately."""
    baseline_id = _create_session()
    rocket_id = _create_session()
    asyncio.create_task(_run_baseline(baseline_id, request.task))
    asyncio.create_task(_run_rocket(rocket_id, request.task))
    return {"baseline_session_id": baseline_id, "rocket_session_id": rocket_id}


@app.post("/api/run-baseline")
async def run_baseline_endpoint(request: TaskRequest) -> dict:
    """Start a baseline run (full agent, no template)."""
    sid = _create_session()
    asyncio.create_task(_run_baseline(sid, request.task))
    return {"session_id": sid}


@app.post("/api/run-rocket")
async def run_rocket_endpoint(request: TaskRequest) -> dict:
    """Start a rocket run (Playwright + agent). Requires a matching template."""
    sid = _create_session()
    asyncio.create_task(_run_rocket(sid, request.task))
    return {"session_id": sid}


@app.get("/api/status/{session_id}")
async def get_status(session_id: str) -> SessionStatus:
    """Poll for real-time session status. Frontend calls every 500ms."""
    s = sessions.get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


@app.get("/api/templates")
async def list_templates() -> list[dict]:
    """List all stored templates from Supabase."""
    try:
        from supabase import create_client
        client = create_client(
            os.environ.get("SUPABASE_URL", ""),
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
        )
        result = client.table("task_templates").select(
            "id, domain, task_pattern, confidence, handoff_index, steps, parameters, success_count, created_at"
        ).order("created_at", desc=True).limit(20).execute()

        return [
            {
                "id": t["id"],
                "domain": t["domain"],
                "pattern": t["task_pattern"],
                "confidence": t["confidence"],
                "steps": [
                    {
                        "id": f"s{i}",
                        "description": s.get("description", s.get("action", f"Step {i}")),
                        "type": s.get("type", "fixed"),
                        "handoff": i == t["handoff_index"],
                    }
                    for i, s in enumerate(t.get("steps", []))
                ],
                "created_at": t.get("created_at", ""),
                "uses": t.get("success_count", 0),
            }
            for t in result.data
        ]
    except Exception as e:
        logger.warning("Failed to list templates: %s", e)
        return []


@app.delete("/api/templates/{template_id}")
async def delete_template(template_id: str) -> dict:
    try:
        from supabase import create_client
        client = create_client(
            os.environ.get("SUPABASE_URL", ""),
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
        )
        client.table("task_templates").delete().eq("id", template_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"deleted": template_id}


@app.get("/api/health")
async def health() -> dict:
    active = len([s for s in sessions.values() if s.status == "running"])
    return {"status": "ok", "version": "0.1.0", "sessions_active": active}
