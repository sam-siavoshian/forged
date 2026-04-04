"""Database layer for the Rocket Booster system."""

from .client import get_supabase, get_pg_pool, close_pg_pool
from .embeddings import generate_embedding, generate_embeddings_batch
from .templates import (
    create_template,
    update_template_after_execution,
    update_baseline_duration,
    get_template_by_id,
    list_templates_by_domain,
)
from .traces import record_execution_trace
from .site_knowledge import update_selectors, get_selectors, get_site_knowledge

__all__ = [
    "get_supabase",
    "get_pg_pool",
    "close_pg_pool",
    "generate_embedding",
    "generate_embeddings_batch",
    "create_template",
    "update_template_after_execution",
    "update_baseline_duration",
    "get_template_by_id",
    "list_templates_by_domain",
    "record_execution_trace",
    "update_selectors",
    "get_selectors",
    "get_site_knowledge",
]
