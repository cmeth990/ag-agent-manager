"""
Failure mode handlers for ingestion agents.
"""
from app.failure_modes.html_parser import parse_html_with_fallback, HTMLParserError
from app.failure_modes.paywall import detect_paywall, PaywallDetected
from app.failure_modes.circular_citation import detect_circular_citations, CircularCitationError
from app.failure_modes.model_version import track_model_version, get_model_version

__all__ = [
    "parse_html_with_fallback",
    "HTMLParserError",
    "detect_paywall",
    "PaywallDetected",
    "detect_circular_citations",
    "CircularCitationError",
    "track_model_version",
    "get_model_version",
]
