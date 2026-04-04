"""Tests for the setup script.

Verifies the setup is idempotent (can be run twice without errors).
Requires a real Supabase instance.
"""

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("SUPABASE_DB_URL"),
        reason="SUPABASE_DB_URL not set — skipping integration tests",
    ),
]


@pytest.mark.asyncio
async def test_setup_is_idempotent():
    """Running setup twice should not raise errors."""
    from src.db.setup import run_setup

    # Run once
    await run_setup()
    # Run again — should not fail
    await run_setup()


@pytest.mark.asyncio
async def test_setup_creates_tables():
    """Verify all required tables exist after setup."""
    import asyncpg
    from dotenv import load_dotenv

    load_dotenv()
    conn = await asyncpg.connect(os.environ["SUPABASE_DB_URL"])

    try:
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        table_names = [t["tablename"] for t in tables]

        assert "task_templates" in table_names
        assert "execution_traces" in table_names
        assert "site_knowledge" in table_names
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_setup_seeds_site_knowledge():
    """Verify site knowledge is seeded for amazon.com and google.com."""
    import asyncpg
    from dotenv import load_dotenv

    load_dotenv()
    conn = await asyncpg.connect(os.environ["SUPABASE_DB_URL"])

    try:
        rows = await conn.fetch("SELECT domain FROM site_knowledge")
        domains = [r["domain"] for r in rows]

        assert "amazon.com" in domains
        assert "google.com" in domains
    finally:
        await conn.close()
