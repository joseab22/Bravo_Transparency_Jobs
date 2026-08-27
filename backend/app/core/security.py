from __future__ import annotations

import re
import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings

_DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def get_device_id(x_device_id: str | None = Header(default=None)) -> str:
    """Identify an anonymous browser for favorites/applications/notes.

    JobLens has no login system, so a client-generated device ID (sent as
    this header) is the only owner key available for per-user data.
    """
    if not x_device_id or not _DEVICE_ID_PATTERN.match(x_device_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid X-Device-Id header is required.",
        )
    return x_device_id


def get_optional_device_id(x_device_id: str | None = Header(default=None)) -> str | None:
    if x_device_id and _DEVICE_ID_PATTERN.match(x_device_id):
        return x_device_id
    return None


def require_admin_key(
    x_admin_key: str | None = Header(default=None),
) -> None:
    """Require a constant-time checked admin key for modifying operations."""
    expected = settings.admin_api_key

    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrative access is not configured",
        )

    if not x_admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrative authorization required",
        )

    if not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid administrative credentials",
        )
