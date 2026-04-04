"""
Template Validator — validates templates before storage.

Checks:
- All actions are from the browser-use action space
- CSS selectors are syntactically plausible
- Parameters are referenced and defined
- Handoff index is consistent with step classifications
- No human-oriented shortcuts (Cmd+L, etc.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from src.template.generator import InternalTemplate
from src.template.simplifier import VALID_ACTIONS


class ValidationSeverity(Enum):
    ERROR = "error"  # Template is broken, cannot use
    WARNING = "warning"  # May have issues, but usable
    INFO = "info"  # Suggestion for improvement


@dataclass
class ValidationIssue:
    severity: ValidationSeverity
    step_index: int | None
    field: str
    message: str


# Actions that interact with page elements and need selectors
ACTIONS_NEEDING_SELECTORS = frozenset(
    {"click", "input", "select_dropdown", "dropdown_options", "upload_file"}
)

# Human shortcuts that should NEVER appear in templates
HUMAN_SHORTCUTS = frozenset(
    {
        "cmd+l",
        "ctrl+l",
        "cmd+t",
        "ctrl+t",
        "cmd+w",
        "ctrl+w",
        "cmd+r",
        "ctrl+r",
        "cmd+f",
        "ctrl+f",
        "alt+tab",
        "cmd+shift+t",
    }
)


def validate_template(template: InternalTemplate) -> list[ValidationIssue]:
    """
    Validate a template for correctness and completeness.

    Returns a list of issues. If any issue has severity ERROR,
    the template should NOT be stored.
    """
    issues: list[ValidationIssue] = []

    # ── Top-level checks ──

    if not template.domain:
        issues.append(
            ValidationIssue(ValidationSeverity.ERROR, None, "domain", "Template must have a domain.")
        )

    if not template.task_pattern:
        issues.append(
            ValidationIssue(
                ValidationSeverity.ERROR,
                None,
                "task_pattern",
                "Template must have a task_pattern.",
            )
        )

    if not template.steps:
        issues.append(
            ValidationIssue(ValidationSeverity.ERROR, None, "steps", "Template has no steps.")
        )
        return issues  # Nothing else to check

    if template.handoff_index < 0:
        issues.append(
            ValidationIssue(
                ValidationSeverity.ERROR,
                None,
                "handoff_index",
                "handoff_index cannot be negative.",
            )
        )

    if template.handoff_index >= len(template.steps):
        issues.append(
            ValidationIssue(
                ValidationSeverity.ERROR,
                None,
                "handoff_index",
                f"handoff_index ({template.handoff_index}) exceeds step count ({len(template.steps)}).",
            )
        )

    # ── Parameter consistency ──

    defined_params = {p.name for p in template.parameters}
    used_params: set[str] = set()

    for step in template.steps:
        if step.parameter_name:
            used_params.add(step.parameter_name)
            if step.parameter_name not in defined_params:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        step.index,
                        "parameter_name",
                        f"Step references undefined parameter '{step.parameter_name}'. "
                        f"Defined: {defined_params}",
                    )
                )

    for param in template.parameters:
        if param.name not in used_params:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.WARNING,
                    None,
                    f"parameters.{param.name}",
                    f"Parameter '{param.name}' is defined but never used.",
                )
            )

    # ── Per-step checks ──

    for step in template.steps:
        # Valid action?
        if step.action not in VALID_ACTIONS:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    step.index,
                    "action",
                    f"Invalid action '{step.action}'. Must be one of: {sorted(VALID_ACTIONS)}",
                )
            )

        # Check for human shortcuts in params
        _check_for_human_shortcuts(step, issues)

        # Selector checks for element-targeting actions
        if (
            step.classification in ("FIXED", "PARAMETERIZED")
            and step.action in ACTIONS_NEEDING_SELECTORS
            and step.selectors is None
        ):
            issues.append(
                ValidationIssue(
                    ValidationSeverity.WARNING,
                    step.index,
                    "selectors",
                    f"Step is {step.classification} with action '{step.action}' "
                    "but has no selectors. Replay may fail.",
                )
            )

        # Validate CSS selectors
        if step.selectors:
            if step.selectors.primary and not _is_plausible_css_selector(
                step.selectors.primary
            ):
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.WARNING,
                        step.index,
                        "selectors.primary",
                        f"Primary selector looks invalid: '{step.selectors.primary}'",
                    )
                )
            for i, fb in enumerate(step.selectors.fallbacks):
                if not _is_plausible_css_selector(fb):
                    issues.append(
                        ValidationIssue(
                            ValidationSeverity.WARNING,
                            step.index,
                            f"selectors.fallbacks[{i}]",
                            f"Fallback selector looks invalid: '{fb}'",
                        )
                    )

        # PARAMETERIZED must name a parameter
        if step.classification == "PARAMETERIZED" and not step.parameter_name:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    step.index,
                    "parameter_name",
                    "PARAMETERIZED step must specify a parameter_name.",
                )
            )

        # DYNAMIC should have reasoning
        if step.classification == "DYNAMIC" and not step.reasoning:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.WARNING,
                    step.index,
                    "reasoning",
                    "DYNAMIC step should have reasoning explaining what the agent decides.",
                )
            )

    # ── Structural checks ──

    for step in template.steps:
        if step.index > template.handoff_index and step.classification != "DYNAMIC":
            issues.append(
                ValidationIssue(
                    ValidationSeverity.WARNING,
                    step.index,
                    "classification",
                    f"Step after handoff_index ({template.handoff_index}) is "
                    f"'{step.classification}', not 'DYNAMIC'.",
                )
            )
        if step.index <= template.handoff_index and step.classification == "DYNAMIC":
            issues.append(
                ValidationIssue(
                    ValidationSeverity.WARNING,
                    step.index,
                    "classification",
                    f"Step at/before handoff_index ({template.handoff_index}) is "
                    "'DYNAMIC'. Consider moving handoff_index earlier.",
                )
            )

    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    """Check if any issues are severity ERROR."""
    return any(i.severity == ValidationSeverity.ERROR for i in issues)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _is_plausible_css_selector(selector: str) -> bool:
    """Basic check that a string looks like a CSS selector."""
    if not selector or len(selector) > 500:
        return False
    # Must contain at least one selector-ish character
    if not re.search(r"[#.\[\]a-zA-Z]", selector):
        return False
    # Should not contain obvious non-CSS content
    if any(bad in selector for bad in ["http://", "https://", "javascript:", "<", ">"]):
        return False
    return True


def _check_for_human_shortcuts(step: Any, issues: list[ValidationIssue]) -> None:
    """Check for human keyboard shortcuts in step params."""
    params_str = str(step.params).lower()
    for shortcut in HUMAN_SHORTCUTS:
        if shortcut in params_str:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    step.index,
                    "params",
                    f"Step contains human keyboard shortcut '{shortcut}'. "
                    "Templates must use agent-native actions only.",
                )
            )
