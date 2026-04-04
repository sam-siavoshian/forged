"""Tests for the RocketOrchestrator."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.orchestrator import RocketOrchestrator, ExecutionMode
from src.models import OrchestratorResult, OrchestratorSessionState, Template


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.list_templates = AsyncMock(return_value=[])
    db.store_template = AsyncMock()
    db.delete_template = AsyncMock()
    return db


@pytest.fixture
def mock_anthropic():
    return AsyncMock()


@pytest.fixture
def orchestrator(mock_db, mock_anthropic):
    return RocketOrchestrator(
        supabase_client=mock_db,
        anthropic_client=mock_anthropic,
        browser_use_api_key="test-key",
        model="test-model",
    )


def _make_mock_history(*, action_count: int = 5, done: bool = True):
    """Create a mock browser-use AgentHistory."""
    history = MagicMock()
    history.action_names.return_value = [f"action_{i}" for i in range(action_count)]
    history.is_done.return_value = done
    history.final_result.return_value = "Task completed"
    history.errors.return_value = []
    return history


def _make_template(*, score: float = 0.9) -> Template:
    return Template(
        id="tmpl-1",
        task_pattern="Search for {item} on Amazon",
        site_domain="amazon.com",
        playwright_steps=[{"action": "navigate", "url": "https://amazon.com"}],
        parameter_schema={"properties": {"item": {"type": "string"}}},
        similarity_score=score,
        created_at="2026-04-04",
    )


# ---------------------------------------------------------------------------
# Baseline mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_baseline_mode(orchestrator):
    """Baseline mode creates browser, runs agent, returns result."""
    mock_history = _make_mock_history(action_count=8)
    mock_browser_session = MagicMock()
    mock_browser_session.live_url = "https://live.example.com"
    mock_browser_session.cdp_url = "ws://cdp.example.com"

    with (
        patch("src.orchestrator.CloudBrowserManager") as MockBrowserMgr,
        patch("src.orchestrator.RocketOrchestrator._run_baseline") as mock_run,
    ):
        mock_run.return_value = OrchestratorResult(
            session_id="test-session",
            task="Search for mouse on Amazon",
            mode="baseline",
            success=True,
            total_duration_ms=5000,
            browser_creation_ms=1000,
            agent_duration_ms=4000,
            playwright_steps=0,
            agent_steps=8,
            total_steps=8,
            model="test-model",
            live_url="https://live.example.com",
        )

        result = await orchestrator.run_task(
            "Search for mouse on Amazon", ExecutionMode.BASELINE
        )

    assert result.mode == "baseline"
    assert result.success is True
    assert result.playwright_steps == 0
    assert result.agent_steps == 8
    assert result.total_steps == 8
    assert result.browser_creation_ms > 0
    assert result.total_duration_ms > 0


# ---------------------------------------------------------------------------
# Rocket mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rocket_mode_with_template(orchestrator):
    """Rocket mode uses template when found."""
    template = _make_template()

    with patch.object(
        orchestrator, "_find_template", return_value=(template, 50)
    ), patch.object(orchestrator, "_run_rocket") as mock_rocket:
        mock_rocket.return_value = OrchestratorResult(
            session_id="test-session",
            task="Search for keyboard on Amazon",
            mode="rocket",
            success=True,
            total_duration_ms=3000,
            browser_creation_ms=1000,
            template_lookup_ms=50,
            parameter_extraction_ms=200,
            playwright_duration_ms=800,
            agent_duration_ms=1000,
            playwright_steps=3,
            agent_steps=2,
            total_steps=5,
            model="test-model",
        )

        result = await orchestrator.run_task(
            "Search for keyboard on Amazon", ExecutionMode.ROCKET
        )

    assert result.mode == "rocket"
    assert result.success is True
    assert result.playwright_steps == 3
    assert result.template_lookup_ms == 50


@pytest.mark.asyncio
async def test_rocket_mode_no_template_errors(orchestrator):
    """Rocket mode with no template match returns error result (not exception)."""
    with patch.object(orchestrator, "_find_template", return_value=(None, 30)):
        result = await orchestrator.run_task(
            "Do something with no template", ExecutionMode.ROCKET
        )

    # The orchestrator catches ValueError internally and returns error result
    assert result.success is False
    assert result.error is not None
    assert "no template found" in result.error.lower()


# ---------------------------------------------------------------------------
# AUTO mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_mode_with_match(orchestrator):
    """AUTO mode uses rocket path when template is found."""
    template = _make_template(score=0.92)

    with patch.object(
        orchestrator, "_find_template", return_value=(template, 40)
    ), patch.object(orchestrator, "_run_rocket") as mock_rocket:
        mock_rocket.return_value = OrchestratorResult(
            session_id="s1",
            task="test",
            mode="rocket",
            success=True,
            total_duration_ms=2000,
            browser_creation_ms=500,
            playwright_steps=4,
            agent_steps=1,
            total_steps=5,
            model="test-model",
        )

        result = await orchestrator.run_task("test task", ExecutionMode.AUTO)

    assert result.mode == "rocket"
    mock_rocket.assert_called_once()


@pytest.mark.asyncio
async def test_auto_mode_no_match(orchestrator):
    """AUTO mode falls back to baseline when no template."""
    with patch.object(
        orchestrator, "_find_template", return_value=(None, 30)
    ), patch.object(orchestrator, "_run_baseline") as mock_baseline:
        mock_baseline.return_value = OrchestratorResult(
            session_id="s2",
            task="test",
            mode="baseline",
            success=True,
            total_duration_ms=5000,
            browser_creation_ms=1000,
            playwright_steps=0,
            agent_steps=10,
            total_steps=10,
            model="test-model",
        )

        result = await orchestrator.run_task("unknown task", ExecutionMode.AUTO)

    assert result.mode == "baseline"
    mock_baseline.assert_called_once()


# ---------------------------------------------------------------------------
# LEARN mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_learn_mode_extracts_template(orchestrator):
    """LEARN mode runs baseline then extracts template on success."""
    with patch.object(orchestrator, "_run_baseline") as mock_baseline, patch.object(
        orchestrator, "_learn_from_result"
    ) as mock_learn:
        mock_baseline.return_value = OrchestratorResult(
            session_id="s3",
            task="learn this",
            mode="baseline",
            success=True,
            total_duration_ms=6000,
            browser_creation_ms=1000,
            playwright_steps=0,
            agent_steps=12,
            total_steps=12,
            model="test-model",
            trace=MagicMock(),
        )
        mock_learn.return_value = _make_template()

        result = await orchestrator.run_task("learn this", ExecutionMode.LEARN)

    assert result.success is True
    mock_learn.assert_called_once()


@pytest.mark.asyncio
async def test_learn_mode_skips_extraction_on_failure(orchestrator):
    """LEARN mode skips template extraction when baseline fails."""
    with patch.object(orchestrator, "_run_baseline") as mock_baseline, patch.object(
        orchestrator, "_learn_from_result"
    ) as mock_learn:
        mock_baseline.return_value = OrchestratorResult(
            session_id="s4",
            task="fail task",
            mode="baseline",
            success=False,
            error="Agent failed",
            total_duration_ms=3000,
            browser_creation_ms=1000,
            playwright_steps=0,
            agent_steps=5,
            total_steps=5,
            model="test-model",
        )

        result = await orchestrator.run_task("fail task", ExecutionMode.LEARN)

    assert result.success is False
    mock_learn.assert_not_called()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_returns_result_not_exception(orchestrator):
    """Orchestrator catches exceptions and returns error result."""
    with patch.object(
        orchestrator, "_run_baseline", side_effect=RuntimeError("Browser exploded")
    ):
        result = await orchestrator.run_task("test", ExecutionMode.BASELINE)

    assert result.success is False
    assert "Browser exploded" in result.error
    assert result.total_duration_ms == 0


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_state_created(orchestrator):
    """run_task creates a session state entry."""
    with patch.object(orchestrator, "_run_baseline") as mock_baseline:
        mock_baseline.return_value = OrchestratorResult(
            session_id="test-id",
            task="t",
            mode="baseline",
            success=True,
            total_duration_ms=100,
            browser_creation_ms=50,
            playwright_steps=0,
            agent_steps=1,
            total_steps=1,
            model="test-model",
        )

        await orchestrator.run_task("test task", ExecutionMode.BASELINE)

    # There should be exactly one session (the uuid-generated one)
    assert len(orchestrator._sessions) == 1
    session = list(orchestrator._sessions.values())[0]
    assert session.task == "test task"
    assert session.mode == "baseline"


def test_get_session_state_not_found(orchestrator):
    """get_session_state returns None for unknown session."""
    assert orchestrator.get_session_state("nonexistent") is None


# ---------------------------------------------------------------------------
# Template lookup threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_template_below_threshold(orchestrator):
    """Templates below similarity threshold are ignored."""
    low_score_template = _make_template(score=0.5)

    mock_matcher = AsyncMock()
    mock_matcher.find_best_match = AsyncMock(return_value=low_score_template)
    orchestrator._matcher = mock_matcher

    template, ms = await orchestrator._find_template("some task")
    assert template is None


@pytest.mark.asyncio
async def test_find_template_above_threshold(orchestrator):
    """Templates above similarity threshold are returned."""
    good_template = _make_template(score=0.9)

    mock_matcher = AsyncMock()
    mock_matcher.find_best_match = AsyncMock(return_value=good_template)
    orchestrator._matcher = mock_matcher

    template, ms = await orchestrator._find_template("some task")
    assert template is not None
    assert template.similarity_score == 0.9


# ---------------------------------------------------------------------------
# to_response conversion
# ---------------------------------------------------------------------------


def test_orchestrator_result_to_response():
    """OrchestratorResult converts to RunResponse correctly."""
    result = OrchestratorResult(
        session_id="s1",
        task="test",
        mode="baseline",
        success=True,
        total_duration_ms=5000,
        browser_creation_ms=1000,
        agent_duration_ms=4000,
        playwright_steps=0,
        agent_steps=10,
        total_steps=10,
        model="claude-sonnet-4-20250514",
        output="Done",
    )

    resp = result.to_response()
    assert resp.session_id == "s1"
    assert resp.timing.total_duration_ms == 5000
    assert resp.timing.browser_creation_ms == 1000
    assert resp.steps.agent_steps == 10
    assert resp.output == "Done"
    assert resp.model == "claude-sonnet-4-20250514"
