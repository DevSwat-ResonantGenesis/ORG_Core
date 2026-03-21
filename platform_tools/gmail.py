"""Gmail tools for agent execution.

Uses Google OAuth tokens stored in UserApiKey (provider='google-gmail')
via auth_service to send/read emails through the Gmail API.
"""

import os
import logging
from typing import Any, Dict, Optional

import httpx

from .auth import AuthContext

logger = logging.getLogger(__name__)

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8000")
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


async def _get_gmail_token(auth: AuthContext) -> Optional[str]:
    """Fetch the user's Gmail OAuth token from auth_service."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{AUTH_SERVICE_URL}/auth/api-keys",
                headers=auth.headers(),
                params={"provider": "google-gmail"},
            )
            if resp.status_code == 200:
                keys = resp.json()
                if isinstance(keys, list) and keys:
                    return keys[0].get("decrypted_key") or keys[0].get("key")
                if isinstance(keys, dict):
                    items = keys.get("keys", [])
                    if items:
                        return items[0].get("decrypted_key") or items[0].get("key")
    except Exception as e:
        logger.warning(f"Failed to fetch Gmail token: {e}")
    return None


async def _refresh_token_if_needed(token: str, auth: AuthContext) -> str:
    """Attempt to refresh the Google OAuth token via auth_service."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{AUTH_SERVICE_URL}/auth/services/google/refresh",
                json={"service": "google-gmail"},
                headers=auth.headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("access_token", token)
    except Exception:
        pass
    return token


async def tool_gmail_send(
    tool_input: Dict[str, Any],
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Send an email via Gmail API.

    tool_input keys:
      - to: recipient email (required)
      - subject: email subject (required)
      - body: plain-text body (required)
      - cc: optional CC addresses (comma-separated)
    """
    if not auth:
        return {"error": "Auth context required for Gmail"}

    to = tool_input.get("to", "").strip()
    subject = tool_input.get("subject", "").strip()
    body = tool_input.get("body", "").strip()
    cc = tool_input.get("cc", "")

    if not to or not subject or not body:
        return {"error": "to, subject, and body are required"}

    token = await _get_gmail_token(auth)
    if not token:
        return {"error": "No Gmail token found. User must connect Gmail in Settings > Integrations."}

    # Build RFC 2822 message
    import base64
    lines = [
        f"To: {to}",
        f"Subject: {subject}",
    ]
    if cc:
        lines.append(f"Cc: {cc}")
    lines.append("Content-Type: text/plain; charset=utf-8")
    lines.append("")
    lines.append(body)
    raw_message = "\r\n".join(lines)
    encoded = base64.urlsafe_b64encode(raw_message.encode("utf-8")).decode("ascii")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{GMAIL_API_BASE}/messages/send",
                json={"raw": encoded},
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 401:
                token = await _refresh_token_if_needed(token, auth)
                resp = await client.post(
                    f"{GMAIL_API_BASE}/messages/send",
                    json={"raw": encoded},
                    headers={"Authorization": f"Bearer {token}"},
                )
            if resp.status_code < 400:
                data = resp.json()
                return {"success": True, "message_id": data.get("id"), "thread_id": data.get("threadId")}
            return {"error": f"Gmail API returned {resp.status_code}: {resp.text[:300]}"}
    except Exception as e:
        return {"error": f"Gmail send failed: {str(e)[:300]}"}


async def tool_gmail_read(
    tool_input: Dict[str, Any],
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Read recent emails from Gmail inbox.

    tool_input keys:
      - query: Gmail search query (default: 'in:inbox')
      - max_results: number of messages (default: 5, max: 20)
    """
    if not auth:
        return {"error": "Auth context required for Gmail"}

    query = tool_input.get("query", "in:inbox")
    max_results = min(int(tool_input.get("max_results", 5)), 20)

    token = await _get_gmail_token(auth)
    if not token:
        return {"error": "No Gmail token found. User must connect Gmail in Settings > Integrations."}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # List messages
            resp = await client.get(
                f"{GMAIL_API_BASE}/messages",
                params={"q": query, "maxResults": max_results},
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 401:
                token = await _refresh_token_if_needed(token, auth)
                resp = await client.get(
                    f"{GMAIL_API_BASE}/messages",
                    params={"q": query, "maxResults": max_results},
                    headers={"Authorization": f"Bearer {token}"},
                )
            if resp.status_code >= 400:
                return {"error": f"Gmail list failed: {resp.status_code}: {resp.text[:200]}"}

            data = resp.json()
            message_ids = [m["id"] for m in data.get("messages", [])]

            # Fetch each message's metadata
            emails = []
            for msg_id in message_ids[:max_results]:
                msg_resp = await client.get(
                    f"{GMAIL_API_BASE}/messages/{msg_id}",
                    params={"format": "metadata", "metadataHeaders": "From,To,Subject,Date"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                if msg_resp.status_code == 200:
                    msg = msg_resp.json()
                    headers_list = msg.get("payload", {}).get("headers", [])
                    header_map = {h["name"]: h["value"] for h in headers_list}
                    emails.append({
                        "id": msg_id,
                        "from": header_map.get("From", ""),
                        "to": header_map.get("To", ""),
                        "subject": header_map.get("Subject", ""),
                        "date": header_map.get("Date", ""),
                        "snippet": msg.get("snippet", ""),
                    })

            return {"success": True, "emails": emails, "count": len(emails)}
    except Exception as e:
        return {"error": f"Gmail read failed: {str(e)[:300]}"}
