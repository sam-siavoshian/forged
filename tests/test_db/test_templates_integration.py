"""Integration tests for template CRUD.

These tests require a real Supabase instance.
Mark with @pytest.mark.integration and skip if env vars are missing.
"""

import os
import uuid

import pytest
import pytest_asyncio

# Skip entire module if Supabase env vars are not set
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("SUPABASE_DB_URL"),
        reason="SUPABASE_DB_URL not set — skipping integration tests",
    ),
    pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set — skipping integration tests",
    ),
]


@pytest_asyncio.fixture
async def pg_pool():
    """Get a real asyncpg pool for integration tests."""
    from src.db.client import close_pg_pool, get_pg_pool

    pool = await get_pg_pool()
    yield pool
    await close_pg_pool()


@pytest.mark.asyncio
async def test_create_and_retrieve_template(pg_pool):
    """Test creating a template and retrieving it by ID."""
    from src.db.templates import create_template, get_template_by_id

    template_id = await create_template(
        domain="test.example.com",
        action_type="search",
        task_pattern=f"search for {{query}} on test.example.com [{uuid.uuid4()}]",
        parameters=[{"name": "query", "type": "string"}],
        steps=[
            {"index": 0, "type": "fixed", "action": "navigate", "url": "https://test.example.com"},
            {"index": 1, "type": "parameterized", "action": "fill", "param": "query"},
        ],
        handoff_index=2,
    )

    assert template_id is not None
    assert len(template_id) == 36  # UUID format

    template = await get_template_by_id(template_id)
    assert template is not None
    assert template["domain"] == "test.example.com"
    assert template["action_type"] == "search"
    assert template["confidence"] == 0.5
    assert template["success_count"] == 0
    assert len(template["steps"]) == 2

    # Cleanup
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM task_templates WHERE id = $1", template_id
        )


@pytest.mark.asyncio
async def test_update_template_after_success(pg_pool):
    """Test confidence increases after success."""
    from src.db.templates import (
        create_template,
        get_template_by_id,
        update_template_after_execution,
    )

    template_id = await create_template(
        domain="test.example.com",
        action_type="navigate",
        task_pattern=f"go to test.example.com [{uuid.uuid4()}]",
        parameters=[],
        steps=[{"index": 0, "type": "fixed", "action": "navigate"}],
        handoff_index=1,
    )

    await update_template_after_execution(
        template_id=template_id,
        success=True,
        rocket_duration_ms=500,
        agent_duration_ms=1000,
        total_duration_ms=1500,
    )

    template = await get_template_by_id(template_id)
    assert template["confidence"] == pytest.approx(0.55)
    assert template["success_count"] == 1
    assert template["failure_count"] == 0
    assert template["avg_total_duration_ms"] == 1500

    # Cleanup
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM task_templates WHERE id = $1", template_id
        )


@pytest.mark.asyncio
async def test_update_template_after_failure(pg_pool):
    """Test confidence decreases after failure."""
    from src.db.templates import (
        create_template,
        get_template_by_id,
        update_template_after_execution,
    )

    template_id = await create_template(
        domain="test.example.com",
        action_type="navigate",
        task_pattern=f"visit test.example.com [{uuid.uuid4()}]",
        parameters=[],
        steps=[{"index": 0, "type": "fixed", "action": "navigate"}],
        handoff_index=1,
    )

    await update_template_after_execution(
        template_id=template_id,
        success=False,
        rocket_duration_ms=None,
        agent_duration_ms=None,
        total_duration_ms=2000,
    )

    template = await get_template_by_id(template_id)
    assert template["confidence"] == pytest.approx(0.40)
    assert template["success_count"] == 0
    assert template["failure_count"] == 1

    # Cleanup
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM task_templates WHERE id = $1", template_id
        )


@pytest.mark.asyncio
async def test_list_templates_by_domain(pg_pool):
    """Test listing templates by domain."""
    from src.db.templates import create_template, list_templates_by_domain

    unique_domain = f"test-{uuid.uuid4().hex[:8]}.example.com"
    ids = []

    for i in range(3):
        tid = await create_template(
            domain=unique_domain,
            action_type="search",
            task_pattern=f"search test {i} on {unique_domain}",
            parameters=[],
            steps=[{"index": 0, "type": "fixed", "action": "navigate"}],
            handoff_index=1,
        )
        ids.append(tid)

    templates = await list_templates_by_domain(unique_domain)
    assert len(templates) == 3

    # Cleanup
    async with pg_pool.acquire() as conn:
        for tid in ids:
            await conn.execute(
                "DELETE FROM task_templates WHERE id = $1", tid
            )


@pytest.mark.asyncio
async def test_record_execution_trace(pg_pool):
    """Test recording an execution trace."""
    from src.db.traces import record_execution_trace

    trace_id = await record_execution_trace(
        template_id=None,
        task_description="Test baseline run",
        mode="baseline",
        steps_executed=[{"action": "navigate", "url": "https://example.com"}],
        total_duration_ms=5000,
        success=True,
    )

    assert trace_id is not None
    assert len(trace_id) == 36

    # Cleanup
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM execution_traces WHERE id = $1", trace_id
        )
