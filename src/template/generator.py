"""
Template Generator — converts LLM analysis output into canonical Template objects.

Pure transformation, no LLM calls, no network.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# ──────────────────────────────────────────────────────────────
# Internal template types (richer than shared models — used
# within the template module, serialized to shared types for DB)
# ──────────────────────────────────────────────────────────────


@dataclass
class TemplateSelector:
    """Selector strategy for finding an element on the page."""

    primary: str
    fallbacks: list[str] = field(default_factory=list)
    text_fallback: str | None = None


@dataclass
class InternalTemplateParameter:
    """A named parameter that changes between task instances."""

    name: str
    description: str
    type: str = "string"
    required: bool = True


@dataclass
class InternalTemplateStep:
    """A single step in the template."""

    index: int
    action: str
    params: dict[str, Any]
    classification: str  # "FIXED", "PARAMETERIZED", "DYNAMIC"
    selectors: TemplateSelector | None = None
    parameter_name: str | None = None
    parameter_field: str | None = None
    reasoning: str | None = None
    retry_on_failure: bool = True
    wait_after_ms: int = 100


@dataclass
class InternalTemplate:
    """A complete reusable template for browser automation."""

    template_id: str
    domain: str
    action_type: str
    task_pattern: str
    parameters: list[InternalTemplateParameter]
    steps: list[InternalTemplateStep]
    handoff_index: int
    preconditions: list[str]
    source_trace_id: str
    extraction_model: str
    created_at: str
    version: int = 1
    success_count: int = 0
    failure_count: int = 0
    confidence: float = 0.5
    estimated_time_saved_seconds: float = 0.0


# ──────────────────────────────────────────────────────────────
# Generator
# ──────────────────────────────────────────────────────────────


def generate_template(
    analysis: dict[str, Any],
    source_trace_id: str,
    extraction_model: str,
) -> InternalTemplate:
    """
    Convert LLM analysis output into a canonical InternalTemplate.

    Args:
        analysis: Parsed JSON from the LLM analyzer.
        source_trace_id: ID of the trace this template was extracted from.
        extraction_model: Model name used for extraction (e.g. "claude-sonnet-4-6").

    Returns:
        An InternalTemplate ready for validation and storage.
    """
    template_id = str(uuid.uuid4())

    parameters = [
        InternalTemplateParameter(
            name=p["name"],
            description=p.get("description", ""),
            type=p.get("type", "string"),
            required=p.get("required", True),
        )
        for p in analysis.get("parameters", [])
    ]

    steps: list[InternalTemplateStep] = []
    for step_data in analysis.get("steps", []):
        if step_data.get("can_skip", False):
            continue

        selectors = None
        if step_data.get("selectors"):
            s = step_data["selectors"]
            selectors = TemplateSelector(
                primary=s.get("primary", ""),
                fallbacks=s.get("fallbacks", []),
                text_fallback=s.get("text_fallback"),
            )

        param_info = step_data.get("parameter")

        steps.append(
            InternalTemplateStep(
                index=len(steps),
                action=step_data.get("action", "unknown"),
                params=step_data.get("params", {}),
                classification=step_data["classification"],
                selectors=selectors,
                parameter_name=param_info["name"] if param_info else None,
                parameter_field=_infer_parameter_field(
                    step_data.get("action", ""), param_info
                ),
                reasoning=step_data.get("reasoning"),
                retry_on_failure=step_data["classification"]
                in ("FIXED", "PARAMETERIZED"),
                wait_after_ms=_infer_wait_time(step_data.get("action", "")),
            )
        )

    # Validate and clamp handoff_index
    raw_handoff = analysis.get("handoff_index", 0)
    handoff_index = max(0, min(raw_handoff, len(steps) - 1)) if steps else 0

    return InternalTemplate(
        template_id=template_id,
        domain=analysis.get("domain", ""),
        action_type=analysis.get("action_type", ""),
        task_pattern=analysis.get("task_pattern", ""),
        parameters=parameters,
        steps=steps,
        handoff_index=handoff_index,
        preconditions=analysis.get("preconditions", []),
        source_trace_id=source_trace_id,
        extraction_model=extraction_model,
        created_at=datetime.now(timezone.utc).isoformat(),
        estimated_time_saved_seconds=analysis.get(
            "estimated_time_saved_seconds", 0.0
        ),
    )


# ──────────────────────────────────────────────────────────────
# Serialization to shared models (for DB storage)
# ──────────────────────────────────────────────────────────────


def template_to_db_format(template: InternalTemplate) -> dict[str, Any]:
    """
    Convert an InternalTemplate to the dict format expected by the DB layer.

    Maps internal types to the shared models contract:
    - steps become list[dict] matching TemplateStep fields
    - parameters become list[dict] matching TemplateParameter fields
    """
    steps_for_db: list[dict[str, Any]] = []
    for step in template.steps:
        step_dict: dict[str, Any] = {
            "index": step.index,
            "type": step.classification.lower(),  # FIXED -> fixed
            "action": step.action,
            "timeout_ms": step.wait_after_ms,
            "on_failure": "try_fallback" if step.retry_on_failure else "abort",
        }

        # Add selector info
        if step.selectors:
            step_dict["selector"] = step.selectors.primary
            step_dict["fallback_selectors"] = step.selectors.fallbacks

        # Add action-specific fields
        if step.action == "navigate":
            step_dict["url"] = step.params.get("url", "")
        elif step.action == "press" or step.action == "send_keys":
            step_dict["key"] = step.params.get("key", step.params.get("keys", ""))
        elif step.action == "scroll":
            step_dict["direction"] = step.params.get("direction", "down")
            step_dict["amount"] = step.params.get("amount", 500)

        # Add parameter info
        if step.parameter_name:
            step_dict["param"] = step.parameter_name
        if step.params.get("value") or step.params.get("url"):
            step_dict["value"] = step.params.get("value") or step.params.get(
                "url", ""
            )

        # Add dynamic step info
        if step.classification == "DYNAMIC":
            step_dict["description"] = step.reasoning or ""
            step_dict["agent_needed"] = True

        steps_for_db.append(step_dict)

    params_for_db = [
        {
            "name": p.name,
            "type": p.type,
            "description": p.description,
        }
        for p in template.parameters
    ]

    return {
        "domain": template.domain,
        "action_type": template.action_type,
        "task_pattern": template.task_pattern,
        "parameters": params_for_db,
        "steps": steps_for_db,
        "handoff_index": template.handoff_index,
    }


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _infer_parameter_field(action: str, param_info: dict | None) -> str | None:
    """Determine which field of the action params the parameter maps to."""
    if param_info is None:
        return None
    field_map = {
        "input": "text",
        "navigate": "url",
        "search": "query",
        "select_dropdown": "value",
        "find_text": "text",
        "evaluate": "js_code",
    }
    return field_map.get(action, "value")


def _infer_wait_time(action: str) -> int:
    """Estimate ms to wait after an action for the page to settle."""
    wait_map = {
        "navigate": 2000,
        "click": 1000,
        "input": 200,
        "send_keys": 500,
        "search": 2000,
        "go_back": 1500,
        "select_dropdown": 500,
        "scroll": 300,
    }
    return wait_map.get(action, 100)
