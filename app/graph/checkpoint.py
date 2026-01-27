"""Postgres checkpointer setup for LangGraph persistence."""
import os
import logging
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Get database URL from environment variable."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL environment variable not set")
    return url


def create_checkpointer() -> PostgresSaver:
    """
    Create and initialize Postgres checkpointer for LangGraph.
    
    This will create necessary tables if they don't exist.
    
    Returns:
        PostgresSaver instance configured for persistence
    """
    database_url = get_database_url()
    logger.info("Creating checkpointer with ConnectionPool...")
    logger.info(f"Checkpoint module file: {__file__}")
    logger.info(f"PostgresSaver class: {PostgresSaver}")
    logger.info(f"ConnectionPool class: {ConnectionPool}")
    # Log first 50 chars of URL (hide password)
    url_preview = database_url[:50] + "..." if len(database_url) > 50 else database_url
    logger.info(f"Database URL preview: {url_preview}")
    
    # Use ConnectionPool for better connection management
    # This prevents connection timeouts and allows reuse
    pool = ConnectionPool(
        database_url,
        min_size=1,
        max_size=10,
        kwargs={"autocommit": True, "row_factory": dict_row}
    )
    logger.info(f"ConnectionPool created: {type(pool)}")
    
    # Create checkpointer with the connection pool directly
    # PostgresSaver accepts ConnectionPool as the conn parameter
    checkpointer = PostgresSaver(pool)
    logger.info(f"PostgresSaver created: {type(checkpointer)}, has setup: {hasattr(checkpointer, 'setup')}")
    
    # Ensure tables are created
    checkpointer.setup()
    logger.info("Checkpointer setup complete")
    
    return checkpointer
