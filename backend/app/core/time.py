"""UTC time helpers.

Database columns are intentionally stored as naive UTC timestamps for
compatibility with the existing schema. This helper avoids deprecated
``datetime.utcnow()`` while preserving that representation.
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
