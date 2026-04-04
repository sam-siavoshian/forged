"""Tests for embedding generation."""

from unittest.mock import MagicMock, patch

import pytest

from src.db.embeddings import (
    generate_embedding,
    generate_embedding_cached,
    generate_embeddings_batch,
)


def _mock_embedding_response(n: int = 1):
    """Create a mock OpenAI embeddings response."""
    mock_response = MagicMock()
    mock_response.data = []
    for i in range(n):
        item = MagicMock()
        item.embedding = [0.01 * (i + 1)] * 1536
        item.index = i
        mock_response.data.append(item)
    return mock_response


class TestGenerateEmbedding:
    @patch("src.db.embeddings._get_openai")
    def test_returns_list_of_floats(self, mock_get_openai):
        client = MagicMock()
        client.embeddings.create.return_value = _mock_embedding_response(1)
        mock_get_openai.return_value = client

        result = generate_embedding("buy headphones on Amazon")

        assert isinstance(result, list)
        assert len(result) == 1536
        assert all(isinstance(x, float) for x in result)

    @patch("src.db.embeddings._get_openai")
    def test_calls_correct_model(self, mock_get_openai):
        client = MagicMock()
        client.embeddings.create.return_value = _mock_embedding_response(1)
        mock_get_openai.return_value = client

        generate_embedding("test")

        client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input="test",
            encoding_format="float",
        )


class TestGenerateEmbeddingsBatch:
    @patch("src.db.embeddings._get_openai")
    def test_returns_correct_count(self, mock_get_openai):
        client = MagicMock()
        client.embeddings.create.return_value = _mock_embedding_response(3)
        mock_get_openai.return_value = client

        result = generate_embeddings_batch(["a", "b", "c"])

        assert len(result) == 3
        assert all(len(e) == 1536 for e in result)

    @patch("src.db.embeddings._get_openai")
    def test_preserves_order(self, mock_get_openai):
        client = MagicMock()
        # Return in reversed order to test sorting
        mock_response = MagicMock()
        items = []
        for i in [2, 0, 1]:
            item = MagicMock()
            item.embedding = [0.01 * (i + 1)] * 1536
            item.index = i
            items.append(item)
        mock_response.data = items
        client.embeddings.create.return_value = mock_response
        mock_get_openai.return_value = client

        result = generate_embeddings_batch(["a", "b", "c"])

        # Index 0 should have 0.01, index 1 should have 0.02, etc.
        assert result[0][0] == pytest.approx(0.01)
        assert result[1][0] == pytest.approx(0.02)
        assert result[2][0] == pytest.approx(0.03)


class TestGenerateEmbeddingCached:
    @patch("src.db.embeddings._get_openai")
    def test_returns_tuple(self, mock_get_openai):
        client = MagicMock()
        client.embeddings.create.return_value = _mock_embedding_response(1)
        mock_get_openai.return_value = client

        # Clear the cache before testing
        generate_embedding_cached.cache_clear()

        result = generate_embedding_cached("test cached")

        assert isinstance(result, tuple)
        assert len(result) == 1536

    @patch("src.db.embeddings._get_openai")
    def test_cache_hit(self, mock_get_openai):
        client = MagicMock()
        client.embeddings.create.return_value = _mock_embedding_response(1)
        mock_get_openai.return_value = client

        generate_embedding_cached.cache_clear()

        result1 = generate_embedding_cached("same text")
        result2 = generate_embedding_cached("same text")

        assert result1 == result2
        # Should only call the API once
        assert client.embeddings.create.call_count == 1
