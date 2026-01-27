"""Postgres checkpointer setup for LangGraph persistence."""
import os
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row


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
    
    # Use ConnectionPool for better connection management
    # This prevents connection timeouts and allows reuse
    pool = ConnectionPool(
        database_url,
        min_size=1,
        max_size=10,
        kwargs={"autocommit": True, "row_factory": dict_row}
    )
    
    # Create checkpointer with the connection pool directly
    # PostgresSaver accepts ConnectionPool as the conn parameter
    checkpointer = PostgresSaver(pool)
    
    # Ensure tables are created
    checkpointer.setup()
    
    return checkpointer
