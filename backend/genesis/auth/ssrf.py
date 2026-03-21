"""SSRF protection — validate URLs before server-side fetching."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from fastapi import HTTPException

# Private/reserved IP ranges that should never be fetched
BLOCKED_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 private
]

BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal", "169.254.169.254"}


def validate_url(url: str) -> str:
    """Validate a URL is safe for server-side fetching.

    Blocks:
    - Private/internal IP ranges (10.x, 172.16.x, 192.168.x, 127.x)
    - Metadata endpoints (169.254.169.254)
    - localhost and internal hostnames
    - Non-HTTP(S) schemes

    Returns the validated URL or raises HTTPException.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(400, "Invalid URL format")

    # Scheme check
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "Only HTTP/HTTPS URLs are allowed")

    # Hostname check
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(400, "URL must have a hostname")

    if hostname.lower() in BLOCKED_HOSTNAMES:
        raise HTTPException(400, "Cannot scan internal/private URLs")

    # IP check
    try:
        ip = ipaddress.ip_address(hostname)
        for network in BLOCKED_RANGES:
            if ip in network:
                raise HTTPException(400, "Cannot scan private/internal IP addresses")
    except ValueError:
        # Not an IP — it's a hostname, which is fine
        # But check for suspicious patterns
        if re.match(r"^(10|172\.(1[6-9]|2\d|3[01])|192\.168)\.", hostname):
            raise HTTPException(400, "Cannot scan private IP addresses")

    return url
