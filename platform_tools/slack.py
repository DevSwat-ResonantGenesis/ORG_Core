"""Slack tools for agent execution.

Uses Slack bot tokens stored in UserApiKey (provider='slack')
via auth_service to send/read messages through the Slack Web API.
"""

import os
import logging
from typing import Any, Dict, Optional

import httpx

from .auth import AuthContext

logger = logging.getLogger(__name__)

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8000")
SLACK_API_BASE = "https://slack.com/api"


async def _get_slack_token(auth: AuthContext) -> Optional[str]:
    """Fetch the user's Slack bot token from auth_service."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{AUTH_SERVICE_URL}/auth/api-keys",
                headers=auth.headers(),
                params={"provider": "slack"},
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
        logger.warning(f"Failed to fetch Slack token: {e}")
    return None


async def tool_slack_send_message(
    tool_input: Dict[str, Any],
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Send a message to a Slack channel.

    tool_input keys:
      - channel: channel name or ID (required)
      - text: message text (required)
      - thread_ts: optional thread timestamp to reply in thread
    """
    if not auth:
        return {"error": "Auth context required for Slack"}

    channel = tool_input.get("channel", "").strip()
    text = tool_input.get("text", "").strip()
    thread_ts = tool_input.get("thread_ts")

    if not channel or not text:
        return {"error": "channel and text are required"}

    token = await _get_slack_token(auth)
    if not token:
        return {"error": "No Slack token found. User must connect Slack in Settings > Integrations."}

    payload: Dict[str, Any] = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{SLACK_API_BASE}/chat.postMessage",
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            data = resp.json()
            if data.get("ok"):
                return {
                    "success": True,
                    "channel": data.get("channel"),
                    "ts": data.get("ts"),
                    "message": data.get("message", {}).get("text", ""),
                }
            return {"error": f"Slack API error: {data.get('error', 'unknown')}"}
    except Exception as e:
        return {"error": f"Slack send failed: {str(e)[:300]}"}


async def tool_slack_list_channels(
    tool_input: Dict[str, Any],
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """List Slack channels the bot has access to.

    tool_input keys:
      - limit: max channels to return (default: 20, max: 100)
      - types: channel types (default: 'public_channel')
    """
    if not auth:
        return {"error": "Auth context required for Slack"}

    limit = min(int(tool_input.get("limit", 20)), 100)
    types = tool_input.get("types", "public_channel")

    token = await _get_slack_token(auth)
    if not token:
        return {"error": "No Slack token found. User must connect Slack in Settings > Integrations."}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{SLACK_API_BASE}/conversations.list",
                params={"limit": limit, "types": types},
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
                return {"success": True, "channels": channels, "count": len(channels)}
            return {"error": f"Slack API error: {data.get('error', 'unknown')}"}
    except Exception as e:
        return {"error": f"Slack list channels failed: {str(e)[:300]}"}


async def tool_slack_read_messages(
    tool_input: Dict[str, Any],
    auth: Optional[AuthContext] = None,
) -> Dict[str, Any]:
    """Read recent messages from a Slack channel.

    tool_input keys:
      - channel: channel name or ID (required)
      - limit: max messages to return (default: 10, max: 50)
    """
    if not auth:
        return {"error": "Auth context required for Slack"}

    channel = tool_input.get("channel", "").strip()
    limit = min(int(tool_input.get("limit", 10)), 50)

    if not channel:
        return {"error": "channel is required"}

    token = await _get_slack_token(auth)
    if not token:
        return {"error": "No Slack token found. User must connect Slack in Settings > Integrations."}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{SLACK_API_BASE}/conversations.history",
                params={"channel": channel, "limit": limit},
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()
            if data.get("ok"):
                messages = [
                    {
                        "user": msg.get("user", ""),
                        "text": msg.get("text", ""),
                        "ts": msg.get("ts", ""),
                        "type": msg.get("type", ""),
                    }
                    for msg in data.get("messages", [])
                ]
                return {"success": True, "messages": messages, "count": len(messages)}
            return {"error": f"Slack API error: {data.get('error', 'unknown')}"}
    except Exception as e:
        return {"error": f"Slack read failed: {str(e)[:300]}"}
