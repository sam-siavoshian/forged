"""
Trace Simplifier — converts raw browser-use AgentHistoryList
into a clean, LLM-digestible SimplifiedTrace.

Responsibilities:
- Extract action, params, and result from each step
- Convert element indices to stable element descriptors (id, class, aria-label)
- Filter out failed-retry noise
- Remove dead-end exploration (go_back after failure)
- Produce a flat list of SimplifiedStep objects
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


# ──────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────


@dataclass
class SimplifiedStep:
    """A single step in the simplified trace."""

    step_index: int
    action: str  # browser-use action name
    params: dict[str, Any]  # action parameters
    url_before: str
    url_after: str
    element_description: str | None = None  # e.g. "input#search-box[placeholder='Search']"
    element_attributes: dict[str, Any] | None = None  # id, class, aria-label, etc.
    success: bool = True
    error: str | None = None
    duration_ms: int | None = None


@dataclass
class SimplifiedTrace:
    """Complete simplified trace ready for LLM analysis."""

    trace_id: str
    task_description: str
    final_url: str
    success: bool
    total_duration_seconds: float
    steps: list[SimplifiedStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def steps_as_dicts(self) -> list[dict[str, Any]]:
        return [asdict(s) for s in self.steps]


# ──────────────────────────────────────────────────────────────
# Valid browser-use actions (template steps MUST use these)
# ──────────────────────────────────────────────────────────────

VALID_ACTIONS = frozenset(
    {
        "search",
        "navigate",
        "go_back",
        "wait",
        "click",
        "input",
        "upload_file",
        "scroll",
        "find_text",
        "send_keys",
        "evaluate",
        "switch_tab",
        "close_tab",
        "extract",
        "screenshot",
        "dropdown_options",
        "select_dropdown",
        "write_file",
        "read_file",
        "done",
    }
)


# ──────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────


def simplify_trace(
    history: Any,  # AgentHistoryList from browser-use
    task_description: str,
) -> SimplifiedTrace:
    """
    Convert a raw browser-use AgentHistoryList into a SimplifiedTrace.

    1. Extracts action + params + result from each step
    2. Removes LLM reasoning (not needed for templates)
    3. Filters out failed steps that were retried successfully
    4. Captures element descriptions from the DOM snapshot
    """
    trace_id = hashlib.sha256(
        f"{task_description}:{time.time()}".encode()
    ).hexdigest()[:16]

    raw_steps: list[SimplifiedStep] = []
    urls = _safe_urls(history)

    for i, entry in enumerate(history.history):
        model_output = entry.model_output
        result = entry.result
        state = entry.state

        if model_output is None:
            continue

        # Each step can have multiple actions (max_actions_per_step)
        actions = _extract_actions(model_output)
        for action_name, action_params in actions:
            # Extract element info for click/input actions
            element_desc = None
            element_attrs = None
            if action_name in (
                "click",
                "input",
                "select_dropdown",
                "dropdown_options",
                "upload_file",
            ):
                element_index = action_params.get("index")
                if element_index is not None and state and hasattr(state, "element_tree"):
                    element_desc, element_attrs = _extract_element_info(
                        state.element_tree, element_index
                    )

            step_success = result is not None and (
                not hasattr(result, "error") or result.error is None
            )
            step_error = None
            if result and hasattr(result, "error") and result.error:
                step_error = str(result.error)

            raw_steps.append(
                SimplifiedStep(
                    step_index=len(raw_steps),
                    action=action_name,
                    params=action_params,
                    url_before=state.url if state and hasattr(state, "url") else "",
                    url_after=(
                        urls[i + 1]
                        if i + 1 < len(urls)
                        else (state.url if state and hasattr(state, "url") else "")
                    ),
                    element_description=element_desc,
                    element_attributes=element_attrs,
                    success=step_success,
                    error=step_error,
                )
            )

    # Clean up noise
    cleaned = _remove_retry_noise(raw_steps)
    cleaned = _remove_dead_ends(cleaned)

    # Re-index
    for i, step in enumerate(cleaned):
        step.step_index = i

    return SimplifiedTrace(
        trace_id=trace_id,
        task_description=task_description,
        final_url=urls[-1] if urls else "",
        success=_is_done(history),
        total_duration_seconds=_total_duration(history),
        steps=cleaned,
    )


# ──────────────────────────────────────────────────────────────
# Action extraction helpers
# ──────────────────────────────────────────────────────────────


def _extract_actions(model_output: Any) -> list[tuple[str, dict[str, Any]]]:
    """Extract (action_name, params) pairs from a browser-use model output."""
    results: list[tuple[str, dict[str, Any]]] = []

    # browser-use model_output has an .actions list of pydantic models
    actions_list = getattr(model_output, "actions", None)
    if actions_list is None:
        return results

    for action in actions_list:
        action_name = _get_action_name(action)
        action_params = _get_action_params(action)
        if action_name and action_name != "unknown":
            results.append((action_name, action_params))

    return results


def _get_action_name(action: Any) -> str:
    """Extract the action name from a browser-use ActionModel."""
    # browser-use actions are pydantic models with one non-None field
    if hasattr(action, "model_fields"):
        for field_name in action.model_fields:
            if getattr(action, field_name, None) is not None:
                return field_name
    # Fallback: try dict-like access
    if isinstance(action, dict):
        for k, v in action.items():
            if v is not None:
                return k
    return "unknown"


def _get_action_params(action: Any) -> dict[str, Any]:
    """Extract the action parameters as a plain dict."""
    if hasattr(action, "model_fields"):
        for field_name in action.model_fields:
            value = getattr(action, field_name, None)
            if value is not None:
                if hasattr(value, "model_dump"):
                    return value.model_dump()
                elif isinstance(value, dict):
                    return value
                else:
                    return {"value": value}
    if isinstance(action, dict):
        for k, v in action.items():
            if v is not None:
                if isinstance(v, dict):
                    return v
                return {"value": v}
    return {}


# ──────────────────────────────────────────────────────────────
# Element info extraction
# ──────────────────────────────────────────────────────────────


def _extract_element_info(
    element_tree: Any, index: int
) -> tuple[str | None, dict[str, Any] | None]:
    """
    Given a browser-use element tree and an element index,
    extract a human-readable description and stable attributes.
    """
    try:
        elements = element_tree.get_clickable_elements()
        for elem in elements:
            if getattr(elem, "highlight_index", None) == index:
                attrs = {
                    "tag": getattr(elem, "tag_name", None),
                    "id": elem.attributes.get("id") if hasattr(elem, "attributes") else None,
                    "class": elem.attributes.get("class") if hasattr(elem, "attributes") else None,
                    "name": elem.attributes.get("name") if hasattr(elem, "attributes") else None,
                    "type": elem.attributes.get("type") if hasattr(elem, "attributes") else None,
                    "aria-label": (
                        elem.attributes.get("aria-label")
                        if hasattr(elem, "attributes")
                        else None
                    ),
                    "placeholder": (
                        elem.attributes.get("placeholder")
                        if hasattr(elem, "attributes")
                        else None
                    ),
                    "text": (
                        elem.text_content[:200]
                        if hasattr(elem, "text_content") and elem.text_content
                        else None
                    ),
                    "role": elem.attributes.get("role") if hasattr(elem, "attributes") else None,
                    "data-testid": (
                        elem.attributes.get("data-testid")
                        if hasattr(elem, "attributes")
                        else None
                    ),
                    "href": elem.attributes.get("href") if hasattr(elem, "attributes") else None,
                }
                # Strip None values
                attrs = {k: v for k, v in attrs.items() if v is not None}
                description = _build_element_description(
                    attrs.get("tag", "element"), attrs
                )
                return description, attrs
    except Exception:
        pass
    return None, None


def _build_element_description(tag: str, attrs: dict[str, Any]) -> str:
    """Build a CSS-selector-like description: input#search-box[placeholder='Search']."""
    parts = [tag]
    if attrs.get("id"):
        parts.append(f"#{attrs['id']}")
    if attrs.get("class"):
        classes = str(attrs["class"]).split()[:3]
        parts.extend(f".{c}" for c in classes)
    if attrs.get("aria-label"):
        parts.append(f'[aria-label="{attrs["aria-label"]}"]')
    if attrs.get("placeholder"):
        parts.append(f'[placeholder="{attrs["placeholder"]}"]')
    if attrs.get("text") and len(str(attrs["text"])) < 50:
        parts.append(f' "{attrs["text"]}"')
    return "".join(parts)


# ──────────────────────────────────────────────────────────────
# Noise removal
# ──────────────────────────────────────────────────────────────


def _remove_retry_noise(steps: list[SimplifiedStep]) -> list[SimplifiedStep]:
    """
    Remove failed steps that were immediately retried successfully.
    Pattern: step N failed, step N+1 is same action on same URL and succeeded → drop N.
    """
    if not steps:
        return steps

    cleaned: list[SimplifiedStep] = []
    i = 0
    while i < len(steps):
        if (
            not steps[i].success
            and i + 1 < len(steps)
            and steps[i + 1].success
            and steps[i].action == steps[i + 1].action
            and steps[i].url_before == steps[i + 1].url_before
        ):
            # Skip failed step, keep the successful retry
            i += 1
            continue
        cleaned.append(steps[i])
        i += 1
    return cleaned


def _remove_dead_ends(steps: list[SimplifiedStep]) -> list[SimplifiedStep]:
    """
    Remove go_back steps that follow a failure (dead-end exploration).
    Pattern: step N-1 failed, step N is go_back, step N+1 is a different navigation.
    """
    if not steps:
        return steps

    cleaned: list[SimplifiedStep] = []
    i = 0
    while i < len(steps):
        if (
            steps[i].action == "go_back"
            and i + 1 < len(steps)
            and steps[i + 1].action in ("navigate", "click")
            and i >= 1
            and not steps[i - 1].success
        ):
            # Skip the go_back, keep the corrected navigation
            i += 1
            continue
        cleaned.append(steps[i])
        i += 1
    return cleaned


# ──────────────────────────────────────────────────────────────
# Safe accessors for browser-use history (handles missing attrs)
# ──────────────────────────────────────────────────────────────


def _safe_urls(history: Any) -> list[str]:
    try:
        return history.urls()
    except Exception:
        return []


def _is_done(history: Any) -> bool:
    try:
        return history.is_done()
    except Exception:
        return False


def _total_duration(history: Any) -> float:
    try:
        return history.total_duration_seconds()
    except Exception:
        return 0.0
