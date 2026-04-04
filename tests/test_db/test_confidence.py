"""Tests for confidence scoring formula.

Verifies the confidence update formula:
- Success: confidence += 0.1 * (1.0 - confidence)
- Failure: confidence -= 0.2 * confidence
"""

import pytest


def confidence_after_success(confidence: float) -> float:
    """Apply the success formula."""
    return confidence + 0.1 * (1.0 - confidence)


def confidence_after_failure(confidence: float) -> float:
    """Apply the failure formula."""
    return confidence - 0.2 * confidence


class TestConfidenceFormula:
    """Test the confidence update formula produces correct values."""

    def test_success_from_050(self):
        assert confidence_after_success(0.50) == pytest.approx(0.55)

    def test_success_from_070(self):
        assert confidence_after_success(0.70) == pytest.approx(0.73)

    def test_success_from_090(self):
        assert confidence_after_success(0.90) == pytest.approx(0.91)

    def test_success_from_030(self):
        result = confidence_after_success(0.30)
        assert result == pytest.approx(0.37)

    def test_failure_from_050(self):
        assert confidence_after_failure(0.50) == pytest.approx(0.40)

    def test_failure_from_070(self):
        assert confidence_after_failure(0.70) == pytest.approx(0.56)

    def test_failure_from_090(self):
        assert confidence_after_failure(0.90) == pytest.approx(0.72)

    def test_failure_from_030(self):
        assert confidence_after_failure(0.30) == pytest.approx(0.24)


class TestConfidenceAsymptoticBehavior:
    """Test asymptotic properties of the confidence formula."""

    def test_success_approaches_one(self):
        """Many successes should push confidence close to 1.0 but never reach it."""
        c = 0.5
        for _ in range(100):
            c = confidence_after_success(c)
        assert c < 1.0
        assert c > 0.99

    def test_failure_approaches_zero(self):
        """Many failures should push confidence close to 0.0 but never reach it."""
        c = 0.9
        for _ in range(100):
            c = confidence_after_failure(c)
        assert c > 0.0
        assert c < 0.01

    def test_failure_pulls_faster_than_success_builds(self):
        """A failure should pull confidence down more than a success builds it."""
        c = 0.5
        c_after_success = confidence_after_success(c)
        c_after_failure = confidence_after_failure(c)

        gain = c_after_success - c  # +0.05
        loss = c - c_after_failure  # -0.10

        assert loss > gain

    def test_two_successes_needed_to_recover_from_one_failure(self):
        """Roughly 2 successes needed to recover from 1 failure."""
        c = 0.70
        c_after_fail = confidence_after_failure(c)  # 0.56
        c_after_1_success = confidence_after_success(c_after_fail)  # ~0.604
        c_after_2_success = confidence_after_success(c_after_1_success)  # ~0.644

        # After 1 failure + 2 successes, should be close to but below original
        assert c_after_2_success < c
        # But after 3 successes, should be close to or above
        c_after_3_success = confidence_after_success(c_after_2_success)
        assert c_after_3_success > c * 0.95  # within 5% of original


class TestConfidenceBounds:
    """Test that confidence stays within [0.0, 1.0]."""

    def test_never_exceeds_one(self):
        c = 0.999
        c = confidence_after_success(c)
        assert c <= 1.0

    def test_never_goes_negative(self):
        c = 0.001
        c = confidence_after_failure(c)
        assert c >= 0.0

    def test_at_zero_failure_stays_zero(self):
        assert confidence_after_failure(0.0) == 0.0

    def test_at_one_success_stays_one(self):
        # confidence + 0.1 * (1.0 - 1.0) = 1.0
        assert confidence_after_success(1.0) == 1.0
