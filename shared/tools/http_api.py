"""
Shared HTTP API tool — for making authenticated requests to internal platform services.

Only allows calls to internal Docker network services for safety.
Forwards JWT and identity headers for proper authentication.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from .auth import AuthContext, build_service_headers

logger = logging.getLogger(__name__)

# Allowed internal hostnames (Docker service names)
ALLOWED_SUFFIXES = ("_service",)
ALLOWED_EXACT = ("gateway", "localhost", "127.0.0.1")
ALLOWED_DOMAIN_SUFFIXES = (".internal",)


def _is_internal_host(hostname: str) -> bool:
    """Check if a hostname is an allowed internal service."""
    if not hostname:
        return False
    if hostname in ALLOWED_EXACT:
        return True
    for suffix in ALLOWED_SUFFIXES:
        if hostname.endswith(suffix):
            return True
    for suffix in ALLOWED_DOMAIN_SUFFIXES:
        if hostname.endswith(suffix):
            return True
    return False


async def tool_http_request(
    url: str,
    *,
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Make an authenticated HTTP request to an internal platform API.

    Security:
    - Only allows calls to internal Docker network services
    - Forwards JWT token and user identity headers
    - Includes internal service secret when configured

    Used by agent_engine http_request tool. Can also be used by chat skills
    that need to call arbitrary internal APIs.
    """
    if not url or not isinstance(url, str):
        return {"error": "Missing or invalid 'url'"}

    method = (method or "GET").upper()
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        return {"error": f"Unsupported method: {method}. Use GET, POST, PUT, PATCH, or DELETE."}

    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if not _is_internal_host(hostname):
        return {"error": f"Only internal platform URLs allowed. Got: {hostname}. Use the gateway or service names (e.g., http://gateway:8000/...)."}

    headers = build_service_headers(auth) if auth else {"x-user-id": "agent-system"}
    if isinstance(extra_headers, dict):
        headers.update(extra_headers)

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.request(
                method=method,
                url=url,
                json=body if body and method in ("POST", "PUT", "PATCH") else None,
                headers=headers,
            )
            try:
                data = resp.json()
            except Exception:
                data = resp.text[:2000]
            return {"status": resp.status_code, "data": data}
    except Exception as e:
        return {"error": f"HTTP request failed: {e}"}
