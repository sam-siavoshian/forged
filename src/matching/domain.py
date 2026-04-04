"""Domain extraction from task descriptions.

Three strategies in priority order:
1. Parse explicit URLs
2. Keyword-to-domain map
3. Domain-like pattern matching (e.g., "example.com")
"""

import re
from urllib.parse import urlparse

# Fast lookup for common domains (extend as needed)
KEYWORD_DOMAIN_MAP: dict[str, str] = {
    "amazon": "amazon.com",
    "google": "google.com",
    "youtube": "youtube.com",
    "github": "github.com",
    "reddit": "reddit.com",
    "twitter": "twitter.com",
    "x.com": "x.com",
    "linkedin": "linkedin.com",
    "ebay": "ebay.com",
    "walmart": "walmart.com",
    "target": "target.com",
}


def extract_domain(task_description: str) -> str | None:
    """Extract the target website domain from a task description.

    Returns the domain (e.g., "amazon.com") or None if unidentifiable.
    """
    # Strategy 1: Look for explicit URLs
    url_pattern = r"https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})"
    url_match = re.search(url_pattern, task_description)
    if url_match:
        return url_match.group(1).lower()

    # Strategy 2: Keyword matching (case-insensitive)
    task_lower = task_description.lower()
    for keyword, domain in KEYWORD_DOMAIN_MAP.items():
        if keyword in task_lower:
            return domain

    # Strategy 3: Look for domain-like patterns without protocol
    domain_pattern = r"\b([a-zA-Z0-9-]+\.(?:com|org|net|io|co|dev|app))\b"
    domain_match = re.search(domain_pattern, task_description)
    if domain_match:
        return domain_match.group(1).lower()

    return None
