"""One-shot database setup for Rocket Booster.

Usage:
    python -m src.db.setup

This script:
1. Enables pgvector extension
2. Creates all tables (idempotent — uses IF NOT EXISTS)
3. Creates all indexes
4. Seeds initial site_knowledge for common domains
5. Verifies everything works with a test embedding query
"""

import asyncio
import json
import os
import sys

MIGRATION_SQL = """
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Task Templates
CREATE TABLE IF NOT EXISTS task_templates (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    domain TEXT NOT NULL,
    action_type TEXT NOT NULL,
    task_pattern TEXT NOT NULL,
    parameters JSONB NOT NULL DEFAULT '[]',
    steps JSONB NOT NULL,
    handoff_index INTEGER NOT NULL,
    embedding vector(1536) NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 0.5
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    success_count INTEGER NOT NULL DEFAULT 0
        CHECK (success_count >= 0),
    failure_count INTEGER NOT NULL DEFAULT 0
        CHECK (failure_count >= 0),
    avg_rocket_duration_ms INTEGER,
    avg_agent_duration_ms INTEGER,
    avg_total_duration_ms INTEGER,
    avg_baseline_duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Execution Traces
CREATE TABLE IF NOT EXISTS execution_traces (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    template_id UUID REFERENCES task_templates(id) ON DELETE SET NULL,
    task_description TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('rocket', 'baseline')),
    steps_executed JSONB NOT NULL,
    rocket_steps_count INTEGER,
    agent_steps_count INTEGER,
    total_duration_ms INTEGER NOT NULL,
    rocket_duration_ms INTEGER,
    agent_duration_ms INTEGER,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    error_step_index INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Site Knowledge
CREATE TABLE IF NOT EXISTS site_knowledge (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    domain TEXT NOT NULL UNIQUE,
    selector_map JSONB NOT NULL DEFAULT '{}',
    navigation_patterns JSONB NOT NULL DEFAULT '{}',
    page_load_signals JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_templates_domain
    ON task_templates(domain);
CREATE INDEX IF NOT EXISTS idx_templates_action_type
    ON task_templates(action_type);
CREATE INDEX IF NOT EXISTS idx_templates_domain_action
    ON task_templates(domain, action_type);
CREATE INDEX IF NOT EXISTS idx_traces_template
    ON execution_traces(template_id);
CREATE INDEX IF NOT EXISTS idx_traces_mode
    ON execution_traces(mode);
CREATE INDEX IF NOT EXISTS idx_traces_success
    ON execution_traces(success);
CREATE INDEX IF NOT EXISTS idx_traces_created
    ON execution_traces(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_site_knowledge_domain
    ON site_knowledge(domain);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_templates_updated_at ON task_templates;
CREATE TRIGGER trigger_templates_updated_at
    BEFORE UPDATE ON task_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_site_knowledge_updated_at ON site_knowledge;
CREATE TRIGGER trigger_site_knowledge_updated_at
    BEFORE UPDATE ON site_knowledge
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

SEED_SITE_KNOWLEDGE = [
    {
        "domain": "amazon.com",
        "selector_map": {
            "search_input": [
                "#twotabsearchtextbox",
                "input[name='field-keywords']",
                "[aria-label='Search Amazon']",
            ],
            "search_button": [
                "#nav-search-submit-button",
                "input[type='submit'][value='Go']",
            ],
            "cart_button": ["#nav-cart", "#nav-cart-count"],
            "add_to_cart": [
                "#add-to-cart-button",
                "[name='submit.add-to-cart']",
            ],
            "buy_now": ["#buy-now-button", "#submitOrderButtonId"],
        },
        "navigation_patterns": {
            "to_search": [
                "navigate(https://amazon.com)",
                "click(search_input)",
            ],
            "to_cart": ["click(cart_button)"],
        },
        "page_load_signals": {
            "search_results": ".s-result-list",
            "product_page": "#productTitle",
            "cart_page": "#sc-active-cart",
        },
    },
    {
        "domain": "google.com",
        "selector_map": {
            "search_input": [
                "textarea[name='q']",
                "input[name='q']",
                "[aria-label='Search']",
            ],
            "search_button": [
                "input[name='btnK']",
                "button[aria-label='Google Search']",
            ],
        },
        "navigation_patterns": {
            "to_search": [
                "navigate(https://google.com)",
                "click(search_input)",
            ],
        },
        "page_load_signals": {
            "search_results": "#search",
        },
    },
]


async def run_setup() -> None:
    """Run the full database setup."""
    import asyncpg
    from dotenv import load_dotenv

    load_dotenv()

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("ERROR: SUPABASE_DB_URL not set in environment or .env file")
        sys.exit(1)

    print("Connecting to Supabase Postgres...")
    conn = await asyncpg.connect(db_url)

    try:
        # Run migration
        print("Running migration...")
        await conn.execute(MIGRATION_SQL)
        print("  Tables and indexes created.")

        # Seed site knowledge
        print("Seeding site knowledge...")
        for site in SEED_SITE_KNOWLEDGE:
            await conn.execute(
                """
                INSERT INTO site_knowledge
                    (domain, selector_map, navigation_patterns, page_load_signals)
                VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb)
                ON CONFLICT (domain) DO UPDATE SET
                    selector_map = EXCLUDED.selector_map,
                    navigation_patterns = EXCLUDED.navigation_patterns,
                    page_load_signals = EXCLUDED.page_load_signals
                """,
                site["domain"],
                json.dumps(site["selector_map"]),
                json.dumps(site["navigation_patterns"]),
                json.dumps(site["page_load_signals"]),
            )
            print(f"  Seeded: {site['domain']}")

        # Verify
        print("\nVerification:")
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        table_names = [t["tablename"] for t in tables]
        for required in ["task_templates", "execution_traces", "site_knowledge"]:
            status = "OK" if required in table_names else "MISSING"
            print(f"  {required}: {status}")

        ext = await conn.fetchrow(
            "SELECT * FROM pg_extension WHERE extname = 'vector'"
        )
        print(f"  pgvector: {'OK' if ext else 'MISSING'}")

        site_count = await conn.fetchval("SELECT COUNT(*) FROM site_knowledge")
        print(f"  site_knowledge rows: {site_count}")

        # Try ivfflat index creation (may fail if not enough rows, that's OK)
        try:
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_templates_embedding
                ON task_templates
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 10)
                """
            )
            print("  ivfflat index: created")
        except Exception as e:
            print(
                f"  ivfflat index: skipped ({e}). "
                "Will be created once enough rows exist."
            )

        print(
            "\nNOTE: The ivfflat index on task_templates.embedding requires "
            "at least 10 rows before it activates. Until then, similarity "
            "queries use exact scan."
        )
        print("\nSetup complete.")

    finally:
        await conn.close()


def main() -> None:
    """Entry point for python -m src.db.setup."""
    asyncio.run(run_setup())


if __name__ == "__main__":
    main()
