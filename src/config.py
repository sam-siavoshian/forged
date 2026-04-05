"""Centralized configuration for the Forge system.

All tunable constants are defined here and read from environment variables
with sensible defaults. No magic numbers should exist outside this file.

Environment variable naming convention: FORGE_{SECTION}_{KEY}
Example: FORGE_MODEL_AGENT=claude-sonnet-4-6
"""

from __future__ import annotations

import os


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, str(default)))


# ---------------------------------------------------------------------------
# LLM Models — every model name in one place
# ---------------------------------------------------------------------------

MODEL_AGENT = _env("FORGE_MODEL_AGENT", "claude-sonnet-4-6")
MODEL_ANALYZER = _env("FORGE_MODEL_ANALYZER", "claude-sonnet-4-6")
MODEL_HAIKU = _env("FORGE_MODEL_HAIKU", "claude-haiku-4-5-20251001")

# Haiku is used for: domain extraction, action classification, step filtering,
# parameter extraction, template verification, and answer extraction.
# Override individually if needed:
MODEL_DOMAIN_EXTRACTOR = _env("FORGE_MODEL_DOMAIN_EXTRACTOR", MODEL_HAIKU)
MODEL_ACTION_CLASSIFIER = _env("FORGE_MODEL_ACTION_CLASSIFIER", MODEL_HAIKU)
MODEL_STEP_FILTER = _env("FORGE_MODEL_STEP_FILTER", MODEL_HAIKU)
MODEL_PARAM_EXTRACTOR = _env("FORGE_MODEL_PARAM_EXTRACTOR", MODEL_HAIKU)
MODEL_VERIFIER = _env("FORGE_MODEL_VERIFIER", MODEL_HAIKU)
MODEL_ANSWER_EXTRACTOR = _env("FORGE_MODEL_ANSWER_EXTRACTOR", MODEL_HAIKU)


# ---------------------------------------------------------------------------
# Matching thresholds — control template search and confidence bands
# ---------------------------------------------------------------------------

SIMILARITY_THRESHOLD = _env_float("FORGE_SIMILARITY_THRESHOLD", 0.50)
SIMILARITY_VERY_HIGH = _env_float("FORGE_SIMILARITY_VERY_HIGH", 0.90)
SIMILARITY_HIGH = _env_float("FORGE_SIMILARITY_HIGH", 0.75)

# Minimum confidence in DB to even consider a template
DB_MIN_CONFIDENCE = _env_float("FORGE_DB_MIN_CONFIDENCE", 0.2)

# Max results from similarity search
DB_RESULT_LIMIT = _env_int("FORGE_DB_RESULT_LIMIT", 5)

# Direct extraction requires this minimum similarity
DIRECT_EXTRACT_MIN_SIMILARITY = _env_float("FORGE_DIRECT_EXTRACT_MIN_SIMILARITY", 0.90)


# ---------------------------------------------------------------------------
# Confidence learning — how template confidence updates after execution
# ---------------------------------------------------------------------------

CONFIDENCE_SUCCESS_INCREMENT = _env_float("FORGE_CONFIDENCE_SUCCESS_INCREMENT", 0.1)
CONFIDENCE_FAILURE_DECREMENT = _env_float("FORGE_CONFIDENCE_FAILURE_DECREMENT", 0.2)


# ---------------------------------------------------------------------------
# Agent configuration
# ---------------------------------------------------------------------------

AGENT_MAX_FAILURES = _env_int("FORGE_AGENT_MAX_FAILURES", 5)
AGENT_MAX_ACTIONS_PER_STEP = _env_int("FORGE_AGENT_MAX_ACTIONS_PER_STEP", 5)
AGENT_MAX_TOKENS = _env_int("FORGE_AGENT_MAX_TOKENS", 8096)
AGENT_NETWORK_IDLE_TIMEOUT = _env_float("FORGE_AGENT_NETWORK_IDLE_TIMEOUT", 12.0)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

ORCHESTRATOR_MAX_AGENT_STEPS = _env_int("FORGE_ORCHESTRATOR_MAX_AGENT_STEPS", 25)
ORCHESTRATOR_STEP_TIMEOUT_S = _env_int("FORGE_ORCHESTRATOR_STEP_TIMEOUT_S", 30)


# ---------------------------------------------------------------------------
# Action timeouts (ms) — Playwright timeout for executing each action type
# ---------------------------------------------------------------------------

ACTION_TIMEOUT_MS: dict[str, int] = {
    "navigate": _env_int("FORGE_TIMEOUT_NAVIGATE", 15000),
    "click": _env_int("FORGE_TIMEOUT_CLICK", 5000),
    "fill": _env_int("FORGE_TIMEOUT_FILL", 5000),
    "input": _env_int("FORGE_TIMEOUT_INPUT", 5000),
    "press": _env_int("FORGE_TIMEOUT_PRESS", 3000),
    "send_keys": _env_int("FORGE_TIMEOUT_SEND_KEYS", 3000),
    "wait": _env_int("FORGE_TIMEOUT_WAIT", 5000),
    "scroll": _env_int("FORGE_TIMEOUT_SCROLL", 2000),
    "select_dropdown": _env_int("FORGE_TIMEOUT_SELECT_DROPDOWN", 5000),
    "go_back": _env_int("FORGE_TIMEOUT_GO_BACK", 10000),
}
ACTION_TIMEOUT_DEFAULT = _env_int("FORGE_TIMEOUT_DEFAULT", 5000)


# ---------------------------------------------------------------------------
# Post-action wait times (ms) — settling delay after each action type
# ---------------------------------------------------------------------------

ACTION_WAIT_MS: dict[str, int] = {
    "navigate": _env_int("FORGE_WAIT_NAVIGATE", 2000),
    "click": _env_int("FORGE_WAIT_CLICK", 1000),
    "input": _env_int("FORGE_WAIT_INPUT", 200),
    "send_keys": _env_int("FORGE_WAIT_SEND_KEYS", 500),
    "search": _env_int("FORGE_WAIT_SEARCH", 2000),
    "go_back": _env_int("FORGE_WAIT_GO_BACK", 1500),
    "select_dropdown": _env_int("FORGE_WAIT_SELECT_DROPDOWN", 500),
    "scroll": _env_int("FORGE_WAIT_SCROLL", 300),
}
ACTION_WAIT_DEFAULT = _env_int("FORGE_WAIT_DEFAULT", 100)


# ---------------------------------------------------------------------------
# Rocket selector retry budgets (ms)
# ---------------------------------------------------------------------------

SELECTOR_PRIMARY_BUDGET_CAP = _env_int("FORGE_SELECTOR_PRIMARY_CAP", 8000)
SELECTOR_FALLBACK_CAP = _env_int("FORGE_SELECTOR_FALLBACK_CAP", 2000)
SELECTOR_FALLBACK_FLOOR = _env_int("FORGE_SELECTOR_FALLBACK_FLOOR", 800)
SELECTOR_ROLE_BUDGET_MIN = _env_int("FORGE_SELECTOR_ROLE_MIN", 1500)
SELECTOR_ROLE_BUDGET_MAX = _env_int("FORGE_SELECTOR_ROLE_MAX", 3500)


# ---------------------------------------------------------------------------
# Text extraction caps — max characters to send to LLM or extract from page
# ---------------------------------------------------------------------------

PAGE_TEXT_CAP = _env_int("FORGE_PAGE_TEXT_CAP", 15000)
LLM_INPUT_TEXT_CAP = _env_int("FORGE_LLM_INPUT_TEXT_CAP", 8000)


# ---------------------------------------------------------------------------
# Direct extraction
# ---------------------------------------------------------------------------

DIRECT_EXTRACT_TIMEOUT_MS = _env_int("FORGE_DIRECT_EXTRACT_TIMEOUT_MS", 3000)
DIRECT_EXTRACT_FALLBACK_TIMEOUT_MS = _env_int(
    "FORGE_DIRECT_EXTRACT_FALLBACK_TIMEOUT_MS", 1000
)


# ---------------------------------------------------------------------------
# Step filter
# ---------------------------------------------------------------------------

STEP_FILTER_MIN_STEPS = _env_int("FORGE_STEP_FILTER_MIN_STEPS", 2)
STEP_FILTER_MAX_TOKENS = _env_int("FORGE_STEP_FILTER_MAX_TOKENS", 1024)


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

SESSION_TTL_SECONDS = _env_int("FORGE_SESSION_TTL_SECONDS", 300)


# ---------------------------------------------------------------------------
# Domain extraction — supported TLDs for regex-based detection
# ---------------------------------------------------------------------------

DOMAIN_TLDS = _env(
    "FORGE_DOMAIN_TLDS",
    "com,org,net,io,co,dev,app,edu,gov,me,ai,xyz,cloud,tech,info,biz,us,uk,ca",
).split(",")


# ---------------------------------------------------------------------------
# Action types — extensible set of recognized task categories
# ---------------------------------------------------------------------------

ACTION_TYPES = set(
    _env(
        "FORGE_ACTION_TYPES",
        "purchase,search,form_fill,navigate,extract,login,interact",
    ).split(",")
)


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

EMBEDDING_DIMENSIONS = _env_int("FORGE_EMBEDDING_DIMENSIONS", 3072)
