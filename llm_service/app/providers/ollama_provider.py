"""Ollama LLM Provider - Local LLM via SSH tunnel."""

import httpx
import logging
import time
from typing import AsyncIterator, List, Optional

from .base import BaseLLMProvider
from ..models import ChatCompletionRequest, ChatCompletionResponse, StreamChunk

logger = logging.getLogger(__name__)

# Ollama endpoints - try multiple for Docker compatibility
OLLAMA_HOSTS = [
    "http://172.22.0.1:11435",  # Docker network gateway -> socat relay
    "http://172.22.0.1:11434",  # Docker network gateway (direct)
    "http://localhost:11434",   # Direct (if not in container)
]


class OllamaProvider(BaseLLMProvider):
    """Provider for local LLM via Ollama (tunneled from Mac)."""

    def __init__(self, model: str = "llama3.1:8b"):
        self.model = model
        self.timeout = 60.0  # Longer timeout for local inference
        self._base_url = None

    async def _get_base_url(self) -> str:
        """Find working Ollama endpoint."""
        if self._base_url:
            return self._base_url

        for url in OLLAMA_HOSTS:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{url}/api/tags", timeout=5.0)
                    if response.status_code == 200:
                        self._base_url = url
                        logger.info(f"Ollama available at {url}")
                        return url
            except Exception:
                continue

        raise Exception("Ollama not available - check SSH tunnel and socat relay")

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Generate a chat completion using Ollama."""
        base_url = await self._get_base_url()

        # Convert messages to Ollama format
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        # Determine model based on request or use default
        model = self.model
        if hasattr(request, 'model') and request.model:
            if 'code' in request.model.lower():
                model = "codellama:13b"

        try:
            start_time = time.time()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": request.temperature or 0.7,
                            "num_predict": request.max_tokens or 2048,
                        }
                    }
                )
                response.raise_for_status()
                result = response.json()

            latency = time.time() - start_time
            content = result.get("message", {}).get("content", "")

            return ChatCompletionResponse(
                id=f"ollama-{int(time.time())}",
                object="chat.completion",
                created=int(time.time()),
                model=model,
                choices=[{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": "stop" if result.get("done") else "length",
                }],
                usage={
                    "prompt_tokens": result.get("prompt_eval_count", 0),
                    "completion_tokens": result.get("eval_count", 0),
                    "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0),
                },
                provider="ollama",
                latency_ms=int(latency * 1000),
            )

        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama - check SSH tunnel")
            raise Exception("Local LLM unavailable - SSH tunnel may be down")
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming chat completion using Ollama."""
        base_url = await self._get_base_url()

        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        model = self.model
        if hasattr(request, 'model') and request.model:
            if 'code' in request.model.lower():
                model = "codellama:13b"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": True,
                        "options": {
                            "temperature": request.temperature or 0.7,
                            "num_predict": request.max_tokens or 2048,
                        }
                    }
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            import json
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield StreamChunk(
                                    id=f"ollama-stream-{int(time.time())}",
                                    object="chat.completion.chunk",
                                    created=int(time.time()),
                                    model=model,
                                    choices=[{
                                        "index": 0,
                                        "delta": {"content": content},
                                        "finish_reason": None,
                                    }],
                                )
                            if data.get("done"):
                                yield StreamChunk(
                                    id=f"ollama-stream-{int(time.time())}",
                                    object="chat.completion.chunk",
                                    created=int(time.time()),
                                    model=model,
                                    choices=[{
                                        "index": 0,
                                        "delta": {},
                                        "finish_reason": "stop",
                                    }],
                                )
                                break

        except Exception as e:
            logger.error(f"Ollama stream error: {e}")
            raise

    def count_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation for Llama models)."""
        # Llama uses ~4 characters per token on average
        return len(text) // 4
