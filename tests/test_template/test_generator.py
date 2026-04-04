"""Tests for the template generator."""

import pytest

from src.template.generator import (
    InternalTemplate,
    InternalTemplateParameter,
    InternalTemplateStep,
    TemplateSelector,
    generate_template,
    template_to_db_format,
    _infer_parameter_field,
    _infer_wait_time,
)


def _mock_analysis() -> dict:
    return {
        "domain": "amazon.com",
        "action_type": "search",
        "task_pattern": "search for {query} on Amazon",
        "parameters": [
            {"name": "query", "description": "Search query", "type": "string", "required": True}
        ],
        "steps": [
            {
                "action": "navigate",
                "params": {"url": "https://www.amazon.com"},
                "classification": "FIXED",
                "selectors": None,
                "parameter": None,
                "can_skip": False,
            },
            {
                "action": "click",
                "params": {"index": 3},
                "classification": "FIXED",
                "selectors": {
                    "primary": "#twotabsearchtextbox",
                    "fallbacks": ["input[name='field-keywords']"],
                    "text_fallback": "Search Amazon",
                },
                "parameter": None,
                "can_skip": False,
            },
            {
                "action": "input",
                "params": {"index": 3, "text": "wireless mouse"},
                "classification": "PARAMETERIZED",
                "selectors": {
                    "primary": "#twotabsearchtextbox",
                    "fallbacks": [],
                    "text_fallback": None,
                },
                "parameter": {"name": "query", "description": "Search query"},
                "can_skip": False,
            },
            {
                "action": "click",
                "params": {"index": 15},
                "classification": "DYNAMIC",
                "selectors": None,
                "parameter": None,
                "reasoning": "Select the best matching product from search results",
                "can_skip": False,
            },
        ],
        "handoff_index": 2,
        "estimated_time_saved_seconds": 8.0,
        "preconditions": [],
    }


class TestGenerateTemplate:
    def test_basic_generation(self):
        analysis = _mock_analysis()
        template = generate_template(analysis, "trace-001", "claude-sonnet-4-6")

        assert template.domain == "amazon.com"
        assert template.action_type == "search"
        assert template.task_pattern == "search for {query} on Amazon"
        assert template.handoff_index == 2
        assert len(template.steps) == 4
        assert len(template.parameters) == 1
        assert template.parameters[0].name == "query"

    def test_step_classifications(self):
        analysis = _mock_analysis()
        template = generate_template(analysis, "trace-001", "claude-sonnet-4-6")

        assert template.steps[0].classification == "FIXED"
        assert template.steps[1].classification == "FIXED"
        assert template.steps[2].classification == "PARAMETERIZED"
        assert template.steps[3].classification == "DYNAMIC"

    def test_selectors_extracted(self):
        analysis = _mock_analysis()
        template = generate_template(analysis, "trace-001", "claude-sonnet-4-6")

        click_step = template.steps[1]
        assert click_step.selectors is not None
        assert click_step.selectors.primary == "#twotabsearchtextbox"
        assert "input[name='field-keywords']" in click_step.selectors.fallbacks
        assert click_step.selectors.text_fallback == "Search Amazon"

    def test_parameter_name_assigned(self):
        analysis = _mock_analysis()
        template = generate_template(analysis, "trace-001", "claude-sonnet-4-6")

        param_step = template.steps[2]
        assert param_step.parameter_name == "query"
        assert param_step.parameter_field == "text"  # inferred for "input" action

    def test_can_skip_steps_removed(self):
        analysis = _mock_analysis()
        analysis["steps"].insert(1, {
            "action": "wait",
            "params": {},
            "classification": "FIXED",
            "selectors": None,
            "parameter": None,
            "can_skip": True,
        })
        template = generate_template(analysis, "trace-001", "claude-sonnet-4-6")

        actions = [s.action for s in template.steps]
        # The skipped wait should not appear (or if it does, it's still 4 non-skip steps)
        assert len(template.steps) == 4  # same as without the skipped step

    def test_handoff_index_clamped(self):
        analysis = _mock_analysis()
        analysis["handoff_index"] = 999  # Way too high
        template = generate_template(analysis, "trace-001", "claude-sonnet-4-6")
        assert template.handoff_index < len(template.steps)

    def test_negative_handoff_clamped(self):
        analysis = _mock_analysis()
        analysis["handoff_index"] = -5
        template = generate_template(analysis, "trace-001", "claude-sonnet-4-6")
        assert template.handoff_index >= 0

    def test_template_id_is_uuid(self):
        analysis = _mock_analysis()
        template = generate_template(analysis, "trace-001", "claude-sonnet-4-6")
        # UUID format: 8-4-4-4-12
        assert len(template.template_id) == 36
        assert template.template_id.count("-") == 4

    def test_metadata_fields(self):
        analysis = _mock_analysis()
        template = generate_template(analysis, "trace-001", "claude-sonnet-4-6")

        assert template.source_trace_id == "trace-001"
        assert template.extraction_model == "claude-sonnet-4-6"
        assert template.version == 1
        assert template.success_count == 0
        assert template.failure_count == 0
        assert template.confidence == 0.5


class TestTemplateToDB:
    def test_db_format_has_required_fields(self):
        analysis = _mock_analysis()
        template = generate_template(analysis, "trace-001", "claude-sonnet-4-6")
        db = template_to_db_format(template)

        assert "domain" in db
        assert "action_type" in db
        assert "task_pattern" in db
        assert "parameters" in db
        assert "steps" in db
        assert "handoff_index" in db

    def test_step_type_is_lowercase(self):
        analysis = _mock_analysis()
        template = generate_template(analysis, "trace-001", "claude-sonnet-4-6")
        db = template_to_db_format(template)

        for step in db["steps"]:
            assert step["type"] in ("fixed", "parameterized", "dynamic")

    def test_dynamic_step_has_agent_needed(self):
        analysis = _mock_analysis()
        template = generate_template(analysis, "trace-001", "claude-sonnet-4-6")
        db = template_to_db_format(template)

        dynamic_steps = [s for s in db["steps"] if s["type"] == "dynamic"]
        assert len(dynamic_steps) > 0
        for s in dynamic_steps:
            assert s.get("agent_needed") is True


class TestInferParameterField:
    def test_input_maps_to_text(self):
        assert _infer_parameter_field("input", {"name": "q"}) == "text"

    def test_navigate_maps_to_url(self):
        assert _infer_parameter_field("navigate", {"name": "dest"}) == "url"

    def test_search_maps_to_query(self):
        assert _infer_parameter_field("search", {"name": "q"}) == "query"

    def test_none_param_returns_none(self):
        assert _infer_parameter_field("click", None) is None

    def test_unknown_action_defaults_to_value(self):
        assert _infer_parameter_field("scroll", {"name": "x"}) == "value"


class TestInferWaitTime:
    def test_navigate_waits_longest(self):
        assert _infer_wait_time("navigate") == 2000

    def test_input_waits_shortest(self):
        assert _infer_wait_time("input") == 200

    def test_unknown_action_gets_default(self):
        assert _infer_wait_time("unknown_action") == 100
