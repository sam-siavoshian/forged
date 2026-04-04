"""Browser architecture layer — cloud browser, Playwright rocket, and agent handoff."""

from src.browser.cloud import CloudBrowserManager
from src.browser.rocket import PlaywrightRocket, execute_rocket_phase
from src.browser.agent import BrowserUseAgent, run_agent_phase
from src.browser.handoff import HandoffManager

__all__ = [
    "CloudBrowserManager",
    "PlaywrightRocket",
    "execute_rocket_phase",
    "BrowserUseAgent",
    "run_agent_phase",
    "HandoffManager",
]
