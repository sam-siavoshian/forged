"""Tests for the main extractor pipeline and parameter extraction."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.template.extractor import extract_parameters, extract_template_from_trace
from src.template.generator import InternalTemplate, InternalTemplateParameter
from tests.test_template.fake_traces import make_amazon_search_trace


def _mock_analyzer_response() -> dict:
    """A full valid analyzer response."""
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
                "action": "send_keys",
                "params": {"keys": "Enter"},
                "classification": "FIXED",
                "selectors": None,
                "parameter": None,
                "can_skip": False,
            },
            {
                "action": "click",
                "params": {"index": 15},
                "classification": "DYNAMIC",
                "selectors": None,
                "parameter": None,
                "reasoning": "Select the best product from results",
                "can_skip": False,
            },
        ],
        "handoff_index": 3,
        "estimated_time_saved_seconds": 10.0,
        "preconditions": [],
    }


def _make_mock_client(response_data: dict | str) -> AsyncMock:
    """Create a mock client returning given data."""
    client = AsyncMock()
    text = json.dumps(response_data) if isinstance(response_data, dict) else response_data
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=text)]
    client.messages.create = AsyncMock(return_value=mock_resp)
    return client


class TestExtractTemplateFromTrace:
    @pytest.mark.asyncio
    async def test_full_pipeline_succeeds(self):
        client = _make_mock_client(_mock_analyzer_response())
        trace = make_amazon_search_trace()

        template = await extract_template_from_trace(
            trace,
            "Search for wireless mouse under $50 on Amazon",
            client=client,
            model="claude-sonnet-4-6",
        )

        assert isinstance(template, InternalTemplate)
        assert template.domain == "amazon.com"
        assert template.action_type == "search"
        assert len(template.steps) == 5
        assert template.handoff_index == 3

    @pytest.mark.asyncio
    async def test_pipeline_raises_on_validation_error(self):
        # Return a response with an invalid action
        bad_response = _mock_analyzer_response()
        bad_response["steps"][0]["action"] = "press_cmd_l"
        client = _make_mock_client(bad_response)
        trace = make_amazon_search_trace()

        with pytest.raises(ValueError, match="validation failed"):
            await extract_template_from_trace(
                trace,
                "Search on Amazon",
                client=client,
            )

    @pytest.mark.asyncio
    async def test_pipeline_raises_on_empty_trace(self):
        from tests.test_template.fake_traces import make_empty_trace

        client = _make_mock_client(_mock_analyzer_response())
        trace = make_empty_trace()

        with pytest.raises(ValueError, match="no steps"):
            await extract_template_from_trace(trace, "Empty task", client=client)


class TestExtractParameters:
    @pytest.mark.asyncio
    async def test_extracts_single_param(self):
        param_response = {"query": "mechanical keyboard"}
        client = _make_mock_client(param_response)

        template = InternalTemplate(
            template_id="test",
            domain="amazon.com",
            action_type="search",
            task_pattern="search for {query} on Amazon",
            parameters=[
                InternalTemplateParameter(name="query", description="Search query", type="string", required=True)
            ],
            steps=[],
            handoff_index=0,
            preconditions=[],
            source_trace_id="x",
            extraction_model="x",
            created_at="x",
        )

        params = await extract_parameters(
            "Search for mechanical keyboard on Amazon",
            template,
            client=client,
        )

        assert params["query"] == "mechanical keyboard"

    @pytest.mark.asyncio
    async def test_raises_on_missing_required_param(self):
        param_response = {"query": None}  # Can't extract
        client = _make_mock_client(param_response)

        template = InternalTemplate(
            template_id="test",
            domain="amazon.com",
            action_type="search",
            task_pattern="search for {query} on Amazon",
            parameters=[
                InternalTemplateParameter(name="query", description="Search query", type="string", required=True)
            ],
            steps=[],
            handoff_index=0,
            preconditions=[],
            source_trace_id="x",
            extraction_model="x",
            created_at="x",
        )

        with pytest.raises(ValueError, match="Required parameter"):
            await extract_parameters("Do something", template, client=client)

    @pytest.mark.asyncio
    async def test_works_with_dict_template(self):
        param_response = {"product": "headphones"}
        client = _make_mock_client(param_response)

        template_dict = {
            "task_pattern": "buy {product} on Amazon",
            "parameters": [
                {"name": "product", "description": "Product to buy", "type": "string", "required": True}
            ],
        }

        params = await extract_parameters(
            "Buy headphones on Amazon",
            template_dict,
            client=client,
        )
        assert params["product"] == "headphones"

    @pytest.mark.asyncio
    async def test_empty_params_returns_empty(self):
        client = _make_mock_client({})
        template_dict = {"task_pattern": "go to example.com", "parameters": []}
        params = await extract_parameters("go to example.com", template_dict, client=client)
        assert params == {}
