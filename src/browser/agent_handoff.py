"""Prompts for handing off from Playwright rocket to browser-use agent."""

from __future__ import annotations

from typing import Literal

from src.models import RocketResult

HandoffBranch = Literal["none", "full", "partial"]


def build_agent_handoff_prompt(
    task: str,
    rocket_result: RocketResult | None,
    step_summary: str | None = None,
    remaining_dynamic_steps: list[str] | None = None,
) -> tuple[str, bool, HandoffBranch]:
    """Build the agent task string after rocket, and whether URL auto-open should be skipped.

    Args:
        task: The original user task.
        rocket_result: Outcome of the Playwright phase.
        step_summary: Optional per-step summary of what rocket did.
        remaining_dynamic_steps: Descriptions of DYNAMIC template steps that
            still need to happen after the forged steps. These tell the agent
            exactly what work remains (scroll, extract, interact, etc.).

    Returns:
        (prompt, skip_initial_url_open, branch)
        ``skip_initial_url_open`` is True when rocket already ran at least one step.
    """
    if rocket_result is None or rocket_result.steps_completed <= 0:
        return task, False, "none"

    n = rocket_result.steps_completed
    total = rocket_result.total_steps
    url = (rocket_result.current_url or "").strip()
    url_part = f" Current page: {url}" if url else ""

    summary_part = ""
    if step_summary:
        summary_part = f"\n\nAutomation status:\n{step_summary}"

    skipped = rocket_result.skipped_steps
    skip_part = ""
    if skipped:
        skip_part = f" ({len(skipped)} step(s) were skipped as not needed for this task.)"

    # Build remaining work description from dynamic step descriptions
    remaining_part = ""
    if remaining_dynamic_steps:
        steps_text = "\n".join(f"  - {s}" for s in remaining_dynamic_steps)
        remaining_part = f"\n\nRemaining work:\n{steps_text}"

    done_all = (
        not rocket_result.aborted
        and total > 0
        and n >= total
    )

    if done_all:
        if remaining_dynamic_steps:
            # Forged steps done but dynamic steps remain (scroll, extract, etc.)
            prompt = (
                f"Goal: {task}\n\n"
                f"Playwright finished all {n} scripted steps (navigation, search, form fills).{skip_part}{url_part}"
                f"{summary_part}{remaining_part}\n\n"
                f"The page is ready. Do NOT re-navigate or re-search. "
                f"Complete the remaining work described above from the current page state."
            )
        else:
            # Everything is truly done, just read and answer
            prompt = (
                f"Goal: {task}\n\n"
                f"Playwright already finished all {n} scripted steps.{skip_part}{url_part}"
                f"{summary_part}\n"
                f"Do not navigate, search, or sort again unless the page is clearly wrong. "
                f"Read the visible page and answer the goal in a short reply."
            )
        return prompt, True, "full"

    abort = ""
    if rocket_result.aborted and rocket_result.abort_reason:
        abort = f" Stopped early: {rocket_result.abort_reason}"

    prompt = (
        f"Goal: {task}\n\n"
        f"Only {n} of {total} Playwright steps ran.{abort}{skip_part}{url_part}"
        f"{summary_part}{remaining_part}\n"
        f"Complete what is left from this state."
    )
    return prompt, True, "partial"
