"""
Shared Tool Implementations
============================

Reusable tool functions used by both:
- chat_service (skills pipeline)
- agent_engine_service (autonomous agent loop)

Each tool function is a standalone async function that:
1. Takes typed input parameters
2. Returns a structured Dict[str, Any] result
3. Handles its own errors gracefully
4. Accepts an auth_context for proper authentication
"""

from .auth import AuthContext, build_service_headers  # noqa: F401
from .web_search import tool_web_search  # noqa: F401
from .rabbit import tool_create_rabbit_post, tool_list_rabbit_communities, tool_create_rabbit_community  # noqa: F401
from .memory import tool_memory_read, tool_memory_write  # noqa: F401
from .http_api import tool_http_request  # noqa: F401
from .gmail import tool_gmail_send, tool_gmail_read  # noqa: F401
from .slack import tool_slack_send_message, tool_slack_list_channels, tool_slack_read_messages  # noqa: F401

__all__ = [
    "AuthContext",
    "build_service_headers",
    "tool_web_search",
    "tool_create_rabbit_post",
    "tool_list_rabbit_communities",
    "tool_create_rabbit_community",
    "tool_memory_read",
    "tool_memory_write",
    "tool_http_request",
    "tool_gmail_send",
    "tool_gmail_read",
    "tool_slack_send_message",
    "tool_slack_list_channels",
    "tool_slack_read_messages",
]
