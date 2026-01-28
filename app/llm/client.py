"""LLM client factory for knowledge extraction."""
import os
import logging
from typing import Optional
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


def get_llm_base() -> Optional[BaseChatModel]:
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


def get_llm(
    domain: Optional[str] = None,
    queue: Optional[str] = None,
    agent: Optional[str] = None,
) -> Optional[BaseChatModel]:
    """
    Get LLM instance with optional cost tracking.
    
    If domain/queue/agent are provided, returns a cost-tracked wrapper.
    Otherwise returns the base LLM (for backward compatibility).
    
    Args:
        domain: Domain name for cost tracking
        queue: Queue name for cost tracking
        agent: Agent name for cost tracking
    
    Returns:
        LLM instance (tracked if context provided, otherwise base)
    """
    base_llm = get_llm_base()
    if not base_llm:
        return None
    
    # If no context provided, return base LLM (backward compatible)
    if not domain and not queue and not agent:
        return base_llm
    
    # Return tracked LLM wrapper
    try:
        from app.llm.tracked_client import get_tracked_llm
        return get_tracked_llm(domain=domain, queue=queue, agent=agent)
    except ImportError:
        logger.warning("Cost tracking not available, returning base LLM")
        return base_llm


def get_llm_for_agent(state: dict, agent_name: str) -> Optional[BaseChatModel]:
    """
    Get cost-tracked LLM for an agent, extracting context from state.
    
    Args:
        state: AgentState dict
        agent_name: Name of the agent (e.g., "source_gatherer")
    
    Returns:
        Tracked LLM instance or None
    """
    # Extract domain from state (common patterns)
    domain = None
    if "user_input" in state:
        # Try to extract domain from user input or discovered_sources
        discovered = state.get("discovered_sources", {})
        if isinstance(discovered, dict):
            domains = discovered.get("domains", [])
            if domains:
                domain = domains[0]  # Use first domain
    
    # Extract queue from state or use agent name
    queue = state.get("queue", agent_name)
    
    return get_llm(domain=domain, queue=queue, agent=agent_name)
