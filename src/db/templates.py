"""Task template CRUD and confidence scoring.

Handles creation, retrieval, listing, and post-execution updates
for task_templates in Supabase.
"""

import json
from typing import Any

from .client import get_pg_pool
from .embeddings import generate_embedding


async def create_template(
    domain: str,
    action_type: str,
    task_pattern: str,
    parameters: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    handoff_index: int,
) -> str:
    """Create a new task template. Generates the embedding automatically.

    Returns the UUID of the created template.
    """
    embedding = generate_embedding(task_pattern)
    embedding_str = json.dumps(embedding)

    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO task_templates
                (domain, action_type, task_pattern, parameters, steps,
                 handoff_index, embedding)
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, $7::vector)
            RETURNING id
            """,
            domain,
            action_type,
            task_pattern,
            json.dumps(parameters),
            json.dumps(steps),
            handoff_index,
            embedding_str,
        )
        return str(row["id"])


async def get_template_by_id(template_id: str) -> dict[str, Any] | None:
    """Fetch a single template by UUID. Returns None if not found."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, domain, action_type, task_pattern, parameters,
                   steps, handoff_index, confidence, success_count,
                   failure_count, avg_rocket_duration_ms,
                   avg_agent_duration_ms, avg_total_duration_ms,
                   avg_baseline_duration_ms, created_at, updated_at
            FROM task_templates WHERE id = $1
            """,
            template_id,
        )
        if row is None:
            return None
        result = dict(row)
        result["id"] = str(result["id"])
        # Parse JSONB fields
        if isinstance(result["parameters"], str):
            result["parameters"] = json.loads(result["parameters"])
        if isinstance(result["steps"], str):
            result["steps"] = json.loads(result["steps"])
        return result


async def list_templates_by_domain(domain: str) -> list[dict[str, Any]]:
    """List all templates for a given domain, ordered by confidence DESC."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, task_pattern, action_type, confidence,
                   success_count, failure_count
            FROM task_templates
            WHERE domain = $1
            ORDER BY confidence DESC
            """,
            domain,
        )
        return [
            {**dict(row), "id": str(row["id"])}
            for row in rows
        ]


async def update_template_after_execution(
    template_id: str,
    success: bool,
    rocket_duration_ms: int | None,
    agent_duration_ms: int | None,
    total_duration_ms: int,
) -> None:
    """Update a template's confidence and duration stats after an execution.

    Confidence formula:
    - Success: confidence += 0.1 * (1.0 - confidence)
    - Failure: confidence -= 0.2 * confidence
    """
    pool = await get_pg_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT confidence, success_count, failure_count, "
            "avg_rocket_duration_ms, avg_agent_duration_ms, avg_total_duration_ms "
            "FROM task_templates WHERE id = $1",
            template_id,
        )
        if row is None:
            raise ValueError(f"Template {template_id} not found")

        old_confidence = float(row["confidence"])
        old_success = int(row["success_count"])
        old_failure = int(row["failure_count"])
        total_executions = old_success + old_failure + 1

        # Update confidence
        if success:
            new_confidence = old_confidence + 0.1 * (1.0 - old_confidence)
            new_success = old_success + 1
            new_failure = old_failure
        else:
            new_confidence = old_confidence - 0.2 * old_confidence
            new_success = old_success
            new_failure = old_failure + 1

        new_confidence = max(0.0, min(1.0, new_confidence))

        # Running averages
        def running_avg(old_avg: int | None, new_val: int | None) -> int | None:
            if new_val is None:
                return old_avg
            if old_avg is None:
                return new_val
            return int(old_avg + (new_val - old_avg) / total_executions)

        new_avg_rocket = running_avg(
            row["avg_rocket_duration_ms"], rocket_duration_ms
        )
        new_avg_agent = running_avg(
            row["avg_agent_duration_ms"], agent_duration_ms
        )
        new_avg_total = running_avg(
            row["avg_total_duration_ms"], total_duration_ms
        )

        await conn.execute(
            """
            UPDATE task_templates
            SET confidence = $2,
                success_count = $3,
                failure_count = $4,
                avg_rocket_duration_ms = $5,
                avg_agent_duration_ms = $6,
                avg_total_duration_ms = $7
            WHERE id = $1
            """,
            template_id,
            new_confidence,
            new_success,
            new_failure,
            new_avg_rocket,
            new_avg_agent,
            new_avg_total,
        )


async def update_baseline_duration(
    template_id: str,
    baseline_duration_ms: int,
) -> None:
    """Update the baseline (vanilla agent, no rocket) duration for a template."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT avg_baseline_duration_ms, success_count, failure_count "
            "FROM task_templates WHERE id = $1",
            template_id,
        )
        if row is None:
            return

        total = int(row["success_count"]) + int(row["failure_count"]) + 1
        old_avg = row["avg_baseline_duration_ms"]
        if old_avg is None:
            new_avg = baseline_duration_ms
        else:
            new_avg = int(old_avg + (baseline_duration_ms - old_avg) / total)

        await conn.execute(
            "UPDATE task_templates SET avg_baseline_duration_ms = $2 WHERE id = $1",
            template_id,
            new_avg,
        )
