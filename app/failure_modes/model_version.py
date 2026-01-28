"""
Model version tracking: detect model behavior shifts after upgrades.
"""
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def track_model_version(
    model_name: str,
    provider: str,
    version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Track model version for behavior shift detection.
    
    Args:
        model_name: Model name (e.g., "gpt-4o-mini")
        provider: Provider (e.g., "openai")
        version: Optional explicit version string
    
    Returns:
        Version record
    """
    # Extract version from model name or env
    if not version:
        # Try to get from env or model name
        if provider == "openai":
            version = os.getenv("OPENAI_MODEL_VERSION") or model_name
        elif provider == "anthropic":
            version = os.getenv("ANTHROPIC_MODEL_VERSION") or model_name
        else:
            version = model_name
    
    record = {
        "model_name": model_name,
        "provider": provider,
        "version": version,
        "tracked_at": datetime.utcnow().isoformat() + "Z",
    }
    
    logger.debug(f"Tracked model version: {model_name} ({provider}) = {version}")
    return record


def get_model_version(model_name: str, provider: str) -> Optional[str]:
    """Get current tracked version for a model."""
    # For now, return model name (could track in DB)
    return model_name
