"""Domain extraction from task descriptions.

Three strategies in priority order:
1. Parse explicit URLs (fast, regex)
2. Domain-like pattern matching (fast, regex)
3. LLM extraction via Claude Haiku (generalized, no hardcoded maps)
"""

import logging
import re
from functools import lru_cache

from anthropic import Anthropic

from src import config

logger = logging.getLogger(__name__)

_anthropic_client: Anthropic | None = None


def _get_anthropic() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic()
    return _anthropic_client


def extract_domain(task_description: str) -> str | None:
    """Extract the target website domain from a task description.

    Uses regex for explicit URLs/domains first (fast path),
    falls back to LLM extraction for natural language references.
    """
    # Strategy 1: Look for explicit URLs
    url_pattern = r"https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
    url_match = re.search(url_pattern, task_description)
    if url_match:
        return url_match.group(1).lower()

    # Strategy 2: Look for domain-like patterns without protocol
    tld_alternation = "|".join(re.escape(t) for t in config.DOMAIN_TLDS)
    domain_pattern = rf"\b([a-zA-Z0-9-]+\.(?:{tld_alternation}))\b"
    domain_match = re.search(domain_pattern, task_description)
    if domain_match:
        return domain_match.group(1).lower()

    # Strategy 3: LLM extraction (handles "Hacker News", "Amazon", "YouTube", etc.)
    return _llm_extract_domain(task_description)


@lru_cache(maxsize=128)
def _llm_extract_domain(task_description: str) -> str | None:
    """Use Claude Haiku to extract the domain from natural language."""
    client = _get_anthropic()

    response = client.messages.create(
        model=config.MODEL_DOMAIN_EXTRACTOR,
        max_tokens=30,
        system=(
            "Extract the website domain the user wants to visit. "
            "Infer the domain even from brand names, product names, or services "
            "(e.g., 'Amazon' -> amazon.com, 'Gmail' -> mail.google.com, "
            "'Hacker News' -> news.ycombinator.com, 'Chase' -> chase.com, "
            "'Netflix' -> netflix.com). "
            "Respond with ONLY the bare domain. "
            "If genuinely no website can be inferred, respond with exactly: none"
        ),
        messages=[{"role": "user", "content": task_description}],
        temperature=0.0,
    )

    result = response.content[0].text.strip().lower()

    if result == "none" or not result or " " in result:
        logger.debug("LLM domain extraction returned no domain for: %s", task_description[:80])
        return None

    # Clean up — remove any protocol or path the LLM might have included
    result = re.sub(r"^https?://", "", result)
    result = re.sub(r"^www\.", "", result)
    result = result.split("/")[0]

    logger.info("LLM extracted domain: %s from: %s", result, task_description[:80])
    return result
