"""Tests for HandoffManager."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.browser.handoff import HandoffManager
from src.browser.cloud import CloudBrowserManager
from src.browser.rocket import PlaywrightRocket
from src.browser.agent import BrowserUseAgent
from src.models import (
    AgentResult,
    CloudBrowserSession,
    ExecutionResult,
    RocketResult,
    TemplateStep,
)


def _step(action="navigate", **kwargs) -> TemplateStep:
    defaults = {"index": 0, "type": "fixed", "action": action, "timeout_ms": 1000}
    defaults.update(kwargs)
    return TemplateStep(**defaults)


def _session() -> CloudBrowserSession:
    return CloudBrowserSession(
        browser_id="browser_123",
        cdp_url="wss://cdp.example.com/abc",
        live_url="https://live.example.com/abc",
        status="running",
    )


def _rocket_result(completed=3, total=5, aborted=False) -> RocketResult:
    return RocketResult(
        steps_completed=completed,
        total_steps=total,
        duration_seconds=0.5,
        aborted=aborted,
        abort_reason="selector not found" if aborted else None,
        current_url="https://example.com/page",
    )


def _agent_result() -> AgentResult:
    return AgentResult(
        action_names=["click_element", "input_text"],
        model_actions=[{"click": {"index": 1}}],
        model_thoughts=["thinking"],
        urls=["https://example.com"],
        total_duration_seconds=5.0,
        final_result="Task completed",
    )


@pytest.fixture
def mock_cloud():
    cloud = AsyncMock(spec=CloudBrowserManager)
    cloud.create.return_value = _session()
    cloud.stop.return_value = None
    return cloud


@pytest.fixture
def mock_rocket():
    rocket = AsyncMock(spec=PlaywrightRocket)
    rocket.execute.return_value = _rocket_result()
    return rocket


@pytest.fixture
def mock_agent():
    agent = AsyncMock(spec=BrowserUseAgent)
    agent.run.return_value = _agent_result()
    return agent


@pytest.fixture
def manager(mock_cloud, mock_rocket, mock_agent):
    return HandoffManager(
        cloud_manager=mock_cloud, rocket=mock_rocket, agent=mock_agent
    )


# --- Full handoff sequence ---


@pytest.mark.asyncio
async def test_full_handoff_with_template(manager, mock_cloud, mock_rocket, mock_agent):
    steps = [_step("navigate", value="https://example.com"), _step("click", selector="#btn", index=1)]

    result = await manager.execute("Complete the task", template_steps=steps)

    assert result.success is True
    assert result.rocket_result is not None
    assert result.agent_result is not None
    assert result.total_duration_seconds > 0
    assert result.error is None

    # Verify sequence: create → rocket → agent → stop
    mock_cloud.create.assert_called_once()
    mock_rocket.execute.assert_called_once_with("wss://cdp.example.com/abc", steps)
    mock_agent.run.assert_called_once()
    mock_cloud.stop.assert_called_once_with("browser_123")


@pytest.mark.asyncio
async def test_handoff_without_template(manager, mock_cloud, mock_rocket, mock_agent):
    """When no template steps, skip rocket and go straight to agent."""
    result = await manager.execute("Do the full task")

    assert result.success is True
    assert result.rocket_result is None
    assert result.agent_result is not None

    mock_rocket.execute.assert_not_called()
    mock_agent.run.assert_called_once()
    mock_cloud.stop.assert_called_once()


@pytest.mark.asyncio
async def test_handoff_rocket_aborts_agent_still_runs(manager, mock_cloud, mock_rocket, mock_agent):
    """If rocket aborts at step 0, agent should still run the full task."""
    mock_rocket.execute.return_value = RocketResult(
        steps_completed=0,
        total_steps=3,
        duration_seconds=0.1,
        aborted=True,
        abort_reason="connection error",
        current_url=None,
    )

    result = await manager.execute("Task", template_steps=[_step()])

    assert result.success is True
    assert result.rocket_result.aborted is True
    assert result.agent_result is not None
    mock_agent.run.assert_called_once()


@pytest.mark.asyncio
async def test_handoff_partial_rocket_gives_agent_context(manager, mock_cloud, mock_rocket, mock_agent):
    """Partial rocket progress is passed to agent."""
    partial = _rocket_result(completed=2, total=5, aborted=True)
    mock_rocket.execute.return_value = partial

    await manager.execute("Task", template_steps=[_step()])

    # Agent should receive the rocket_result
    call_args = mock_agent.run.call_args
    assert call_args.args[2] is partial  # third arg is rocket_result


# --- Browser cleanup ---


@pytest.mark.asyncio
async def test_browser_always_cleaned_up_on_success(manager, mock_cloud):
    await manager.execute("Task")
    mock_cloud.stop.assert_called_once_with("browser_123")


@pytest.mark.asyncio
async def test_browser_always_cleaned_up_on_rocket_error(mock_cloud, mock_agent):
    rocket = AsyncMock(spec=PlaywrightRocket)
    rocket.execute.side_effect = Exception("Playwright crashed")

    mgr = HandoffManager(cloud_manager=mock_cloud, rocket=rocket, agent=mock_agent)
    result = await mgr.execute("Task", template_steps=[_step()])

    assert result.success is False
    assert "Playwright crashed" in result.error
    mock_cloud.stop.assert_called_once_with("browser_123")


@pytest.mark.asyncio
async def test_browser_always_cleaned_up_on_agent_error(mock_cloud, mock_rocket):
    agent = AsyncMock(spec=BrowserUseAgent)
    agent.run.side_effect = RuntimeError("LLM error")

    mgr = HandoffManager(cloud_manager=mock_cloud, rocket=mock_rocket, agent=agent)
    result = await mgr.execute("Task", template_steps=[_step()])

    # Agent retries 3 times, then the RuntimeError is caught by execute()
    assert result.success is False
    mock_cloud.stop.assert_called_once_with("browser_123")


@pytest.mark.asyncio
async def test_browser_cleanup_failure_doesnt_crash(mock_cloud, mock_rocket, mock_agent):
    mock_cloud.stop.side_effect = Exception("Network error during cleanup")

    mgr = HandoffManager(cloud_manager=mock_cloud, rocket=mock_rocket, agent=mock_agent)
    result = await mgr.execute("Task")

    # Should still return success — cleanup failure is logged but not fatal
    assert result.success is True


# --- Agent retry logic ---


@pytest.mark.asyncio
async def test_agent_retries_on_transient_failure(mock_cloud, mock_rocket):
    agent = AsyncMock(spec=BrowserUseAgent)
    agent.run.side_effect = [
        ConnectionError("CDP dropped"),
        _agent_result(),
    ]

    mgr = HandoffManager(cloud_manager=mock_cloud, rocket=mock_rocket, agent=agent)

    with patch("src.browser.handoff.CDP_RETRY_DELAY_SECONDS", 0):
        result = await mgr.execute("Task")

    assert result.success is True
    assert agent.run.call_count == 2


@pytest.mark.asyncio
async def test_agent_exhausts_retries(mock_cloud, mock_rocket):
    agent = AsyncMock(spec=BrowserUseAgent)
    agent.run.side_effect = ConnectionError("CDP keeps dropping")

    mgr = HandoffManager(cloud_manager=mock_cloud, rocket=mock_rocket, agent=agent)

    with patch("src.browser.handoff.CDP_RETRY_DELAY_SECONDS", 0):
        result = await mgr.execute("Task")

    assert result.success is False
    assert "3 attempts" in result.error
    assert agent.run.call_count == 3


# --- Edge cases ---


@pytest.mark.asyncio
async def test_empty_template_steps_list(manager, mock_rocket, mock_agent):
    """Empty list should skip rocket, not crash."""
    result = await manager.execute("Task", template_steps=[])

    assert result.success is True
    # Empty list is falsy, so rocket is skipped
    mock_rocket.execute.assert_not_called()


@pytest.mark.asyncio
async def test_browser_creation_fails(mock_rocket, mock_agent):
    cloud = AsyncMock(spec=CloudBrowserManager)
    cloud.create.side_effect = RuntimeError("BaaS API unreachable")
    cloud.stop.return_value = None

    mgr = HandoffManager(cloud_manager=cloud, rocket=mock_rocket, agent=mock_agent)
    result = await mgr.execute("Task")

    assert result.success is False
    assert "BaaS API unreachable" in result.error
    # No browser was created, so stop should not be called
    cloud.stop.assert_not_called()


# --- Integration test (skipped by default) ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_baas_browser():
    """Connect to a REAL BaaS browser, navigate to example.com, verify page title.

    Run with: pytest tests/test_browser/test_handoff.py -m integration
    """
    import os
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.environ.get("BROWSER_USE_API_KEY")
    if not api_key or api_key.startswith("bu_xxx"):
        pytest.skip("BROWSER_USE_API_KEY not configured")

    from src.browser.cloud import CloudBrowserManager
    from src.browser.rocket import PlaywrightRocket

    cloud = CloudBrowserManager()
    rocket = PlaywrightRocket()
    session = None

    try:
        session = await cloud.create(timeout_minutes=5, enable_recording=False)
        assert session.cdp_url.startswith("wss://")

        steps = [
            TemplateStep(
                index=0,
                type="fixed",
                action="navigate",
                value="https://example.com",
                timeout_ms=10000,
            ),
            TemplateStep(
                index=1,
                type="fixed",
                action="wait",
                selector="h1",
                timeout_ms=5000,
            ),
        ]

        result = await rocket.execute(session.cdp_url, steps)
        assert result.steps_completed == 2
        assert result.aborted is False
        assert "example.com" in (result.current_url or "")

    finally:
        if session:
            await cloud.stop(session.browser_id)
