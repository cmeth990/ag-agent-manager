"""
Tool sandboxing: agents can only use approved tools.
Prevents arbitrary code execution; only approved tools are allowed.
"""
import logging
import os
from typing import Set, Optional

logger = logging.getLogger(__name__)

# Approved tools for ingestion pipeline (no arbitrary code execution)
DEFAULT_APPROVED_TOOLS: Set[str] = {
    "llm_invoke",       # LLM API calls
    "http_get",         # HTTP GET (subject to network allowlist)
    "kg_query",         # KG read queries
    "kg_apply_diff",    # KG write (with approval flow)
    "file_read",        # Read file (for improvement agent context only)
    "file_write",       # Write file (improvement agent, with approval)
    "git_add_commit",   # Git add/commit (improvement agent, with approval)
}

# Tools that are NEVER allowed (high risk)
BLOCKED_TOOLS: Set[str] = {
    "eval",
    "exec",
    "subprocess",
    "os.system",
    "shell",
    "run_command",
    "execute_code",
    "__import__",
}


class ApprovedToolsRegistry:
    """Registry of approved tools. Only these can be invoked by agents."""
    _approved: Set[str] = set(DEFAULT_APPROVED_TOOLS)
    _blocked: Set[str] = set(BLOCKED_TOOLS)

    @classmethod
    def approve(cls, tool_name: str) -> None:
        cls._approved.add(tool_name)
        logger.info(f"Tool approved: {tool_name}")

    @classmethod
    def revoke(cls, tool_name: str) -> None:
        cls._approved.discard(tool_name)
        logger.info(f"Tool revoked: {tool_name}")

    @classmethod
    def block(cls, tool_name: str) -> None:
        cls._blocked.add(tool_name)
        cls._approved.discard(tool_name)

    @classmethod
    def is_approved(cls, tool_name: str) -> bool:
        if tool_name in cls._blocked:
            return False
        return tool_name in cls._approved

    @classmethod
    def list_approved(cls) -> Set[str]:
        return set(cls._approved)

    @classmethod
    def list_blocked(cls) -> Set[str]:
        return set(cls._blocked)


def is_tool_allowed(tool_name: str) -> bool:
    """Check if a tool is allowed for use by agents."""
    return ApprovedToolsRegistry.is_approved(tool_name)


def require_tool(tool_name: str) -> None:
    """
    Require that the current operation uses an approved tool.
    Raises SecurityError if tool is not approved.
    """
    if not ApprovedToolsRegistry.is_approved(tool_name):
        raise SecurityError(
            f"Tool '{tool_name}' is not approved. "
            f"Approved tools: {sorted(ApprovedToolsRegistry.list_approved())}"
        )


class SecurityError(Exception):
    """Raised when a security policy is violated."""
    pass


# Load additional approved tools from env (comma-separated)
_env_approved = os.getenv("SECURITY_APPROVED_TOOLS", "")
if _env_approved:
    for t in _env_approved.split(","):
        t = t.strip()
        if t:
            ApprovedToolsRegistry.approve(t)

_env_blocked = os.getenv("SECURITY_BLOCKED_TOOLS", "")
if _env_blocked:
    for t in _env_blocked.split(","):
        t = t.strip()
        if t:
            ApprovedToolsRegistry.block(t)
