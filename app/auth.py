"""Admin/telemetry API key auth for protected endpoints."""
import os
from typing import Optional

from fastapi import Header, HTTPException, status


def _get_expected_key() -> Optional[str]:
    """Expected admin API key from env. Empty string is treated as unset."""
    v = os.getenv("ADMIN_API_KEY", "").strip()
    return v or None


def require_admin_key(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    authorization: Optional[str] = Header(None),
) -> None:
    """
    Dependency that requires a valid admin API key for protected routes.

    - If ADMIN_API_KEY is not set: no check (allow all, for local dev).
    - If set: client must send the key via header:
      - X-Admin-Key: <key>
      - or Authorization: Bearer <key>

    Use on telemetry, queue (DLQ/triage/stuck), and kg rollback endpoints.
    """
    expected = _get_expected_key()
    if not expected:
        return

    provided: Optional[str] = None
    if x_admin_key:
        provided = x_admin_key.strip()
    elif authorization and authorization.startswith("Bearer "):
        provided = authorization[7:].strip()

    if not provided or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid admin API key. Set X-Admin-Key or Authorization: Bearer <key>.",
        )
