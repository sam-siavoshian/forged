"""
LLM Analyzer — sends simplified traces to Claude for classification.

Classifies each step as FIXED / PARAMETERIZED / DYNAMIC.
Extracts CSS selectors, parameters, handoff point, and domain info.

CRITICAL: All actions MUST be from the browser-use action space.
NEVER suggest human shortcuts (Cmd+L, Ctrl+T, etc.).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

from anthropic import AsyncAnthropic

from src.template.simplifier import SimplifiedTrace

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# System prompt — defines classification rules
# ──────────────────────────────────────────────────────────────

ANALYZER_SYSTEM_PROMPT = """\
You are a browser automation trace analyzer. Your job is to examine a sequence \
of browser actions and classify each step for template extraction.

IMPORTANT CONSTRAINTS:
- All actions MUST be from the browser-use action space: navigate, click, input, \
scroll, send_keys, wait, search, go_back, find_text, evaluate, switch_tab, \
close_tab, extract, screenshot, dropdown_options, select_dropdown, upload_file, \
write_file, read_file, done.
- NEVER suggest human-oriented actions like keyboard shortcuts (Cmd+L, Ctrl+T, etc.).
- NEVER suggest browser chrome interactions (address bar, bookmarks, etc.).
- Templates are for a browser automation agent, not a human user.

CLASSIFICATION RULES:
- FIXED: This exact action with these exact parameters will be the same every time \
this template runs, regardless of the specific task instance. Examples: navigating \
to a known URL, clicking a persistent UI element like a search icon.
- PARAMETERIZED: The action type and target element are the same, but one or more \
parameter values change based on the task. Examples: typing a search query (the \
element is always the search box, but the text changes), navigating to a URL that \
contains a variable path segment.
- DYNAMIC: This step requires the agent to observe the current page state and make \
a decision. The action, target, or both could vary. Examples: selecting a specific \
product from search results, choosing a shipping option based on criteria.

OUTPUT FORMAT: Respond with valid JSON only, no markdown fences, no commentary.\
"""


# ──────────────────────────────────────────────────────────────
# User prompt template
# ──────────────────────────────────────────────────────────────

ANALYZER_USER_PROMPT = """\
Analyze the following browser automation trace and extract a reusable template.

ORIGINAL TASK: {task_description}

SIMPLIFIED TRACE:
{trace_json}

For each step, provide:
1. "classification": "FIXED" | "PARAMETERIZED" | "DYNAMIC"
2. "selectors": (for FIXED and PARAMETERIZED steps) an object with:
   - "primary": the most stable CSS selector for the target element
   - "fallbacks": array of 2-3 alternative selectors in order of stability
   - "text_fallback": text content to match if all CSS selectors fail
   Use this priority: id > data-testid > aria-label > name > role+type > class-based > text
3. "parameter": (for PARAMETERIZED steps) an object with:
   - "name": a descriptive snake_case parameter name
   - "description": what this parameter represents
   - "source": where in the task description this value comes from
4. "reasoning": (for DYNAMIC steps) what the agent needs to figure out
5. "can_skip": boolean, true if this step is unnecessary overhead (e.g., redundant waits)

Also provide:
- "domain": the primary domain this template targets
- "action_type": a short category (e.g., "search", "purchase", "login", "form_fill", "data_extraction")
- "task_pattern": a generalized task description with {{parameter_name}} placeholders
- "parameters": array of all unique parameters with name, description, type (string/number/boolean), and whether required
- "handoff_index": the index of the LAST step that is FIXED or PARAMETERIZED before the first DYNAMIC step
- "estimated_time_saved_seconds": rough estimate of time saved by the deterministic prefix
- "preconditions": any requirements (e.g., "requires_auth", "requires_javascript")

Respond with this exact JSON structure:
{{
  "domain": "example.com",
  "action_type": "category",
  "task_pattern": "do {{thing}} on example.com",
  "parameters": [
    {{
      "name": "thing",
      "description": "The thing to do",
      "type": "string",
      "required": true
    }}
  ],
  "steps": [
    {{
      "original_step_index": 0,
      "action": "navigate",
      "params": {{}},
      "classification": "FIXED",
      "selectors": {{
        "primary": "#element-id",
        "fallbacks": ["[data-testid='element']", "[aria-label='Element']"],
        "text_fallback": "Element Text"
      }},
      "parameter": null,
      "reasoning": null,
      "can_skip": false
    }}
  ],
  "handoff_index": 5,
  "estimated_time_saved_seconds": 8.0,
  "preconditions": []
}}\
"""


# ──────────────────────────────────────────────────────────────
# Analyzer function
# ──────────────────────────────────────────────────────────────


async def analyze_trace(
    simplified_trace: SimplifiedTrace,
    client: AsyncAnthropic | None = None,
    model: str = "claude-sonnet-4-6",
) -> dict[str, Any]:
    """
    Send the simplified trace to Claude for classification and template extraction.

    Args:
        simplified_trace: The cleaned trace from the simplifier.
        client: AsyncAnthropic client. If None, creates one from env.
        model: Claude model to use. Sonnet for accuracy, Haiku for speed.

    Returns:
        Parsed JSON dict with classification results.

    Raises:
        ValueError: If the LLM returns invalid JSON.
    """
    if client is None:
        client = AsyncAnthropic()

    trace_json = json.dumps(
        [asdict(step) for step in simplified_trace.steps],
        indent=2,
    )

    user_prompt = ANALYZER_USER_PROMPT.format(
        task_description=simplified_trace.task_description,
        trace_json=trace_json,
    )

    logger.info(
        "Analyzing trace with %d steps using %s", len(simplified_trace.steps), model
    )

    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=ANALYZER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.0,
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown fences if the model included them despite instructions
    raw_text = _strip_markdown_fences(raw_text)

    try:
        analysis = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error("LLM returned invalid JSON: %s", raw_text[:500])
        raise ValueError(
            f"LLM returned invalid JSON. First 500 chars: {raw_text[:500]}"
        ) from e

    # Basic validation of the response structure
    _validate_analysis_structure(analysis)

    logger.info(
        "Analysis complete: domain=%s, action_type=%s, %d steps, handoff_index=%d",
        analysis.get("domain"),
        analysis.get("action_type"),
        len(analysis.get("steps", [])),
        analysis.get("handoff_index", -1),
    )

    return analysis


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (may have language tag)
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _validate_analysis_structure(analysis: dict[str, Any]) -> None:
    """Raise ValueError if the analysis is missing required fields."""
    required_top = ["domain", "action_type", "task_pattern", "steps", "handoff_index"]
    missing = [f for f in required_top if f not in analysis]
    if missing:
        raise ValueError(f"LLM analysis missing required fields: {missing}")

    if not isinstance(analysis["steps"], list):
        raise ValueError("LLM analysis 'steps' must be a list")

    for i, step in enumerate(analysis["steps"]):
        if "classification" not in step:
            raise ValueError(f"Step {i} missing 'classification' field")
        if step["classification"] not in ("FIXED", "PARAMETERIZED", "DYNAMIC"):
            raise ValueError(
                f"Step {i} has invalid classification: {step['classification']}"
            )
