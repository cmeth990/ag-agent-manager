"""Postgres checkpointer setup for LangGraph persistence."""
import os
from langgraph.checkpoint.postgres import PostgresSaver


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
    
    # PostgresSaver accepts a connection string directly via from_conn_string
    # This method handles connection management internally
    checkpointer = PostgresSaver.from_conn_string(database_url)
    
    # Ensure tables are created
    checkpointer.setup()
    
    return checkpointer
