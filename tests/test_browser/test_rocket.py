"""Tests for PlaywrightRocket."""

from __future__ import annotations

import pytest

from unittest.mock import AsyncMock, MagicMock, patch

from src.browser.rocket import (
    PlaywrightRocket,
    RocketAbortError,
    _aria_label_from_css_selector,
    _execute_step,
    execute_rocket_phase,
)
from src.models import RocketResult, TemplateStep


def _step(action="navigate", **kwargs) -> TemplateStep:
    """Helper to create TemplateStep with sensible defaults."""
    defaults = {
        "index": 0,
        "type": "fixed",
        "action": action,
        "timeout_ms": 1000,
    }
    defaults.update(kwargs)
    return TemplateStep(**defaults)


@pytest.fixture
def rocket():
    return PlaywrightRocket()


# --- _execute_step unit tests ---


@pytest.mark.asyncio
async def test_execute_step_navigate():
    page = AsyncMock()
    step = _step("navigate", value="https://example.com")
    await _execute_step(page, step, 0)
    page.goto.assert_called_once_with(
        "https://example.com", wait_until="domcontentloaded", timeout=1000
    )


@pytest.mark.asyncio
async def test_execute_step_navigate_uses_url_field():
    page = AsyncMock()
    step = _step("navigate", url="https://example.com", value=None)
    await _execute_step(page, step, 0)
    page.goto.assert_called_once_with(
        "https://example.com", wait_until="domcontentloaded", timeout=1000
    )


@pytest.mark.asyncio
async def test_execute_step_click():
    page = AsyncMock()
    step = _step("click", selector="#btn")
    await _execute_step(page, step, 0)
    page.wait_for_selector.assert_called_once_with("#btn", state="visible", timeout=1000)
    page.click.assert_called_once_with("#btn")


@pytest.mark.asyncio
async def test_execute_step_fill():
    page = AsyncMock()
    step = _step("fill", selector="#input", value="hello")
    await _execute_step(page, step, 0)
    # clear_first=True by default, so fill called twice (clear + value)
    assert page.fill.call_count == 2
    page.fill.assert_any_call("#input", "")
    page.fill.assert_any_call("#input", "hello")


@pytest.mark.asyncio
async def test_execute_step_fill_no_clear():
    page = AsyncMock()
    step = _step("fill", selector="#input", value="hello", clear_first=False)
    await _execute_step(page, step, 0)
    assert page.fill.call_count == 1
    page.fill.assert_called_once_with("#input", "hello")


def test_aria_label_from_css_selector_extracts_quoted_value():
    assert _aria_label_from_css_selector(
        "a[aria-label='Price: Low to High']"
    ) == "Price: Low to High"
    assert _aria_label_from_css_selector(
        'button[aria-label="Sort by price"]'
    ) == "Sort by price"
    assert _aria_label_from_css_selector("#id-only") is None


@pytest.mark.asyncio
async def test_execute_step_click_role_option_when_css_times_out():
    """Stale Amazon CSS; role=option matches native sort dropdown (see terminal logs)."""
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    page = AsyncMock()
    page.wait_for_selector.side_effect = PlaywrightTimeout("no css match")

    mock_first = AsyncMock()
    mock_first.wait_for = AsyncMock()
    mock_first.click = AsyncMock()
    mock_loc = MagicMock()
    mock_loc.first = mock_first
    page.get_by_role = MagicMock(return_value=mock_loc)

    step = _step(
        "click",
        selector="a[aria-label='Price: Low to High']",
        timeout_ms=5000,
    )
    await _execute_step(page, step, 0)

    page.get_by_role.assert_called_once_with("option", name="Price: Low to High", exact=False)
    mock_first.wait_for.assert_called_once()
    mock_first.click.assert_called_once()


@pytest.mark.asyncio
async def test_execute_step_input_alias_for_fill():
    """Template analyzer emits 'input' (browser-use); rocket maps it to fill."""
    page = AsyncMock()
    step = _step("input", selector="#twotabsearchtextbox", value="query")
    await _execute_step(page, step, 0)
    assert page.fill.call_count == 2
    page.fill.assert_any_call("#twotabsearchtextbox", "")
    page.fill.assert_any_call("#twotabsearchtextbox", "query")


@pytest.mark.asyncio
async def test_execute_step_press_with_selector():
    page = AsyncMock()
    step = _step("press", selector="#input", key="Enter")
    await _execute_step(page, step, 0)
    page.press.assert_called_once_with("#input", "Enter")


@pytest.mark.asyncio
async def test_execute_step_press_no_selector():
    page = AsyncMock()
    step = _step("press", key="Escape")
    await _execute_step(page, step, 0)
    page.keyboard.press.assert_called_once_with("Escape")


@pytest.mark.asyncio
async def test_execute_step_press_missing_key():
    page = AsyncMock()
    step = _step("press")
    with pytest.raises(RocketAbortError, match="missing key/value"):
        await _execute_step(page, step, 0)


@pytest.mark.asyncio
async def test_execute_step_wait():
    page = AsyncMock()
    step = _step("wait", selector=".loaded")
    await _execute_step(page, step, 0)
    page.wait_for_selector.assert_called_once_with(".loaded", state="visible", timeout=1000)


@pytest.mark.asyncio
async def test_execute_step_unknown_action():
    page = AsyncMock()
    step = _step("teleport")
    with pytest.raises(RocketAbortError, match="Unknown action"):
        await _execute_step(page, step, 0)


@pytest.mark.asyncio
async def test_execute_step_timeout_becomes_abort():
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    page = AsyncMock()
    page.wait_for_selector.side_effect = PlaywrightTimeout("timeout")
    step = _step("click", selector="#missing")
    with pytest.raises(RocketAbortError, match="No selector found"):
        await _execute_step(page, step, 0)


# --- Fallback selectors ---


@pytest.mark.asyncio
async def test_fallback_selector_used():
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    page = AsyncMock()
    # Primary selector fails, fallback succeeds
    page.wait_for_selector.side_effect = [
        PlaywrightTimeout("not found"),
        None,  # fallback works
    ]

    step = _step("click", selector="#primary", fallback_selectors=["#fallback"])
    await _execute_step(page, step, 0)
    page.click.assert_called_once_with("#fallback")


@pytest.mark.asyncio
async def test_all_selectors_fail():
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    page = AsyncMock()
    page.wait_for_selector.side_effect = PlaywrightTimeout("not found")

    step = _step("click", selector="#a", fallback_selectors=["#b", "#c"])
    with pytest.raises(RocketAbortError, match="No selector found.*tried 3"):
        await _execute_step(page, step, 0)


# --- Full rocket execution (mocked Playwright) ---


@pytest.mark.asyncio
async def test_rocket_empty_steps(rocket: PlaywrightRocket):
    result = await rocket.execute("wss://fake", [])
    assert result.steps_completed == 0
    assert result.total_steps == 0
    assert result.aborted is False


@pytest.mark.asyncio
async def test_rocket_all_steps_succeed(rocket: PlaywrightRocket):
    mock_page = AsyncMock()
    mock_page.url = "https://example.com/done"

    mock_browser = AsyncMock()
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser.contexts = [mock_context]

    mock_pw = AsyncMock()

    with patch("src.browser.rocket.async_playwright") as mock_ap:
        mock_ap_instance = AsyncMock()
        mock_ap_instance.chromium.connect_over_cdp.return_value = mock_browser
        mock_ap.return_value.start.return_value = mock_ap_instance

        # Patch _connect_playwright directly for simplicity
        with patch("src.browser.rocket._connect_playwright") as mock_connect:
            mock_connect.return_value = (mock_pw, mock_browser, mock_page)

            steps = [
                _step("navigate", value="https://example.com"),
                _step("click", selector="#btn", index=1),
            ]
            result = await rocket.execute("wss://fake", steps)

    assert result.steps_completed == 2
    assert result.total_steps == 2
    assert result.aborted is False
    assert result.current_url == "https://example.com/done"
    assert len(result.step_timings) == 2
    mock_browser.disconnect.assert_called_once()
    mock_pw.stop.assert_called_once()


@pytest.mark.asyncio
async def test_rocket_aborts_on_failure(rocket: PlaywrightRocket):
    mock_page = AsyncMock()
    mock_page.url = "https://example.com"

    # First step succeeds, second fails
    call_count = 0
    original_goto = mock_page.goto

    async def mock_goto(*args, **kwargs):
        nonlocal call_count
        call_count += 1

    mock_page.goto = mock_goto

    from playwright.async_api import TimeoutError as PlaywrightTimeout

    mock_page.wait_for_selector.side_effect = PlaywrightTimeout("not found")

    mock_browser = AsyncMock()
    mock_pw = AsyncMock()

    with patch("src.browser.rocket._connect_playwright") as mock_connect:
        mock_connect.return_value = (mock_pw, mock_browser, mock_page)

        steps = [
            _step("navigate", value="https://example.com"),
            _step("click", selector="#missing", index=1),
        ]
        result = await rocket.execute("wss://fake", steps)

    assert result.steps_completed == 1
    assert result.total_steps == 2
    assert result.aborted is True
    assert "No selector found" in result.abort_reason
    # Playwright always disconnected even on abort
    mock_browser.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_rocket_disconnects_on_connection_error(rocket: PlaywrightRocket):
    """If _connect_playwright raises, we should still clean up."""
    with patch("src.browser.rocket._connect_playwright") as mock_connect:
        mock_connect.side_effect = Exception("CDP connection refused")

        steps = [_step("navigate", value="https://example.com")]

        with pytest.raises(Exception, match="CDP connection refused"):
            await rocket.execute("wss://fake", steps)


# --- Convenience function ---


@pytest.mark.asyncio
async def test_execute_rocket_phase_convenience():
    with patch.object(PlaywrightRocket, "execute") as mock_execute:
        mock_execute.return_value = RocketResult(
            steps_completed=1, total_steps=1, duration_seconds=0.1, aborted=False
        )

        result = await execute_rocket_phase("wss://fake", [_step("navigate", value="https://example.com")])

    assert result.steps_completed == 1
    mock_execute.assert_called_once()
