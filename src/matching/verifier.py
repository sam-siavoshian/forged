"""LLM verification for medium-confidence template matches.

Uses Claude Haiku to verify whether a template genuinely fits a user's
task before executing, preventing false-positive matches.
"""

import logging

from anthropic import AsyncAnthropic

from src import config

logger = logging.getLogger(__name__)

VERIFIER_SYSTEM = (
    "You verify whether a browser automation template matches a user's task. "
    "Respond with only \"yes\" or \"no\"."
)

VERIFIER_USER = """\
Does this template match the task?

Task: "{task_description}"
Template: "{template_task_pattern}" on {domain}
Similarity: {similarity:.0%}

Answer "yes" if the template can accomplish the task with the right parameters.
Answer "no" if the task requires fundamentally different actions.\
"""


async def verify_template_match(
    task_description: str,
    template_task_pattern: str,
    domain: str,
    similarity: float,
    client: AsyncAnthropic | None = None,
) -> bool:
    """Verify a medium-confidence match using Claude Haiku.

    Returns True if the LLM confirms the template fits the task.
    """
    if client is None:
        client = AsyncAnthropic()

    user_prompt = VERIFIER_USER.format(
        task_description=task_description,
        template_task_pattern=template_task_pattern,
        domain=domain,
        similarity=similarity,
    )

    logger.info(
        "Verifying match: task=%r template=%r similarity=%.2f",
        task_description[:80],
        template_task_pattern[:80],
        similarity,
    )

    response = await client.messages.create(
        model=config.MODEL_VERIFIER,
        max_tokens=8,
        system=VERIFIER_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.0,
    )

    answer = response.content[0].text.strip().lower()
    is_match = answer.startswith("yes")

    logger.info("Verification result: %s (raw: %r)", is_match, answer)
    return is_match
