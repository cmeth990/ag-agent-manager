"""LLM client factory for knowledge extraction."""
import os
import logging
from typing import Optional
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


def get_llm() -> Optional[BaseChatModel]:
    """
    Get configured LLM instance.
    
    Checks for API keys in order:
    1. OPENAI_API_KEY -> ChatOpenAI
    2. ANTHROPIC_API_KEY -> ChatAnthropic
    
    Returns:
        LLM instance or None if no API key found
    """
    # Try OpenAI first
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            logger.info("Using OpenAI ChatOpenAI")
            # Use cheapest model: gpt-4o-mini (cheaper than gpt-3.5-turbo!)
            # Can override with OPENAI_MODEL env var if needed
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            return ChatOpenAI(
                model=model,  # Default: gpt-4o-mini (most cost-effective)
                temperature=0.0,  # Deterministic extraction
                api_key=openai_key
            )
        except ImportError:
            logger.warning("langchain-openai not installed, skipping OpenAI")
    
    # Try Anthropic
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            from langchain_anthropic import ChatAnthropic
            logger.info("Using Anthropic ChatAnthropic")
            return ChatAnthropic(
                model="claude-3-haiku-20240307",  # Cost-effective model
                temperature=0.0,
                api_key=anthropic_key
            )
        except ImportError:
            logger.warning("langchain-anthropic not installed, skipping Anthropic")
    
    logger.warning("No LLM API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY")
    return None
