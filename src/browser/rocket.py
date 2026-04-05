"""Playwright rocket phase — executes deterministic template steps at millisecond speed."""

from __future__ import annotations

import logging
import re
import time

from playwright.async_api import (
    Browser,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
    async_playwright,
)

from src.models import RocketResult, TemplateStep

logger = logging.getLogger("rocket_booster.rocket")


class RocketAbortError(Exception):
    """Raised when a template step fails and we must hand off to the agent early."""

    def __init__(self, step_index: int, step: TemplateStep, reason: str):
        self.step_index = step_index
        self.step = step
        self.reason = reason
        super().__init__(f"Rocket aborted at step {step_index}: {reason}")


async def _connect_playwright(cdp_url: str) -> tuple[Playwright, Browser, Page]:
    """Connect Playwright to an existing cloud browser via CDP.

    Returns the Playwright instance, Browser handle, and the active Page.
    The caller MUST call disconnect when done.
    """
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(cdp_url)

    default_context = browser.contexts[0]
    page = (
        default_context.pages[0]
        if default_context.pages
        else await default_context.new_page()
    )

    return pw, browser, page


def _aria_label_from_css_selector(selector: str | None) -> str | None:
    """Extract text from CSS [aria-label='...'] / [aria-label=\"...\"] for locator fallback."""
    if not selector:
        return None
    m = re.search(r"aria-label\s*=\s*(['\"])([^'\"]+)\1", selector, re.I)
    return m.group(2).strip() if m else None


def _click_label_candidates(step: TemplateStep) -> list[str]:
    """Build ordered labels for get_by_role('option') when CSS selectors are stale."""
    seen: set[str] = set()
    out: list[str] = []
    v = (step.value or "").strip()
    if v and len(v) < 200:
        seen.add(v)
        out.append(v)
    for sel in [step.selector, *step.fallback_selectors]:
        al = _aria_label_from_css_selector(sel)
        if al and al not in seen:
            seen.add(al)
            out.append(al)
    return out


async def _try_click_role_option(page: Page, label: str, timeout_ms: int) -> bool:
    """Amazon/native <select> options expose role=option; CSS often breaks after DOM churn."""
    try:
        loc = page.get_by_role("option", name=label, exact=False)
        first = loc.first
        await first.wait_for(state="visible", timeout=timeout_ms)
        await first.click(timeout=timeout_ms)
        return True
    except Exception:
        return False


async def _try_selector(
    page: Page, step: TemplateStep, step_index: int
) -> str:
    """Try the primary selector, then each fallback. Returns the working selector.

    Primary uses full timeout_ms; fallbacks use a short budget so 4 stale selectors
    do not cost ~4× the full timeout (runtime evidence: ~20s for 4×5s).

    Raises RocketAbortError if none work.
    """
    selectors = [step.selector] + step.fallback_selectors if step.selector else []
    nonempty = [s for s in selectors if s]

    for i, selector in enumerate(nonempty):
        # First attempt: full budget (capped). Later: fast-fail — templates often
        # store redundant fallbacks that all miss after a site redesign.
        if i == 0:
            budget = min(step.timeout_ms, 8000)
        else:
            budget = min(2000, max(800, step.timeout_ms // 3))

        try:
            await page.wait_for_selector(
                selector, state=step.state, timeout=budget
            )
            return selector
        except PlaywrightTimeout:
            continue

    raise RocketAbortError(
        step_index,
        step,
        f"No selector found (tried {len(nonempty)}): primary='{step.selector}', "
        f"fallbacks={step.fallback_selectors}",
    )


async def _execute_click(page: Page, step: TemplateStep, step_index: int) -> None:
    """Click via CSS selector, then role=option by aria-label/value if CSS is stale."""
    role_budget = min(3500, max(1500, step.timeout_ms))
    try:
        selector = await _try_selector(page, step, step_index)
        await page.click(selector)
        return
    except RocketAbortError:
        for label in _click_label_candidates(step):
            if await _try_click_role_option(page, label, role_budget):
                logger.info(
                    "Click recovered via get_by_role(option) label=%r (CSS stale)",
                    label[:60] + ("..." if len(label) > 60 else ""),
                )
                return
        raise


async def _execute_step(page: Page, step: TemplateStep, step_index: int) -> None:
    """Execute a single template step against the Playwright page.

    Raises RocketAbortError if the step cannot be completed.
    """
    try:
        if step.action == "navigate":
            await page.goto(
                step.value or step.url,
                wait_until="domcontentloaded",
                timeout=step.timeout_ms,
            )

        elif step.action == "click":
            await _execute_click(page, step, step_index)

        elif step.action in ("fill", "input"):
            # "input" is browser-use / template vocabulary; Playwright uses fill().
            selector = await _try_selector(page, step, step_index)
            if step.clear_first:
                await page.fill(selector, "")
            await page.fill(selector, step.value or "")

        elif step.action == "press":
            key = step.key or step.value
            if not key:
                raise RocketAbortError(step_index, step, "Press step missing key/value")
            if step.selector:
                selector = await _try_selector(page, step, step_index)
                await page.press(selector, key)
            else:
                await page.keyboard.press(key)

        elif step.action == "wait":
            await _try_selector(page, step, step_index)

        elif step.action == "scroll":
            delta = step.amount or 300
            if step.direction == "up":
                delta = -delta
            await page.mouse.wheel(0, delta)

        elif step.action == "wait_time":
            import asyncio

            await asyncio.sleep((step.ms or 1000) / 1000.0)

        else:
            raise RocketAbortError(step_index, step, f"Unknown action: {step.action}")

    except RocketAbortError:
        raise
    except PlaywrightTimeout:
        if step.action == "navigate":
            target = step.value or step.url or "unknown URL"
            msg = f"Timeout after {step.timeout_ms}ms navigating to '{target}'"
        else:
            msg = f"Timeout after {step.timeout_ms}ms on selector '{step.selector}'"
        raise RocketAbortError(step_index, step, msg)
    except Exception as e:
        raise RocketAbortError(step_index, step, str(e))


class PlaywrightRocket:
    """Executes template steps against a cloud browser via Playwright CDP."""

    async def execute(
        self,
        cdp_url: str,
        template_steps: list[TemplateStep],
    ) -> RocketResult:
        """Connect to the cloud browser, run all steps, disconnect cleanly.

        On any step failure, aborts gracefully and returns partial progress.
        CRITICAL: Uses browser.disconnect() NOT browser.close() to preserve the BaaS browser.
        """
        if not template_steps:
            return RocketResult(
                steps_completed=0,
                total_steps=0,
                duration_seconds=0.0,
                aborted=False,
            )

        pw: Playwright | None = None
        browser: Browser | None = None
        start_time = time.monotonic()
        step_timings: list[float] = []

        try:
            pw, browser, page = await _connect_playwright(cdp_url)
            completed = 0

            for i, step in enumerate(template_steps):
                step_start = time.monotonic()
                try:
                    await _execute_step(page, step, i)
                    step_timings.append(time.monotonic() - step_start)
                    completed += 1
                    logger.info(
                        "Step %d/%d completed in %.0fms: %s",
                        i + 1,
                        len(template_steps),
                        step_timings[-1] * 1000,
                        step.action,
                    )
                except RocketAbortError as e:
                    step_timings.append(time.monotonic() - step_start)
                    logger.warning("Rocket abort at step %d: %s", i, e.reason)
                    return RocketResult(
                        steps_completed=completed,
                        total_steps=len(template_steps),
                        duration_seconds=time.monotonic() - start_time,
                        aborted=True,
                        abort_reason=e.reason,
                        current_url=page.url,
                        step_timings=step_timings,
                    )

            current_url = page.url
            return RocketResult(
                steps_completed=completed,
                total_steps=len(template_steps),
                duration_seconds=time.monotonic() - start_time,
                aborted=False,
                current_url=current_url,
                step_timings=step_timings,
            )

        finally:
            # Release CDP connection without destroying the BaaS browser.
            # Playwright 1.48+ doesn't have disconnect() on Browser.
            # Stopping the Playwright instance releases the CDP connection
            # without sending a Browser.close command to the remote browser.
            if pw:
                await pw.stop()


async def execute_rocket_phase(
    cdp_url: str, template_steps: list[TemplateStep]
) -> RocketResult:
    """Module-level convenience function."""
    rocket = PlaywrightRocket()
    return await rocket.execute(cdp_url, template_steps)
