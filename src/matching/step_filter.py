"""LLM-powered step filter for template adaptation.

Given a user's task and a template's steps, determines which steps are
relevant to the user's specific request. Uses Claude Haiku for speed (~500ms).

This enables partial template execution: if a template has 6 steps but
the user only needs 3, we skip the irrelevant ones instead of running
all of them and failing.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from src import config

logger = logging.getLogger(__name__)


@dataclass
class StepFilterResult:
    """Result of step filtering."""
    execute_indices: list[int]
    skip_indices: list[int]
    adjusted_handoff_index: int
    reasoning: str


SYSTEM_PROMPT = """You are a step filter for a browser automation system.
Given a user's task and a template's steps, determine which steps are
NECESSARY to fulfill the user's specific request.

You must preserve step ordering. Never reorder steps. Only skip steps
that are clearly not needed for the user's goal.

Return ONLY valid JSON. No explanation, no markdown fences."""


def _build_user_prompt(
    task: str,
    task_pattern: str,
    steps: list[dict[str, Any]],
    parameters: dict[str, str | None],
    handoff_index: int,
) -> str:
    steps_desc = []
    for i, s in enumerate(steps):
        if i > handoff_index:
            break
        action = s.get("action", "unknown")
        desc = s.get("description", action)
        param = s.get("param")
        param_value = parameters.get(param) if param else None
        param_info = ""
        if param:
            if param_value:
                param_info = f" [uses param '{param}'='{param_value}']"
            else:
                param_info = f" [uses param '{param}'=MISSING]"
        steps_desc.append(f"  {i}: {action} — {desc}{param_info}")

    steps_text = "\n".join(steps_desc)
    params_text = json.dumps(parameters, indent=2)

    return f"""USER TASK: {task}

TEMPLATE PATTERN: {task_pattern}

TEMPLATE STEPS (indices 0 to {handoff_index}):
{steps_text}

EXTRACTED PARAMETERS:
{params_text}

For each step index (0 to {handoff_index}), decide: EXECUTE or SKIP.

Rules:
1. Navigate steps (usually index 0) are almost always EXECUTE.
2. If a step uses a parameter that is null/MISSING, mark it SKIP.
3. If the user's task is a SUBSET of the template (e.g., "just search"
   when template does search+click+extract), SKIP steps beyond what
   the user asked for.
4. If the user's task MATCHES the full template, EXECUTE all steps.
5. Never skip a step that a later EXECUTE step depends on (e.g., don't
   skip "search" if "click first result" is EXECUTE).

Return JSON:
{{
  "steps": [
    {{"index": 0, "decision": "EXECUTE", "reason": "navigate to site"}},
    {{"index": 1, "decision": "SKIP", "reason": "user did not ask to search"}}
  ],
  "reasoning": "one sentence summary"
}}"""


async def filter_steps(
    task: str,
    task_pattern: str,
    steps: list[dict[str, Any]],
    parameters: dict[str, str | None],
    handoff_index: int,
) -> StepFilterResult:
    """Filter template steps to match the user's specific task.

    Uses Claude Haiku for speed. Falls back to executing all steps
    if the LLM call fails or returns garbage.
    """
    # If only 1-2 steps, no point filtering
    rocket_steps = [s for i, s in enumerate(steps) if i <= handoff_index]
    if len(rocket_steps) <= config.STEP_FILTER_MIN_STEPS:
        indices = list(range(len(rocket_steps)))
        return StepFilterResult(
            execute_indices=indices,
            skip_indices=[],
            adjusted_handoff_index=handoff_index,
            reasoning="Too few steps to filter",
        )

    # Check if any parameters are missing — if all present, likely full match
    missing_params = [k for k, v in parameters.items() if v is None]
    all_params_present = len(missing_params) == 0

    # If all parameters present, skip the LLM call and execute everything
    if all_params_present:
        indices = list(range(min(handoff_index + 1, len(steps))))
        return StepFilterResult(
            execute_indices=indices,
            skip_indices=[],
            adjusted_handoff_index=handoff_index,
            reasoning="All parameters present, executing full template",
        )

    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

        user_prompt = _build_user_prompt(task, task_pattern, steps, parameters, handoff_index)

        response = await client.messages.create(
            model=config.MODEL_STEP_FILTER,
            max_tokens=config.STEP_FILTER_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3].strip()

        data = json.loads(raw)
        step_decisions = data.get("steps", [])
        reasoning = data.get("reasoning", "")

        execute = []
        skip = []
        for sd in step_decisions:
            idx = sd.get("index", -1)
            decision = sd.get("decision", "EXECUTE").upper()
            if 0 <= idx <= handoff_index:
                if decision == "SKIP":
                    skip.append(idx)
                else:
                    execute.append(idx)

        # Safety: if ALL steps are skipped, fall back to executing all
        if not execute:
            logger.warning("Step filter returned all-SKIP, falling back to full execution")
            indices = list(range(min(handoff_index + 1, len(steps))))
            return StepFilterResult(
                execute_indices=indices,
                skip_indices=[],
                adjusted_handoff_index=handoff_index,
                reasoning="Fallback: filter returned all-SKIP",
            )

        adjusted = max(execute) if execute else handoff_index

        logger.info(
            "Step filter: execute=%s skip=%s reason=%s",
            execute, skip, reasoning,
        )

        return StepFilterResult(
            execute_indices=sorted(execute),
            skip_indices=sorted(skip),
            adjusted_handoff_index=adjusted,
            reasoning=reasoning,
        )

    except Exception as e:
        logger.warning("Step filter failed (using all steps): %s", e)
        indices = list(range(min(handoff_index + 1, len(steps))))
        return StepFilterResult(
            execute_indices=indices,
            skip_indices=[],
            adjusted_handoff_index=handoff_index,
            reasoning=f"Fallback: filter error ({e})",
        )
