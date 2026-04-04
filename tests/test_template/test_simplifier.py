"""Tests for the trace simplifier."""

import pytest
from src.template.simplifier import simplify_trace, SimplifiedTrace, SimplifiedStep
from tests.test_template.fake_traces import (
    make_amazon_search_trace,
    make_google_search_trace,
    make_form_fill_trace,
    make_empty_trace,
    make_all_failed_trace,
    make_retry_noise_trace,
    make_single_step_trace,
)


class TestSimplifyTrace:
    def test_amazon_search_produces_correct_step_count(self):
        trace = make_amazon_search_trace()
        result = simplify_trace(trace, "Search for wireless mouse under $50 on Amazon")
        # 5 steps: navigate, click, input, send_keys, click
        assert len(result.steps) == 5

    def test_amazon_search_actions_match(self):
        trace = make_amazon_search_trace()
        result = simplify_trace(trace, "Search for wireless mouse under $50 on Amazon")
        actions = [s.action for s in result.steps]
        assert actions == ["navigate", "click", "input", "send_keys", "click"]

    def test_amazon_search_element_info_extracted(self):
        trace = make_amazon_search_trace()
        result = simplify_trace(trace, "Search for wireless mouse under $50 on Amazon")
        # Step 1 (click search box) should have element info
        click_step = result.steps[1]
        assert click_step.element_attributes is not None
        assert click_step.element_attributes["id"] == "twotabsearchtextbox"
        assert "Search Amazon" in click_step.element_description

    def test_google_search_produces_3_steps(self):
        trace = make_google_search_trace()
        result = simplify_trace(trace, "Search for python tutorial on Google")
        assert len(result.steps) == 3

    def test_form_fill_handles_multi_action_steps(self):
        trace = make_form_fill_trace()
        result = simplify_trace(trace, "Fill out contact form on example.com")
        # Step 3 has 2 actions (input + click), so total should be 5 or 6
        actions = [s.action for s in result.steps]
        assert "input" in actions
        assert "click" in actions
        assert len(result.steps) >= 5  # navigate + 3 inputs + click

    def test_trace_metadata_correct(self):
        trace = make_amazon_search_trace()
        result = simplify_trace(trace, "Search for wireless mouse under $50 on Amazon")
        assert result.task_description == "Search for wireless mouse under $50 on Amazon"
        assert result.success is True
        assert result.total_duration_seconds == 35.2
        assert result.trace_id  # Should be non-empty
        assert len(result.trace_id) == 16

    def test_urls_captured(self):
        trace = make_amazon_search_trace()
        result = simplify_trace(trace, "Search for wireless mouse under $50 on Amazon")
        # First step should have url_before = amazon.com (state url)
        assert "amazon.com" in result.steps[0].url_before or "amazon.com" in result.steps[0].url_after


class TestRetryNoiseRemoval:
    def test_retry_noise_removed(self):
        trace = make_retry_noise_trace()
        result = simplify_trace(trace, "Test retry noise")
        # Should have 2 steps: navigate + successful click (failed click removed)
        assert len(result.steps) == 2
        assert all(s.success for s in result.steps)

    def test_retry_noise_actions_correct(self):
        trace = make_retry_noise_trace()
        result = simplify_trace(trace, "Test retry noise")
        actions = [s.action for s in result.steps]
        assert actions == ["navigate", "click"]


class TestEdgeCases:
    def test_empty_trace(self):
        trace = make_empty_trace()
        result = simplify_trace(trace, "Empty task")
        assert len(result.steps) == 0
        assert result.success is False
        assert result.total_duration_seconds == 0.0

    def test_all_failed_trace(self):
        trace = make_all_failed_trace()
        result = simplify_trace(trace, "All failures")
        # All steps failed, so after retry noise removal some may remain
        assert result.success is False

    def test_single_step_trace(self):
        trace = make_single_step_trace()
        result = simplify_trace(trace, "Single step")
        assert len(result.steps) == 1
        assert result.steps[0].action == "navigate"
        assert result.success is True

    def test_step_indices_sequential(self):
        trace = make_amazon_search_trace()
        result = simplify_trace(trace, "Test indices")
        for i, step in enumerate(result.steps):
            assert step.step_index == i, f"Step {i} has index {step.step_index}"
