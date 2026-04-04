"""Site selector and navigation pattern storage.

Manages cached knowledge about specific websites: common selectors,
navigation patterns, and page load signals.
"""

import json
from typing import Any

from .client import get_pg_pool


async def update_selectors(
    domain: str,
    element_name: str,
    working_selector: str,
) -> None:
    """Add a working selector to the site_knowledge for a domain.

    Appends to the list if not already present. Creates the domain entry if needed.
    """
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        # Upsert the domain
        await conn.execute(
            """
            INSERT INTO site_knowledge
                (domain, selector_map, navigation_patterns, page_load_signals)
            VALUES ($1, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb)
            ON CONFLICT (domain) DO NOTHING
            """,
            domain,
        )

        # Append selector if not already in the array
        await conn.execute(
            """
            UPDATE site_knowledge
            SET selector_map = jsonb_set(
                selector_map,
                ARRAY[$2],
                COALESCE(selector_map->$2, '[]'::jsonb) || to_jsonb($3::text),
                true
            )
            WHERE domain = $1
              AND NOT (COALESCE(selector_map->$2, '[]'::jsonb) ? $3)
            """,
            domain,
            element_name,
            working_selector,
        )


async def get_selectors(domain: str, element_name: str) -> list[str]:
    """Get known selectors for a named element on a domain.

    Returns an empty list if unknown.
    """
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT selector_map->$2 AS selectors "
            "FROM site_knowledge WHERE domain = $1",
            domain,
            element_name,
        )
        if row is None or row["selectors"] is None:
            return []
        return json.loads(row["selectors"])


async def get_site_knowledge(domain: str) -> dict[str, Any] | None:
    """Get full site knowledge for a domain. Returns None if not found."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM site_knowledge WHERE domain = $1",
            domain,
        )
        if row is None:
            return None
        result = dict(row)
        result["id"] = str(result["id"])
        # Parse JSONB fields
        for field in ("selector_map", "navigation_patterns", "page_load_signals"):
            if isinstance(result[field], str):
                result[field] = json.loads(result[field])
        return result
