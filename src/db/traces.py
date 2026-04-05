"""Execution trace recording.

Records every task execution (both forge and baseline vanilla runs)
into the execution_traces table. Falls back to Supabase REST when
direct PostgreSQL is unavailable (e.g. campus WiFi blocking connections).
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


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
) -> str | None:
    """Record an execution trace. Returns the trace UUID or None on failure."""

    # Try direct PostgreSQL first
    try:
        from .client import get_pg_pool
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
    except Exception as pg_err:
        logger.debug("PG trace insert failed, trying REST fallback: %s", pg_err)

    # Fallback: Supabase REST
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            return None

        client = create_client(url, key)
        row_data: dict[str, Any] = {
            "task_description": task_description,
            "mode": mode,
            "steps_executed": steps_executed,
            "total_duration_ms": total_duration_ms,
            "success": success,
        }
        if template_id:
            row_data["template_id"] = template_id
        if rocket_steps_count is not None:
            row_data["rocket_steps_count"] = rocket_steps_count
        if agent_steps_count is not None:
            row_data["agent_steps_count"] = agent_steps_count
        if rocket_duration_ms is not None:
            row_data["rocket_duration_ms"] = rocket_duration_ms
        if agent_duration_ms is not None:
            row_data["agent_duration_ms"] = agent_duration_ms
        if error_message:
            row_data["error_message"] = error_message
        if error_step_index is not None:
            row_data["error_step_index"] = error_step_index

        result = client.table("execution_traces").insert(row_data).execute()
        if result.data:
            return str(result.data[0].get("id", ""))
        return None
    except Exception as rest_err:
        logger.warning("REST trace insert also failed: %s", rest_err)
        return None
