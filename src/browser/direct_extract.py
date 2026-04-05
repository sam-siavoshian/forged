"""Direct page extraction — reads data from the DOM using stored CSS selectors.

Eliminates the agent phase for extract-type tasks with high-confidence
template matches. After the rocket phase navigates to the target page,
this module reads specific data fields directly via Playwright selectors.

Falls back to None (triggering agent handoff) if any selector fails,
returns empty content, or the CDP connection errors.
"""

from __future__ import annotations

import logging
from typing import Any

from playwright.async_api import (
    Playwright,
    async_playwright,
)

from src import config

logger = logging.getLogger("rocket_booster.direct_extract")


async def direct_extract(
    cdp_url: str,
    extraction_selectors: dict[str, dict[str, Any]],
    timeout_ms: int | None = None,
) -> dict[str, str] | None:
    """Extract data from the current page using CSS selectors stored in the template.

    Each entry in extraction_selectors maps a field name to:
      {
        "selector": "h1.title",          # Primary CSS selector
        "fallback_selectors": [".title"], # Alternative selectors
        "description": "Page title",      # Human-readable description
      }

    Returns a dict of {field_name: extracted_text} if ALL selectors succeed,
    or None if any field cannot be extracted (signals the caller to fall back
    to the full agent phase).

    Uses pw.stop() for cleanup to release the CDP connection without killing
    the remote BaaS browser — same pattern as PlaywrightRocket in rocket.py.

    Args:
        cdp_url: CDP WebSocket URL for the cloud browser.
        extraction_selectors: Field-to-selector mapping from the template.
        timeout_ms: Maximum time per selector lookup (default 3s).

    Returns:
        Dict of field names to extracted text, or None on any failure.
    """
    if timeout_ms is None:
        timeout_ms = config.DIRECT_EXTRACT_TIMEOUT_MS
    if not extraction_selectors:
        return None

    pw: Playwright | None = None

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.connect_over_cdp(cdp_url)

        default_context = browser.contexts[0]
        page = (
            default_context.pages[0]
            if default_context.pages
            else None
        )
        if page is None:
            logger.warning("No page available in browser context")
            return None

        results: dict[str, str] = {}

        for field_name, field_config in extraction_selectors.items():
            selector = field_config.get("selector")
            fallbacks = field_config.get("fallback_selectors", [])

            if not selector:
                logger.warning("Field '%s' has no selector", field_name)
                return None

            text = await _try_extract_text(page, selector, timeout_ms)

            # Try fallback selectors if primary fails
            if not text:
                fallback_timeout = min(config.DIRECT_EXTRACT_FALLBACK_TIMEOUT_MS, timeout_ms)
                for fb_selector in fallbacks:
                    text = await _try_extract_text(page, fb_selector, fallback_timeout)
                    if text:
                        logger.info(
                            "Field '%s' extracted via fallback selector: %s",
                            field_name, fb_selector[:60],
                        )
                        break

            if not text:
                logger.info(
                    "Field '%s' extraction failed (selector='%s', %d fallbacks tried)",
                    field_name, selector[:60], len(fallbacks),
                )
                return None  # Any failure → fall back to agent

            results[field_name] = text

        logger.info(
            "Direct extraction succeeded: %d fields extracted",
            len(results),
        )
        return results

    except Exception as e:
        logger.warning("Direct extraction error: %s", e)
        return None

    finally:
        if pw:
            await pw.stop()


async def _try_extract_text(page, selector: str, timeout_ms: int) -> str | None:
    """Try to read text content from a CSS selector. Returns None on failure."""
    try:
        text = await page.text_content(selector, timeout=timeout_ms)
        if text and text.strip():
            return text.strip()
        return None
    except Exception:
        return None
