"""Action type classification from task descriptions.

Uses Claude Haiku for generalized classification — no hardcoded keyword maps.
Classifies into: purchase, search, form_fill, navigate, extract, login, or other.
"""

import logging
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


VALID_ACTION_TYPES = config.ACTION_TYPES


def classify_action_type(task_description: str) -> str | None:
    """Classify a task description into an action type using LLM.

    Returns one of: purchase, search, form_fill, navigate, extract, login,
    interact, or None if unclassifiable.
    """
    return _llm_classify_action(task_description)


@lru_cache(maxsize=128)
def _llm_classify_action(task_description: str) -> str | None:
    """Use Claude Haiku to classify the action type."""
    client = _get_anthropic()

    response = client.messages.create(
        model=config.MODEL_ACTION_CLASSIFIER,
        max_tokens=15,
        system=(
            "Classify the browser task into exactly ONE action type. "
            "Respond with ONLY one word from this list:\n"
            "purchase - buying/ordering/adding to cart\n"
            "search - searching/finding/looking up information\n"
            "form_fill - filling forms/submitting/registering/signing up\n"
            "navigate - visiting/opening/going to a page\n"
            "extract - scraping/copying/downloading data\n"
            "login - signing in/authenticating\n"
            "interact - general clicking/browsing/engaging with a site\n"
            "If the task doesn't fit any category, respond with: none"
        ),
        messages=[{"role": "user", "content": task_description}],
        temperature=0.0,
    )

    result = response.content[0].text.strip().lower()

    if result in VALID_ACTION_TYPES:
        logger.info("LLM classified action: %s for: %s", result, task_description[:80])
        return result

    logger.debug("LLM action classification returned '%s' for: %s", result, task_description[:80])
    return None
