"""
Template Extractor — the main pipeline orchestrating all extraction steps.

Public API:
  extract_template_from_trace(history, task) → InternalTemplate
  extract_parameters(task, template) → dict[str, str]
"""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import AsyncAnthropic

from src.template.analyzer import analyze_trace
from src.template.generator import InternalTemplate, generate_template, template_to_db_format
from src.template.simplifier import SimplifiedTrace, simplify_trace
from src.template.validator import ValidationSeverity, has_errors, validate_template

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Main pipeline: trace → template
# ──────────────────────────────────────────────────────────────


async def extract_template_from_trace(
    history: Any,  # AgentHistoryList from browser-use
    task_description: str,
    client: AsyncAnthropic | None = None,
    model: str = "claude-sonnet-4-6",
) -> InternalTemplate:
    """
    Full extraction pipeline: raw trace → simplified → analyzed → template → validated.

    Args:
        history: browser-use AgentHistoryList from agent.run()
        task_description: The original task string
        client: AsyncAnthropic client (created from env if None)
        model: Claude model for analysis

    Returns:
        A validated InternalTemplate ready for storage.

    Raises:
        ValueError: If validation finds ERROR-level issues.
        ValueError: If LLM returns unparseable output.
    """
    if client is None:
        client = AsyncAnthropic()

    # Step 1: Simplify the trace
    logger.info("Step 1/4: Simplifying trace")
    simplified = simplify_trace(history, task_description)
    logger.info("Simplified: %d steps from raw trace", len(simplified.steps))

    if not simplified.steps:
        raise ValueError("Trace has no steps after simplification — nothing to extract")

    # Step 2: LLM analysis
    logger.info("Step 2/4: Analyzing with %s", model)
    analysis = await analyze_trace(simplified, client=client, model=model)

    # Step 3: Generate template
    logger.info("Step 3/4: Generating template")
    template = generate_template(
        analysis=analysis,
        source_trace_id=simplified.trace_id,
        extraction_model=model,
    )

    # Step 4: Validate
    logger.info("Step 4/4: Validating template")
    issues = validate_template(template)

    errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
    warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]

    if warnings:
        for w in warnings:
            logger.warning("Validation warning (step %s): %s", w.step_index, w.message)

    if errors:
        error_msgs = [f"  [{e.field}] {e.message}" for e in errors]
        raise ValueError(
            f"Template validation failed with {len(errors)} error(s):\n"
            + "\n".join(error_msgs)
        )

    logger.info(
        "Template extracted: domain=%s, action_type=%s, %d steps, handoff=%d, "
        "%d warnings",
        template.domain,
        template.action_type,
        len(template.steps),
        template.handoff_index,
        len(warnings),
    )

    return template


# ──────────────────────────────────────────────────────────────
# Parameter extraction: task + template → param values
# ──────────────────────────────────────────────────────────────

PARAM_EXTRACTOR_SYSTEM = """\
You extract parameter values from a natural language task description, given a \
known template pattern. Return ONLY valid JSON with the parameter values. \
No explanation, no markdown.\
"""

PARAM_EXTRACTOR_USER = """\
TEMPLATE PATTERN: {task_pattern}

TEMPLATE PARAMETERS:
{parameters_json}

USER TASK: {user_task}

Extract the value for each parameter from the user's task. If a parameter \
is required but cannot be determined from the task, set its value to null.

Return JSON: {{"param_name": "value", ...}}\
"""


async def extract_parameters(
    task: str,
    template: InternalTemplate | dict[str, Any],
    client: AsyncAnthropic | None = None,
    model: str = "claude-haiku-4-5-20251001",
) -> dict[str, str | None]:
    """
    Extract parameter values from a task description using the template's pattern.

    Uses Claude Haiku for speed — this is a simple extraction task.

    Args:
        task: The user's natural language task.
        template: InternalTemplate or dict with task_pattern and parameters.
        client: AsyncAnthropic client.
        model: Model to use (Haiku recommended for speed).

    Returns:
        Dict mapping parameter names to extracted values.

    Raises:
        ValueError: If required parameters can't be extracted.
    """
    if client is None:
        client = AsyncAnthropic()

    # Handle both InternalTemplate and dict
    if isinstance(template, dict):
        task_pattern = template["task_pattern"]
        parameters = template.get("parameters", [])
    else:
        task_pattern = template.task_pattern
        parameters = [
            {"name": p.name, "description": p.description, "type": p.type, "required": p.required}
            for p in template.parameters
        ]

    if not parameters:
        return {}

    params_json = json.dumps(parameters, indent=2)

    user_prompt = PARAM_EXTRACTOR_USER.format(
        task_pattern=task_pattern,
        parameters_json=params_json,
        user_task=task,
    )

    response = await client.messages.create(
        model=model,
        max_tokens=512,
        system=PARAM_EXTRACTOR_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.0,
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown fences
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        if raw_text.endswith("```"):
            raw_text = raw_text.rsplit("```", 1)[0]
        raw_text = raw_text.strip()

    try:
        params = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Parameter extraction returned invalid JSON: {raw_text[:300]}"
        ) from e

    # Validate required params
    for p in parameters:
        if isinstance(p, dict):
            name = p["name"]
            required = p.get("required", True)
        else:
            name = p.name
            required = p.required
        if required and (name not in params or params[name] is None):
            raise ValueError(
                f"Required parameter '{name}' could not be extracted from task: {task}"
            )

    logger.info("Extracted parameters: %s", params)
    return params
