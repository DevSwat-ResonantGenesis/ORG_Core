"""
Slack platform tool for agents.

Agents can send messages and read channels on behalf of users
who have connected their Slack workspace via OAuth.

Token is fetched from auth_service user_api_keys (provider='slack').
"""

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from .auth import AuthContext, build_service_headers

logger = logging.getLogger(__name__)

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8000")
SLACK_API = "https://slack.com/api"


async def _get_slack_token(auth: AuthContext) -> Optional[str]:
    """Get the user's Slack bot token from auth_service."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{AUTH_SERVICE_URL}/api-keys/user/{auth.user_id}",
                headers=build_service_headers(auth),
            )
            if resp.status_code != 200:
                return None
            for key in resp.json().get("keys", []):
                if key.get("provider") == "slack" and key.get("decrypted_key"):
                    return key["decrypted_key"]
    except Exception as e:
        logger.warning(f"[SLACK] Failed to fetch token: {e}")
    return None


async def tool_slack_send_message(
    tool_input: Dict[str, Any],
    *,
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Send a message to a Slack channel or DM."""
    if not auth:
        return {"error": "Authentication required to send Slack message."}

    channel = tool_input.get("channel", "").strip()
    text = tool_input.get("text", "").strip()

    if not channel or not text:
        return {"error": "Missing required fields: 'channel' (channel name or ID), 'text'."}

    token = await _get_slack_token(auth)
    if not token:
        return {"error": "Slack not connected. Ask the user to connect Slack in Settings > Integrations."}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{SLACK_API}/chat.postMessage",
                json={"channel": channel, "text": text},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            data = resp.json()
            if data.get("ok"):
                return {
                    "status": "sent",
                    "channel": data.get("channel"),
                    "ts": data.get("ts"),
                    "message": data.get("message", {}).get("text", ""),
                }
            return {"error": f"Slack API error: {data.get('error', 'unknown')}"}
    except Exception as e:
        return {"error": f"Slack send failed: {str(e)[:300]}"}


async def tool_slack_list_channels(
    tool_input: Dict[str, Any],
    *,
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """List Slack channels the bot has access to."""
    if not auth:
        return {"error": "Authentication required."}

    token = await _get_slack_token(auth)
    if not token:
        return {"error": "Slack not connected. Ask the user to connect Slack in Settings > Integrations."}

    limit = min(int(tool_input.get("limit", 50)), 200)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{SLACK_API}/conversations.list",
                params={"limit": limit, "types": "public_channel,private_channel"},
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()
            if data.get("ok"):
                channels = [
                    {
                        "id": ch["id"],
                        "name": ch.get("name", ""),
                        "topic": ch.get("topic", {}).get("value", ""),
                        "num_members": ch.get("num_members", 0),
                        "is_private": ch.get("is_private", False),
                    }
                    for ch in data.get("channels", [])
                ]
                return {"channels": channels, "total": len(channels)}
            return {"error": f"Slack API error: {data.get('error', 'unknown')}"}
    except Exception as e:
        return {"error": f"Slack list channels failed: {str(e)[:300]}"}


async def tool_slack_read_messages(
    tool_input: Dict[str, Any],
    *,
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Read recent messages from a Slack channel."""
    if not auth:
        return {"error": "Authentication required."}

    channel = tool_input.get("channel", "").strip()
    if not channel:
        return {"error": "Missing required field: 'channel' (channel name or ID)."}

    limit = min(int(tool_input.get("limit", 20)), 100)

    token = await _get_slack_token(auth)
    if not token:
        return {"error": "Slack not connected. Ask the user to connect Slack in Settings > Integrations."}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{SLACK_API}/conversations.history",
                params={"channel": channel, "limit": limit},
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()
            if data.get("ok"):
                messages: List[Dict[str, Any]] = []
                for msg in data.get("messages", []):
                    messages.append({
                        "user": msg.get("user", ""),
                        "text": msg.get("text", ""),
                        "ts": msg.get("ts", ""),
                        "type": msg.get("type", ""),
                    })
                return {"messages": messages, "total": len(messages)}
            return {"error": f"Slack API error: {data.get('error', 'unknown')}"}
    except Exception as e:
        return {"error": f"Slack read failed: {str(e)[:300]}"}
