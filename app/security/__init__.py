"""
Security mitigations for ingestion agents.
"""
from app.security.tools import ApprovedToolsRegistry, is_tool_allowed, require_tool, SecurityError
from app.security.network import is_url_allowed, get_allowed_domains
from app.security.sanitize import sanitize_content, sanitize_for_llm
from app.security.prompt_injection import wrap_untrusted_content, PROMPT_INJECTION_PREFIX
from app.security.corroboration import require_corroboration, CorroborationError
from app.security.anomaly import check_ingestion_anomaly, record_ingestion

__all__ = [
    "ApprovedToolsRegistry",
    "is_tool_allowed",
    "require_tool",
    "SecurityError",
    "is_url_allowed",
    "get_allowed_domains",
    "sanitize_content",
    "sanitize_for_llm",
    "wrap_untrusted_content",
    "PROMPT_INJECTION_PREFIX",
    "require_corroboration",
    "CorroborationError",
    "check_ingestion_anomaly",
    "record_ingestion",
]
