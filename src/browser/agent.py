"""Browser-use agent wrapper with CDP connection for the agent phase."""

from __future__ import annotations

import logging
import time

from browser_use import Agent, BrowserSession
from langchain_anthropic import ChatAnthropic

from src.models import AgentResult, RocketResult

logger = logging.getLogger("rocket_booster.agent")


def _build_task_description(
    task: str, rocket_result: RocketResult | None
) -> str:
    """Build a contextual task description for the agent.

    If the rocket phase completed some steps, tell the agent where it is
    and what's been done so it doesn't redo work.
    """
    if rocket_result and rocket_result.steps_completed > 0:
        return (
            f"You are already on the page: {rocket_result.current_url}. "
            f"The first {rocket_result.steps_completed} steps of the task have "
            f"already been completed via automation. "
            f"Complete the remaining task: {task}"
        )
    return task


class BrowserUseAgent:
    """Wraps the browser-use Agent with CDP connection to a cloud browser."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        temperature: float = 0,
        max_tokens: int = 8096,
        max_failures: int = 5,
        max_actions_per_step: int = 5,
    ):
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_failures = max_failures
        self._max_actions_per_step = max_actions_per_step

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
        agent_task = _build_task_description(task, rocket_result)

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
        }
        if custom_tools is not None:
            agent_kwargs["tools"] = custom_tools

        agent = Agent(**agent_kwargs)

        logger.info("Agent starting: %s", agent_task[:120])
        start_time = time.monotonic()

        result = await agent.run()
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
