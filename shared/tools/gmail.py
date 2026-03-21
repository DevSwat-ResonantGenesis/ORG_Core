"""
Gmail platform tool for agents.

Agents can send emails and read inbox on behalf of users
who have connected their Google account with Gmail scopes.

Token is fetched from auth_service user_api_keys (provider='gmail').
"""

import base64
import logging
import os
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import httpx

from .auth import AuthContext, build_service_headers

logger = logging.getLogger(__name__)

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8000")
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1"


async def _get_gmail_token(auth: AuthContext) -> Optional[str]:
    """Get the user's Gmail OAuth refresh token from auth_service, then exchange for access token."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{AUTH_SERVICE_URL}/api-keys/user/{auth.user_id}",
                headers=build_service_headers(auth),
            )
            if resp.status_code != 200:
                return None
            for key in resp.json().get("keys", []):
                if key.get("provider") == "gmail" and key.get("decrypted_key"):
                    return key["decrypted_key"]
    except Exception as e:
        logger.warning(f"[GMAIL] Failed to fetch token: {e}")
    return None


async def _refresh_access_token(refresh_token: str) -> Optional[str]:
    """Exchange a Google refresh token for a short-lived access token."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return refresh_token  # Assume it's already an access token

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if resp.status_code == 200:
                return resp.json().get("access_token")
    except Exception as e:
        logger.warning(f"[GMAIL] Token refresh failed: {e}")
    return None


async def tool_gmail_send(
    tool_input: Dict[str, Any],
    *,
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Send an email via Gmail API."""
    if not auth:
        return {"error": "Authentication required to send email."}

    to = tool_input.get("to", "").strip()
    subject = tool_input.get("subject", "").strip()
    body = tool_input.get("body", "").strip()

    if not to or not subject or not body:
        return {"error": "Missing required fields: 'to', 'subject', 'body'."}

    refresh_token = await _get_gmail_token(auth)
    if not refresh_token:
        return {"error": "Gmail not connected. Ask the user to connect Gmail in Settings > Integrations."}

    access_token = await _refresh_access_token(refresh_token)
    if not access_token:
        return {"error": "Failed to refresh Gmail access token. User may need to re-connect Gmail."}

    # Build RFC 2822 message
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{GMAIL_API}/users/me/messages/send",
                json={"raw": raw},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                return {
                    "status": "sent",
                    "message_id": data.get("id"),
                    "thread_id": data.get("threadId"),
                }
            return {"error": f"Gmail API error {resp.status_code}: {resp.text[:300]}"}
    except Exception as e:
        return {"error": f"Gmail send failed: {str(e)[:300]}"}


async def tool_gmail_read(
    tool_input: Dict[str, Any],
    *,
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Read recent emails from Gmail inbox."""
    if not auth:
        return {"error": "Authentication required to read email."}

    max_results = min(int(tool_input.get("max_results", 10)), 20)
    query = tool_input.get("query", "")  # Gmail search query

    refresh_token = await _get_gmail_token(auth)
    if not refresh_token:
        return {"error": "Gmail not connected. Ask the user to connect Gmail in Settings > Integrations."}

    access_token = await _refresh_access_token(refresh_token)
    if not access_token:
        return {"error": "Failed to refresh Gmail access token."}

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # List messages
            params = {"maxResults": max_results}
            if query:
                params["q"] = query
            list_resp = await client.get(
                f"{GMAIL_API}/users/me/messages",
                params=params,
                headers=headers,
            )
            if list_resp.status_code != 200:
                return {"error": f"Gmail list error {list_resp.status_code}: {list_resp.text[:200]}"}

            messages_list = list_resp.json().get("messages", [])
            if not messages_list:
                return {"messages": [], "total": 0}

            # Fetch each message's metadata
            emails: List[Dict[str, Any]] = []
            for msg_ref in messages_list[:max_results]:
                msg_resp = await client.get(
                    f"{GMAIL_API}/users/me/messages/{msg_ref['id']}",
                    params={"format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]},
                    headers=headers,
                )
                if msg_resp.status_code == 200:
                    msg = msg_resp.json()
                    header_map = {}
                    for h in msg.get("payload", {}).get("headers", []):
                        header_map[h["name"].lower()] = h["value"]
                    emails.append({
                        "id": msg["id"],
                        "thread_id": msg.get("threadId"),
                        "from": header_map.get("from", ""),
                        "to": header_map.get("to", ""),
                        "subject": header_map.get("subject", ""),
                        "date": header_map.get("date", ""),
                        "snippet": msg.get("snippet", ""),
                    })

            return {"messages": emails, "total": len(emails)}
    except Exception as e:
        return {"error": f"Gmail read failed: {str(e)[:300]}"}
