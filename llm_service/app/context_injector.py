"""Context injection for enriching LLM prompts with memory and cognitive data."""

from typing import List, Optional

import httpx

from .config import settings
from .models import Message, MessageRole


class ContextInjector:
    """Injects context from memory and cognitive services into prompts."""

    def __init__(self):
        self.memory_url = settings.MEMORY_SERVICE_URL
        self.cognitive_url = settings.COGNITIVE_SERVICE_URL
        self.chat_url = settings.CHAT_SERVICE_URL

    async def get_memory_context(
        self,
        user_id: Optional[str],
        conversation_id: Optional[str],
        query: str,
        limit: int = 5,
    ) -> List[dict]:
        """Retrieve relevant memories for context."""
        if not user_id:
            return []

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self.memory_url}/memory/retrieve",
                    json={
                        "user_id": user_id,
                        "chat_id": conversation_id,
                        "query": query,
                        "limit": limit,
                    },
                )
                if response.status_code == 200:
                    return response.json()
        except httpx.RequestError:
            pass
        return []

    async def get_cognitive_context(
        self,
        user_id: Optional[str],
        limit: int = 3,
    ) -> List[dict]:
        """Retrieve recent cognitive insights (anomalies, patterns)."""
        if not user_id:
            return []

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.cognitive_url}/cognitive/insights",
                    params={"user_id": user_id, "limit": limit},
                )
                if response.status_code == 200:
                    return response.json()
        except httpx.RequestError:
            pass
        return []

    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> List[dict]:
        """Retrieve recent conversation history."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.chat_url}/chat/conversations/{conversation_id}/messages",
                    params={"limit": limit},
                )
                if response.status_code == 200:
                    return response.json()
        except httpx.RequestError:
            pass
        return []

    def format_memory_context(self, memories: List[dict]) -> str:
        """Format memories into a context string."""
        if not memories:
            return ""

        lines = ["## Relevant Memories:"]
        for mem in memories:
            content = mem.get("content", "")
            source = mem.get("source", "unknown")
            lines.append(f"- [{source}] {content}")

        return "\n".join(lines)

    def format_cognitive_context(self, insights: List[dict]) -> str:
        """Format cognitive insights into a context string."""
        if not insights:
            return ""

        lines = ["## Recent Insights:"]
        for insight in insights:
            kind = insight.get("kind", "insight")
            payload = insight.get("payload", "")
            lines.append(f"- [{kind}] {payload}")

        return "\n".join(lines)

    async def inject_context(
        self,
        messages: List[Message],
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        inject_memory: bool = True,
        inject_cognitive: bool = True,
    ) -> List[Message]:
        """Inject context into the message list."""
        if not inject_memory and not inject_cognitive:
            return messages

        # Get the last user message for context retrieval
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.role == MessageRole.USER:
                last_user_msg = msg.content
                break

        context_parts = []

        if inject_memory:
            memories = await self.get_memory_context(
                user_id, conversation_id, last_user_msg
            )
            mem_context = self.format_memory_context(memories)
            if mem_context:
                context_parts.append(mem_context)

        if inject_cognitive:
            insights = await self.get_cognitive_context(user_id)
            cog_context = self.format_cognitive_context(insights)
            if cog_context:
                context_parts.append(cog_context)

        if not context_parts:
            return messages

        # Create context message
        context_content = "\n\n".join(context_parts)
        context_message = Message(
            role=MessageRole.SYSTEM,
            content=f"Use the following context to inform your response:\n\n{context_content}",
        )

        # Insert after first system message or at beginning
        result = list(messages)
        insert_idx = 0
        for i, msg in enumerate(result):
            if msg.role == MessageRole.SYSTEM:
                insert_idx = i + 1
                break

        result.insert(insert_idx, context_message)
        return result


context_injector = ContextInjector()
