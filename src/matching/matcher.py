"""Three-layer matching orchestrator.

Combines domain extraction, action type classification, and pgvector
cosine similarity search to find the best matching template for a task.
"""

import json
from dataclasses import dataclass
from typing import Any

from ..db.client import get_pg_pool
from ..db.embeddings import generate_embedding
from .action_type import classify_action_type
from .domain import extract_domain


@dataclass
class TemplateMatch:
    """Result of a successful template match."""

    template_id: str
    task_pattern: str
    steps: list[dict[str, Any]]
    handoff_index: int
    parameters: list[dict[str, Any]]
    similarity: float
    confidence: float
    confidence_band: str  # "very_high", "high", "medium"
    domain: str
    action_type: str


async def find_matching_template(
    task_description: str,
) -> TemplateMatch | None:
    """Three-layer matching: domain -> action_type -> semantic similarity.

    Returns the best matching TemplateMatch, or None if no match found.

    Confidence bands:
    - >= 0.90: very_high — execute all rocket steps
    - 0.75-0.89: high — execute all rocket steps
    - 0.50-0.74: medium — only execute fixed steps
    - < 0.50: no match
    """
    # Layer 1: Domain extraction
    domain = extract_domain(task_description)
    if domain is None:
        return None

    # Layer 2: Action type classification
    action_type = classify_action_type(task_description)

    # Layer 3: Embedding similarity search
    embedding = generate_embedding(task_description)
    embedding_str = json.dumps(embedding)

    pool = await get_pg_pool()

    if action_type:
        query = """
            SELECT
                id, task_pattern, steps, handoff_index, parameters,
                confidence, action_type, domain,
                1 - (embedding <=> $1::vector) AS similarity
            FROM task_templates
            WHERE domain = $2
              AND action_type = $3
              AND confidence >= 0.2
            ORDER BY embedding <=> $1::vector ASC
            LIMIT 1
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                query, embedding_str, domain, action_type
            )
    else:
        query = """
            SELECT
                id, task_pattern, steps, handoff_index, parameters,
                confidence, action_type, domain,
                1 - (embedding <=> $1::vector) AS similarity
            FROM task_templates
            WHERE domain = $2
              AND confidence >= 0.2
            ORDER BY embedding <=> $1::vector ASC
            LIMIT 1
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, embedding_str, domain)

    if row is None:
        return None

    similarity = float(row["similarity"])

    # Apply similarity threshold
    if similarity < 0.50:
        return None

    # Determine confidence band
    if similarity >= 0.90:
        band = "very_high"
    elif similarity >= 0.75:
        band = "high"
    else:
        band = "medium"

    return TemplateMatch(
        template_id=str(row["id"]),
        task_pattern=row["task_pattern"],
        steps=(
            json.loads(row["steps"])
            if isinstance(row["steps"], str)
            else row["steps"]
        ),
        handoff_index=row["handoff_index"],
        parameters=(
            json.loads(row["parameters"])
            if isinstance(row["parameters"], str)
            else row["parameters"]
        ),
        similarity=similarity,
        confidence=float(row["confidence"]),
        confidence_band=band,
        domain=row["domain"],
        action_type=row["action_type"],
    )
