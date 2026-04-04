"""Tests for the FastAPI backend."""

from __future__ import annotations

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
from fastapi.testclient import TestClient

from src.api import app, _results
from src.orchestrator import RocketOrchestrator, ExecutionMode
from src.models import (
    OrchestratorResult,
    OrchestratorSessionState,
    Template,
    RunResponse,
    TimingBreakdown,
    StepCounts,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_orchestrator():
    """Replace lifespan so TestClient doesn't create a real orchestrator."""
    import src.api as api_module

    mock_orch = AsyncMock(spec=RocketOrchestrator)
    mock_orch._sessions = {}
    mock_orch.get_session_state = MagicMock(return_value=None)
    mock_orch.list_templates = AsyncMock(return_value=[])
    mock_orch.delete_template = AsyncMock()

    @asynccontextmanager
    async def _mock_lifespan(_app):
        api_module.orchestrator = mock_orch
        yield
        api_module.orchestrator = None

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _mock_lifespan
    _results.clear()
    yield mock_orch
    app.router.lifespan_context = original_lifespan
    api_module.orchestrator = None
    _results.clear()


def _make_result(
    *,
    mode: str = "baseline",
    success: bool = True,
    total_ms: int = 5000,
    browser_ms: int = 1000,
    agent_ms: int = 4000,
    pw_steps: int = 0,
    agent_steps: int = 8,
) -> OrchestratorResult:
    return OrchestratorResult(
        session_id="test-session-1",
        task="Search for mouse on Amazon",
        mode=mode,
        success=success,
        total_duration_ms=total_ms,
        browser_creation_ms=browser_ms,
        agent_duration_ms=agent_ms,
        playwright_steps=pw_steps,
        agent_steps=agent_steps,
        total_steps=pw_steps + agent_steps,
        model="test-model",
        output="Found 3 mice",
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health():
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


def test_cors_headers():
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.headers.get("access-control-allow-origin") in ("*", "http://localhost:3000")


# ---------------------------------------------------------------------------
# POST /api/run
# ---------------------------------------------------------------------------


def test_run_baseline(_patch_orchestrator):
    mock_orch = _patch_orchestrator
    mock_orch.run_task = AsyncMock(return_value=_make_result(mode="baseline"))

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/run",
            json={"task": "Search for mouse on Amazon", "mode": "baseline"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "baseline"
    assert data["success"] is True
    assert data["timing"]["total_duration_ms"] == 5000
    assert data["steps"]["agent_steps"] == 8


def test_run_invalid_mode(_patch_orchestrator):
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/run",
            json={"task": "Search for mouse on Amazon", "mode": "invalid_mode"},
        )
    assert resp.status_code == 422  # Pydantic validation (pattern mismatch)


def test_run_empty_task():
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/api/run", json={"task": "", "mode": "baseline"})
    assert resp.status_code == 422  # min_length=5


def test_run_short_task():
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/api/run", json={"task": "ab", "mode": "baseline"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/run-baseline
# ---------------------------------------------------------------------------


def test_run_baseline_endpoint(_patch_orchestrator):
    mock_orch = _patch_orchestrator
    mock_orch.run_task = AsyncMock(return_value=_make_result(mode="baseline"))

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/run-baseline",
            json={"task": "Search for mouse on Amazon"},
        )

    assert resp.status_code == 200
    assert resp.json()["mode"] == "baseline"


# ---------------------------------------------------------------------------
# POST /api/run-rocket
# ---------------------------------------------------------------------------


def test_run_rocket_endpoint(_patch_orchestrator):
    mock_orch = _patch_orchestrator
    mock_orch.run_task = AsyncMock(
        return_value=_make_result(mode="rocket", pw_steps=3, agent_steps=2)
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/run-rocket",
            json={"task": "Search for keyboard on Amazon"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "rocket"
    assert data["steps"]["playwright_steps"] == 3


def test_run_rocket_no_template(_patch_orchestrator):
    mock_orch = _patch_orchestrator
    mock_orch.run_task = AsyncMock(side_effect=ValueError("No template found"))

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/run-rocket",
            json={"task": "Some task with no template"},
        )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/learn
# ---------------------------------------------------------------------------


def test_learn_endpoint(_patch_orchestrator):
    mock_orch = _patch_orchestrator
    mock_orch.run_task = AsyncMock(return_value=_make_result(mode="baseline"))

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/learn",
            json={"task": "Learn searching on Amazon"},
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/status/{session_id}
# ---------------------------------------------------------------------------


def test_status_found(_patch_orchestrator):
    mock_orch = _patch_orchestrator
    mock_orch.get_session_state = MagicMock(
        return_value=OrchestratorSessionState(
            session_id="s1",
            task="test task",
            mode="baseline",
            status="running_agent",
            live_url="https://live.example.com",
        )
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/status/s1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running_agent"
    assert data["live_url"] == "https://live.example.com"


def test_status_not_found(_patch_orchestrator):
    mock_orch = _patch_orchestrator
    mock_orch.get_session_state = MagicMock(return_value=None)

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/status/nonexistent")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/result/{session_id}
# ---------------------------------------------------------------------------


def test_result_found(_patch_orchestrator):
    import src.api as api_module

    run_resp = _make_result().to_response()
    api_module._results["test-session-1"] = run_resp

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/result/test-session-1")

    assert resp.status_code == 200
    assert resp.json()["session_id"] == "test-session-1"


def test_result_not_found():
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/result/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/templates
# ---------------------------------------------------------------------------


def test_list_templates_empty(_patch_orchestrator):
    mock_orch = _patch_orchestrator
    mock_orch.list_templates = AsyncMock(return_value=[])

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/templates")

    assert resp.status_code == 200
    assert resp.json() == []


def test_list_templates_with_data(_patch_orchestrator):
    mock_orch = _patch_orchestrator
    mock_orch.list_templates = AsyncMock(
        return_value=[
            Template(
                id="t1",
                task_pattern="Search for {item} on Amazon",
                site_domain="amazon.com",
                playwright_steps=[{"action": "nav"}, {"action": "click"}],
                parameter_schema={"properties": {"item": {"type": "string"}}},
                created_at="2026-04-04",
                usage_count=5,
            )
        ]
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/templates")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "t1"
    assert data[0]["playwright_step_count"] == 2
    assert data[0]["parameter_names"] == ["item"]


# ---------------------------------------------------------------------------
# DELETE /api/templates/{template_id}
# ---------------------------------------------------------------------------


def test_delete_template(_patch_orchestrator):
    mock_orch = _patch_orchestrator

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.delete("/api/templates/t1")

    assert resp.status_code == 200
    assert resp.json()["deleted"] == "t1"
    mock_orch.delete_template.assert_called_once_with("t1")


# ---------------------------------------------------------------------------
# POST /api/compare
# ---------------------------------------------------------------------------


def test_compare_endpoint(_patch_orchestrator):
    mock_orch = _patch_orchestrator

    baseline = _make_result(mode="baseline", total_ms=8000, agent_steps=12, pw_steps=0)
    baseline.session_id = "baseline-s"
    rocket = _make_result(mode="rocket", total_ms=3000, agent_steps=3, pw_steps=4)
    rocket.session_id = "rocket-s"

    mock_orch.run_task = AsyncMock(side_effect=[baseline, rocket])

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/compare",
            json={"task": "Search for mouse on Amazon"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["baseline"]["mode"] == "baseline"
    assert data["rocket"]["mode"] == "rocket"
    assert data["speedup_factor"] > 1.0
    assert data["time_saved_ms"] == 5000
    assert data["steps_saved"] == 5  # 12 - 7
