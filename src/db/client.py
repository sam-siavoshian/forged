"""Supabase + asyncpg connection management.

Dual connection strategy:
- supabase-py for CRUD operations and simple queries
- asyncpg pool for pgvector similarity searches and raw SQL
"""

import os

import asyncpg
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

# --- Supabase client (CRUD, simple queries) ---
_supabase_client: Client | None = None


def get_supabase() -> Client:
    """Get or create the singleton Supabase client."""
    global _supabase_client
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
            )
        _supabase_client = create_client(url, key)
    return _supabase_client


# --- Direct Postgres pool (pgvector queries) ---
_pg_pool: asyncpg.Pool | None = None


async def get_pg_pool() -> asyncpg.Pool:
    """Get or create the singleton asyncpg connection pool."""
    global _pg_pool
    if _pg_pool is None:
        db_url = os.environ.get("SUPABASE_DB_URL", "")
        if not db_url:
            raise RuntimeError("SUPABASE_DB_URL must be set")
        _pg_pool = await asyncpg.create_pool(
            db_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
    return _pg_pool


async def close_pg_pool() -> None:
    """Close the asyncpg connection pool. Call on shutdown."""
    global _pg_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
