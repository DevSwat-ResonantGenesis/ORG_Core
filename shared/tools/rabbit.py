"""
Shared Rabbit (Reddit-like) tools — used by both chat skills and agent tools.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

from .auth import AuthContext, build_service_headers

logger = logging.getLogger(__name__)

RABBIT_API_URL = os.getenv("RABBIT_API_URL", "http://rabbit_api_service:8000")


async def tool_create_rabbit_post(
    title: str,
    body: str,
    community_slug: Optional[str] = None,
    *,
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Create a post on a Rabbit community.

    If community_slug is not provided, posts to the first available community.
    """
    if not title or not isinstance(title, str):
        return {"error": "Missing or invalid 'title'"}
    if not body or not isinstance(body, str):
        return {"error": "Missing or invalid 'body'"}

    headers = build_service_headers(auth) if auth else {"x-user-id": "agent-system"}

    if not community_slug or not isinstance(community_slug, str):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{RABBIT_API_URL}/rabbit/communities")
                if resp.status_code == 200:
                    communities = resp.json()
                    if communities:
                        community_slug = communities[0].get("slug", "r/general")
                    else:
                        return {"error": "No communities exist. Create one first with create_rabbit_community."}
                else:
                    return {"error": f"Failed to list communities: HTTP {resp.status_code}"}
        except Exception as e:
            return {"error": f"Failed to list communities: {e}"}

    payload = {
        "title": title.strip(),
        "body": body.strip(),
        "community_slug": community_slug.strip(),
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{RABBIT_API_URL}/rabbit/posts",
                json=payload,
                headers=headers,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                return {
                    "success": True,
                    "post_id": data.get("id"),
                    "title": data.get("title"),
                    "community_id": data.get("community_id"),
                    "message": f"Post '{title}' created successfully in {community_slug}",
                }
            else:
                detail = ""
                try:
                    detail = resp.json().get("detail", "")
                except Exception:
                    detail = resp.text[:200]
                return {"error": f"Failed to create post: HTTP {resp.status_code} - {detail}"}
    except Exception as e:
        return {"error": f"Failed to create post: {e}"}


async def tool_list_rabbit_communities(
    *,
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """List available Rabbit communities."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{RABBIT_API_URL}/rabbit/communities")
            if resp.status_code == 200:
                communities = resp.json()
                return {
                    "communities": [
                        {"slug": c.get("slug"), "name": c.get("name"), "description": c.get("description")}
                        for c in communities
                    ],
                    "count": len(communities),
                }
            return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": f"Failed to list communities: {e}"}


async def tool_create_rabbit_community(
    slug: str,
    name: str,
    description: str = "",
    *,
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Create a new Rabbit community."""
    if not slug or not isinstance(slug, str):
        return {"error": "Missing or invalid 'slug' (e.g., 'r/technology')"}
    if not name or not isinstance(name, str):
        return {"error": "Missing or invalid 'name'"}

    headers = build_service_headers(auth) if auth else {"x-user-id": "agent-system"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{RABBIT_API_URL}/rabbit/communities",
                json={"slug": slug.strip(), "name": name.strip(), "description": (description or "").strip()},
                headers=headers,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                return {"success": True, "community": data, "message": f"Community '{name}' ({slug}) created."}
            else:
                detail = ""
                try:
                    detail = resp.json().get("detail", "")
                except Exception:
                    detail = resp.text[:200]
                return {"error": f"Failed to create community: HTTP {resp.status_code} - {detail}"}
    except Exception as e:
        return {"error": f"Failed to create community: {e}"}
