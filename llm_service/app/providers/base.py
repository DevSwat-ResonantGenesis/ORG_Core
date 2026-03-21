from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional

from ..models import ChatCompletionRequest, ChatCompletionResponse, StreamChunk


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Generate a chat completion."""
        pass

    @abstractmethod
    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming chat completion."""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        pass
