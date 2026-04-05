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
import os
import time
import uuid
import logging
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
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
    action_type: str | None = None  # "navigate", "click", "fill", "template_match", "done", etc.
    details: dict | None = None  # structured data for expandable cards


class SessionStatus(BaseModel):
    session_id: str
    status: str  # "pending", "running", "complete", "error"
    phase: str  # "idle", "rocket", "agent", "complete", "error", "learning"
    current_step: str
    steps: list[StepInfo]
    live_url: str | None = None
    duration_ms: float
    error: str | None = None
    completed_at: float | None = None
    mode_used: str | None = None  # "rocket" or "baseline_learn"
    template_match: dict | None = None  # {similarity, domain, task_pattern}
    task: str | None = None  # original task text
    result: str | None = None  # agent's final answer text
    agent_complete: bool = False  # True when agent finished (template may still be extracting)
    agent_duration_ms: float | None = None  # agent-only duration (excludes template extraction)


sessions: dict[str, SessionStatus] = {}
chat_sessions: list[str] = []  # ordered list of chat session IDs (newest first)


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
    # Mark completion time for GC
    if kwargs.get("status") in ("complete", "error"):
        s.completed_at = time.time()


def _step(
    sid: str,
    desc: str,
    stype: str,
    dur_ms: float | None = None,
    action_type: str | None = None,
    details: dict | None = None,
) -> None:
    s = sessions.get(sid)
    if s is None:
        return
    s.steps.append(StepInfo(
        id=f"step_{len(s.steps)}",
        description=desc,
        type=stype,
        timestamp=time.time() * 1000,
        durationMs=dur_ms,
        action_type=action_type,
        details=details,
    ))
    s.current_step = desc


# ---------------------------------------------------------------------------
# Session garbage collection — prune completed sessions after 5 minutes
# ---------------------------------------------------------------------------

SESSION_TTL_SECONDS = 300


async def _session_gc_loop() -> None:
    """Background task that prunes old completed/errored sessions."""
    while True:
        await asyncio.sleep(60)
        now = time.time()
        expired = [
            sid for sid, s in sessions.items()
            if s.completed_at and (now - s.completed_at) > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            del sessions[sid]
        if expired:
            logger.debug("GC pruned %d expired sessions", len(expired))


# ---------------------------------------------------------------------------
# Parameter filling — the critical bridge between templates and Playwright
# ---------------------------------------------------------------------------


def _fill_parameters(
    steps: list[dict[str, Any]],
    params: dict[str, str | None],
    handoff_index: int,
) -> list[TemplateStep]:
    """Convert DB step dicts to TemplateStep objects with parameter values filled."""
    filled: list[TemplateStep] = []
    for s in steps[: handoff_index + 1]:
        action = s.get("action")
        raw_timeout = s.get("timeout_ms", 5000)
        if action == "navigate" and raw_timeout < 10000:
            raw_timeout = 15000

        step = TemplateStep(
            index=s.get("index", len(filled)),
            type=s.get("type", "fixed"),
            action=action,
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
            timeout_ms=raw_timeout,
            on_failure=s.get("on_failure", "abort"),
        )
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
    """Run the browser-use agent on the cloud browser. Returns (history, bu_session)."""
    from browser_use import Agent, BrowserSession as BUSession

    try:
        from browser_use import ChatAnthropic as BUChat
        llm = BUChat(model="claude-sonnet-4-6", temperature=0, max_tokens=8096)
    except ImportError:
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0, max_tokens=8096)

    bu_session = BUSession(
        cdp_url=cdp_url,
        keep_alive=True,
        wait_for_network_idle_page_load_time=12.0,
    )

    agent_task = task
    if rocket_steps_done > 0:
        agent_task = (
            f"Continue this task: {task}\n\n"
            f"The browser has already completed {rocket_steps_done} steps via Playwright automation. "
            f"The page shows the result of those actions. "
            f"Pick up from the current state and complete the remaining work."
        )

    _agent_step_clock: list[float] = [time.monotonic()]  # mutable container for closure

    async def on_step(browser_state, model_output, n_steps):
        now = time.monotonic()
        elapsed_ms = (now - _agent_step_clock[0]) * 1000
        _agent_step_clock[0] = now

        actions = model_output.action if model_output and model_output.action else []
        action_names = []
        for a in actions:
            for k, v in a.model_dump(exclude_unset=True).items():
                if v is not None and k != "index":
                    action_names.append(k)
        goal = model_output.next_goal if model_output else None
        desc = goal or ", ".join(action_names) or f"Step {n_steps}"
        _step(session_id, f"Agent: {desc}", "agent", elapsed_ms)

    _step(session_id, "Agent starting...", "agent")
    agent = Agent(
        task=agent_task,
        llm=llm,
        browser_session=bu_session,
        max_failures=5,
        max_actions_per_step=5,
        register_new_step_callback=on_step,
        # Disable URL auto-detection after rocket handoff — the browser is
        # already on the right page, re-navigating wastes ~8s.
        directly_open_url=rocket_steps_done == 0,
    )
    history = await agent.run()

    return history, bu_session


def _extract_and_store_result(session_id: str, history) -> None:
    """Extract the agent's final answer text and store it on the session."""
    result_text = None
    try:
        result_text = history.final_result()
    except Exception:
        try:
            result_text = str(history.final_result) if hasattr(history, 'final_result') else None
        except Exception:
            pass
    if result_text:
        _update(session_id, result=result_text)


# ---------------------------------------------------------------------------
# LEARN flow: agent runs → extract template → store in Supabase
# ---------------------------------------------------------------------------


async def _run_learn(session_id: str, task: str) -> None:
    """Full learn flow: run agent, extract template, store in DB."""
    start_ms = time.monotonic() * 1000
    mgr = browser = None
    bu_session = None

    try:
        _update(session_id, status="running", phase="agent")
        mgr, browser, cdp_url = await _create_browser(session_id)

        history, bu_session = await _run_agent(session_id, task, cdp_url)

        # Signal agent completion immediately so frontend can stop the timer
        # and show the result. Template extraction continues in background.
        agent_elapsed = time.monotonic() * 1000 - start_ms
        agent_result_text = None
        try:
            agent_result_text = history.final_result()
        except Exception:
            try:
                agent_result_text = str(history.final_result) if hasattr(history, 'final_result') else None
            except Exception:
                pass
        _update(
            session_id,
            phase="learning",
            agent_complete=True,
            agent_duration_ms=agent_elapsed,
            result=agent_result_text,
        )
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
        if bu_session:
            try:
                await bu_session.close()
            except Exception:
                pass
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
    bu_session = None

    try:
        _update(session_id, status="running", phase="agent")
        mgr, browser, cdp_url = await _create_browser(session_id)
        _history, bu_session = await _run_agent(session_id, task, cdp_url)

        elapsed = time.monotonic() * 1000 - start_ms
        _update(session_id, status="complete", phase="complete", duration_ms=elapsed, current_step="Done")

    except Exception as e:
        elapsed = time.monotonic() * 1000 - start_ms
        logger.exception("Baseline failed: %s", e)
        _update(session_id, status="error", phase="error", duration_ms=elapsed, error=str(e), current_step=f"Error: {e}")

    finally:
        if bu_session:
            try:
                await bu_session.close()
            except Exception:
                pass
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
    bu_session = None

    try:
        _update(session_id, status="running", phase="rocket")

        _step(session_id, "Searching for matching template...", "playwright")

        from src.matching.matcher import find_matching_template
        match = await find_matching_template(task)

        if match is None:
            _step(session_id, "No matching template found. Learn this task first!", "agent")
            elapsed = time.monotonic() * 1000 - start_ms
            _update(session_id, status="error", phase="error", duration_ms=elapsed, error="No matching template. Run Learn first.")
            return

        band_label = f"{match.confidence_band} confidence" if match.needs_verification else ""
        _step(session_id, f"Template matched! {match.similarity:.0%} similarity to '{match.task_pattern}' {band_label}".strip(), "playwright")

        _step(session_id, "Extracting parameters from task...", "playwright")

        from src.template.extractor import extract_parameters
        params = await extract_parameters(task, {
            "task_pattern": match.task_pattern,
            "parameters": match.parameters,
        })
        param_summary = ", ".join(f"{k}={v}" for k, v in params.items() if v)
        _step(session_id, f"Parameters: {param_summary}", "playwright")

        filled_steps = _fill_parameters(match.steps, params, match.handoff_index)
        _step(session_id, f"Prepared {len(filled_steps)} Playwright steps", "playwright")

        mgr, browser, cdp_url = await _create_browser(session_id)

        _step(session_id, "Launching Playwright rocket...", "playwright")

        from src.browser.rocket import PlaywrightRocket
        rocket = PlaywrightRocket()
        rocket_result = await rocket.execute(cdp_url, filled_steps)

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

        _update(session_id, phase="agent")
        _step(session_id, "Handing off to agent for dynamic steps...", "agent")
        _history, bu_session = await _run_agent(session_id, task, cdp_url, rocket_result.steps_completed)

        elapsed = time.monotonic() * 1000 - start_ms
        _update(session_id, status="complete", phase="complete", duration_ms=elapsed, current_step="Done")

    except Exception as e:
        elapsed = time.monotonic() * 1000 - start_ms
        logger.exception("Rocket failed: %s", e)
        _update(session_id, status="error", phase="error", duration_ms=elapsed, error=str(e), current_step=f"Error: {e}")

    finally:
        if bu_session:
            try:
                await bu_session.close()
            except Exception:
                pass
        if mgr and browser:
            try:
                await mgr.stop(browser.browser_id)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# CHAT flow: auto-mode (rocket if template exists, baseline+learn if not)
# ---------------------------------------------------------------------------


async def _run_chat(session_id: str, task: str) -> None:
    """Auto-mode: search for template, use rocket if found, baseline+learn if not."""
    start_ms = time.monotonic() * 1000
    mgr = browser = bu_session = None

    try:
        _update(session_id, status="running", phase="rocket", task=task)
        _step(session_id, "Searching for matching template...", "playwright", action_type="template_match")

        from src.matching.matcher import find_matching_template
        match = await find_matching_template(task)

        if match and match.confidence_band in ("high", "very_high"):
            # --- ROCKET PATH ---
            _update(session_id, mode_used="rocket", template_match={
                "similarity": round(match.similarity, 3),
                "domain": match.domain,
                "task_pattern": match.task_pattern,
            })
            _step(session_id, f"Template matched! {match.similarity:.0%} similarity",
                  "playwright", action_type="template_match",
                  details={"similarity": round(match.similarity, 3), "domain": match.domain,
                           "pattern": match.task_pattern, "mode": "rocket"})

            _step(session_id, "Extracting parameters...", "playwright", action_type="agent_action")
            from src.template.extractor import extract_parameters
            params = await extract_parameters(task, {
                "task_pattern": match.task_pattern,
                "parameters": match.parameters,
            })
            param_summary = ", ".join(f"{k}={v}" for k, v in params.items() if v)
            if param_summary:
                _step(session_id, f"Parameters: {param_summary}", "playwright", action_type="agent_action")

            filled_steps = _fill_parameters(match.steps, params, match.handoff_index)
            mgr, browser, cdp_url = await _create_browser(session_id)

            _step(session_id, "Launching Playwright rocket...", "playwright", action_type="agent_action")
            from src.browser.rocket import PlaywrightRocket
            rocket = PlaywrightRocket()
            rocket_result = await rocket.execute(cdp_url, filled_steps)

            for i, timing in enumerate(rocket_result.step_timings):
                if i < len(filled_steps):
                    action = filled_steps[i].action or "step"
                    desc = filled_steps[i].description or action
                    _step(session_id, desc, "playwright", timing * 1000, action_type=action)

            if rocket_result.aborted:
                _step(session_id, f"Rocket aborted: {rocket_result.abort_reason}", "playwright")

            _update(session_id, phase="agent")
            _step(session_id, "Handing off to agent...", "agent", action_type="agent_action")
            history, bu_session = await _run_agent(session_id, task, cdp_url, rocket_result.steps_completed)

            # Extract agent's final answer
            _extract_and_store_result(session_id, history)

        else:
            # --- BASELINE + LEARN PATH ---
            _update(session_id, mode_used="baseline_learn", phase="agent")
            if match:
                _step(session_id, f"Low confidence match ({match.similarity:.0%}). Running full agent...",
                      "agent", action_type="template_match",
                      details={"similarity": round(match.similarity, 3), "mode": "baseline_learn"})
            else:
                _step(session_id, "No template found. Running full agent and learning...",
                      "agent", action_type="template_match", details={"mode": "baseline_learn"})

            mgr, browser, cdp_url = await _create_browser(session_id)
            history, bu_session = await _run_agent(session_id, task, cdp_url)

            # Extract agent's final answer
            _extract_and_store_result(session_id, history)

            # Auto-learn
            _update(session_id, phase="learning")
            _step(session_id, "Learning template from this run...", "agent", action_type="agent_action")
            try:
                from src.template.extractor import extract_template_from_trace
                from src.template.generator import template_to_db_format
                from src.db.templates import create_template
                template = await extract_template_from_trace(history, task)
                db_dict = template_to_db_format(template)
                template_id = await create_template(**db_dict)
                _step(session_id, f"Template learned! (ID: {template_id[:8]}...)", "agent", action_type="done")
            except Exception as learn_err:
                logger.warning("Auto-learn failed (non-fatal): %s", learn_err)

        elapsed = time.monotonic() * 1000 - start_ms
        _update(session_id, status="complete", phase="complete", duration_ms=elapsed, current_step="Done")

    except Exception as e:
        elapsed = time.monotonic() * 1000 - start_ms
        logger.exception("Chat failed: %s", e)
        _update(session_id, status="error", phase="error", duration_ms=elapsed, error=str(e), current_step=f"Error: {e}")

    finally:
        if bu_session:
            try:
                await bu_session.close()
            except Exception:
                pass
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


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_session_gc_loop())


class TaskRequest(BaseModel):
    task: str = Field(..., min_length=3, max_length=2000)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/chat")
async def chat(request: TaskRequest) -> dict:
    """Start a chat session: auto-selects rocket or baseline+learn."""
    sid = _create_session()
    _update(sid, task=request.task)
    chat_sessions.insert(0, sid)
    if len(chat_sessions) > 50:
        chat_sessions.pop()
    asyncio.create_task(_run_chat(sid, request.task))
    return {"session_id": sid}


@app.get("/api/chat/sessions")
async def list_chat_sessions() -> list[dict]:
    """List recent chat sessions for sidebar history."""
    result = []
    for sid in chat_sessions[:20]:
        s = sessions.get(sid)
        if s is None:
            continue
        result.append({
            "session_id": s.session_id,
            "task": s.task or "",
            "status": s.status,
            "mode_used": s.mode_used,
            "duration_ms": s.duration_ms,
        })
    return result


@app.post("/api/learn")
async def learn(request: TaskRequest) -> dict:
    """Learn a task: run agent, extract template, store for future rockets."""
    sid = _create_session()
    asyncio.create_task(_run_learn(sid, request.task))
    return {"session_id": sid}


@app.post("/api/search-template")
async def search_template(request: TaskRequest) -> dict:
    """Search for a matching template WITHOUT starting a run."""
    try:
        from src.matching.matcher import find_matching_template
        match = await find_matching_template(request.task)
        if match:
            return {
                "found": True,
                "template_id": match.template_id,
                "task_pattern": match.task_pattern,
                "similarity": round(match.similarity, 3),
                "confidence": round(match.confidence, 3),
                "confidence_band": match.confidence_band,
                "domain": match.domain,
                "action_type": match.action_type,
                "playwright_steps": match.handoff_index + 1,
                "total_steps": len(match.steps),
                "needs_verification": match.needs_verification,
            }
        return {"found": False}
    except Exception as e:
        err_type = type(e).__name__
        logger.warning("Template search failed (%s): %s", err_type, e)
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
    sid = _create_session()
    asyncio.create_task(_run_baseline(sid, request.task))
    return {"session_id": sid}


@app.post("/api/run-rocket")
async def run_rocket_endpoint(request: TaskRequest) -> dict:
    sid = _create_session()
    asyncio.create_task(_run_rocket(sid, request.task))
    return {"session_id": sid}


@app.get("/api/status/{session_id}")
async def get_status(session_id: str) -> SessionStatus:
    """Poll for real-time session status. Frontend calls every 500ms."""
    s = sessions.get(session_id)
    if s is None:
        return SessionStatus(
            session_id=session_id,
            status="not_found",
            phase="idle",
            current_step="",
            steps=[],
            duration_ms=0,
        )
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
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
    return {"deleted": template_id}


@app.get("/api/health")
async def health() -> dict:
    active = len([s for s in sessions.values() if s.status == "running"])
    return {"status": "ok", "version": "0.1.0", "sessions_active": active}
