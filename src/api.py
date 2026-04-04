"""FastAPI backend for the Rocket Booster system.

The frontend operates on an async polling model:
  1. POST /api/compare → returns {baseline_session_id, rocket_session_id} immediately
  2. GET /api/status/{id} → polled every 500ms, returns phase, steps, live_url, duration
  3. Tasks run in background via asyncio.create_task
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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


def _create_session(mode: str) -> str:
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


def _update_session(sid: str, **kwargs: Any) -> None:
    s = sessions.get(sid)
    if s is None:
        return
    for k, v in kwargs.items():
        if hasattr(s, k):
            setattr(s, k, v)


def _add_step(sid: str, description: str, step_type: str, duration_ms: float | None = None) -> None:
    s = sessions.get(sid)
    if s is None:
        return
    s.steps.append(StepInfo(
        id=f"step_{len(s.steps)}",
        description=description,
        type=step_type,
        timestamp=time.time() * 1000,
        durationMs=duration_ms,
    ))
    s.current_step = description


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------


async def _run_task_background(session_id: str, task: str, mode: str) -> None:
    """Run a browser task in background, updating session state as it progresses."""
    start_ms = time.monotonic() * 1000

    try:
        _update_session(session_id, status="running", phase="agent" if mode == "baseline" else "rocket")

        # Import the pieces we need
        from src.browser.cloud import CloudBrowserManager

        api_key = os.environ.get("BROWSER_USE_API_KEY", "")
        if not api_key:
            raise RuntimeError("BROWSER_USE_API_KEY not set")

        # Step 1: Create cloud browser
        _add_step(session_id, "Creating cloud browser...", "agent")
        browser_mgr = CloudBrowserManager(api_key)
        browser_session = await browser_mgr.create()
        _update_session(session_id, live_url=browser_session.live_url)
        _add_step(session_id, "Browser ready", "agent", 1000)

        cdp_url = browser_session.cdp_url

        # Step 2: If rocket mode, check for template and run Playwright
        rocket_steps_done = 0
        if mode in ("rocket", "auto"):
            try:
                from src.matching.matcher import find_matching_template
                _add_step(session_id, "Searching for matching template...", "playwright")
                match = await find_matching_template(task)

                if match and match.similarity >= 0.75:
                    _update_session(session_id, phase="rocket")
                    _add_step(session_id, f"Template found! ({match.similarity:.0%} match)", "playwright")

                    # Run Playwright rocket
                    from src.browser.rocket import PlaywrightRocket
                    from src.models import TemplateStep

                    rocket = PlaywrightRocket(cdp_url=cdp_url)
                    steps = [TemplateStep(**s) if isinstance(s, dict) else s for s in match.steps]
                    playwright_steps = [s for s in steps[:match.handoff_index + 1]]

                    for i, step in enumerate(playwright_steps):
                        desc = step.get("description", step.get("action", f"Step {i}")) if isinstance(step, dict) else (step.description or step.action or f"Step {i}")
                        step_start = time.monotonic()
                        try:
                            await rocket.execute_step(step)
                            dur = (time.monotonic() - step_start) * 1000
                            _add_step(session_id, desc, "playwright", dur)
                            rocket_steps_done += 1
                        except Exception as e:
                            _add_step(session_id, f"Rocket aborted: {e}", "playwright")
                            break

                    # Disconnect Playwright
                    await rocket.disconnect()
                    _add_step(session_id, "Playwright disconnected, handing off to agent", "playwright")
                else:
                    _add_step(session_id, "No template match, using full agent", "agent")
            except ImportError:
                _add_step(session_id, "Matching module not available, using full agent", "agent")
            except Exception as e:
                _add_step(session_id, f"Template lookup failed: {e}", "agent")

        # Step 3: Run browser-use agent
        _update_session(session_id, phase="agent")
        _add_step(session_id, "Starting browser-use agent...", "agent")

        from browser_use import Agent, BrowserSession as BUSession

        bu_session = BUSession(cdp_url=cdp_url, keep_alive=True)

        # Use browser-use's own ChatAnthropic wrapper (has .provider attribute)
        try:
            from browser_use import ChatAnthropic as BUChatAnthropic
            llm = BUChatAnthropic(
                model="claude-sonnet-4-6",
                temperature=0,
                max_tokens=8096,
            )
        except ImportError:
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(
                model="claude-sonnet-4-6",
                temperature=0,
                max_tokens=8096,
            )

        agent_task = task
        if rocket_steps_done > 0:
            agent_task = (
                f"Continue this task: {task}\n\n"
                f"The browser has already completed {rocket_steps_done} steps via automation. "
                f"The page is currently showing the result of those actions. "
                f"Pick up from the current state and complete the remaining work."
            )

        agent = Agent(
            task=agent_task,
            llm=llm,
            browser_session=bu_session,
            max_failures=5,
            max_actions_per_step=5,
        )

        _add_step(session_id, "Agent thinking...", "agent")
        history = await agent.run()

        # Log agent steps
        for action_name in history.action_names():
            _add_step(session_id, f"Agent: {action_name}", "agent")

        # Cleanup
        try:
            await browser_mgr.stop(browser_session.browser_id)
        except Exception:
            pass

        elapsed = time.monotonic() * 1000 - start_ms
        _update_session(
            session_id,
            status="complete",
            phase="complete",
            duration_ms=elapsed,
            current_step="Done",
        )

        # If learning mode, extract template
        if mode == "learn":
            _update_session(session_id, phase="learning")
            try:
                from src.template.extractor import extract_template_from_trace
                from src.template.generator import template_to_db_format
                _add_step(session_id, "Extracting template from trace...", "agent")
                template = await extract_template_from_trace(history, task)
                _add_step(session_id, "Template extracted!", "agent")
                _update_session(session_id, phase="complete")
            except Exception as e:
                _add_step(session_id, f"Template extraction failed: {e}", "agent")
                _update_session(session_id, phase="complete")

    except Exception as e:
        elapsed = time.monotonic() * 1000 - start_ms
        logger.exception("Task failed: %s", e)
        _update_session(
            session_id,
            status="error",
            phase="error",
            duration_ms=elapsed,
            error=str(e),
            current_step=f"Error: {e}",
        )


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


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class TaskRequest(BaseModel):
    task: str = Field(..., min_length=3, max_length=2000)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/compare")
async def compare(request: TaskRequest) -> dict:
    """Start baseline + rocket runs in parallel, return session IDs immediately."""
    baseline_id = _create_session("baseline")
    rocket_id = _create_session("rocket")

    asyncio.create_task(_run_task_background(baseline_id, request.task, "baseline"))
    asyncio.create_task(_run_task_background(rocket_id, request.task, "auto"))

    return {
        "baseline_session_id": baseline_id,
        "rocket_session_id": rocket_id,
    }


@app.post("/api/run-baseline")
async def run_baseline(request: TaskRequest) -> dict:
    """Start a baseline run, return session ID immediately."""
    sid = _create_session("baseline")
    asyncio.create_task(_run_task_background(sid, request.task, "baseline"))
    return {"session_id": sid}


@app.post("/api/run-rocket")
async def run_rocket(request: TaskRequest) -> dict:
    """Start a rocket run, return session ID immediately."""
    sid = _create_session("rocket")
    asyncio.create_task(_run_task_background(sid, request.task, "rocket"))
    return {"session_id": sid}


@app.post("/api/learn")
async def learn(request: TaskRequest) -> dict:
    """Start a learning run (baseline + extract template), return session ID."""
    sid = _create_session("learn")
    asyncio.create_task(_run_task_background(sid, request.task, "learn"))
    return {"session_id": sid}


@app.get("/api/status/{session_id}")
async def get_status(session_id: str) -> SessionStatus:
    """Poll for real-time session status. Frontend calls this every 500ms."""
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
    """Delete a stored template."""
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
    return {
        "status": "ok",
        "version": "0.1.0",
        "sessions_active": len([s for s in sessions.values() if s.status == "running"]),
    }
