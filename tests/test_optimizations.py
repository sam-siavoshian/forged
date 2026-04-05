"""Tests for performance optimizations: speculative browser + direct extraction."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.browser.direct_extract import direct_extract, _try_extract_text


# ──────────────────────────────────────────────────────────────
# Direct extraction engine tests
# ──────────────────────────────────────────────────────────────


class FakePage:
    """Minimal mock for Playwright Page with configurable text_content."""

    def __init__(self, selector_results: dict[str, str | None]):
        self._results = selector_results

    async def text_content(self, selector: str, timeout: int = 3000) -> str | None:
        result = self._results.get(selector)
        if result is None:
            raise Exception(f"Selector not found: {selector}")
        return result


class FakeContext:
    def __init__(self, page):
        self.pages = [page]


class FakeBrowser:
    def __init__(self, page):
        self._contexts = [FakeContext(page)]

    @property
    def contexts(self):
        return self._contexts


@pytest.mark.asyncio
async def test_direct_extract_happy_path():
    """All selectors found, returns dict of extracted text."""
    page = FakePage({
        "h1.title": "  Breaking News: AI Gets Faster  ",
        ".author": "Sam S.",
    })

    selectors = {
        "title": {
            "selector": "h1.title",
            "fallback_selectors": [],
            "description": "Article title",
        },
        "author": {
            "selector": ".author",
            "fallback_selectors": [],
            "description": "Author name",
        },
    }

    with patch("src.browser.direct_extract.async_playwright") as mock_pw:
        mock_instance = AsyncMock()
        mock_instance.chromium.connect_over_cdp = AsyncMock(return_value=FakeBrowser(page))
        mock_pw.return_value.start = AsyncMock(return_value=mock_instance)
        mock_instance.stop = AsyncMock()

        result = await direct_extract("ws://fake:1234", selectors)

    assert result is not None
    assert result["title"] == "Breaking News: AI Gets Faster"
    assert result["author"] == "Sam S."


@pytest.mark.asyncio
async def test_direct_extract_fallback_on_empty():
    """Primary returns empty string → returns None for agent fallback."""
    page = FakePage({
        "h1.title": "   ",  # Whitespace only
    })

    selectors = {
        "title": {
            "selector": "h1.title",
            "fallback_selectors": [],
            "description": "Title",
        },
    }

    with patch("src.browser.direct_extract.async_playwright") as mock_pw:
        mock_instance = AsyncMock()
        mock_instance.chromium.connect_over_cdp = AsyncMock(return_value=FakeBrowser(page))
        mock_pw.return_value.start = AsyncMock(return_value=mock_instance)
        mock_instance.stop = AsyncMock()

        result = await direct_extract("ws://fake:1234", selectors)

    assert result is None


@pytest.mark.asyncio
async def test_direct_extract_fallback_on_timeout():
    """Primary selector throws exception → tries fallback → returns None if all fail."""
    page = FakePage({
        # Primary "h1.missing" not in dict → raises exception
        ".alt-title": "Fallback Title",
    })

    selectors = {
        "title": {
            "selector": "h1.missing",
            "fallback_selectors": [".alt-title"],
            "description": "Title",
        },
    }

    with patch("src.browser.direct_extract.async_playwright") as mock_pw:
        mock_instance = AsyncMock()
        mock_instance.chromium.connect_over_cdp = AsyncMock(return_value=FakeBrowser(page))
        mock_pw.return_value.start = AsyncMock(return_value=mock_instance)
        mock_instance.stop = AsyncMock()

        result = await direct_extract("ws://fake:1234", selectors)

    assert result is not None
    assert result["title"] == "Fallback Title"


@pytest.mark.asyncio
async def test_direct_extract_all_selectors_fail():
    """Primary and all fallbacks fail → returns None."""
    page = FakePage({})  # Empty, everything throws

    selectors = {
        "title": {
            "selector": "h1.missing",
            "fallback_selectors": [".also-missing", "#nope"],
            "description": "Title",
        },
    }

    with patch("src.browser.direct_extract.async_playwright") as mock_pw:
        mock_instance = AsyncMock()
        mock_instance.chromium.connect_over_cdp = AsyncMock(return_value=FakeBrowser(page))
        mock_pw.return_value.start = AsyncMock(return_value=mock_instance)
        mock_instance.stop = AsyncMock()

        result = await direct_extract("ws://fake:1234", selectors)

    assert result is None


@pytest.mark.asyncio
async def test_direct_extract_empty_selectors():
    """Empty extraction_selectors dict → returns None immediately."""
    result = await direct_extract("ws://fake:1234", {})
    assert result is None


@pytest.mark.asyncio
async def test_direct_extract_none_selectors():
    """None extraction_selectors → returns None immediately."""
    result = await direct_extract("ws://fake:1234", None)
    assert result is None


# ──────────────────────────────────────────────────────────────
# Speculative browser pre-creation tests
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_browser_silent_returns_timing():
    """_create_browser_silent() returns (mgr, browser, cdp_url, creation_ms)."""
    from unittest.mock import patch
    import os

    mock_browser = MagicMock()
    mock_browser.cdp_url = "ws://test:1234"
    mock_browser.live_url = "https://live.test"
    mock_browser.browser_id = "test-123"

    mock_mgr = AsyncMock()
    mock_mgr.create = AsyncMock(return_value=mock_browser)

    with patch.dict(os.environ, {"BROWSER_USE_API_KEY": "test-key"}), \
         patch("src.browser.cloud.CloudBrowserManager", return_value=mock_mgr):
        from src.api import _create_browser_silent

        mgr, browser, cdp_url, creation_ms = await _create_browser_silent()

    assert cdp_url == "ws://test:1234"
    assert creation_ms >= 0
    assert browser.browser_id == "test-123"


@pytest.mark.asyncio
async def test_create_browser_silent_no_api_key():
    """_create_browser_silent() raises if BROWSER_USE_API_KEY not set."""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {}, clear=True):
        # Unset the key
        os.environ.pop("BROWSER_USE_API_KEY", None)
        from src.api import _create_browser_silent
        with pytest.raises(RuntimeError, match="BROWSER_USE_API_KEY"):
            await _create_browser_silent()
