"""
Model tiering: use smaller/cheaper models for simple tasks, bigger for complex.
Enables cost optimization through task-appropriate model selection.
"""
import logging
import os
from typing import Optional, Literal
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

# Model tiers
TIER_CHEAP = "cheap"  # gpt-4o-mini, claude-3-haiku
TIER_MID = "mid"      # gpt-4o, claude-3-sonnet
TIER_EXPENSIVE = "expensive"  # gpt-4-turbo, claude-3-opus

# Task complexity mapping
TASK_TIERS = {
    # Cheap tier: simple classification, filtering, triage
    "triage": TIER_CHEAP,
    "classification": TIER_CHEAP,
    "dedupe_suggestion": TIER_CHEAP,
    "extraction_draft": TIER_CHEAP,
    "source_filtering": TIER_CHEAP,
    "simple_extraction": TIER_CHEAP,
    "regex_validation": TIER_CHEAP,
    
    # Mid tier: standard extraction, entity linking
    "extraction": TIER_MID,
    "entity_linking": TIER_MID,
    "source_scoring": TIER_MID,
    "domain_scouting": TIER_MID,
    
    # Expensive tier: complex reasoning, synthesis
    "ontology_placement": TIER_EXPENSIVE,
    "contradiction_resolution": TIER_EXPENSIVE,
    "complex_disambiguation": TIER_EXPENSIVE,
    "multi_source_synthesis": TIER_EXPENSIVE,
    "evidence_synthesis": TIER_EXPENSIVE,
}


def get_model_for_tier(tier: str, provider: Optional[str] = None) -> str:
    """
    Get model name for a tier.
    
    Args:
        tier: TIER_CHEAP, TIER_MID, or TIER_EXPENSIVE
        provider: "openai" or "anthropic" (None = auto-detect)
    
    Returns:
        Model name
    """
    # Auto-detect provider from env
    if not provider:
        if os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        else:
            provider = "openai"  # Default
    
    if provider == "openai":
        if tier == TIER_CHEAP:
            return os.getenv("OPENAI_MODEL_CHEAP", "gpt-4o-mini")
        elif tier == TIER_MID:
            return os.getenv("OPENAI_MODEL_MID", "gpt-4o")
        else:  # TIER_EXPENSIVE
            return os.getenv("OPENAI_MODEL_EXPENSIVE", "gpt-4-turbo")
    else:  # anthropic
        if tier == TIER_CHEAP:
            return os.getenv("ANTHROPIC_MODEL_CHEAP", "claude-3-haiku-20240307")
        elif tier == TIER_MID:
            return os.getenv("ANTHROPIC_MODEL_MID", "claude-3-sonnet-20240229")
        else:  # TIER_EXPENSIVE
            return os.getenv("ANTHROPIC_MODEL_EXPENSIVE", "claude-3-opus-20240229")


def get_llm_for_task(
    task_type: str,
    domain: Optional[str] = None,
    queue: Optional[str] = None,
    agent: Optional[str] = None,
    force_tier: Optional[str] = None,
) -> Optional[BaseChatModel]:
    """
    Get LLM instance appropriate for task complexity.
    
    Args:
        task_type: Task type (e.g., "triage", "extraction", "ontology_placement")
        domain: Domain for cost tracking
        queue: Queue for cost tracking
        agent: Agent for cost tracking
        force_tier: Override tier selection (TIER_CHEAP, TIER_MID, TIER_EXPENSIVE)
    
    Returns:
        LLM instance or None
    """
    # Determine tier
    if force_tier:
        tier = force_tier
    else:
        tier = TASK_TIERS.get(task_type, TIER_MID)  # Default to mid
    
    # Get model name for tier
    model_name = get_model_for_tier(tier)
    
    # Create LLM instance
    try:
        if os.getenv("OPENAI_API_KEY"):
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=model_name,
                temperature=0.0,
                api_key=os.getenv("OPENAI_API_KEY")
            )
            logger.debug(f"Using {tier} tier model '{model_name}' for task '{task_type}'")
            return llm
        elif os.getenv("ANTHROPIC_API_KEY"):
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(
                model=model_name,
                temperature=0.0,
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
            logger.debug(f"Using {tier} tier model '{model_name}' for task '{task_type}'")
            return llm
    except Exception as e:
        logger.error(f"Failed to create LLM for tier {tier}: {e}")
    
    # Fallback to base LLM
    from app.llm.client import get_llm_base
    return get_llm_base()


def get_tier_for_task(task_type: str) -> str:
    """Get tier for a task type."""
    return TASK_TIERS.get(task_type, TIER_MID)
