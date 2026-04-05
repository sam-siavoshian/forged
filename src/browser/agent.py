"""Browser-use agent wrapper with CDP connection for the agent phase."""

from __future__ import annotations

import logging
import time

from browser_use import Agent, BrowserSession
from langchain_anthropic import ChatAnthropic

from src import config

from src.browser.agent_handoff import build_agent_handoff_prompt
from src.browser.session_cleanup import release_browser_session
from src.models import AgentResult, RocketResult

logger = logging.getLogger("rocket_booster.agent")


class BrowserUseAgent:
    """Wraps the browser-use Agent with CDP connection to a cloud browser."""

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0,
        max_tokens: int | None = None,
        max_failures: int | None = None,
        max_actions_per_step: int | None = None,
    ):
        self._model = model or config.MODEL_AGENT
        self._temperature = temperature
        self._max_tokens = max_tokens or config.AGENT_MAX_TOKENS
        self._max_failures = max_failures or config.AGENT_MAX_FAILURES
        self._max_actions_per_step = max_actions_per_step or config.AGENT_MAX_ACTIONS_PER_STEP

    async def run(
        self,
        cdp_url: str,
        task: str,
        rocket_result: RocketResult | None = None,
        custom_tools: object | None = None,
    ) -> AgentResult:
        """Connect to the cloud browser and run the agent to completion.

        Args:
            cdp_url: Chrome DevTools Protocol WebSocket URL.
            task: The task description for the agent.
            rocket_result: Optional result from a prior rocket phase.
            custom_tools: Optional tools object (e.g., for memory lookup).

        Returns:
            AgentResult with trace data.
        """
        agent_task, rocket_handoff, _branch = build_agent_handoff_prompt(
            task, rocket_result
        )

        llm = ChatAnthropic(
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )

        session = BrowserSession(
            cdp_url=cdp_url,
            keep_alive=True,
        )

        agent_kwargs: dict = {
            "task": agent_task,
            "llm": llm,
            "browser_session": session,
            "max_failures": self._max_failures,
            "max_actions_per_step": self._max_actions_per_step,
            "directly_open_url": not rocket_handoff,
        }
        if custom_tools is not None:
            agent_kwargs["tools"] = custom_tools

        agent = Agent(**agent_kwargs)

        logger.info("Agent starting: %s", agent_task[:120])
        start_time = time.monotonic()

        try:
            result = await agent.run()
        finally:
            await release_browser_session(session)

        duration = time.monotonic() - start_time

        history = agent.history
        agent_result = AgentResult(
            action_names=history.action_names(),
            model_actions=history.model_actions(),
            model_thoughts=history.model_thoughts(),
            urls=history.urls(),
            total_duration_seconds=duration,
            final_result=result,
        )

        logger.info(
            "Agent finished: %d actions in %.2fs",
            len(agent_result.action_names),
            duration,
        )
        return agent_result


async def run_agent_phase(
    cdp_url: str,
    task: str,
    rocket_result: RocketResult | None = None,
) -> AgentResult:
    """Module-level convenience function."""
    agent = BrowserUseAgent()
    return await agent.run(cdp_url, task, rocket_result)
