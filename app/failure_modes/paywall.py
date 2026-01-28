"""
Paywall detection: detect when paywalls appear.
"""
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PaywallDetected(Exception):
    """Raised when a paywall is detected."""
    pass


PAYWALL_INDICATORS = [
    # Keywords
    r"subscribe",
    r"subscription",
    r"paywall",
    r"premium",
    r"unlock",
    r"purchase",
    r"buy now",
    r"members only",
    r"sign up",
    # Common paywall services
    r"piano\.io",
    r"metered",
    r"freemium",
    # HTML patterns
    r"class.*paywall",
    r"id.*paywall",
    r"data-paywall",
]


def detect_paywall(
    html: str,
    url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Detect if content is behind a paywall.
    
    Returns:
        Dict with:
        - is_paywall: bool
        - confidence: float (0.0-1.0)
        - indicators: list of matched indicators
        - message: optional message
    """
    if not html:
        return {"is_paywall": False, "confidence": 0.0, "indicators": []}
    
    html_lower = html.lower()
    url_lower = (url or "").lower()
    
    matched_indicators = []
    
    for pattern in PAYWALL_INDICATORS:
        if re.search(pattern, html_lower, re.IGNORECASE) or \
           (url_lower and re.search(pattern, url_lower, re.IGNORECASE)):
            matched_indicators.append(pattern)
    
    confidence = min(1.0, len(matched_indicators) * 0.3)  # Each indicator adds 0.3
    is_paywall = len(matched_indicators) >= 2 or confidence >= 0.6
    
    if is_paywall:
        logger.warning(f"Paywall detected: {len(matched_indicators)} indicators matched")
        return {
            "is_paywall": True,
            "confidence": confidence,
            "indicators": matched_indicators,
            "message": f"Paywall detected ({len(matched_indicators)} indicators)",
        }
    
    return {
        "is_paywall": False,
        "confidence": confidence,
        "indicators": matched_indicators,
    }
