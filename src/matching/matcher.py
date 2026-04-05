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

from .. import config
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
    extraction_selectors: dict[str, Any] | None = None


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

# In-memory template cache: (domain, action_type) → TemplateMatch.
# Survives across requests while the server is running. Cleared on restart.
# This lets the second MCP call skip the entire matching pipeline.
_template_cache: dict[tuple[str, str | None], TemplateMatch] = {}


def cache_template(match: TemplateMatch) -> None:
    """Populate the in-memory template cache (called after auto-learn too)."""
    _template_cache[match.domain] = match
    logger.info("Template cached: domain=%s action_type=%s", match.domain, match.action_type)


def _cache_lookup(domain: str, action_type: str | None) -> TemplateMatch | None:
    """Flexible cache lookup: tries exact domain, then subdomain matching."""
    # Exact hit
    if domain in _template_cache:
        return _template_cache[domain]
    # Subdomain matching (en.wikipedia.org → wikipedia.org, or vice versa)
    for cached_domain, match in _template_cache.items():
        if _domain_matches(cached_domain, domain):
            return match
    return None


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
            f"""
            SELECT id, task_pattern, steps, handoff_index, parameters, confidence,
                   action_type, domain, extraction_selectors,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM task_templates
            WHERE confidence >= {config.DB_MIN_CONFIDENCE}
              AND (domain = $2 OR domain LIKE '%.' || $2 OR $2 LIKE '%.' || domain
                   OR position($2 in domain) > 0 OR position(domain in $2) > 0)
              AND ($3::text IS NULL OR action_type = $3)
            ORDER BY embedding <=> $1::vector ASC
            LIMIT {config.DB_RESULT_LIMIT}
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
        "action_type, domain, embedding, extraction_selectors"
    ).gte("confidence", config.DB_MIN_CONFIDENCE)
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

        # Boost similarity when domain and action type match.
        # This prevents near-misses from falling below threshold
        # when the task structure is clearly the same.
        if _domain_matches(t.get("domain", ""), domain):
            sim += 0.05
        if action_type and t.get("action_type") == action_type:
            sim += 0.05

        t["similarity"] = min(sim, 1.0)  # cap at 1.0
        scored.append(t)

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:config.DB_RESULT_LIMIT]


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

    # Fast path: check in-memory cache before hitting embeddings/DB
    cached = _cache_lookup(domain, action_type)
    if cached:
        logger.info(
            "Cache hit: domain=%s action_type=%s template=%s (skipping embedding search)",
            domain, action_type, cached.template_id[:8],
        )
        return cached

    # Layer 3: Embedding similarity search
    query_text = build_query_embedding_text(
        task_description=task_description,
        domain=domain,
        action_type=action_type,
    )
    embedding = generate_embedding(query_text)

    # Try pgvector first, fall back to REST
    rows = await _search_via_pgvector(embedding, domain, action_type)
    if not rows:
        rows = await _search_via_rest(embedding, domain, action_type)

    if not rows:
        return None

    row = rows[0]
    similarity = float(row.get("similarity", 0))

    # Apply similarity threshold — 0.50 minimum (medium band reaches LLM verifier)
    if similarity < config.SIMILARITY_THRESHOLD:
        logger.info("Best match similarity %.3f below %.2f threshold", similarity, config.SIMILARITY_THRESHOLD)
        return None

    # Determine confidence band
    if similarity >= config.SIMILARITY_VERY_HIGH:
        band = "very_high"
    elif similarity >= config.SIMILARITY_HIGH:
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

    # Parse extraction_selectors from DB row
    extraction_selectors = row.get("extraction_selectors")
    if isinstance(extraction_selectors, str):
        try:
            extraction_selectors = json.loads(extraction_selectors)
        except (json.JSONDecodeError, TypeError):
            extraction_selectors = None

    result = TemplateMatch(
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
        extraction_selectors=extraction_selectors,
    )

    # Cache for instant reuse on next request
    cache_template(result)

    return result
