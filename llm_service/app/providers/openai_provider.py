import json
import time
import uuid
from typing import AsyncIterator, List, Optional

from openai import AsyncOpenAI

from ..config import settings
from ..models import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Message,
    MessageRole,
    StreamChunk,
    ToolCall,
    Usage,
)
from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.default_model = settings.OPENAI_MODEL

    def _convert_messages(self, messages: List[Message]) -> List[dict]:
        """Convert internal message format to OpenAI format."""
        result = []
        for msg in messages:
            m = {"role": msg.role.value, "content": msg.content}
            if msg.name:
                m["name"] = msg.name
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            result.append(m)
        return result

    def _convert_tools(self, tools: Optional[List]) -> Optional[List[dict]]:
        """Convert internal tool format to OpenAI format."""
        if not tools:
            return None
        return [t.model_dump() for t in tools]

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Generate a chat completion using OpenAI."""
        model = request.model or self.default_model
        messages = self._convert_messages(request.messages)
        tools = self._convert_tools(request.tools)

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            if request.tool_choice:
                kwargs["tool_choice"] = request.tool_choice

        response = await self.client.chat.completions.create(**kwargs)

        # Convert response
        choices = []
        for i, choice in enumerate(response.choices):
            tool_calls = None
            if choice.message.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id,
                        type=tc.type,
                        function={
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    )
                    for tc in choice.message.tool_calls
                ]

            choices.append(
                ChatCompletionChoice(
                    index=i,
                    message=Message(
                        role=MessageRole(choice.message.role),
                        content=choice.message.content or "",
                    ),
                    finish_reason=choice.finish_reason or "stop",
                    tool_calls=tool_calls,
                )
            )

        return ChatCompletionResponse(
            id=response.id,
            created=response.created,
            model=response.model,
            choices=choices,
            usage=Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
        )

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming chat completion using OpenAI."""
        model = request.model or self.default_model
        messages = self._convert_messages(request.messages)
        tools = self._convert_tools(request.tools)

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
        }

        if tools:
            kwargs["tools"] = tools
            if request.tool_choice:
                kwargs["tool_choice"] = request.tool_choice

        stream = await self.client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices:
                delta = {}
                choice = chunk.choices[0]

                if choice.delta.role:
                    delta["role"] = choice.delta.role
                if choice.delta.content:
                    delta["content"] = choice.delta.content
                if choice.delta.tool_calls:
                    delta["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name if tc.function else None,
                                "arguments": tc.function.arguments if tc.function else None,
                            },
                        }
                        for tc in choice.delta.tool_calls
                    ]

                yield StreamChunk(
                    id=chunk.id,
                    created=chunk.created,
                    model=chunk.model,
                    delta=delta,
                    finish_reason=choice.finish_reason,
                )

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken."""
        try:
            import tiktoken

            encoding = tiktoken.encoding_for_model(self.default_model)
            return len(encoding.encode(text))
        except Exception:
            # Fallback: rough estimate
            return len(text) // 4
