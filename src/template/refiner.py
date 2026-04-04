"""
Template Refiner — compares template vs actual execution trace,
recommends improvements.

Refinement types:
- SELECTOR_UPDATE: A selector failed, another worked
- STEP_PROMOTION: A DYNAMIC step always does the same thing → FIXED
- HANDOFF_EXTENSION: The rocket can burn longer
- PATH_OPTIMIZATION: Agent found a shorter path
- SELECTOR_ADDITION: Step lacks fallback selectors
- NO_CHANGE: Template worked perfectly
"""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import AsyncAnthropic

from src.template.generator import InternalTemplate
from src.template.simplifier import SimplifiedTrace

logger = logging.getLogger(__name__)


REFINEMENT_SYSTEM_PROMPT = """\
You are comparing a browser automation template against the actual execution trace \
to determine if the template should be updated.

RULES:
- Only recommend changes with strong evidence (not one-off flukes).
- Stability is paramount. A template that works 95% of the time is better than \
  one that's "optimal" but fragile.
- If the agent found a shorter path, verify it's generalizable before adopting.
- All actions must be from the browser-use action space.

OUTPUT FORMAT: Respond with valid JSON only, no markdown fences.\
"""

REFINEMENT_USER_PROMPT = """\
TEMPLATE (version {version}):
{template_json}

ACTUAL EXECUTION TRACE:
{trace_json}

EXECUTION RESULT: {outcome}

Compare the template against what actually happened and recommend updates:

1. SELECTOR_UPDATE: A selector failed but another worked. Provide the new ordering.
2. STEP_PROMOTION: A DYNAMIC step always does the same thing. Promote to FIXED or PARAMETERIZED.
3. HANDOFF_EXTENSION: The rocket could burn longer (handoff_index can increase).
4. PATH_OPTIMIZATION: The agent found a shorter/better path.
5. SELECTOR_ADDITION: A step lacks fallback selectors; provide them based on what worked.
6. NO_CHANGE: The template worked perfectly.

Return JSON:
{{
  "recommendations": [
    {{
      "type": "SELECTOR_UPDATE" | "STEP_PROMOTION" | "HANDOFF_EXTENSION" | "PATH_OPTIMIZATION" | "SELECTOR_ADDITION" | "NO_CHANGE",
      "step_index": <int or null>,
      "details": {{...}},
      "confidence": 0.0-1.0,
      "reasoning": "Why this change"
    }}
  ]
}}\
"""


async def refine_template(
    template: InternalTemplate,
    trace: SimplifiedTrace,
    success: bool,
    client: AsyncAnthropic | None = None,
    model: str = "claude-sonnet-4-6",
    min_confidence: float = 0.8,
) -> list[dict[str, Any]]:
    """
    Compare a template against an actual execution trace and return
    high-confidence refinement recommendations.

    Args:
        template: The template that was used for this execution.
        trace: The simplified trace of what actually happened.
        success: Whether the overall task succeeded.
        client: AsyncAnthropic client.
        model: Model for analysis.
        min_confidence: Only return recommendations above this threshold.

    Returns:
        List of recommendation dicts with type, step_index, details, confidence, reasoning.
        Empty list if no refinements needed or confidence too low.
    """
    if client is None:
        client = AsyncAnthropic()

    template_json = _template_to_json(template)
    trace_json = json.dumps(trace.steps_as_dicts(), indent=2)

    user_prompt = REFINEMENT_USER_PROMPT.format(
        version=template.version,
        template_json=template_json,
        trace_json=trace_json,
        outcome="success" if success else "failure",
    )

    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=REFINEMENT_SYSTEM_PROMPT,
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
        result = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error("Refinement LLM returned invalid JSON: %s", raw_text[:300])
        return []

    recommendations = result.get("recommendations", [])

    # Filter by confidence
    high_confidence = [
        r for r in recommendations if r.get("confidence", 0) >= min_confidence
    ]

    if high_confidence:
        logger.info(
            "Refinement: %d recommendations (%d above %.1f confidence)",
            len(recommendations),
            len(high_confidence),
            min_confidence,
        )
        for r in high_confidence:
            logger.info(
                "  %s (step %s, confidence %.2f): %s",
                r.get("type"),
                r.get("step_index"),
                r.get("confidence", 0),
                r.get("reasoning", "")[:100],
            )
    else:
        logger.info("Refinement: no high-confidence recommendations")

    return high_confidence


def apply_refinements(
    template: InternalTemplate,
    recommendations: list[dict[str, Any]],
) -> InternalTemplate:
    """
    Apply a list of refinement recommendations to a template.
    Returns a new template (does not mutate the input).

    Only applies changes that are safe and well-understood:
    - SELECTOR_UPDATE: reorder/add selectors
    - SELECTOR_ADDITION: add fallback selectors
    - HANDOFF_EXTENSION: increase handoff_index
    - STEP_PROMOTION: change classification from DYNAMIC to FIXED/PARAMETERIZED

    Skips PATH_OPTIMIZATION (too risky without human review).
    """
    import copy

    updated = copy.deepcopy(template)
    updated.version += 1

    for rec in recommendations:
        rec_type = rec.get("type", "")
        step_idx = rec.get("step_index")
        details = rec.get("details", {})

        if rec_type == "SELECTOR_UPDATE" and step_idx is not None:
            if 0 <= step_idx < len(updated.steps):
                step = updated.steps[step_idx]
                if step.selectors and details.get("new_primary"):
                    step.selectors.primary = details["new_primary"]
                if step.selectors and details.get("new_fallbacks"):
                    step.selectors.fallbacks = details["new_fallbacks"]

        elif rec_type == "SELECTOR_ADDITION" and step_idx is not None:
            if 0 <= step_idx < len(updated.steps):
                step = updated.steps[step_idx]
                if step.selectors and details.get("additional_fallbacks"):
                    existing = set(step.selectors.fallbacks)
                    for fb in details["additional_fallbacks"]:
                        if fb not in existing:
                            step.selectors.fallbacks.append(fb)

        elif rec_type == "HANDOFF_EXTENSION":
            new_handoff = details.get("new_handoff_index")
            if (
                new_handoff is not None
                and new_handoff > updated.handoff_index
                and new_handoff < len(updated.steps)
            ):
                updated.handoff_index = new_handoff

        elif rec_type == "STEP_PROMOTION" and step_idx is not None:
            if 0 <= step_idx < len(updated.steps):
                step = updated.steps[step_idx]
                new_class = details.get("new_classification")
                if new_class in ("FIXED", "PARAMETERIZED") and step.classification == "DYNAMIC":
                    step.classification = new_class
                    if new_class == "PARAMETERIZED" and details.get("parameter_name"):
                        step.parameter_name = details["parameter_name"]

        elif rec_type == "NO_CHANGE":
            pass  # Nothing to do

        # PATH_OPTIMIZATION is intentionally skipped — too risky for auto-apply

    return updated


def _template_to_json(template: InternalTemplate) -> str:
    """Serialize template to JSON for the LLM prompt."""
    steps_data = []
    for s in template.steps:
        step_dict: dict[str, Any] = {
            "index": s.index,
            "action": s.action,
            "classification": s.classification,
            "params": s.params,
        }
        if s.selectors:
            step_dict["selectors"] = {
                "primary": s.selectors.primary,
                "fallbacks": s.selectors.fallbacks,
                "text_fallback": s.selectors.text_fallback,
            }
        if s.parameter_name:
            step_dict["parameter_name"] = s.parameter_name
        if s.reasoning:
            step_dict["reasoning"] = s.reasoning
        steps_data.append(step_dict)

    return json.dumps(
        {
            "domain": template.domain,
            "action_type": template.action_type,
            "task_pattern": template.task_pattern,
            "handoff_index": template.handoff_index,
            "steps": steps_data,
        },
        indent=2,
    )
