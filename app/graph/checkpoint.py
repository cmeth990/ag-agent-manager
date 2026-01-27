"""Postgres checkpointer setup for LangGraph persistence."""
import os
import logging
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Get database URL from environment variable."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL environment variable not set")
    return url


def create_checkpointer():
    """
    Create and initialize checkpointer for LangGraph.
    
    Uses MemorySaver for now due to PostgresSaver NotImplementedError bug.
    TODO: Fix PostgresSaver once langgraph-checkpoint-postgres is updated.
    
    Returns:
        MemorySaver instance (in-memory persistence)
    """
    # Temporarily use MemorySaver due to PostgresSaver NotImplementedError bug
    # PostgresSaver has a bug where aget_tuple raises NotImplementedError
    # Once langgraph-checkpoint-postgres is fixed, we can switch back to PostgresSaver
    logger.info("Using MemorySaver checkpointer (in-memory persistence)")
    logger.info("Note: PostgresSaver has NotImplementedError bug, using MemorySaver as workaround")
    
    checkpointer = MemorySaver()
    logger.info("MemorySaver checkpointer created")
    
    return checkpointer
