"""Action type classification from task descriptions.

Classifies tasks into one of six action types using keyword scoring:
purchase, search, form_fill, navigate, extract, login.
"""

ACTION_KEYWORDS: dict[str, list[str]] = {
    "purchase": [
        "buy",
        "purchase",
        "order",
        "add to cart",
        "checkout",
        "add to bag",
    ],
    "search": ["search", "find", "look up", "look for", "query"],
    "form_fill": [
        "fill",
        "submit",
        "complete",
        "apply",
        "sign up",
        "register",
        "contact form",
    ],
    "navigate": ["go to", "navigate", "open", "visit", "browse to"],
    "extract": ["extract", "scrape", "get the", "copy", "download", "grab"],
    "login": ["log in", "login", "sign in", "authenticate"],
}


def classify_action_type(task_description: str) -> str | None:
    """Classify a task description into an action type.

    Returns the action type string or None if unclear.
    Uses keyword frequency — if multiple match, picks the one with more keyword hits.
    """
    task_lower = task_description.lower()
    scores: dict[str, int] = {}

    for action, keywords in ACTION_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in task_lower:
                score += 1
        if score > 0:
            scores[action] = score

    if not scores:
        return None

    return max(scores, key=lambda k: scores[k])
