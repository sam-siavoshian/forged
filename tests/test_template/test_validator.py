"""Tests for the template validator."""

import pytest

from src.template.generator import (
    InternalTemplate,
    InternalTemplateParameter,
    InternalTemplateStep,
    TemplateSelector,
)
from src.template.validator import (
    ValidationSeverity,
    has_errors,
    validate_template,
    _is_plausible_css_selector,
)


def _make_valid_template() -> InternalTemplate:
    """A minimal valid template for testing."""
    return InternalTemplate(
        template_id="test-uuid",
        domain="amazon.com",
        action_type="search",
        task_pattern="search for {query} on Amazon",
        parameters=[
            InternalTemplateParameter(name="query", description="Search query", type="string", required=True)
        ],
        steps=[
            InternalTemplateStep(
                index=0,
                action="navigate",
                params={"url": "https://www.amazon.com"},
                classification="FIXED",
            ),
            InternalTemplateStep(
                index=1,
                action="click",
                params={"index": 3},
                classification="FIXED",
                selectors=TemplateSelector(primary="#twotabsearchtextbox", fallbacks=["input[name='field-keywords']"]),
            ),
            InternalTemplateStep(
                index=2,
                action="input",
                params={"index": 3, "text": "wireless mouse"},
                classification="PARAMETERIZED",
                parameter_name="query",
                parameter_field="text",
                selectors=TemplateSelector(primary="#twotabsearchtextbox"),
            ),
            InternalTemplateStep(
                index=3,
                action="click",
                params={"index": 15},
                classification="DYNAMIC",
                reasoning="Select the best product from results",
            ),
        ],
        handoff_index=2,
        preconditions=[],
        source_trace_id="trace-001",
        extraction_model="claude-sonnet-4-6",
        created_at="2026-04-04T00:00:00Z",
    )


class TestValidateTemplate:
    def test_valid_template_no_errors(self):
        template = _make_valid_template()
        issues = validate_template(template)
        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        assert len(errors) == 0

    def test_missing_domain_is_error(self):
        template = _make_valid_template()
        template.domain = ""
        issues = validate_template(template)
        assert has_errors(issues)
        assert any("domain" in i.field for i in issues)

    def test_missing_task_pattern_is_error(self):
        template = _make_valid_template()
        template.task_pattern = ""
        issues = validate_template(template)
        assert has_errors(issues)

    def test_no_steps_is_error(self):
        template = _make_valid_template()
        template.steps = []
        issues = validate_template(template)
        assert has_errors(issues)

    def test_negative_handoff_is_error(self):
        template = _make_valid_template()
        template.handoff_index = -1
        issues = validate_template(template)
        assert has_errors(issues)

    def test_handoff_exceeds_steps_is_error(self):
        template = _make_valid_template()
        template.handoff_index = 99
        issues = validate_template(template)
        assert has_errors(issues)

    def test_invalid_action_is_error(self):
        template = _make_valid_template()
        template.steps[0].action = "press_cmd_l"  # Human shortcut!
        issues = validate_template(template)
        assert has_errors(issues)
        assert any("Invalid action" in i.message for i in issues)

    def test_undefined_parameter_is_error(self):
        template = _make_valid_template()
        template.steps[2].parameter_name = "nonexistent_param"
        issues = validate_template(template)
        assert has_errors(issues)
        assert any("undefined parameter" in i.message for i in issues)

    def test_unused_parameter_is_warning(self):
        template = _make_valid_template()
        template.parameters.append(
            InternalTemplateParameter(name="unused", description="Not used", type="string")
        )
        issues = validate_template(template)
        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]
        assert any("never used" in i.message for i in warnings)

    def test_parameterized_without_name_is_error(self):
        template = _make_valid_template()
        template.steps[2].parameter_name = None
        issues = validate_template(template)
        assert has_errors(issues)

    def test_dynamic_without_reasoning_is_warning(self):
        template = _make_valid_template()
        template.steps[3].reasoning = None
        issues = validate_template(template)
        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]
        assert any("reasoning" in i.message for i in warnings)

    def test_click_without_selectors_is_warning(self):
        template = _make_valid_template()
        template.steps[1].selectors = None
        issues = validate_template(template)
        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]
        assert any("no selectors" in i.message for i in warnings)

    def test_human_shortcut_in_params_is_error(self):
        template = _make_valid_template()
        template.steps[0].params = {"keys": "cmd+l"}
        issues = validate_template(template)
        assert has_errors(issues)
        assert any("human keyboard shortcut" in i.message for i in issues)

    def test_step_after_handoff_not_dynamic_is_warning(self):
        template = _make_valid_template()
        # Change step 3 (after handoff=2) to FIXED
        template.steps[3].classification = "FIXED"
        issues = validate_template(template)
        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]
        assert any("after handoff_index" in i.message for i in warnings)

    def test_dynamic_before_handoff_is_warning(self):
        template = _make_valid_template()
        # Change step 1 (before handoff=2) to DYNAMIC
        template.steps[1].classification = "DYNAMIC"
        template.steps[1].reasoning = "Something"
        issues = validate_template(template)
        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]
        assert any("before handoff_index" in i.message or "at/before handoff_index" in i.message for i in warnings)


class TestHasErrors:
    def test_no_issues_no_errors(self):
        assert not has_errors([])

    def test_only_warnings_no_errors(self):
        from src.template.validator import ValidationIssue
        issues = [ValidationIssue(ValidationSeverity.WARNING, None, "x", "warning")]
        assert not has_errors(issues)

    def test_error_detected(self):
        from src.template.validator import ValidationIssue
        issues = [ValidationIssue(ValidationSeverity.ERROR, None, "x", "error")]
        assert has_errors(issues)


class TestCSSSelector:
    def test_valid_id_selector(self):
        assert _is_plausible_css_selector("#my-element")

    def test_valid_class_selector(self):
        assert _is_plausible_css_selector(".btn-primary")

    def test_valid_attribute_selector(self):
        assert _is_plausible_css_selector("[aria-label='Search']")

    def test_valid_complex_selector(self):
        assert _is_plausible_css_selector("input#search.form-control[type='text']")

    def test_empty_is_invalid(self):
        assert not _is_plausible_css_selector("")

    def test_url_is_invalid(self):
        assert not _is_plausible_css_selector("https://example.com")

    def test_too_long_is_invalid(self):
        assert not _is_plausible_css_selector("x" * 501)
