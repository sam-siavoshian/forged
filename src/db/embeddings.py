"""OpenAI embedding generation for task templates.

Uses text-embedding-3-small (1536 dimensions).
Includes LRU cache for repeated embedding requests.
"""

import os
from functools import lru_cache

from openai import OpenAI

_openai_client: OpenAI | None = None


def _get_openai() -> OpenAI:
    """Get or create the singleton OpenAI client."""
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY must be set for embedding generation"
            )
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


def generate_embedding(text: str) -> list[float]:
    """Generate a 1536-dimensional embedding for the given text.

    Args:
        text: The text to embed (typically a task_pattern like "buy {product} on Amazon").

    Returns:
        List of 1536 floats representing the embedding vector.
    """
    client = _get_openai()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        encoding_format="float",
    )
    return response.data[0].embedding


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts in a single API call.

    OpenAI supports up to 2048 inputs per batch.
    """
    client = _get_openai()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
        encoding_format="float",
    )
    sorted_data = sorted(response.data, key=lambda x: x.index)
    return [item.embedding for item in sorted_data]


@lru_cache(maxsize=256)
def generate_embedding_cached(text: str) -> tuple[float, ...]:
    """Cached version of generate_embedding.

    Returns a tuple (hashable) instead of list for LRU cache compatibility.
    """
    return tuple(generate_embedding(text))
