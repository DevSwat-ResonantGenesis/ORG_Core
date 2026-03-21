"""
Shared memory tools — used by both chat skills and agent tools.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

from .auth import AuthContext, build_service_headers

logger = logging.getLogger(__name__)

MEMORY_SERVICE_URL = os.getenv("MEMORY_SERVICE_URL", "http://memory_service:8000")


async def tool_memory_read(
    query: str,
    *,
    limit: int = 5,
    retrieval_mode: str = "hybrid",
    auth: Optional[AuthContext] = None,
    chat_id: Optional[str] = None,
    agent_hash: Optional[str] = None,
    team_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve relevant memories for a query.

    Used by both chat_service memory_search skill and agent_engine memory.read tool.
    """
    if not query or not isinstance(query, str) or not query.strip():
        return {"error": "Missing or invalid 'query'"}

    limit = max(1, min(int(limit), 25))
    if retrieval_mode not in ("embedding", "hash_sphere", "hybrid"):
        retrieval_mode = "hybrid"

    headers = build_service_headers(auth) if auth else {}

    payload: Dict[str, Any] = {
        "query": query.strip(),
        "limit": limit,
        "use_vector_search": True,
        "retrieval_mode": retrieval_mode,
        "user_id": auth.user_id if auth else None,
        "org_id": auth.org_id if auth else None,
        "agent_hash": agent_hash,
        "team_id": team_id,
        "chat_id": chat_id,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    url = f"{MEMORY_SERVICE_URL.rstrip('/')}/memory/retrieve"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code != 200:
            return {"error": f"memory.read failed: HTTP {resp.status_code}", "detail": (resp.text or "")[:500]}

        try:
            data = resp.json()
        except Exception:
            data = []
        return {"memories": data}
    except Exception as e:
        return {"error": f"memory.read failed: {e}"}


async def tool_memory_write(
    content: str,
    *,
    source: str = "platform",
    metadata: Optional[Dict[str, Any]] = None,
    generate_embedding: bool = True,
    auth: Optional[AuthContext] = None,
    chat_id: Optional[str] = None,
    agent_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """Store a memory entry.

    Used by both chat_service and agent_engine memory.write tool.
    """
    if not content or not isinstance(content, str) or not content.strip():
        return {"error": "Missing or invalid 'content'"}

    if metadata is not None and not isinstance(metadata, dict):
        metadata = {"raw": str(metadata)}

    headers = build_service_headers(auth) if auth else {}

    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "user_id": auth.user_id if auth else None,
        "org_id": auth.org_id if auth else None,
        "agent_hash": agent_hash,
        "source": source,
        "content": content.strip(),
        "metadata": metadata,
        "generate_embedding": bool(generate_embedding),
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    url = f"{MEMORY_SERVICE_URL.rstrip('/')}/memory/ingest"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code != 200:
            return {"error": f"memory.write failed: HTTP {resp.status_code}", "detail": (resp.text or "")[:500]}

        try:
            return resp.json()
        except Exception:
            return {"ok": True}
    except Exception as e:
        return {"error": f"memory.write failed: {e}"}
