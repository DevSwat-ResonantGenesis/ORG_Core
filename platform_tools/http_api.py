"""Internal HTTP API tool for agent execution."""

import os
from typing import Any, Dict, Optional

import httpx

from .auth import AuthContext

# Known internal service base URLs
INTERNAL_SERVICES = {
    "rabbit_api_service": os.getenv("RABBIT_API_SERVICE_URL", "http://rabbit_api_service:8000"),
    "auth_service": os.getenv("AUTH_SERVICE_URL", "http://auth_service:8000"),
    "memory_service": os.getenv("MEMORY_SERVICE_URL", "http://memory_service:8000"),
    "chat_service": os.getenv("CHAT_SERVICE_URL", "http://chat_service:8000"),
    "billing_service": os.getenv("BILLING_SERVICE_URL", "http://billing_service:8000"),
    "ed_service": os.getenv("ED_SERVICE_URL", "http://ed_service:8000"),
}


async def tool_http_request(
    url: str,
    method: str = "GET",
    body: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Make an authenticated HTTP request to an internal platform API."""
    if not url:
        return {"error": "url is required"}

    req_headers = auth.headers() if auth else {}
    if headers:
        req_headers.update(headers)
    req_headers.setdefault("Content-Type", "application/json")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method=method.upper(),
                url=url,
                json=body if method.upper() in ("POST", "PUT", "PATCH") else None,
                headers=req_headers,
            )
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text[:2000]}
            return {
                "success": resp.status_code < 400,
                "status_code": resp.status_code,
                "data": data,
            }
    except Exception as e:
        return {"error": f"HTTP request failed: {str(e)[:300]}"}
