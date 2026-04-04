"""Orchestrates the Playwright → agent handoff sequence."""

from __future__ import annotations

import asyncio
import logging
import time

from src.models import (
    AgentResult,
    CloudBrowserSession,
    ExecutionResult,
    RocketResult,
    SessionState,
    TemplateStep,
)
from src.browser.cloud import CloudBrowserManager
from src.browser.rocket import PlaywrightRocket
from src.browser.agent import BrowserUseAgent

logger = logging.getLogger("rocket_booster.handoff")

MAX_CDP_RETRIES = 3
CDP_RETRY_DELAY_SECONDS = 2.0


class HandoffManager:
    """Orchestrates the full browser lifecycle: create → rocket → agent → cleanup.

    Enforces the CDP one-client rule by ensuring Playwright disconnects
    before the agent connects. Handles graceful degradation when the
    rocket phase fails.
    """

    def __init__(
        self,
        cloud_manager: CloudBrowserManager | None = None,
        rocket: PlaywrightRocket | None = None,
        agent: BrowserUseAgent | None = None,
    ):
        self._cloud = cloud_manager or CloudBrowserManager()
        self._rocket = rocket or PlaywrightRocket()
        self._agent = agent or BrowserUseAgent()

    async def execute(
        self,
        task: str,
        template_steps: list[TemplateStep] | None = None,
        browser_timeout_minutes: int = 120,
    ) -> ExecutionResult:
        """Run the full handoff sequence.

        1. Create a cloud browser
        2. If template_steps provided: run rocket phase, then disconnect Playwright
        3. Run agent phase against the same browser
        4. Always clean up the browser in finally

        Returns ExecutionResult with combined timing and trace data.
        """
        state = SessionState()
        start_time = time.monotonic()

        try:
            # Phase 0: Create cloud browser
            state.phase = "browser_created"
            session = await self._cloud.create(timeout_minutes=browser_timeout_minutes)
            state.browser_session = session
            cdp_url = session.cdp_url

            # Phase 1: Rocket (if we have template steps)
            if template_steps:
                state.phase = "rocket_running"
                logger.info("Starting rocket phase: %d steps", len(template_steps))
                rocket_result = await self._rocket.execute(cdp_url, template_steps)
                state.rocket_result = rocket_result
                state.phase = "rocket_done"

                logger.info(
                    "Rocket phase: %d/%d steps in %.2fs%s",
                    rocket_result.steps_completed,
                    rocket_result.total_steps,
                    rocket_result.duration_seconds,
                    f" (aborted: {rocket_result.abort_reason})" if rocket_result.aborted else "",
                )
            else:
                logger.info("No template steps — skipping rocket phase")

            # Phase 2: Agent (with retry for CDP connection issues)
            state.phase = "agent_running"
            agent_result = await self._safe_agent_connect(
                cdp_url, task, state.rocket_result
            )
            state.agent_result = agent_result
            state.phase = "agent_done"

            total_duration = time.monotonic() - start_time
            return ExecutionResult(
                success=True,
                rocket_result=state.rocket_result,
                agent_result=agent_result,
                total_duration_seconds=total_duration,
            )

        except Exception as e:
            logger.exception("Handoff failed: %s", e)
            total_duration = time.monotonic() - start_time
            return ExecutionResult(
                success=False,
                rocket_result=state.rocket_result,
                agent_result=state.agent_result,
                total_duration_seconds=total_duration,
                error=str(e),
            )

        finally:
            # Always clean up the browser to avoid leaked sessions ($0.06/hr)
            state.phase = "stopped"
            if state.browser_session:
                try:
                    await self._cloud.stop(state.browser_session.browser_id)
                except Exception as cleanup_err:
                    logger.error("Browser cleanup failed: %s", cleanup_err)

    async def _safe_agent_connect(
        self,
        cdp_url: str,
        task: str,
        rocket_result: RocketResult | None,
    ) -> AgentResult:
        """Attempt to connect the agent with retry logic for transient CDP failures."""
        last_error: Exception | None = None

        for attempt in range(MAX_CDP_RETRIES):
            try:
                return await self._agent.run(cdp_url, task, rocket_result)
            except Exception as e:
                last_error = e
                logger.warning(
                    "Agent connect attempt %d/%d failed: %s",
                    attempt + 1,
                    MAX_CDP_RETRIES,
                    e,
                )
                if attempt < MAX_CDP_RETRIES - 1:
                    await asyncio.sleep(CDP_RETRY_DELAY_SECONDS * (attempt + 1))

        raise RuntimeError(
            f"Agent failed to connect after {MAX_CDP_RETRIES} attempts. "
            f"Last error: {last_error}"
        )
