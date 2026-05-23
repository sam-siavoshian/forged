# Contributing

Thanks for considering a PR.

## Setup

```bash
git clone https://github.com/sam-siavoshian/forged.git
cd forged
bash setup_mcp.sh                # backend deps + register MCP server
cd frontend && bun install && cd ..
cp .env.example .env             # then fill in the keys
```

Required keys (see `.env.example`):

- `ANTHROPIC_API_KEY` (Claude Sonnet + Haiku)
- `OPENAI_API_KEY` (embeddings)
- `BROWSER_USE_API_KEY` (cloud browser BaaS)
- `SUPABASE_URL` / `SUPABASE_KEY` / `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_DB_URL`

## Run locally

```bash
./dev.sh         # backend on :8000, dashboard on :5173
```

## Tests

```bash
pytest tests/ -v                       # unit + integration
pytest tests/ -v -m "not integration"  # unit only (no real API keys needed)
```

Integration tests hit Anthropic, OpenAI, Browser Use, and Supabase. Skip them locally unless your keys are set.

## Filing PRs

- Keep diffs small. One concern per PR.
- Open a draft PR early for non-trivial work so we can agree on the approach before the refactor.
- Include manual repro steps for behavior changes.
- Match the existing voice: lowercase headers, numbers over adjectives, no fluff.

## Bugs

Use the templates under [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/). Include:

- OS, Python version, Playwright version
- MCP client (Claude Code, Cursor, Windsurf, etc)
- The task that failed + the failure mode (template miss, selector break, agent loop, etc)
- Live browser URL from the run if the session was preserved
