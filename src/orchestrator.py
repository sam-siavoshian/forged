"""RocketOrchestrator — central coordinator for the Rocket Booster system."""

from __future__ import annotations

import time
import uuid
import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Defensive imports — subsystems may not be built yet
# ---------------------------------------------------------------------------

try:
    from src.browser.manager import CloudBrowserManager
except ImportError:
    CloudBrowserManager = None  # type: ignore[assignment,misc]

try:
    from src.browser.rocket import PlaywrightRocket
except ImportError:
    PlaywrightRocket = None  # type: ignore[assignment,misc]

try:
    from src.template.extractor import TemplateExtractor
except ImportError:
    TemplateExtractor = None  # type: ignore[assignment,misc]

try:
    from src.matching.matcher import TemplateMatcher
except ImportError:
    TemplateMatcher = None  # type: ignore[assignment,misc]

try:
    from src.db.client import SupabaseClient
except ImportError:
    SupabaseClient = None  # type: ignore[assignment,misc]

from src.models import (
    OrchestratorResult,
    OrchestratorSessionState,
    Template,
)


# ---------------------------------------------------------------------------
# Execution mode enum
# ---------------------------------------------------------------------------


class ExecutionMode(str, Enum):
    AUTO = "auto"
    BASELINE = "baseline"
    ROCKET = "rocket"
    LEARN = "learn"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _ms() -> int:
    """Current time in monotonic milliseconds."""
    return int(time.monotonic() * 1000)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class RocketOrchestrator:
    """
    Central coordinator for the Rocket Booster system.

    Routes tasks to the correct execution path (baseline vs rocket),
    manages browser session lifecycle, collects timing data at every
    phase boundary, triggers template extraction after learning runs,
    and provides session state for real-time frontend updates.
    """

    SIMILARITY_THRESHOLD = 0.78
    MAX_AGENT_STEPS = 25
    STEP_TIMEOUT_S = 30

    def __init__(
        self,
        supabase_client: Any,
        anthropic_client: Any,
        browser_use_api_key: str,
        *,
        model: str = "claude-sonnet-4-20250514",
    ):
        self._db = supabase_client
        self._anthropic = anthropic_client
        self._browser_use_api_key = browser_use_api_key
        self._model = model

        self._matcher = TemplateMatcher(supabase_client) if TemplateMatcher else None
        self._extractor = TemplateExtractor(anthropic_client) if TemplateExtractor else None
        self._sessions: dict[str, OrchestratorSessionState] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_task(
        self,
        task: str,
        mode: ExecutionMode = ExecutionMode.AUTO,
    ) -> OrchestratorResult:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = OrchestratorSessionState(
            session_id=session_id,
            task=task,
            mode=mode.value,
            status="starting",
        )

        try:
            if mode == ExecutionMode.BASELINE:
                return await self._run_baseline(session_id, task)

            if mode == ExecutionMode.ROCKET:
                template, lookup_ms = await self._find_template(task)
                if template is None:
                    raise ValueError(
                        f"ROCKET mode requested but no template found for: {task!r}"
                    )
                return await self._run_rocket(session_id, task, template, lookup_ms)

            if mode == ExecutionMode.LEARN:
                result = await self._run_baseline(session_id, task)
                if result.success:
                    await self._learn_from_result(session_id, task, result)
                return result

            # AUTO: check DB first
            template, lookup_ms = await self._find_template(task)
            if template is not None:
                logger.info(
                    "Template match found (score=%.3f), using rocket mode",
                    template.similarity_score,
                )
                return await self._run_rocket(session_id, task, template, lookup_ms)
            else:
                logger.info("No template match, falling back to baseline")
                return await self._run_baseline(session_id, task)

        except Exception as exc:
            logger.exception("Task execution failed: %s", exc)
            self._update_session(session_id, status="error", error=str(exc))
            return OrchestratorResult(
                session_id=session_id,
                task=task,
                mode=mode.value,
                success=False,
                error=str(exc),
                total_duration_ms=0,
                browser_creation_ms=0,
                playwright_steps=0,
                agent_steps=0,
                total_steps=0,
                model=self._model,
            )

    def get_session_state(self, session_id: str) -> OrchestratorSessionState | None:
        return self._sessions.get(session_id)

    # ------------------------------------------------------------------
    # Template lookup
    # ------------------------------------------------------------------

    async def _find_template(self, task: str) -> tuple[Template | None, int]:
        if self._matcher is None:
            return None, 0

        t0 = _ms()
        match = await self._matcher.find_best_match(task)
        lookup_ms = _ms() - t0

        if match is None:
            return None, lookup_ms

        if match.similarity_score < self.SIMILARITY_THRESHOLD:
            logger.info(
                "Best match score %.3f below threshold %.2f, ignoring",
                match.similarity_score,
                self.SIMILARITY_THRESHOLD,
            )
            return None, lookup_ms

        return match, lookup_ms

    # ------------------------------------------------------------------
    # Baseline execution
    # ------------------------------------------------------------------

    async def _run_baseline(
        self,
        session_id: str,
        task: str,
    ) -> OrchestratorResult:
        self._update_session(session_id, status="creating_browser")

        t_total = _ms()
        t0 = _ms()

        if CloudBrowserManager is None:
            raise RuntimeError("CloudBrowserManager not available — src.browser not built yet")

        browser_mgr = CloudBrowserManager(self._browser_use_api_key)
        browser_session = await browser_mgr.create_session()
        browser_creation_ms = _ms() - t0

        self._update_session(
            session_id,
            status="running_agent",
            live_url=browser_session.live_url,
        )

        t0 = _ms()
        from browser_use import Agent, BrowserSession as BUSession
        from langchain_anthropic import ChatAnthropic

        bu_session = BUSession(
            cdp_url=browser_session.cdp_url,
            keep_alive=True,
        )
        llm = ChatAnthropic(
            model=self._model,
            temperature=0,
            max_tokens=8096,
        )
        agent = Agent(
            task=task,
            llm=llm,
            browser_session=bu_session,
            max_failures=5,
            max_actions_per_step=5,
        )
        history = await agent.run()
        agent_duration_ms = _ms() - t0

        total_duration_ms = _ms() - t_total
        self._update_session(session_id, status="complete")

        return OrchestratorResult(
            session_id=session_id,
            task=task,
            mode="baseline",
            total_duration_ms=total_duration_ms,
            template_lookup_ms=None,
            parameter_extraction_ms=None,
            browser_creation_ms=browser_creation_ms,
            playwright_duration_ms=None,
            agent_duration_ms=agent_duration_ms,
            template_extraction_ms=None,
            playwright_steps=0,
            agent_steps=len(history.action_names()),
            total_steps=len(history.action_names()),
            success=history.is_done(),
            output=history.final_result(),
            error=str(history.errors()[-1]) if history.errors() else None,
            live_url=browser_session.live_url,
            model=self._model,
            llm_cost_usd=None,
            trace=history,
        )

    # ------------------------------------------------------------------
    # Rocket execution
    # ------------------------------------------------------------------

    async def _run_rocket(
        self,
        session_id: str,
        task: str,
        template: Template,
        lookup_ms: int,
    ) -> OrchestratorResult:
        self._update_session(session_id, status="extracting_params")

        t_total = _ms()

        # Step 1: Parameter extraction via LLM
        t0 = _ms()
        if self._extractor is None:
            raise RuntimeError("TemplateExtractor not available — src.template not built yet")

        params = await self._extractor.extract_parameters(task, template)
        parameter_extraction_ms = _ms() - t0
        logger.info("Extracted parameters: %s", params)

        # Step 2: Create cloud browser
        self._update_session(session_id, status="creating_browser")
        t0 = _ms()

        if CloudBrowserManager is None:
            raise RuntimeError("CloudBrowserManager not available — src.browser not built yet")

        browser_mgr = CloudBrowserManager(self._browser_use_api_key)
        browser_session = await browser_mgr.create_session()
        browser_creation_ms = _ms() - t0

        self._update_session(
            session_id,
            status="running_playwright",
            live_url=browser_session.live_url,
        )

        # Step 3: Playwright rocket (deterministic steps)
        t0 = _ms()

        if PlaywrightRocket is None:
            raise RuntimeError("PlaywrightRocket not available — src.browser not built yet")

        rocket = PlaywrightRocket(
            cdp_url=browser_session.cdp_url,
            step_timeout_s=self.STEP_TIMEOUT_S,
        )
        playwright_error = None
        try:
            rocket_result = await rocket.execute(
                steps=template.playwright_steps,
                params=params,
            )
            playwright_duration_ms = _ms() - t0
            playwright_steps = rocket_result.steps_completed
        except Exception as exc:
            playwright_duration_ms = _ms() - t0
            playwright_steps = 0
            playwright_error = str(exc)
            logger.warning("Playwright rocket failed (%s), falling back to full agent", exc)

        # Step 4: Agent handoff
        self._update_session(session_id, status="running_agent")
        t0 = _ms()

        if playwright_error is None and playwright_steps > 0:
            agent_task = (
                f"Continue this task: {task}\n\n"
                f"The browser has already completed {playwright_steps} steps. "
                f"The page is currently showing the result of those actions. "
                f"Pick up from the current state and complete the remaining work."
            )
        else:
            agent_task = task

        from browser_use import Agent, BrowserSession as BUSession
        from langchain_anthropic import ChatAnthropic

        bu_session = BUSession(
            cdp_url=browser_session.cdp_url,
            keep_alive=True,
        )
        llm = ChatAnthropic(
            model=self._model,
            temperature=0,
            max_tokens=8096,
        )
        agent = Agent(
            task=agent_task,
            llm=llm,
            browser_session=bu_session,
            max_failures=5,
            max_actions_per_step=5,
        )
        history = await agent.run()
        agent_duration_ms = _ms() - t0

        total_duration_ms = _ms() - t_total
        self._update_session(session_id, status="complete")

        return OrchestratorResult(
            session_id=session_id,
            task=task,
            mode="rocket",
            total_duration_ms=total_duration_ms,
            template_lookup_ms=lookup_ms,
            parameter_extraction_ms=parameter_extraction_ms,
            browser_creation_ms=browser_creation_ms,
            playwright_duration_ms=playwright_duration_ms,
            agent_duration_ms=agent_duration_ms,
            template_extraction_ms=None,
            playwright_steps=playwright_steps,
            agent_steps=len(history.action_names()),
            total_steps=playwright_steps + len(history.action_names()),
            success=history.is_done(),
            output=history.final_result(),
            error=history.errors()[-1] if history.errors() else playwright_error,
            live_url=browser_session.live_url,
            model=self._model,
            llm_cost_usd=None,
            trace=history,
        )

    # ------------------------------------------------------------------
    # Template learning
    # ------------------------------------------------------------------

    async def _learn_from_result(
        self,
        session_id: str,
        task: str,
        result: OrchestratorResult,
    ) -> Template | None:
        if result.trace is None:
            logger.warning("No trace available for template extraction")
            return None

        if self._extractor is None:
            logger.warning("TemplateExtractor not available — cannot learn")
            return None

        self._update_session(session_id, status="extracting_template")

        t0 = _ms()
        template = await self._extractor.extract_template(
            task=task,
            trace=result.trace,
        )
        extraction_ms = _ms() - t0

        if template is None:
            logger.warning("Template extraction returned None")
            return None

        await self._db.store_template(template)
        logger.info(
            "Stored template %s (%d playwright steps, extraction took %d ms)",
            template.id,
            len(template.playwright_steps),
            extraction_ms,
        )

        result.template_extraction_ms = extraction_ms
        self._update_session(session_id, status="complete")

        return template

    # ------------------------------------------------------------------
    # Session state management
    # ------------------------------------------------------------------

    def _update_session(self, session_id: str, **kwargs: Any) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        for key, value in kwargs.items():
            setattr(session, key, value)

    # ------------------------------------------------------------------
    # Public: list templates (delegates to DB client)
    # ------------------------------------------------------------------

    async def list_templates(self) -> list[Template]:
        if self._db is None:
            return []
        return await self._db.list_templates()

    async def delete_template(self, template_id: str) -> None:
        if self._db is None:
            return
        await self._db.delete_template(template_id)
