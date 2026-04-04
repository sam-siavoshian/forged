"""Tests for the three-layer matching orchestrator.

Mocks the embedding API and pgvector queries to test matching logic
across all confidence bands.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.matching.matcher import TemplateMatch, find_matching_template


def _fake_embedding() -> list[float]:
    """Return a fake 1536-dimensional embedding."""
    return [0.01] * 1536


def _make_row(similarity: float, confidence: float = 0.5) -> dict:
    """Create a mock database row."""
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "task_pattern": "buy {product} on Amazon",
        "steps": json.dumps([{"index": 0, "type": "fixed", "action": "navigate"}]),
        "handoff_index": 5,
        "parameters": json.dumps([{"name": "product", "type": "string"}]),
        "confidence": confidence,
        "action_type": "purchase",
        "domain": "amazon.com",
        "similarity": similarity,
    }


@pytest.fixture
def mock_embedding():
    with patch(
        "src.matching.matcher.generate_embedding",
        return_value=_fake_embedding(),
    ) as m:
        yield m


class _FakeAcquire:
    """Fake async context manager for pool.acquire()."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def mock_pool():
    conn = AsyncMock()

    pool = MagicMock()
    pool.acquire.return_value = _FakeAcquire(conn)

    async def _get_pool():
        return pool

    with patch(
        "src.matching.matcher.get_pg_pool",
        side_effect=_get_pool,
    ) as p:
        yield conn, p


class TestConfidenceBands:
    """Test that similarity scores map to correct confidence bands."""

    @pytest.mark.asyncio
    async def test_very_high_band(self, mock_embedding, mock_pool):
        conn, _ = mock_pool
        conn.fetchrow.return_value = _make_row(similarity=0.95)

        result = await find_matching_template("Buy headphones on Amazon")

        assert result is not None
        assert result.confidence_band == "very_high"
        assert result.similarity == 0.95

    @pytest.mark.asyncio
    async def test_high_band(self, mock_embedding, mock_pool):
        conn, _ = mock_pool
        conn.fetchrow.return_value = _make_row(similarity=0.82)

        result = await find_matching_template("Buy headphones on Amazon")

        assert result is not None
        assert result.confidence_band == "high"

    @pytest.mark.asyncio
    async def test_medium_band(self, mock_embedding, mock_pool):
        conn, _ = mock_pool
        conn.fetchrow.return_value = _make_row(similarity=0.60)

        result = await find_matching_template("Buy headphones on Amazon")

        assert result is not None
        assert result.confidence_band == "medium"

    @pytest.mark.asyncio
    async def test_below_threshold_returns_none(self, mock_embedding, mock_pool):
        conn, _ = mock_pool
        conn.fetchrow.return_value = _make_row(similarity=0.40)

        result = await find_matching_template("Buy headphones on Amazon")

        assert result is None

    @pytest.mark.asyncio
    async def test_boundary_090(self, mock_embedding, mock_pool):
        conn, _ = mock_pool
        conn.fetchrow.return_value = _make_row(similarity=0.90)

        result = await find_matching_template("Buy headphones on Amazon")
        assert result is not None
        assert result.confidence_band == "very_high"

    @pytest.mark.asyncio
    async def test_boundary_075(self, mock_embedding, mock_pool):
        conn, _ = mock_pool
        conn.fetchrow.return_value = _make_row(similarity=0.75)

        result = await find_matching_template("Buy headphones on Amazon")
        assert result is not None
        assert result.confidence_band == "high"

    @pytest.mark.asyncio
    async def test_boundary_050(self, mock_embedding, mock_pool):
        conn, _ = mock_pool
        conn.fetchrow.return_value = _make_row(similarity=0.50)

        result = await find_matching_template("Buy headphones on Amazon")
        assert result is not None
        assert result.confidence_band == "medium"


class TestDomainFiltering:
    """Test that domain extraction gates the matching."""

    @pytest.mark.asyncio
    async def test_no_domain_returns_none(self, mock_embedding):
        result = await find_matching_template("Do something vague")
        assert result is None

    @pytest.mark.asyncio
    async def test_domain_extracted_from_keyword(self, mock_embedding, mock_pool):
        conn, _ = mock_pool
        conn.fetchrow.return_value = _make_row(similarity=0.85)

        result = await find_matching_template("Buy something on Amazon")

        assert result is not None
        assert result.domain == "amazon.com"


class TestNoDbMatch:
    """Test when the database returns no matching template."""

    @pytest.mark.asyncio
    async def test_no_rows_returns_none(self, mock_embedding, mock_pool):
        conn, _ = mock_pool
        conn.fetchrow.return_value = None

        result = await find_matching_template("Buy headphones on Amazon")
        assert result is None


class TestActionTypeRouting:
    """Test that action type classification affects the query."""

    @pytest.mark.asyncio
    async def test_with_action_type(self, mock_embedding, mock_pool):
        conn, _ = mock_pool
        conn.fetchrow.return_value = _make_row(similarity=0.85)

        result = await find_matching_template("Buy headphones on Amazon")

        # Should have called with 3 params (embedding, domain, action_type)
        call_args = conn.fetchrow.call_args
        assert len(call_args[0]) == 4  # query + 3 params

    @pytest.mark.asyncio
    async def test_without_action_type(self, mock_embedding, mock_pool):
        conn, _ = mock_pool
        conn.fetchrow.return_value = _make_row(similarity=0.85)

        # "Go to Amazon" has navigate action, but let's test with no action
        with patch(
            "src.matching.matcher.classify_action_type",
            return_value=None,
        ):
            result = await find_matching_template("Something on Amazon")

        # Should have called with 2 params (embedding, domain)
        call_args = conn.fetchrow.call_args
        assert len(call_args[0]) == 3  # query + 2 params


class TestTemplateMatchDataclass:
    """Test the TemplateMatch dataclass fields."""

    @pytest.mark.asyncio
    async def test_all_fields_populated(self, mock_embedding, mock_pool):
        conn, _ = mock_pool
        conn.fetchrow.return_value = _make_row(similarity=0.92, confidence=0.8)

        result = await find_matching_template("Buy headphones on Amazon")

        assert isinstance(result, TemplateMatch)
        assert result.template_id == "00000000-0000-0000-0000-000000000001"
        assert result.task_pattern == "buy {product} on Amazon"
        assert result.handoff_index == 5
        assert result.similarity == 0.92
        assert result.confidence == 0.8
        assert result.confidence_band == "very_high"
        assert result.domain == "amazon.com"
        assert result.action_type == "purchase"
        assert isinstance(result.steps, list)
        assert isinstance(result.parameters, list)
