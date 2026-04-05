"""Three-layer matching orchestrator.

Combines domain extraction, action type classification, and embedding
cosine similarity search to find the best matching template for a task.

Tries pgvector SQL-native search first (fastest), falls back to Supabase
REST + in-Python similarity if direct PG is unavailable (campus networks).
Medium-confidence matches are verified by LLM.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..db.embeddings import build_query_embedding_text, generate_embedding
from .action_type import classify_action_type
from .domain import extract_domain
from .verifier import verify_template_match

logger = logging.getLogger(__name__)


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
    needs_verification: bool  # True for medium band (0.50-0.74)


def _domain_matches(stored: str, query: str) -> bool:
    """Flexible domain matching — handles subdomains and partial matches."""
    return (
        stored == query
        or stored.endswith(f".{query}")
        or query.endswith(f".{stored}")
        or query in stored
        or stored in query
    )


_pgvector_available: bool | None = None  # Cached after first attempt


async def _search_via_pgvector(
    embedding: list[float], domain: str, action_type: str | None
) -> list[dict[str, Any]] | None:
    """Try SQL-native pgvector search. Returns None if PG is unavailable.

    Caches the result of the first attempt so subsequent calls don't waste
    time on DNS resolution failures (e.g., campus WiFi blocking direct PG).
    """
    global _pgvector_available
    if _pgvector_available is False:
        return None

    try:
        from ..db.client import get_pg_pool

        pool = await get_pg_pool()
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"

        rows = await pool.fetch(
            """
            SELECT id, task_pattern, steps, handoff_index, parameters, confidence,
                   action_type, domain,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM task_templates
            WHERE confidence >= 0.2
              AND (domain = $2 OR domain LIKE '%.' || $2 OR $2 LIKE '%.' || domain
                   OR position($2 in domain) > 0 OR position(domain in $2) > 0)
              AND ($3::text IS NULL OR action_type = $3)
            ORDER BY embedding <=> $1::vector ASC
            LIMIT 5
            """,
            embedding_str,
            domain,
            action_type,
        )
        _pgvector_available = True
        return [dict(r) for r in rows]
    except Exception as e:
        _pgvector_available = False
        logger.info("pgvector unavailable (will use REST fallback): %s", e)
        return None


async def _search_via_rest(
    embedding: list[float], domain: str, action_type: str | None
) -> list[dict[str, Any]]:
    """Fallback: fetch templates via Supabase REST, compute similarity in Python."""
    from supabase import create_client

    client = create_client(
        os.environ.get("SUPABASE_URL", ""),
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
    )

    query = client.table("task_templates").select(
        "id, task_pattern, steps, handoff_index, parameters, confidence, "
        "action_type, domain, embedding"
    ).gte("confidence", 0.2)
    result = query.execute()

    # Filter by domain
    domain_filtered = [
        t for t in result.data
        if _domain_matches(t.get("domain", ""), domain)
    ]
    candidates = domain_filtered if domain_filtered else result.data

    # Compute cosine similarity in Python
    query_vec = np.array(embedding)
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return []

    scored = []
    for t in candidates:
        t_emb = t.get("embedding")
        if not t_emb:
            continue
        if isinstance(t_emb, str):
            t_emb = json.loads(t_emb)
        t_vec = np.array(t_emb)
        t_norm = np.linalg.norm(t_vec)
        if t_norm == 0:
            continue
        sim = float(np.dot(query_vec, t_vec) / (query_norm * t_norm))
        t["similarity"] = sim
        scored.append(t)

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:5]


async def find_matching_template(
    task_description: str,
) -> TemplateMatch | None:
    """Three-layer matching: domain -> action_type -> semantic similarity.

    Returns the best matching TemplateMatch, or None if no match found.

    Layer 1: Extract domain from task description (LLM-powered)
    Layer 2: Classify action type (LLM-powered)
    Layer 3: Embedding similarity search (pgvector or REST fallback)

    Confidence bands:
    - >= 0.90: very_high — execute all rocket steps
    - 0.75-0.89: high — execute all rocket steps
    - 0.50-0.74: medium — LLM-verified, only execute fixed steps
    - < 0.50: no match
    """
    # Layer 1: Domain extraction
    domain = extract_domain(task_description)
    if domain is None:
        logger.info("Could not extract domain from: %s", task_description[:80])
        return None

    # Layer 2: Action type classification
    action_type = classify_action_type(task_description)
    logger.info("Matching: domain=%s action_type=%s", domain, action_type)

    # Layer 3: Embedding similarity search
    query_text = build_query_embedding_text(
        task_description=task_description,
        domain=domain,
        action_type=action_type,
    )
    embedding = generate_embedding(query_text)

    # Try pgvector first, fall back to REST
    rows = await _search_via_pgvector(embedding, domain, action_type)
    if rows is None:
        rows = await _search_via_rest(embedding, domain, action_type)

    if not rows:
        return None

    row = rows[0]
    similarity = float(row.get("similarity", 0))

    # Apply similarity threshold — 0.50 minimum (medium band reaches LLM verifier)
    if similarity < 0.50:
        logger.info("Best match similarity %.3f below 0.50 threshold", similarity)
        return None

    # Determine confidence band
    if similarity >= 0.90:
        band = "very_high"
    elif similarity >= 0.75:
        band = "high"
    else:
        band = "medium"

    # LLM verification for medium-confidence matches
    needs_verification = band == "medium"
    if needs_verification:
        logger.info(
            "Medium-confidence match (%.3f), running LLM verification",
            similarity,
        )
        is_valid = await verify_template_match(
            task_description=task_description,
            template_task_pattern=row["task_pattern"],
            domain=row.get("domain", domain),
            similarity=similarity,
        )
        if not is_valid:
            logger.info("LLM verification rejected the match")
            return None

    steps = row.get("steps", [])
    if isinstance(steps, str):
        steps = json.loads(steps)
    parameters = row.get("parameters", [])
    if isinstance(parameters, str):
        parameters = json.loads(parameters)

    return TemplateMatch(
        template_id=str(row["id"]),
        task_pattern=row["task_pattern"],
        steps=steps,
        handoff_index=row.get("handoff_index", 0) or 0,
        parameters=parameters,
        similarity=similarity,
        confidence=float(row.get("confidence", 0.5)),
        confidence_band=band,
        domain=row.get("domain", domain),
        action_type=row.get("action_type", action_type or "unknown"),
        needs_verification=needs_verification,
    )
