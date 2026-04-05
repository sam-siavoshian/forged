"""Playwright rocket phase — executes deterministic template steps at millisecond speed."""

from __future__ import annotations

import logging
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


async def _try_selector(
    page: Page, step: TemplateStep, step_index: int
) -> str:
    """Try the primary selector, then each fallback. Returns the working selector.

    Raises RocketAbortError if none work.
    """
    selectors = [step.selector] + step.fallback_selectors if step.selector else []

    for selector in selectors:
        try:
            await page.wait_for_selector(
                selector, state=step.state, timeout=step.timeout_ms
            )
            return selector
        except PlaywrightTimeout:
            continue

    raise RocketAbortError(
        step_index,
        step,
        f"No selector found (tried {len(selectors)}): primary='{step.selector}', "
        f"fallbacks={step.fallback_selectors}",
    )


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
            selector = await _try_selector(page, step, step_index)
            await page.click(selector)

        elif step.action == "fill":
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
        raise RocketAbortError(
            step_index,
            step,
            f"Timeout after {step.timeout_ms}ms on selector '{step.selector}'",
        )
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
