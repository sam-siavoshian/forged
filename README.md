# Forged ⚒️

Browser automation that learns. An MCP server that makes AI agents faster at repeated browser tasks by recording what works and replaying deterministic steps via Playwright.

**47.4s → 8.8s on the second run. 5.4x faster. Zero config.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-server-7c3aed.svg)](https://modelcontextprotocol.io/)
[![Playwright](https://img.shields.io/badge/playwright-1.52-2EAD33.svg)](https://playwright.dev/)

<!-- TODO: add demo.gif (8-12s, <5MB) showing baseline run vs forged run side by side. Replace this comment with: <p align="center"><img src="docs/demo.gif" width="720" alt="Forged demo"></p> -->

## What it does

Every time an AI agent browses a website, it starts from scratch. Login flows, navigation, search bars, all rediscovered through expensive LLM calls. 3 to 5 seconds per step, every single time.

Forged fixes this. It sits between your AI assistant and the browser, records successful traces, extracts reusable templates, and replays deterministic steps at millisecond speed. The LLM only handles steps that genuinely need reasoning.

```
Run 1: Full AI agent. Every step through Claude.              47.4s
Run 2: 9 Playwright steps + 1 agent step.                     8.8s  (5.4x faster)
Run 5: 80% deterministic, 20% reasoning.                      ~3s
```

## Install

```bash
git clone https://github.com/sam-siavoshian/forged.git
cd forged
bash setup_mcp.sh
```

The wizard finds your Python, installs dependencies (`mcp`, `httpx`), and registers Forged with Claude Code at user or project scope. Works with any MCP-compatible assistant (Cursor, Windsurf, etc).

After install, start the backend + frontend dev servers:

```bash
./dev.sh         # backend on :8000, dashboard on :5173
```

Set the keys from `.env.example` first: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `BROWSER_USE_API_KEY`, `SUPABASE_URL` / `SUPABASE_KEY` / `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_DB_URL`.

## How it works

### The matching pipeline

When your AI calls `run_browser_task("Search for keyboards on Amazon")`, three things happen:

1. **Domain extraction**. Regex pulls `amazon.com` from the task. Falls back to Claude Haiku if no URL is present ("Amazon" → `amazon.com`).
2. **Action classification**. Haiku classifies the task into one of 7 categories: `search`, `purchase`, `form_fill`, `navigate`, `extract`, `login`, `interact`.
3. **Vector similarity search**. The task is embedded via OpenAI `text-embedding-3-large` (3072 dimensions) and compared against stored templates using pgvector's `<=>` cosine distance operator. Filtered by domain and action type before the vector search even runs.

If similarity is high enough (≥0.50), a template is matched. If not, the full agent runs and Forged learns a template from the trace.

### Confidence bands

| Band      | Similarity | What happens                            |
| --------- | ---------- | --------------------------------------- |
| Very High | ≥ 90%      | Execute all rocket steps immediately    |
| High      | 75-89%     | Execute all rocket steps                |
| Medium    | 50-74%     | LLM verifies the match before executing |
| No match  | < 50%      | Full agent, auto-learn template         |

Template confidence updates after every execution: success adds `+0.1 * (1 - confidence)`, failure subtracts `0.2 * confidence`. Templates that keep working gain confidence. Templates that break lose it fast.

### Template extraction

After a successful agent run, Forged analyzes the trace and classifies each step:

- **FIXED**. Same action and target every time. Navigate to URL, click a button, press Enter. Replayed via Playwright.
- **PARAMETERIZED**. Same action, different value. Typing a search query into a fixed input field. Playwright fills the extracted parameter.
- **DYNAMIC**. Requires reasoning. Choosing a product by price, answering a CAPTCHA, making a subjective decision. Handled by the AI agent.

The `handoff_index` marks where Playwright stops and the agent takes over. Everything before it is deterministic. Everything after needs intelligence.

```
Template: "Search for {{query}} on Amazon"

Step 0: navigate → amazon.com                    FIXED       (Playwright)
Step 1: click → search input                     FIXED       (Playwright)
Step 2: fill → search input with {{query}}       PARAMETERIZED (Playwright)
Step 3: press → Enter                            FIXED       (Playwright)
                                                 ─── handoff_index = 3 ───
Step 4: click → product matching criteria        DYNAMIC     (Agent)
```

### Step filtering

When a template has 10 steps but the task only needs 5, Forged doesn't blindly run all 10. Claude Haiku evaluates each step against the specific task and marks them `EXECUTE` or `SKIP`. If a step's parameter is missing from the task, it gets skipped. If the task is a subset of the template, only the relevant prefix executes.

One Amazon template handles both "search for keyboards" (steps 0-3) and "search for keyboards and buy the cheapest one" (steps 0-7).

### The rocket engine

Playwright connects to a cloud browser via CDP (Chrome DevTools Protocol) and replays template steps:

1. **Primary selector**. CSS selector with full timeout budget (capped at 8s).
2. **Fallback selectors**. Alternative CSS selectors with reduced timeout (1/3 budget, min 800ms).
3. **Role-based fallback**. `get_by_role("option")` for native `<select>` dropdowns when CSS breaks.
4. **Text/aria fallback**. Extracted aria-label from CSS selectors as last resort.

If a step fails, the `on_failure` strategy kicks in: `retry` (once after 500ms), `continue` (skip it), `try_fallback` (already tried, skip), or `abort` (hand off to agent with context of what completed).

After Playwright finishes, the agent gets a prompt describing exactly what was done: "Playwright finished 5 of 7 steps. Navigation and search are complete. The search results page is loaded. Complete the remaining work from the current page state."

### Why cloud browsers

Forged uses Browser Use's BaaS API for cloud browsers instead of local Playwright because:

- **Handoff**. Rocket connects via CDP, executes Playwright steps, disconnects with `pw.stop()` (not `browser.close()`, which would kill the remote session), then the agent reconnects to the same browser. Local Playwright can't hand off a live session between two different automation libraries.
- **Live debugging**. Every session gets a `live_url` where you can watch the browser in real-time.
- **Isolation**. Each task gets a clean browser. No cross-task state contamination.

Rate limits are handled with exponential backoff: 5s → 10s → 20s → 40s → 80s → 120s (capped), with jitter, up to 6 retries.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Claude Code / Cursor / Windsurf                        │
│  (any MCP-compatible assistant)                         │
└──────────────────────┬──────────────────────────────────┘
                       │ MCP (stdio)
┌──────────────────────▼──────────────────────────────────┐
│  Forged MCP Server                                      │
│  2 tools: run_browser_task, list_learned_skills         │
│  Thin proxy → polls HTTP API                            │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────────┐
│  Forged Backend (FastAPI)                               │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │  Matcher    │  │  Rocket      │  │  Learner      │   │
│  │  3-layer    │  │  Playwright  │  │  Trace → tpl  │   │
│  │  pipeline   │  │  execution   │  │  extraction   │   │
│  └──────┬──────┘  └──────┬───────┘  └───────┬───────┘   │
│         │                │                  │           │
│  ┌──────▼────────────────▼──────────────────▼───────┐   │
│  │  Supabase (PostgreSQL + pgvector)                │   │
│  │  Templates, embeddings, traces, site knowledge   │   │
│  └──────────────────────────────────────────────────┘   │
│                          │                              │
│  ┌───────────────────────▼──────────────────────────┐   │
│  │  Browser Use BaaS (cloud browser via CDP)        │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## MCP tools

### `run_browser_task`

Execute any browser task. Forged handles routing automatically.

```
Input:  task (string), e.g. "Go to news.ycombinator.com and get the top story"
Output: Result text, mode (rocket/baseline), duration, step breakdown, live browser URL
```

If a template matches, Playwright replays deterministic steps and the agent handles the rest. If no template exists, the full agent runs and a template is auto-learned for next time.

### `list_learned_skills`

See what Forged has learned.

```
Input:  domain (string, optional), filter by site (e.g. "amazon.com")
Output: Templates with confidence scores, step counts, usage stats, average speedup
```

## Database

PostgreSQL with pgvector on Supabase. Three tables:

**`task_templates`**. Learned browser automation templates. Each has a domain, action type, task pattern with `{{param}}` placeholders, step array (JSONB), handoff index, 3072-dim embedding, and confidence score that updates after every execution.

**`execution_traces`**. Every run recorded. Mode (rocket vs baseline), step-by-step actions, timing breakdown (rocket ms, agent ms, total ms), success/failure, error context. Used for analysis and debugging.

**`site_knowledge`**. Cached CSS selectors per domain. When a selector works, it's added to the fallback chain. Navigation patterns and page load signals stored for reliability.

The system uses dual connections: `asyncpg` pool for pgvector similarity search (fast, needs direct PG), Supabase REST client for CRUD (works through firewalls). If direct PG is blocked (campus WiFi), it falls back to REST + in-Python cosine similarity via NumPy.

## Project structure

```
src/
  api.py                 FastAPI endpoints + session management
  config.py              All tunable constants (thresholds, timeouts, models)
  models.py              Pydantic models and dataclasses
  orchestrator.py        Task orchestration logic
  browser/
    rocket.py            Playwright execution engine
    agent.py             Browser Use agent wrapper
    agent_handoff.py     Builds context-aware handoff prompts
    cloud.py             Cloud browser lifecycle (BaaS API)
  matching/
    matcher.py           Three-layer matching pipeline
    domain.py            Domain extraction (regex + LLM)
    action_type.py       Action classification (LLM)
    verifier.py          Medium-confidence LLM verification
    step_filter.py       Adapts templates to specific tasks
  template/
    extractor.py         Full extraction pipeline orchestrator
    simplifier.py        Trace cleanup (retry noise, dead ends)
    analyzer.py          LLM step classification (FIXED/PARAM/DYNAMIC)
    generator.py         Canonical template generation
    validator.py         Template validation (ERROR/WARNING checks)
  db/
    client.py            Dual connection management (asyncpg + Supabase)
    setup.py             Schema creation and migration
    templates.py         Template CRUD + confidence learning
    traces.py            Execution trace recording
    embeddings.py        OpenAI embedding generation (3072-dim)
    site_knowledge.py    Selector caching per domain

frontend/               React 19 + TypeScript + Vite + Tailwind dashboard
mcp_server.py           MCP server (2 tools, stdio transport)
setup_mcp.sh            One-command setup wizard
dev.sh                  Local dev runner (backend + frontend)
tests/                  pytest suite mirroring src/ layout
```

## Tech stack

- **Backend**: Python 3.11+, FastAPI 0.115, Uvicorn 0.34
- **Browser automation**: Playwright 1.52 (rocket engine), Browser Use 0.2 (agent), Browser Use BaaS (cloud browsers)
- **LLMs**: Claude Sonnet 4.6 (agent execution, template analysis), Claude Haiku 4.5 (classification, verification, parameter extraction)
- **Embeddings**: OpenAI `text-embedding-3-large` (3072 dimensions)
- **Database**: Supabase PostgreSQL with pgvector
- **Frontend**: React 19, TypeScript, Vite 8, Tailwind 4, Bun
- **MCP**: Official Python MCP SDK 1.0, stdio transport

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). Run `pytest tests/ -v` before opening a PR. Open a draft early for non-trivial changes.

## License

[MIT](LICENSE) © [@sam-siavoshian](https://github.com/sam-siavoshian)

---

Built with ❤️ at Diamond Hack UCSD '26 by Saam Siavoshian.
