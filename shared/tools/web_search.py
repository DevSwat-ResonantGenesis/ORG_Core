"""
Shared web search tool — used by both chat skills and agent tools.
"""

from __future__ import annotations

import logging
import re
from html import unescape
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, parse_qs, unquote, urlparse

import httpx

from .auth import AuthContext

logger = logging.getLogger(__name__)

USER_AGENT = "Genesis2026-Platform/1.0 (+https://dev-swat.com)"


def _parse_ddg_redirect_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        uddg = qs.get("uddg", [None])[0]
        if uddg:
            return unquote(uddg)
    except Exception:
        pass
    return url


def _strip_html(html: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", html)
    cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_results_from_ddg_html(html: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    try:
        patterns = [
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            r'<a[^>]+class="result-link"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            r'<a[^>]+rel="nofollow"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        ]
        for pattern in patterns:
            for m in re.finditer(pattern, html, flags=re.IGNORECASE | re.DOTALL):
                url = m.group(1)
                title_html = m.group(2)
                title = _strip_html(unescape(title_html or ""))
                if not title:
                    continue
                url = unescape(url)
                if url.startswith("/l/") or "duckduckgo.com/l/" in url:
                    url = _parse_ddg_redirect_url(url)
                if url.startswith("//"):
                    url = "https:" + url
                if not url.startswith("http"):
                    continue
                results.append({"title": title[:200], "url": url})
                if len(results) >= 10:
                    return results
    except Exception:
        return results
    return results


async def tool_web_search(
    query: str,
    *,
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Search the web using DuckDuckGo.

    Returns a list of {title, url} results.
    Used by both chat_service web_search skill and agent_engine web_search tool.
    """
    if not query or not isinstance(query, str):
        return {"error": "Missing or invalid 'query'"}

    url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_redirect=1&no_html=1"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}

            try:
                data = resp.json() if resp.content else {}
            except Exception:
                return {"error": "DuckDuckGo returned invalid JSON"}

        results: List[Dict[str, Any]] = []

        def _collect(topic: Any) -> None:
            if isinstance(topic, dict) and topic.get("Text") and topic.get("FirstURL"):
                results.append({"title": topic.get("Text"), "url": topic.get("FirstURL")})
            if isinstance(topic, dict) and isinstance(topic.get("Topics"), list):
                for t in topic.get("Topics"):
                    _collect(t)

        for t in data.get("RelatedTopics") or []:
            _collect(t)

        # Fallback: scrape lite.duckduckgo.com HTML if instant answer API returned nothing
        if not results:
            try:
                lite_url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
                html_headers = {
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                }
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=html_headers) as client:
                    resp = await client.get(lite_url)
                    if resp.status_code == 200:
                        results = _extract_results_from_ddg_html(resp.text or "")
            except Exception:
                pass

        if not results:
            return {
                "query": query,
                "results": [],
                "message": "No results found. Try a different search query.",
            }

        return {
            "query": query,
            "results": results[:10],
            "count": len(results[:10]),
        }
    except Exception as e:
        return {"error": f"Web search failed: {e}"}
