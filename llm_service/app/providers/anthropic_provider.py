import json
import time
import uuid
from typing import AsyncIterator, List, Optional

from anthropic import AsyncAnthropic

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


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM provider."""

    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.default_model = settings.ANTHROPIC_MODEL

    def _convert_messages(self, messages: List[Message]) -> tuple:
        """Convert internal message format to Anthropic format.
        
        Returns (system_prompt, messages_list)
        """
        system_prompt = None
        converted = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_prompt = msg.content
            else:
                role = "user" if msg.role == MessageRole.USER else "assistant"
                converted.append({"role": role, "content": msg.content})

        return system_prompt, converted

    def _convert_tools(self, tools: Optional[List]) -> Optional[List[dict]]:
        """Convert internal tool format to Anthropic format."""
        if not tools:
            return None

        result = []
        for tool in tools:
            result.append({
                "name": tool.function.name,
                "description": tool.function.description,
                "input_schema": tool.function.parameters,
            })
        return result

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Generate a chat completion using Anthropic."""
        model = request.model or self.default_model
        system_prompt, messages = self._convert_messages(request.messages)
        tools = self._convert_tools(request.tools)

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if tools:
            kwargs["tools"] = tools

        response = await self.client.messages.create(**kwargs)

        # Extract content
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        type="function",
                        function={
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    )
                )

        return ChatCompletionResponse(
            id=response.id,
            created=int(time.time()),
            model=response.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=Message(role=MessageRole.ASSISTANT, content=content),
                    finish_reason=response.stop_reason or "stop",
                    tool_calls=tool_calls if tool_calls else None,
                )
            ],
            usage=Usage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            ),
        )

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming chat completion using Anthropic."""
        model = request.model or self.default_model
        system_prompt, messages = self._convert_messages(request.messages)
        tools = self._convert_tools(request.tools)

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if tools:
            kwargs["tools"] = tools

        stream_id = str(uuid.uuid4())
        created = int(time.time())

        async with self.client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        yield StreamChunk(
                            id=stream_id,
                            created=created,
                            model=model,
                            delta={"content": event.delta.text},
                            finish_reason=None,
                        )
                elif event.type == "message_stop":
                    yield StreamChunk(
                        id=stream_id,
                        created=created,
                        model=model,
                        delta={},
                        finish_reason="stop",
                    )

    def count_tokens(self, text: str) -> int:
        """Estimate token count for Anthropic models."""
        # Anthropic doesn't provide a public tokenizer
        # Use rough estimate: ~4 chars per token
        return len(text) // 4
