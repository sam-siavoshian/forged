"""FastAPI backend for the Forge system.

Three flows:
  LEARN: Agent runs task → extract template → store in Supabase
  RACE:  Baseline (full agent) vs Forge (Playwright + agent handoff)
  RUN:   Single execution (auto/baseline/forge mode)

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

from src import config
from src.browser.agent_handoff import build_agent_handoff_prompt
from src.models import RocketResult, TemplateStep

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



async def _session_gc_loop() -> None:
    """Background task that prunes old completed/errored sessions."""
    while True:
        await asyncio.sleep(60)
        now = time.time()
        expired = [
            sid for sid, s in sessions.items()
            if s.completed_at and (now - s.completed_at) > config.SESSION_TTL_SECONDS
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


def _get_dynamic_step_descriptions(
    steps: list[dict[str, Any]],
    handoff_index: int,
) -> list[str]:
    """Extract descriptions of DYNAMIC steps after the handoff point.

    These tell the agent what work remains after Playwright finishes
    (e.g. 'scroll to History section', 'extract creator name').
    """
    descs = []
    for s in steps[handoff_index + 1:]:
        if s.get("type") == "dynamic" and s.get("description"):
            descs.append(s["description"])
    return descs


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


async def _create_browser_silent():
    """Create a BaaS cloud browser WITHOUT recording UI steps.

    Used for speculative pre-creation where browser spins up in parallel
    with template search. The caller flushes timing into the session
    timeline after awaiting, preserving step ordering.

    Returns (manager, browser_session, cdp_url, creation_ms).
    """
    from src.browser.cloud import CloudBrowserManager

    api_key = os.environ.get("BROWSER_USE_API_KEY", "")
    if not api_key:
        raise RuntimeError("BROWSER_USE_API_KEY not set")

    t0 = time.monotonic()
    mgr = CloudBrowserManager(api_key)
    browser = await mgr.create()
    creation_ms = (time.monotonic() - t0) * 1000
    return mgr, browser, browser.cdp_url, creation_ms


# ---------------------------------------------------------------------------
# Shared: run browser-use agent
# ---------------------------------------------------------------------------


async def _run_agent(
    session_id: str,
    task: str,
    cdp_url: str,
    rocket_result: RocketResult | None = None,
    step_summary: str | None = None,
    remaining_dynamic_steps: list[str] | None = None,
):
    """Run the browser-use agent on the cloud browser. Returns (history, bu_session).

    Always releases the CDP session in ``finally`` so browser-use does not try to
    reconnect after the cloud browser is stopped (503/404 on WebSocket).
    """
    from browser_use import Agent, BrowserSession as BUSession

    from src.browser.session_cleanup import release_browser_session

    try:
        from browser_use import ChatAnthropic as BUChat
        llm = BUChat(model=config.MODEL_AGENT, temperature=0, max_tokens=config.AGENT_MAX_TOKENS)
    except ImportError:
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model=config.MODEL_AGENT, temperature=0, max_tokens=config.AGENT_MAX_TOKENS)

    bu_session = BUSession(
        cdp_url=cdp_url,
        keep_alive=True,
        wait_for_network_idle_page_load_time=config.AGENT_NETWORK_IDLE_TIMEOUT,
    )

    agent_task, rocket_handoff, _handoff_branch = build_agent_handoff_prompt(
        task, rocket_result, step_summary=step_summary,
        remaining_dynamic_steps=remaining_dynamic_steps,
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
        max_failures=config.AGENT_MAX_FAILURES,
        max_actions_per_step=config.AGENT_MAX_ACTIONS_PER_STEP,
        register_new_step_callback=on_step,
        # Disable URL auto-detection after rocket handoff — the browser is
        # already on the right page, re-navigating wastes ~8s.
        directly_open_url=not rocket_handoff,
    )
    try:
        history = await agent.run()
        return history, bu_session
    finally:
        await release_browser_session(bu_session)


async def _extract_answer_from_page(task: str, page_text: str) -> str:
    """Use Claude Haiku to extract the answer from raw page text.

    This replaces the full browser-use agent loop (~35s) with a single
    fast LLM call (~1-2s) when Playwright has already navigated to the
    right page and all steps are complete.
    """
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()
    response = await client.messages.create(
        model=config.MODEL_ANSWER_EXTRACTOR,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": (
                f"Task: {task}\n\n"
                f"Page content (visible text from the browser):\n"
                f"{page_text[:config.LLM_INPUT_TEXT_CAP]}\n\n"
                f"Extract the answer to the task from the page content above. "
                f"Be concise and direct. Return only the requested information."
            ),
        }],
    )
    return response.content[0].text


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


def _build_step_summary(filled_steps: list, rocket_result) -> str:
    """Build a human-readable summary of what the rocket phase did.

    This is passed to the agent so it knows which steps completed,
    which were skipped, and which failed.
    """
    lines = []
    for i, step in enumerate(filled_steps):
        desc = step.description or step.action or f"Step {i}"
        if i < len(rocket_result.step_outcomes):
            outcome, reason = rocket_result.step_outcomes[i]
            if outcome == "completed":
                lines.append(f"  [DONE] Step {i}: {desc}")
            elif outcome == "completed_after_retry":
                lines.append(f"  [DONE after retry] Step {i}: {desc}")
            elif outcome in ("skipped", "fallback_failed"):
                lines.append(f"  [SKIPPED] Step {i}: {desc} — {reason}")
            elif outcome == "aborted":
                lines.append(f"  [FAILED] Step {i}: {desc} — {reason}")
        else:
            lines.append(f"  [NOT REACHED] Step {i}: {desc}")
    return "\n".join(lines) if lines else ""


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

        # Persist trace
        try:
            from src.db.traces import record_execution_trace
            await record_execution_trace(
                template_id=None,
                task_description=task,
                mode="baseline",
                steps_executed=[s.model_dump() for s in sessions[session_id].steps],
                total_duration_ms=int(elapsed),
                success=True,
            )
        except Exception:
            logger.warning("Failed to record baseline trace (non-fatal)")

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
    """Run task using Forge: Playwright for known steps, agent for the rest."""
    start_ms = time.monotonic() * 1000
    mgr = browser = None
    bu_session = None
    browser_task: asyncio.Task | None = None

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

        # Start browser creation in parallel with parameter extraction.
        # Browser boot takes 2-4s; param extraction takes 1-2s. Overlapping
        # them saves 1-3s on every forge run.
        browser_task = asyncio.create_task(_create_browser(session_id))

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

        # Await browser (likely already done by now)
        mgr, browser, cdp_url = await browser_task

        _step(session_id, "Running forged path...", "playwright")

        from src.browser.rocket import PlaywrightRocket
        rocket = PlaywrightRocket()
        rocket_result = await rocket.execute(cdp_url, filled_steps)

        for i, timing in enumerate(rocket_result.step_timings):
            if i < len(filled_steps):
                desc = filled_steps[i].description or filled_steps[i].action or f"Step {i}"
                _step(session_id, desc, "playwright", timing * 1000)

        if rocket_result.aborted:
            _step(session_id, f"Forge aborted at step {rocket_result.steps_completed}: {rocket_result.abort_reason}", "playwright")
        else:
            _step(
                session_id,
                f"Forge complete! {rocket_result.steps_completed} steps in {rocket_result.duration_seconds:.1f}s",
                "playwright",
            )

        # FAST PATH: skip agent if all steps done, no dynamic steps remain,
        # and page content is available for direct extraction.
        dynamic_descs = _get_dynamic_step_descriptions(match.steps, match.handoff_index)
        if (not rocket_result.aborted
                and rocket_result.page_content
                and rocket_result.steps_completed >= len(filled_steps)
                and not dynamic_descs):
            _step(session_id, "All steps complete. Extracting answer directly...",
                  "playwright", action_type="extract")
            try:
                answer = await _extract_answer_from_page(task, rocket_result.page_content)
                _update(session_id, result=answer, agent_complete=True)
                _step(session_id, "Answer extracted (no agent needed)",
                      "playwright", action_type="done")
            except Exception as extract_err:
                logger.warning("Fast extraction failed in _run_rocket, falling back: %s", extract_err)
                _update(session_id, phase="agent")
                _step(session_id, "Handing off to agent...", "agent")
                dynamic_descs = _get_dynamic_step_descriptions(match.steps, match.handoff_index)
                _history, bu_session = await _run_agent(session_id, task, cdp_url, rocket_result, remaining_dynamic_steps=dynamic_descs)
        else:
            _update(session_id, phase="agent")
            _step(session_id, "Handing off to agent for dynamic steps...", "agent")
            dynamic_descs = _get_dynamic_step_descriptions(match.steps, match.handoff_index)
            _history, bu_session = await _run_agent(session_id, task, cdp_url, rocket_result, remaining_dynamic_steps=dynamic_descs)

        elapsed = time.monotonic() * 1000 - start_ms
        _update(session_id, status="complete", phase="complete", duration_ms=elapsed, current_step="Done")

        # Persist trace
        try:
            from src.db.traces import record_execution_trace
            await record_execution_trace(
                template_id=match.template_id if match else None,
                task_description=task,
                mode="rocket",
                steps_executed=[s.model_dump() for s in sessions[session_id].steps],
                total_duration_ms=int(elapsed),
                success=True,
                rocket_steps_count=rocket_result.steps_completed if rocket_result else 0,
                rocket_duration_ms=int(rocket_result.duration_seconds * 1000) if rocket_result else None,
            )
        except Exception:
            logger.warning("Failed to record rocket trace (non-fatal)")

    except Exception as e:
        elapsed = time.monotonic() * 1000 - start_ms
        logger.exception("Forge failed: %s", e)
        _update(session_id, status="error", phase="error", duration_ms=elapsed, error=str(e), current_step=f"Error: {e}")

    finally:
        # If browser_task was created but never awaited (error before await),
        # await it now so we can clean up the browser we started.
        if browser_task and not browser_task.done():
            try:
                mgr, browser, cdp_url = await browser_task
            except Exception:
                pass
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
    browser_future: asyncio.Task | None = None

    try:
        _update(session_id, status="running", phase="rocket", task=task)

        # Speculative browser pre-creation: launch browser in parallel with
        # template search. The browser is needed in BOTH paths (rocket and
        # baseline), so there is zero waste. Uses _create_browser_silent()
        # to avoid interleaving UI steps with template search progress.
        browser_future = asyncio.create_task(_create_browser_silent())

        _step(session_id, "Searching for matching template...", "playwright", action_type="template_match")

        from src.matching.matcher import find_matching_template
        match = await find_matching_template(task)

        # Any TemplateMatch from find_matching_template is usable: medium band
        # already passed LLM verification in the matcher.
        if match:
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

            # Step filter: determine which steps are relevant to this specific task
            from src.matching.step_filter import filter_steps
            filter_result = await filter_steps(
                task=task,
                task_pattern=match.task_pattern,
                steps=match.steps,
                parameters=params,
                handoff_index=match.handoff_index,
            )

            if filter_result.skip_indices:
                _step(
                    session_id,
                    f"Adapted: executing {len(filter_result.execute_indices)} of "
                    f"{match.handoff_index + 1} steps "
                    f"(skipping {len(filter_result.skip_indices)})",
                    "playwright",
                    action_type="agent_action",
                    details={"skipped": filter_result.skip_indices, "reason": filter_result.reasoning},
                )

            # Filter steps to only those the LLM said to execute
            filtered_steps = [
                s for idx, s in enumerate(match.steps)
                if idx in filter_result.execute_indices and idx <= match.handoff_index
            ]
            effective_handoff = len(filtered_steps) - 1 if filtered_steps else 0

            filled_steps = _fill_parameters(filtered_steps, params, effective_handoff)

            # Await speculative browser (likely already done by now — started
            # before template search, and search + params + filter take ~2s)
            mgr, browser, cdp_url, browser_creation_ms = await browser_future
            browser_future = None  # Mark as consumed
            _update(session_id, live_url=browser.live_url)
            _step(session_id, f"Browser ready ({browser_creation_ms:.0f}ms, pre-created)", "agent", browser_creation_ms)

            _step(session_id, "Running forged path...", "playwright", action_type="agent_action")
            from src.browser.rocket import PlaywrightRocket
            rocket = PlaywrightRocket()
            rocket_result = await rocket.execute(cdp_url, filled_steps)

            for i, timing in enumerate(rocket_result.step_timings):
                if i < len(filled_steps):
                    action = filled_steps[i].action or "step"
                    desc = filled_steps[i].description or action
                    # Include outcome info if step was skipped or retried
                    if i < len(rocket_result.step_outcomes):
                        outcome, reason = rocket_result.step_outcomes[i]
                        if outcome == "skipped":
                            desc = f"[SKIPPED] {desc}: {reason}"
                        elif outcome == "completed_after_retry":
                            desc = f"[RETRIED] {desc}"
                    _step(session_id, desc, "playwright", timing * 1000, action_type=action)

            if rocket_result.aborted:
                _step(session_id, f"Forge aborted: {rocket_result.abort_reason}", "playwright")

            # Build step summary for smarter agent handoff
            step_summary = _build_step_summary(filled_steps, rocket_result)

            # ── Extraction tier system (fastest → slowest) ──
            #
            # TIER 0: Direct DOM extraction via stored CSS selectors (~200ms, zero LLM)
            #         Requires: extraction_selectors on template + high confidence + no abort
            # TIER 1: Haiku extraction from captured page content (~1-2s, one Haiku call)
            #         Requires: all steps completed + page_content captured
            # TIER 2: Full agent handoff (~5-15s, multiple Sonnet calls)
            #         Fallback for everything else

            extraction_done = False

            # TIER 0: Direct DOM extraction — zero LLM calls
            if (match.extraction_selectors
                    and match.similarity >= config.DIRECT_EXTRACT_MIN_SIMILARITY
                    and not rocket_result.aborted
                    and rocket_result.steps_completed > 0):
                _step(session_id, "Attempting direct DOM extraction...", "playwright", action_type="extract")
                from src.browser.direct_extract import direct_extract
                extracted = await direct_extract(cdp_url, match.extraction_selectors)
                if extracted:
                    result_text = "\n".join(f"**{k}**: {v}" for k, v in extracted.items())
                    _update(session_id, result=result_text, agent_complete=True,
                            agent_duration_ms=(time.monotonic() * 1000 - start_ms))
                    _step(session_id, f"Extracted {len(extracted)} fields directly (no LLM needed)",
                          "playwright", 200, action_type="done")
                    extraction_done = True
                else:
                    logger.info("Direct extraction returned None, trying next tier")

            # TIER 1: Haiku extraction from page content (~1-2s)
            if (not extraction_done
                    and not rocket_result.aborted
                    and rocket_result.page_content
                    and rocket_result.steps_completed >= len(filled_steps)):
                _step(session_id, "Extracting answer from page content...",
                      "playwright", action_type="extract")
                try:
                    answer = await _extract_answer_from_page(task, rocket_result.page_content)
                    _update(session_id, result=answer, agent_complete=True,
                            agent_duration_ms=(time.monotonic() * 1000 - start_ms))
                    _step(session_id, "Answer extracted (no agent needed)",
                          "playwright", action_type="done")
                    extraction_done = True
                except Exception as extract_err:
                    logger.warning("Haiku extraction failed: %s", extract_err)

            # TIER 2: Full agent handoff (fallback)
            if not extraction_done:
                _update(session_id, phase="agent")
                _step(session_id, "Handing off to agent...", "agent", action_type="agent_action")
                dynamic_descs = _get_dynamic_step_descriptions(match.steps, match.handoff_index)
                history, bu_session = await _run_agent(session_id, task, cdp_url, rocket_result, step_summary=step_summary, remaining_dynamic_steps=dynamic_descs)
                _extract_and_store_result(session_id, history)

        else:
            # --- BASELINE + LEARN PATH ---
            _update(session_id, mode_used="baseline_learn", phase="agent")
            _step(session_id, "No template found. Running full agent and learning...",
                  "agent", action_type="template_match", details={"mode": "baseline_learn"})

            # Await speculative browser (started before template search)
            mgr, browser, cdp_url, browser_creation_ms = await browser_future
            browser_future = None  # Mark as consumed
            _update(session_id, live_url=browser.live_url)
            _step(session_id, f"Browser ready ({browser_creation_ms:.0f}ms, pre-created)", "agent", browser_creation_ms)
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
        # Clean up speculative browser if it was never consumed
        if browser_future is not None and not browser_future.done():
            browser_future.cancel()
            try:
                await browser_future
            except (asyncio.CancelledError, Exception):
                pass
        elif browser_future is not None and browser_future.done():
            # Browser was created but never awaited (error before consumption)
            try:
                _mgr, _browser, _cdp, _ms = browser_future.result()
                await _mgr.stop(_browser.browser_id)
            except Exception:
                pass
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


app = FastAPI(title="Forge API", version="0.1.0")

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
    """Start a chat session: auto-selects forge or baseline+learn."""
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
    """Learn a task: run agent, extract template, store for future forging."""
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
    """Start baseline + forge runs in parallel. Returns session IDs immediately."""
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


@app.get("/api/race-history")
async def race_history() -> list[dict]:
    """Return recent race results (baseline + forge pairs) from execution_traces."""
    try:
        from supabase import create_client
        client = create_client(
            os.environ.get("SUPABASE_URL", ""),
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
        )
        result = client.table("execution_traces").select(
            "id, task_description, mode, total_duration_ms, rocket_duration_ms, rocket_steps_count, success, created_at"
        ).order("created_at", desc=True).limit(40).execute()

        # Group by task_description — pair baseline + rocket runs
        from collections import defaultdict
        groups: dict[str, dict] = defaultdict(lambda: {"baseline": None, "rocket": None})
        for row in result.data:
            task = row["task_description"]
            mode = row["mode"]
            if groups[task][mode] is None:
                groups[task][mode] = row

        pairs = []
        for task, g in groups.items():
            if g["baseline"] and g["rocket"]:
                b_ms = g["baseline"]["total_duration_ms"]
                r_ms = g["rocket"]["total_duration_ms"]
                speedup = round(b_ms / r_ms, 2) if r_ms > 0 else 0
                pairs.append({
                    "task": task,
                    "baseline_duration_ms": b_ms,
                    "rocket_duration_ms": r_ms,
                    "speedup": speedup,
                    "rocket_steps": g["rocket"].get("rocket_steps_count"),
                    "created_at": g["rocket"].get("created_at", g["baseline"].get("created_at", "")),
                })

        pairs.sort(key=lambda x: x["created_at"], reverse=True)
        return pairs[:20]
    except Exception as e:
        logger.warning("Failed to fetch race history: %s", e)
        return []


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
