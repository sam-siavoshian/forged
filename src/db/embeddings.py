"""OpenAI embedding generation for task templates.

Uses text-embedding-3-large (3072 dimensions) with normalized structural
text so that task variations match their templates.
"""

import os
import re
from functools import lru_cache
from typing import Any

from openai import OpenAI

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMS = 3072

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


def _normalize_task_for_embedding(text: str) -> str:
    """Normalize a task description to its structural pattern.

    Strips specific parameter values so that "search for Dog" and
    "search for artificial intelligence" produce similar embeddings.
    Keeps action verbs and domain references.

    Examples:
      "Go to wikipedia.org, search for 'Dog', and extract the first and second paragraph"
      → "go to wikipedia.org, search for [query], and extract [content]"

      "Go to amazon.com, search for 'wireless mouse', sort by price low to high"
      → "go to amazon.com, search for [query], sort by [criteria]"
    """
    t = text.lower()

    # Remove quoted strings: "Dog", 'artificial intelligence', "wireless mouse"
    t = re.sub(r'"[^"]*"', '[query]', t)
    t = re.sub(r"'[^']*'", '[query]', t)

    # Replace {param_name} placeholders with [param] (for stored patterns)
    t = re.sub(r'\{[^}]+\}', '[param]', t)

    # Replace "#N" patterns (like "#1 story") with [rank]
    t = re.sub(r'#\d+', '[rank]', t)

    # Normalize extraction scope: "first paragraph", "first and second paragraph",
    # "top 3 comments", "all ingredients" → [content]
    t = re.sub(r'(the\s+)?(first|second|third|top|all|every)\s+(and\s+\w+\s+)?(paragraph|comment|result|ingredient|item|section|entry|review)s?', '[content]', t)

    # Collapse multiple spaces
    t = re.sub(r'\s+', ' ', t).strip()

    return t


def build_embedding_text(
    task_pattern: str,
    steps: list[dict[str, Any]],
    parameters: list[dict[str, Any]],
    domain: str,
    action_type: str,
    site_knowledge: dict[str, Any] | None = None,
) -> str:
    """Build a normalized text representation for embedding.

    Normalizes the task pattern to its structural skeleton so that
    variations of the same task type produce similar embeddings.
    """
    normalized = _normalize_task_for_embedding(task_pattern)
    lines = [f"task: {normalized}"]
    lines.append(f"domain: {domain}")
    lines.append(f"action: {action_type}")
    return "\n".join(lines)


def build_query_embedding_text(
    task_description: str,
    domain: str | None = None,
    action_type: str | None = None,
) -> str:
    """Build a normalized query embedding text.

    Normalizes the user's task to its structural skeleton, matching
    the format used for stored template embeddings.
    """
    normalized = _normalize_task_for_embedding(task_description)
    lines = [f"task: {normalized}"]
    if domain:
        lines.append(f"domain: {domain}")
    if action_type:
        lines.append(f"action: {action_type}")
    return "\n".join(lines)


def generate_embedding(text: str) -> list[float]:
    """Generate a 3072-dimensional embedding for the given text.

    Args:
        text: The text to embed (rich composite text or raw task description).

    Returns:
        List of 3072 floats representing the embedding vector.
    """
    client = _get_openai()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
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
        model=EMBEDDING_MODEL,
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
