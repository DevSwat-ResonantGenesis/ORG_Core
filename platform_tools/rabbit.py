"""Rabbit community platform tools for agent execution."""

import os
from typing import Any, Dict, Optional

import httpx

from .auth import AuthContext

RABBIT_API_URL = os.getenv("RABBIT_API_SERVICE_URL", "http://rabbit_api_service:8000")


async def tool_create_rabbit_post(
    title: str,
    body: str,
    community_slug: str = "",
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Create a post on a Rabbit community."""
    if not title or not body:
        return {"error": "title and body are required"}
    headers = auth.headers() if auth else {}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{RABBIT_API_URL}/api/communities/{community_slug}/posts",
                json={"title": title, "body": body},
                headers=headers,
            )
            if resp.status_code < 400:
                return {"success": True, "post": resp.json()}
            return {"error": f"Rabbit API returned {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"error": f"Rabbit post failed: {str(e)[:200]}"}


async def tool_list_rabbit_communities(
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """List available Rabbit communities."""
    headers = auth.headers() if auth else {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{RABBIT_API_URL}/api/communities",
                headers=headers,
            )
            if resp.status_code < 400:
                return {"success": True, "communities": resp.json()}
            return {"error": f"Rabbit API returned {resp.status_code}"}
    except Exception as e:
        return {"error": f"Rabbit list failed: {str(e)[:200]}"}


async def tool_create_rabbit_community(
    slug: str,
    name: str,
    description: str = "",
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Create a new Rabbit community."""
    if not slug or not name:
        return {"error": "slug and name are required"}
    headers = auth.headers() if auth else {}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{RABBIT_API_URL}/api/communities",
                json={"slug": slug, "name": name, "description": description},
                headers=headers,
            )
            if resp.status_code < 400:
                return {"success": True, "community": resp.json()}
            return {"error": f"Rabbit API returned {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"error": f"Rabbit create failed: {str(e)[:200]}"}
