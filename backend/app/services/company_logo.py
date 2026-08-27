from __future__ import annotations

import re

_PROTOCOL_RE = re.compile(r"^https?://", re.IGNORECASE)
_LOGO_BASE_URL = "https://logos-api.apistemic.com/domain:"


def resolve_logo_url(website: str | None) -> str | None:
    """Build a logo URL for a company's website domain via apistemic logos.

    Client browsers fetch directly from apistemic's CDN (no server-side
    proxying or storage): the CDN already caches per domain, and their
    per-request rate limit only applies to server-side callers, not to a
    browser loading an <img> tag.
    """
    if not website:
        return None

    domain = _PROTOCOL_RE.sub("", website.strip()).split("/")[0].split("?")[0].lower()
    if domain.startswith("www."):
        domain = domain[4:]

    if not domain or "." not in domain:
        return None

    return f"{_LOGO_BASE_URL}{domain}"
