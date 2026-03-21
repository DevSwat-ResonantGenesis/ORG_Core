"""Tool execution system for agent reasoning."""

import json
from typing import Any, Callable, Dict, List, Optional

import httpx

from .config import settings
from .models import Tool, ToolCall, ToolFunction


class ToolRegistry:
    """Registry for available tools — definitions from shared rg_tool_registry."""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._tool_definitions: Dict[str, Tool] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """Register tools: definitions from unified registry, handlers local."""
        from .rg_tool_registry.builtin_tools import build_registry
        shared = build_registry()

        # Map shared tool names → local handlers
        _handler_map = {
            "memory_search": self._search_memory,
            "http_request": self._http_request,
        }

        # Register tools that have local handlers
        for name, handler in _handler_map.items():
            td = shared.get(name)
            if td:
                openai_fmt = td.to_openai()
                self.register(
                    name=td.name, description=td.description,
                    parameters=openai_fmt["function"]["parameters"],
                    handler=handler,
                )

        # Also register legacy handlers that don't exist in shared registry
        self.register(
            name="search_memory", description="Search user's memory for relevant information",
            parameters={"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 5}}, "required": ["query"]},
            handler=self._search_memory,
        )
        self.register(
            name="get_conversation_context", description="Get conversation context",
            parameters={"type": "object", "properties": {"conversation_id": {"type": "string"}}, "required": ["conversation_id"]},
            handler=self._get_conversation_context,
        )
        self.register(
            name="create_workflow", description="Create a new workflow automation",
            parameters={"type": "object", "properties": {"name": {"type": "string"}, "trigger": {"type": "string"}, "actions": {"type": "array", "items": {"type": "object"}}}, "required": ["name", "trigger", "actions"]},
            handler=self._create_workflow,
        )

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
    ):
        """Register a tool."""
        self._tools[name] = handler
        self._tool_definitions[name] = Tool(
            type="function",
            function=ToolFunction(
                name=name,
                description=description,
                parameters=parameters,
            ),
        )

    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a tool handler by name."""
        return self._tools.get(name)

    def get_tool_definition(self, name: str) -> Optional[Tool]:
        """Get a tool definition by name."""
        return self._tool_definitions.get(name)

    def get_all_tools(self) -> List[Tool]:
        """Get all registered tool definitions."""
        return list(self._tool_definitions.values())

    async def execute(
        self,
        tool_call: ToolCall,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> str:
        """Execute a tool call and return the result."""
        tool_name = tool_call.function.get("name")
        arguments_str = tool_call.function.get("arguments", "{}")

        try:
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError:
            return f"Error: Invalid JSON arguments: {arguments_str}"

        handler = self.get_tool(tool_name)
        if not handler:
            return f"Error: Unknown tool: {tool_name}"

        try:
            # Add context to arguments
            arguments["_user_id"] = user_id
            arguments["_conversation_id"] = conversation_id

            result = await handler(**arguments)
            return json.dumps(result) if isinstance(result, (dict, list)) else str(result)
        except Exception as e:
            return f"Error executing tool {tool_name}: {str(e)}"

    # Built-in tool handlers
    async def _search_memory(
        self,
        query: str,
        limit: int = 5,
        _user_id: Optional[str] = None,
        **kwargs,
    ) -> List[dict]:
        """Search memory service."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{settings.MEMORY_SERVICE_URL}/memory/retrieve",
                    json={
                        "user_id": _user_id,
                        "query": query,
                        "limit": limit,
                    },
                )
                if response.status_code == 200:
                    return response.json()
        except httpx.RequestError as e:
            return {"error": str(e)}
        return []

    async def _get_conversation_context(
        self,
        conversation_id: str,
        _user_id: Optional[str] = None,
        **kwargs,
    ) -> dict:
        """Get conversation context from chat service."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{settings.CHAT_SERVICE_URL}/chat/conversations/{conversation_id}/context",
                    headers={"x-user-id": _user_id} if _user_id else {},
                )
                if response.status_code == 200:
                    return response.json()
        except httpx.RequestError as e:
            return {"error": str(e)}
        return {"error": "Failed to get conversation context"}

    async def _create_workflow(
        self,
        name: str,
        trigger: str,
        actions: List[dict],
        _user_id: Optional[str] = None,
        **kwargs,
    ) -> dict:
        """Create a workflow in workflow service."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"http://workflow_service:8000/workflow/workflows",
                    json={
                        "name": name,
                        "trigger": trigger,
                        "actions": actions,
                        "user_id": _user_id,
                    },
                )
                if response.status_code in (200, 201):
                    return response.json()
        except httpx.RequestError as e:
            return {"error": str(e)}
        return {"error": "Failed to create workflow"}

    async def _http_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict] = None,
        body: Optional[Dict] = None,
        **kwargs,
    ) -> dict:
        """Make an HTTP request."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if method in ("POST", "PUT") else None,
                )
                return {
                    "status_code": response.status_code,
                    "body": response.text[:1000],  # Limit response size
                }
        except httpx.RequestError as e:
            return {"error": str(e)}


tool_registry = ToolRegistry()
