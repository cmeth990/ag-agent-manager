"""LLM client factory for knowledge extraction."""
import os
import logging
from typing import Optional
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


# Moonshot/Kimi API is OpenAI-compatible; use global endpoint (not China) for privacy
MOONSHOT_BASE_URL = "https://api.moonshot.ai/v1"


def get_llm_manager() -> Optional[BaseChatModel]:
    """
    Get LLM for the manager (orchestration / improvement agent).
    Uses OpenAI or Anthropic only — never Moonshot.
    Priority: OPENAI_API_KEY, then ANTHROPIC_API_KEY.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            logger.info("Manager LLM: OpenAI")
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            return ChatOpenAI(
                model=model,
                temperature=0.0,
                api_key=openai_key
            )
        except ImportError:
            logger.warning("langchain-openai not installed, skipping OpenAI")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            from langchain_anthropic import ChatAnthropic
            logger.info("Manager LLM: Anthropic")
            return ChatAnthropic(
                model="claude-3-haiku-20240307",
                temperature=0.0,
                api_key=anthropic_key
            )
        except ImportError:
            logger.warning("langchain-anthropic not installed, skipping Anthropic")
    logger.warning("No manager LLM: set OPENAI_API_KEY or ANTHROPIC_API_KEY for improvement/orchestration")
    return None


def get_llm_base() -> Optional[BaseChatModel]:
    """
    Get configured LLM instance for agents (extractor, gatherer, scout, etc.).
    Prefers Moonshot when set; then OpenAI; then Anthropic.
    Order: MOONSHOT_API_KEY -> OPENAI_API_KEY -> ANTHROPIC_API_KEY.
    """
    # Agents: prefer Moonshot first
    moonshot_key = os.getenv("MOONSHOT_API_KEY") or os.getenv("KIMI_API_KEY")
    if moonshot_key:
        try:
            from langchain_openai import ChatOpenAI
            model = os.getenv("MOONSHOT_MODEL", "moonshot-v1-8k")
            logger.info("Agents LLM: Kimi/Moonshot (global endpoint)")
            return ChatOpenAI(
                model=model,
                temperature=0.0,
                api_key=moonshot_key,
                base_url=MOONSHOT_BASE_URL,
            )
        except ImportError:
            logger.warning("langchain-openai not installed, cannot use Moonshot")
        except Exception as e:
            logger.warning("Moonshot/Kimi init failed: %s", e)

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            logger.info("Agents LLM: OpenAI")
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            return ChatOpenAI(
                model=model,
                temperature=0.0,
                api_key=openai_key
            )
        except ImportError:
            logger.warning("langchain-openai not installed, skipping OpenAI")

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            from langchain_anthropic import ChatAnthropic
            logger.info("Agents LLM: Anthropic")
            return ChatAnthropic(
                model="claude-3-haiku-20240307",
                temperature=0.0,
                api_key=anthropic_key
            )
        except ImportError:
            logger.warning("langchain-anthropic not installed, skipping Anthropic")

    logger.warning(
        "No agents LLM: set MOONSHOT_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY"
    )
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
    Get cost-tracked LLM for an agent.
    Manager (improvement_agent) uses OpenAI/Anthropic only; other agents use Moonshot-first path.
    """
    domain = None
    if "user_input" in state:
        discovered = state.get("discovered_sources", {})
        if isinstance(discovered, dict):
            domains = discovered.get("domains", [])
            if domains:
                domain = domains[0]
    queue = state.get("queue", agent_name)

    # Manager: improvement agent uses OpenAI/Anthropic only
    if agent_name == "improvement_agent":
        base_llm = get_llm_manager()
    else:
        base_llm = get_llm_base()
    if not base_llm:
        return None
    try:
        from app.llm.tracked_client import get_tracked_llm
        return get_tracked_llm(
            llm=base_llm,
            domain=domain,
            queue=queue,
            agent=agent_name,
        )
    except Exception:
        return base_llm
