"""Tests for the LLM analyzer — mocks the Anthropic API."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.template.analyzer import (
    ANALYZER_SYSTEM_PROMPT,
    analyze_trace,
    _strip_markdown_fences,
    _validate_analysis_structure,
)
from src.template.simplifier import SimplifiedStep, SimplifiedTrace


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


def _make_simple_trace() -> SimplifiedTrace:
    return SimplifiedTrace(
        trace_id="test123",
        task_description="Search for wireless mouse on Amazon",
        final_url="https://www.amazon.com/s?k=wireless+mouse",
        success=True,
        total_duration_seconds=30.0,
        steps=[
            SimplifiedStep(
                step_index=0,
                action="navigate",
                params={"url": "https://www.amazon.com"},
                url_before="about:blank",
                url_after="https://www.amazon.com",
            ),
            SimplifiedStep(
                step_index=1,
                action="click",
                params={"index": 3},
                url_before="https://www.amazon.com",
                url_after="https://www.amazon.com",
                element_description="input#twotabsearchtextbox",
                element_attributes={"id": "twotabsearchtextbox", "tag": "input"},
            ),
            SimplifiedStep(
                step_index=2,
                action="input",
                params={"index": 3, "text": "wireless mouse"},
                url_before="https://www.amazon.com",
                url_after="https://www.amazon.com",
                element_description="input#twotabsearchtextbox",
                element_attributes={"id": "twotabsearchtextbox", "tag": "input"},
            ),
        ],
    )


def _mock_llm_response() -> dict:
    """A realistic LLM analysis response."""
    return {
        "domain": "amazon.com",
        "action_type": "search",
        "task_pattern": "search for {query} on Amazon",
        "parameters": [
            {
                "name": "query",
                "description": "The search query",
                "type": "string",
                "required": True,
            }
        ],
        "steps": [
            {
                "original_step_index": 0,
                "action": "navigate",
                "params": {"url": "https://www.amazon.com"},
                "classification": "FIXED",
                "selectors": None,
                "parameter": None,
                "reasoning": None,
                "can_skip": False,
            },
            {
                "original_step_index": 1,
                "action": "click",
                "params": {"index": 3},
                "classification": "FIXED",
                "selectors": {
                    "primary": "#twotabsearchtextbox",
                    "fallbacks": ["input[name='field-keywords']"],
                    "text_fallback": None,
                },
                "parameter": None,
                "reasoning": None,
                "can_skip": False,
            },
            {
                "original_step_index": 2,
                "action": "input",
                "params": {"index": 3, "text": "wireless mouse"},
                "classification": "PARAMETERIZED",
                "selectors": {
                    "primary": "#twotabsearchtextbox",
                    "fallbacks": ["input[name='field-keywords']"],
                    "text_fallback": None,
                },
                "parameter": {
                    "name": "query",
                    "description": "The search query",
                    "source": "task description",
                },
                "reasoning": None,
                "can_skip": False,
            },
        ],
        "handoff_index": 2,
        "estimated_time_saved_seconds": 6.0,
        "preconditions": [],
    }


def _make_mock_client(response_data: dict) -> AsyncMock:
    """Create a mock AsyncAnthropic client that returns the given JSON."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(response_data))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    return mock_client


# ──────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────


class TestAnalyzeTrace:
    @pytest.mark.asyncio
    async def test_returns_valid_analysis(self):
        response_data = _mock_llm_response()
        client = _make_mock_client(response_data)
        trace = _make_simple_trace()

        result = await analyze_trace(trace, client=client)

        assert result["domain"] == "amazon.com"
        assert result["action_type"] == "search"
        assert len(result["steps"]) == 3
        assert result["handoff_index"] == 2

    @pytest.mark.asyncio
    async def test_passes_correct_model(self):
        response_data = _mock_llm_response()
        client = _make_mock_client(response_data)
        trace = _make_simple_trace()

        await analyze_trace(trace, client=client, model="claude-haiku-4-5-20251001")

        call_kwargs = client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"

    @pytest.mark.asyncio
    async def test_system_prompt_forbids_human_shortcuts(self):
        assert "NEVER suggest human-oriented actions" in ANALYZER_SYSTEM_PROMPT
        assert "Cmd+L" in ANALYZER_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_raises_on_invalid_json(self):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is not JSON at all")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        trace = _make_simple_trace()

        with pytest.raises(ValueError, match="invalid JSON"):
            await analyze_trace(trace, client=mock_client)

    @pytest.mark.asyncio
    async def test_raises_on_missing_fields(self):
        incomplete = {"domain": "test.com"}  # Missing steps, handoff_index, etc.
        client = _make_mock_client(incomplete)
        trace = _make_simple_trace()

        with pytest.raises(ValueError, match="missing required fields"):
            await analyze_trace(trace, client=client)


class TestStripMarkdownFences:
    def test_strips_json_fences(self):
        text = '```json\n{"key": "value"}\n```'
        assert _strip_markdown_fences(text) == '{"key": "value"}'

    def test_strips_plain_fences(self):
        text = '```\n{"key": "value"}\n```'
        assert _strip_markdown_fences(text) == '{"key": "value"}'

    def test_no_fences_unchanged(self):
        text = '{"key": "value"}'
        assert _strip_markdown_fences(text) == '{"key": "value"}'


class TestValidateAnalysisStructure:
    def test_valid_structure_passes(self):
        data = _mock_llm_response()
        _validate_analysis_structure(data)  # Should not raise

    def test_missing_domain_raises(self):
        data = {"action_type": "search", "task_pattern": "x", "steps": [], "handoff_index": 0}
        with pytest.raises(ValueError, match="missing required fields"):
            _validate_analysis_structure(data)

    def test_invalid_classification_raises(self):
        data = _mock_llm_response()
        data["steps"][0]["classification"] = "INVALID"
        with pytest.raises(ValueError, match="invalid classification"):
            _validate_analysis_structure(data)
