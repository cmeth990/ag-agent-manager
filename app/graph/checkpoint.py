"""Postgres checkpointer setup for LangGraph persistence."""
import os
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool


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
    
    # Convert postgresql:// to postgresql+psycopg:// to use psycopg3
    # This avoids needing psycopg2-binary
    if database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
        # Replace postgresql:// with postgresql+psycopg:// to use psycopg3
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    
    # Create engine with NullPool for serverless environments (Railway)
    engine = create_engine(
        database_url,
        poolclass=NullPool,
        connect_args={
            "options": "-c timezone=utc"
        }
    )
    
    # Create checkpointer - this will initialize tables
    checkpointer = PostgresSaver(engine)
    
    # Ensure tables are created
    checkpointer.setup()
    
    return checkpointer
