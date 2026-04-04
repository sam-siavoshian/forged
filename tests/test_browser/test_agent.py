"""Tests for BrowserUseAgent."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.browser.agent import BrowserUseAgent, _build_task_description, run_agent_phase
from src.models import AgentResult, RocketResult


# --- _build_task_description ---


def test_build_task_no_rocket():
    result = _build_task_description("Book a flight", None)
    assert result == "Book a flight"


def test_build_task_rocket_zero_steps():
    rocket = RocketResult(
        steps_completed=0,
        total_steps=3,
        duration_seconds=0.1,
        aborted=True,
        abort_reason="connection failed",
        current_url=None,
    )
    result = _build_task_description("Book a flight", rocket)
    assert result == "Book a flight"  # No context added when 0 steps done


def test_build_task_rocket_partial():
    rocket = RocketResult(
        steps_completed=3,
        total_steps=5,
        duration_seconds=0.5,
        aborted=True,
        abort_reason="selector not found",
        current_url="https://flights.example.com/results",
    )
    result = _build_task_description("Book a flight SFO to JFK", rocket)
    assert "already on the page: https://flights.example.com/results" in result
    assert "first 3 steps" in result
    assert "Book a flight SFO to JFK" in result


def test_build_task_rocket_complete():
    rocket = RocketResult(
        steps_completed=5,
        total_steps=5,
        duration_seconds=1.0,
        aborted=False,
        current_url="https://flights.example.com/checkout",
    )
    result = _build_task_description("Book a flight", rocket)
    assert "first 5 steps" in result
    assert "checkout" in result


# --- BrowserUseAgent.run() ---


@pytest.mark.asyncio
async def test_agent_run_success():
    mock_history = MagicMock()
    mock_history.action_names.return_value = ["click_element", "input_text"]
    mock_history.model_actions.return_value = [{"click_element": {"index": 1}}, {"input_text": {"text": "hi"}}]
    mock_history.model_thoughts.return_value = ["I see a button", "I need to type"]
    mock_history.urls.return_value = ["https://example.com"]

    mock_agent_instance = AsyncMock()
    mock_agent_instance.run.return_value = "Task completed"
    mock_agent_instance.history = mock_history

    with patch("src.browser.agent.Agent") as mock_agent_cls, \
         patch("src.browser.agent.ChatAnthropic"), \
         patch("src.browser.agent.BrowserSession"):

        mock_agent_cls.return_value = mock_agent_instance

        agent = BrowserUseAgent()
        result = await agent.run("wss://fake", "Do something")

    assert isinstance(result, AgentResult)
    assert result.action_names == ["click_element", "input_text"]
    assert result.final_result == "Task completed"
    assert result.total_duration_seconds > 0


@pytest.mark.asyncio
async def test_agent_run_with_rocket_context():
    mock_history = MagicMock()
    mock_history.action_names.return_value = ["click_element"]
    mock_history.model_actions.return_value = [{}]
    mock_history.model_thoughts.return_value = ["done"]
    mock_history.urls.return_value = ["https://example.com"]

    mock_agent_instance = AsyncMock()
    mock_agent_instance.run.return_value = "Done"
    mock_agent_instance.history = mock_history

    rocket_result = RocketResult(
        steps_completed=2,
        total_steps=3,
        duration_seconds=0.3,
        aborted=True,
        current_url="https://example.com/step2",
    )

    with patch("src.browser.agent.Agent") as mock_agent_cls, \
         patch("src.browser.agent.ChatAnthropic"), \
         patch("src.browser.agent.BrowserSession"):

        mock_agent_cls.return_value = mock_agent_instance

        agent = BrowserUseAgent()
        result = await agent.run("wss://fake", "Complete the task", rocket_result)

    # Verify the task was augmented with rocket context
    call_kwargs = mock_agent_cls.call_args.kwargs
    assert "already on the page" in call_kwargs["task"]
    assert "first 2 steps" in call_kwargs["task"]


@pytest.mark.asyncio
async def test_agent_run_with_custom_tools():
    mock_history = MagicMock()
    mock_history.action_names.return_value = []
    mock_history.model_actions.return_value = []
    mock_history.model_thoughts.return_value = []
    mock_history.urls.return_value = []

    mock_agent_instance = AsyncMock()
    mock_agent_instance.run.return_value = None
    mock_agent_instance.history = mock_history

    custom_tools = MagicMock()

    with patch("src.browser.agent.Agent") as mock_agent_cls, \
         patch("src.browser.agent.ChatAnthropic"), \
         patch("src.browser.agent.BrowserSession"):

        mock_agent_cls.return_value = mock_agent_instance

        agent = BrowserUseAgent()
        await agent.run("wss://fake", "Task", custom_tools=custom_tools)

    call_kwargs = mock_agent_cls.call_args.kwargs
    assert call_kwargs["tools"] is custom_tools


@pytest.mark.asyncio
async def test_agent_run_exception_propagates():
    with patch("src.browser.agent.Agent") as mock_agent_cls, \
         patch("src.browser.agent.ChatAnthropic"), \
         patch("src.browser.agent.BrowserSession"):

        mock_agent_cls.return_value.run.side_effect = RuntimeError("LLM quota exceeded")

        agent = BrowserUseAgent()
        with pytest.raises(RuntimeError, match="LLM quota exceeded"):
            await agent.run("wss://fake", "Task")


# --- Convenience function ---


@pytest.mark.asyncio
async def test_run_agent_phase_convenience():
    with patch.object(BrowserUseAgent, "run") as mock_run:
        mock_run.return_value = AgentResult(
            action_names=["click"],
            total_duration_seconds=1.0,
            final_result="Done",
        )

        result = await run_agent_phase("wss://fake", "Task")

    assert result.final_result == "Done"
    mock_run.assert_called_once()
