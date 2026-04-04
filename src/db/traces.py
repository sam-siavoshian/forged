"""Execution trace recording.

Records every task execution (both rocket-boosted and baseline vanilla runs)
into the execution_traces table.
"""

import json
from typing import Any

from .client import get_pg_pool


async def record_execution_trace(
    template_id: str | None,
    task_description: str,
    mode: str,
    steps_executed: list[dict[str, Any]],
    total_duration_ms: int,
    success: bool,
    rocket_steps_count: int | None = None,
    agent_steps_count: int | None = None,
    rocket_duration_ms: int | None = None,
    agent_duration_ms: int | None = None,
    error_message: str | None = None,
    error_step_index: int | None = None,
) -> str:
    """Record an execution trace. Returns the trace UUID."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO execution_traces
                (template_id, task_description, mode, steps_executed,
                 rocket_steps_count, agent_steps_count, total_duration_ms,
                 rocket_duration_ms, agent_duration_ms, success,
                 error_message, error_step_index)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
            """,
            template_id,
            task_description,
            mode,
            json.dumps(steps_executed),
            rocket_steps_count,
            agent_steps_count,
            total_duration_ms,
            rocket_duration_ms,
            agent_duration_ms,
            success,
            error_message,
            error_step_index,
        )
        return str(row["id"])
