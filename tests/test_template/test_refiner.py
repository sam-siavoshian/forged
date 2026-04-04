"""Tests for the template refiner."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.template.generator import (
    InternalTemplate,
    InternalTemplateParameter,
    InternalTemplateStep,
    TemplateSelector,
)
from src.template.refiner import apply_refinements, refine_template
from src.template.simplifier import SimplifiedStep, SimplifiedTrace


def _make_template() -> InternalTemplate:
    return InternalTemplate(
        template_id="tmpl-001",
        domain="amazon.com",
        action_type="search",
        task_pattern="search for {query} on Amazon",
        parameters=[
            InternalTemplateParameter(name="query", description="Search query")
        ],
        steps=[
            InternalTemplateStep(
                index=0,
                action="navigate",
                params={"url": "https://amazon.com"},
                classification="FIXED",
            ),
            InternalTemplateStep(
                index=1,
                action="click",
                params={"index": 3},
                classification="FIXED",
                selectors=TemplateSelector(
                    primary="#twotabsearchtextbox",
                    fallbacks=["input[name='field-keywords']"],
                ),
            ),
            InternalTemplateStep(
                index=2,
                action="input",
                params={"index": 3, "text": "wireless mouse"},
                classification="PARAMETERIZED",
                parameter_name="query",
                selectors=TemplateSelector(primary="#twotabsearchtextbox"),
            ),
            InternalTemplateStep(
                index=3,
                action="click",
                params={"index": 15},
                classification="DYNAMIC",
                reasoning="Pick the best product",
            ),
        ],
        handoff_index=2,
        preconditions=[],
        source_trace_id="trace-001",
        extraction_model="claude-sonnet-4-6",
        created_at="2026-04-04T00:00:00Z",
        version=1,
    )


def _make_trace() -> SimplifiedTrace:
    return SimplifiedTrace(
        trace_id="trace-002",
        task_description="Search for headphones on Amazon",
        final_url="https://amazon.com/dp/XYZ",
        success=True,
        total_duration_seconds=25.0,
        steps=[
            SimplifiedStep(0, "navigate", {"url": "https://amazon.com"}, "", "https://amazon.com"),
            SimplifiedStep(1, "click", {"index": 3}, "https://amazon.com", "https://amazon.com"),
            SimplifiedStep(2, "input", {"index": 3, "text": "headphones"}, "https://amazon.com", "https://amazon.com"),
            SimplifiedStep(3, "click", {"index": 22}, "https://amazon.com/s", "https://amazon.com/dp/XYZ"),
        ],
    )


def _make_mock_client(recommendations: list[dict]) -> AsyncMock:
    client = AsyncMock()
    resp = MagicMock()
    resp.content = [MagicMock(text=json.dumps({"recommendations": recommendations}))]
    client.messages.create = AsyncMock(return_value=resp)
    return client


class TestRefineTemplate:
    @pytest.mark.asyncio
    async def test_returns_high_confidence_recommendations(self):
        recs = [
            {"type": "NO_CHANGE", "step_index": None, "details": {}, "confidence": 0.95, "reasoning": "Works fine"},
        ]
        client = _make_mock_client(recs)
        template = _make_template()
        trace = _make_trace()

        result = await refine_template(template, trace, success=True, client=client)
        assert len(result) == 1
        assert result[0]["type"] == "NO_CHANGE"

    @pytest.mark.asyncio
    async def test_filters_low_confidence(self):
        recs = [
            {"type": "SELECTOR_UPDATE", "step_index": 1, "details": {}, "confidence": 0.3, "reasoning": "Maybe"},
            {"type": "NO_CHANGE", "step_index": None, "details": {}, "confidence": 0.9, "reasoning": "Fine"},
        ]
        client = _make_mock_client(recs)
        template = _make_template()
        trace = _make_trace()

        result = await refine_template(template, trace, success=True, client=client, min_confidence=0.8)
        assert len(result) == 1
        assert result[0]["type"] == "NO_CHANGE"

    @pytest.mark.asyncio
    async def test_handles_invalid_json_gracefully(self):
        client = AsyncMock()
        resp = MagicMock()
        resp.content = [MagicMock(text="not json at all")]
        client.messages.create = AsyncMock(return_value=resp)

        template = _make_template()
        trace = _make_trace()

        result = await refine_template(template, trace, success=True, client=client)
        assert result == []  # Graceful fallback


class TestApplyRefinements:
    def test_selector_update(self):
        template = _make_template()
        recs = [
            {
                "type": "SELECTOR_UPDATE",
                "step_index": 1,
                "details": {
                    "new_primary": "[data-testid='search-input']",
                    "new_fallbacks": ["#twotabsearchtextbox", "input[name='q']"],
                },
                "confidence": 0.95,
            }
        ]

        updated = apply_refinements(template, recs)
        assert updated.steps[1].selectors.primary == "[data-testid='search-input']"
        assert updated.version == 2
        # Original unchanged
        assert template.steps[1].selectors.primary == "#twotabsearchtextbox"
        assert template.version == 1

    def test_selector_addition(self):
        template = _make_template()
        recs = [
            {
                "type": "SELECTOR_ADDITION",
                "step_index": 1,
                "details": {"additional_fallbacks": ["[aria-label='Search']"]},
                "confidence": 0.9,
            }
        ]

        updated = apply_refinements(template, recs)
        assert "[aria-label='Search']" in updated.steps[1].selectors.fallbacks

    def test_handoff_extension(self):
        template = _make_template()
        assert template.handoff_index == 2

        recs = [
            {
                "type": "HANDOFF_EXTENSION",
                "step_index": None,
                "details": {"new_handoff_index": 3},
                "confidence": 0.85,
            }
        ]

        updated = apply_refinements(template, recs)
        assert updated.handoff_index == 3

    def test_handoff_extension_rejected_if_lower(self):
        template = _make_template()
        recs = [
            {
                "type": "HANDOFF_EXTENSION",
                "step_index": None,
                "details": {"new_handoff_index": 1},  # Lower than current
                "confidence": 0.9,
            }
        ]

        updated = apply_refinements(template, recs)
        assert updated.handoff_index == 2  # Unchanged

    def test_step_promotion(self):
        template = _make_template()
        assert template.steps[3].classification == "DYNAMIC"

        recs = [
            {
                "type": "STEP_PROMOTION",
                "step_index": 3,
                "details": {"new_classification": "FIXED"},
                "confidence": 0.9,
            }
        ]

        updated = apply_refinements(template, recs)
        assert updated.steps[3].classification == "FIXED"

    def test_no_change_is_noop(self):
        template = _make_template()
        recs = [{"type": "NO_CHANGE", "step_index": None, "details": {}, "confidence": 1.0}]

        updated = apply_refinements(template, recs)
        assert updated.version == 2  # Version bumps even on no-change
        assert len(updated.steps) == len(template.steps)

    def test_does_not_mutate_original(self):
        template = _make_template()
        original_primary = template.steps[1].selectors.primary

        recs = [
            {
                "type": "SELECTOR_UPDATE",
                "step_index": 1,
                "details": {"new_primary": "NEW_SELECTOR"},
                "confidence": 0.9,
            }
        ]

        apply_refinements(template, recs)
        assert template.steps[1].selectors.primary == original_primary
