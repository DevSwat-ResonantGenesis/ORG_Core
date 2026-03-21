"""LLM Service API routes."""

import json
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from .agent import Agent
from .config import settings
from .context_injector import context_injector
from .models import (
    AgentRequest,
    AgentResponse,
    ChatCompletionRequest,
    ChatCompletionResponse,
    AgentRouteQueryRequest,
    StreamChunk,
    Tool,
)
from .providers.openai_provider import OpenAIProvider
from .providers.anthropic_provider import AnthropicProvider
from .providers.ollama_provider import OllamaProvider
from .multi_provider.multi_ai_router import MultiAIRouter
from .tool_executor import tool_registry


router = APIRouter(prefix="/llm", tags=["llm"])
multi_router = MultiAIRouter()


def get_provider(provider_name: Optional[str] = None):
    """Get the appropriate LLM provider."""
    provider = provider_name or settings.DEFAULT_PROVIDER

    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise HTTPException(status_code=400, detail="Anthropic API key not configured")
        return AnthropicProvider()
    elif provider == "ollama" or provider == "local":
        return OllamaProvider(model="llama3.1:8b")
    elif provider == "codellama":
        return OllamaProvider(model="codellama:13b")
    else:
        if not settings.OPENAI_API_KEY:
            raise HTTPException(status_code=400, detail="OpenAI API key not configured")
        return OpenAIProvider()


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    http_request: Request,
):
    """Generate a chat completion with automatic provider fallback."""
    # Get user context from headers
    user_id = http_request.headers.get("x-user-id") or request.user_id

    # Inject context if requested
    messages = request.messages
    if request.inject_memory or request.inject_cognitive:
        messages = await context_injector.inject_context(
            messages=messages,
            user_id=user_id,
            conversation_id=request.conversation_id,
            inject_memory=request.inject_memory,
            inject_cognitive=request.inject_cognitive,
        )

    # Update request with enriched messages
    enriched_request = request.model_copy(update={"messages": messages})

    # Check for user custom API keys (BYOK)
    user_keys = request.user_api_keys or {}
    
    # Build provider fallback order
    preferred = request.provider or settings.DEFAULT_PROVIDER
    fallback_order = []
    
    # If user has custom keys, prioritize those providers
    if user_keys.get("openai"):
        fallback_order.append("openai")
    if user_keys.get("anthropic"):
        fallback_order.append("anthropic")
    if user_keys.get("groq"):
        fallback_order.append("multi_router_groq")
    if user_keys.get("google"):
        fallback_order.append("multi_router_gemini")
    
    # Add preferred provider if not already added
    if preferred == "anthropic" and settings.ANTHROPIC_API_KEY and "anthropic" not in fallback_order:
        fallback_order.append("anthropic")
    elif preferred == "openai" and settings.OPENAI_API_KEY and "openai" not in fallback_order:
        fallback_order.append("openai")
    
    # Add Groq first (only provider with working quota currently)
    if "multi_router_groq" not in fallback_order:
        fallback_order.append("multi_router_groq")
    
    # Add other system providers as fallbacks
    if "openai" not in fallback_order and settings.OPENAI_API_KEY:
        fallback_order.append("openai")
    if "anthropic" not in fallback_order and settings.ANTHROPIC_API_KEY:
        fallback_order.append("anthropic")
    
    # Also try multi-provider router as last resort (has groq, gemini)
    fallback_order.append("multi_router")
    
    if request.stream:
        # For streaming, try providers in order
        for provider_name in fallback_order:
            try:
                if provider_name == "multi_router":
                    # Multi-router doesn't support streaming, skip
                    continue
                provider = get_provider(provider_name)
                
                async def generate():
                    async for chunk in provider.chat_completion_stream(enriched_request):
                        yield f"data: {chunk.model_dump_json()}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    generate(),
                    media_type="text/event-stream",
                )
            except Exception:
                continue
        raise HTTPException(status_code=503, detail="All providers failed")
    else:
        # Non-streaming: try providers with fallback
        last_error = None
        for provider_name in fallback_order:
            try:
                if provider_name.startswith("multi_router"):
                    # Use multi-provider router (supports user keys for groq/gemini)
                    messages_as_dicts = [{"role": m.role.value if hasattr(m.role, 'value') else str(m.role), "content": m.content} for m in enriched_request.messages]
                    message_content = messages_as_dicts[-1]["content"] if messages_as_dicts else ""
                    
                    # Set user API keys if provided
                    multi_router.set_user_api_keys(user_keys if user_keys else None)
                    
                    # Determine preferred provider for multi-router
                    multi_preferred = None
                    if provider_name == "multi_router_groq":
                        multi_preferred = "groq"
                    elif provider_name == "multi_router_gemini":
                        multi_preferred = "gemini"
                    
                    result = multi_router.route_query(
                        message=message_content,
                        context=messages_as_dicts[:-1] if len(messages_as_dicts) > 1 else None,
                        preferred_provider=multi_preferred,
                    )
                    
                    # Clear user keys after use
                    multi_router.set_user_api_keys(None)
                    
                    if result.get("metadata", {}).get("error"):
                        last_error = result.get("response", "Multi-router failed")
                        continue
                    usage_meta = result.get("metadata", {}).get("usage") or {}
                    prompt_tokens = int(usage_meta.get("prompt_tokens") or 0)
                    completion_tokens = int(usage_meta.get("completion_tokens") or 0)
                    total_tokens = int(usage_meta.get("total_tokens") or (prompt_tokens + completion_tokens))
                    # Convert multi-router response to ChatCompletionResponse format
                    return ChatCompletionResponse(
                        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                        object="chat.completion",
                        created=int(time.time()),
                        model=result.get("metadata", {}).get("model", "unknown"),
                        choices=[{
                            "index": 0,
                            "message": {"role": "assistant", "content": result.get("response", "")},
                            "finish_reason": "stop",
                        }],
                        usage={
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                        },
                    )
                else:
                    # Direct provider call - check for user custom key
                    if user_keys.get(provider_name):
                        # Use user's custom API key via multi-router
                        messages_as_dicts = [{"role": m.role.value if hasattr(m.role, 'value') else str(m.role), "content": m.content} for m in enriched_request.messages]
                        message_content = messages_as_dicts[-1]["content"] if messages_as_dicts else ""
                        
                        multi_router.set_user_api_keys(user_keys)
                        result = multi_router.route_query(
                            message=message_content,
                            context=messages_as_dicts[:-1] if len(messages_as_dicts) > 1 else None,
                            preferred_provider=provider_name,
                        )
                        multi_router.set_user_api_keys(None)
                        
                        if result.get("metadata", {}).get("error"):
                            last_error = result.get("response", f"{provider_name} with user key failed")
                            continue
                        usage_meta = result.get("metadata", {}).get("usage") or {}
                        prompt_tokens = int(usage_meta.get("prompt_tokens") or 0)
                        completion_tokens = int(usage_meta.get("completion_tokens") or 0)
                        total_tokens = int(usage_meta.get("total_tokens") or (prompt_tokens + completion_tokens))
                        return ChatCompletionResponse(
                            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                            object="chat.completion",
                            created=int(time.time()),
                            model=result.get("metadata", {}).get("model", "unknown"),
                            choices=[{
                                "index": 0,
                                "message": {"role": "assistant", "content": result.get("response", "")},
                                "finish_reason": "stop",
                            }],
                            usage={
                                "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "total_tokens": total_tokens,
                            },
                        )
                    else:
                        # Use system API key
                        provider = get_provider(provider_name)
                        return await provider.chat_completion(enriched_request)
            except Exception as e:
                last_error = str(e)
                continue
        
        raise HTTPException(status_code=503, detail=f"All providers failed. Last error: {last_error}")


@router.post("/chat/completions/stream")
async def chat_completions_stream(
    request: ChatCompletionRequest,
    http_request: Request,
):
    """Generate a streaming chat completion using SSE."""
    user_id = http_request.headers.get("x-user-id") or request.user_id

    # Inject context if requested
    messages = request.messages
    if request.inject_memory or request.inject_cognitive:
        messages = await context_injector.inject_context(
            messages=messages,
            user_id=user_id,
            conversation_id=request.conversation_id,
            inject_memory=request.inject_memory,
            inject_cognitive=request.inject_cognitive,
        )

    enriched_request = request.model_copy(update={"messages": messages, "stream": True})
    provider = get_provider(request.provider)

    async def event_generator():
        async for chunk in provider.chat_completion_stream(enriched_request):
            yield {
                "event": "message",
                "data": chunk.model_dump_json(),
            }
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())


@router.post("/agent/run", response_model=AgentResponse)
async def run_agent(
    request: AgentRequest,
    http_request: Request,
):
    """Run an agent task with tool use."""
    user_id = http_request.headers.get("x-user-id") or request.user_id

    # Update request with user context
    request.user_id = user_id

    agent = Agent(provider=settings.DEFAULT_PROVIDER)
    return await agent.run(request)


@router.get("/tools")
async def list_tools():
    """List all available tools."""
    tools = tool_registry.get_all_tools()
    return {"tools": [t.model_dump() for t in tools]}


@router.post("/tools/register")
async def register_tool(tool: Tool):
    """Register a custom tool (for dynamic tool registration)."""
    # Note: This is a simplified version. In production, you'd want
    # to validate and store tool handlers properly.
    return {"status": "registered", "tool": tool.function.name}


@router.post("/tokens/count")
async def count_tokens(text: str, provider: Optional[str] = None):
    """Count tokens in text."""
    llm = get_provider(provider)
    count = llm.count_tokens(text)
    return {"text_length": len(text), "token_count": count}


@router.post("/agents/route-query")
async def agents_route_query(request: AgentRouteQueryRequest):
    """Route agent requests through the multi-provider router (isolated from chat)."""
    multi_router.set_user_api_keys(request.user_api_keys)
    result = multi_router.route_query(
        message=request.message,
        context=request.context,
        preferred_provider=request.preferred_provider,
        images=request.images,
    )
    multi_router.set_user_api_keys(None)
    return result


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "service": "llm",
        "status": "ok",
        "providers": {
            "openai": bool(settings.OPENAI_API_KEY),
            "anthropic": bool(settings.ANTHROPIC_API_KEY),
        },
    }


@router.get("/providers")
async def providers_catalog(http_request: Request):
    """Live provider catalog — pings each API to confirm it's actually up.

    Returns every known provider with:
      - **live** availability (real HTTP ping, not just "key exists")
      - full model list
      - capabilities / strengths from the intelligent router
      - tier, description, default model
      - per-user BYOK status (has_user_key) when x-user-id header present
    """
    import asyncio
    import os
    import httpx
    from .services.intelligent_router import intelligent_router, ProviderTier

    user_id = http_request.headers.get("x-user-id")

    # ── Helpers ──────────────────────────────────────────────────
    # Pings use REAL chat completions (max_tokens=1) to detect quota
    # issues — matching provider_status_ws.py in chat_service.
    # Each returns (live: bool, models: list[str]).
    # Keys may be comma-separated; always split and use the first one.

    def _first_key(raw: str) -> str:
        if not raw:
            return ""
        return raw.split(",")[0].strip()

    # ── Model filters — only show useful chat models ─────────────

    def _filter_openai(model_id: str) -> bool:
        low = model_id.lower()
        # Must start with a known chat prefix
        if not any(low.startswith(p) for p in
                   ("gpt-3.5-turbo", "gpt-4", "gpt-5", "o1", "o3", "o4")):
            return False
        # Skip non-chat variants
        if any(s in low for s in ("audio", "realtime", "transcribe", "tts",
                                   "search", "image", "instruct", "codex",
                                   "safeguard", "-16k")):
            return False
        # Skip date-stamped duplicates: -2024-08-06, -0125, -1106
        import re
        if re.search(r"-\d{4}-\d{2}-\d{2}$", low) or re.search(r"-\d{4}$", low):
            return False
        return True

    def _filter_groq(model_id: str) -> bool:
        low = model_id.lower()
        # Skip non-chat / utility models
        if any(s in low for s in ("whisper", "guard", "prompt-guard",
                                   "orpheus", "allam", "compound",
                                   "openai/gpt-oss")):
            return False
        return True

    def _filter_gemini(model_id: str) -> bool:
        low = model_id.lower()
        if "gemini" not in low:
            return False
        # Skip internal/variant suffixes
        if any(s in low for s in ("-001", "-002", "-exp-", "-lite",
                                   "-image", "-preview", "-thinking",
                                   "computer-use", "embedding")):
            return False
        return True

    def _filter_anthropic(model_id: str) -> bool:
        low = model_id.lower()
        if "claude" not in low:
            return False
        # Skip very old dated models (pre-2025)
        import re
        dated = re.search(r"-(\d{8})$", low)
        if dated and int(dated.group(1)) < 20250101:
            return False
        return True

    # Preferred default model per provider (first match wins)
    _PREFERRED = {
        "groq": ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile"],
        "openai": ["gpt-4o", "gpt-5", "gpt-4o-mini"],
        "anthropic": ["claude-sonnet-4-5", "claude-sonnet-4", "claude-3-5-sonnet"],
        "google": ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"],
    }

    def _pick_default(provider_key: str, models: list) -> str:
        for pref in _PREFERRED.get(provider_key, []):
            # Exact match first
            if pref in models:
                return pref
            # Then prefix match (e.g. "claude-sonnet-4-5" → "claude-sonnet-4-5-20250929")
            for m in models:
                if m.startswith(pref + "-"):
                    return m
        return models[0] if models else ""

    # ── Ping + fetch models per provider ──────────────────────────

    async def _check_openai() -> tuple:
        key = _first_key(settings.OPENAI_API_KEY or "")
        if not key:
            return False, []
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                # Ping with real completion
                pr = await c.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json={"model": "gpt-3.5-turbo",
                          "messages": [{"role": "user", "content": "hi"}],
                          "max_tokens": 1})
                live = pr.status_code == 200
                # Fetch real model list (works even if quota exceeded)
                mr = await c.get("https://api.openai.com/v1/models",
                                 headers={"Authorization": f"Bearer {key}"})
                models = []
                if mr.status_code == 200:
                    models = sorted(
                        {m["id"] for m in mr.json().get("data", [])
                         if _filter_openai(m["id"])},
                        reverse=True)  # newest first (gpt-5 > gpt-4)
                return live, models
        except Exception:
            return False, []

    async def _check_groq() -> tuple:
        key = _first_key(settings.GROQ_API_KEY or "") or \
              _first_key(settings.GROQ_API_KEY_2 or "")
        if not key:
            return False, []
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                pr = await c.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json={"model": "llama-3.3-70b-versatile",
                          "messages": [{"role": "user", "content": "hi"}],
                          "max_tokens": 1})
                live = pr.status_code == 200
                mr = await c.get("https://api.groq.com/openai/v1/models",
                                 headers={"Authorization": f"Bearer {key}"})
                models = []
                if mr.status_code == 200:
                    models = sorted(
                        {m["id"] for m in mr.json().get("data", [])
                         if _filter_groq(m["id"])})
                return live, models
        except Exception:
            return False, []

    async def _check_anthropic() -> tuple:
        key = _first_key(settings.ANTHROPIC_API_KEY or "")
        if not key:
            return False, []
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                pr = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": key,
                             "anthropic-version": "2023-06-01",
                             "Content-Type": "application/json"},
                    json={"model": "claude-3-haiku-20240307",
                          "max_tokens": 1,
                          "messages": [{"role": "user", "content": "hi"}]})
                live = pr.status_code == 200
                # Anthropic has a models endpoint now
                models = []
                try:
                    mr = await c.get(
                        "https://api.anthropic.com/v1/models",
                        headers={"x-api-key": key,
                                 "anthropic-version": "2023-06-01"})
                    if mr.status_code == 200:
                        data = mr.json()
                        model_list = data.get("data", [])
                        models = sorted({m["id"] for m in model_list
                                        if "claude" in m.get("id", "").lower()})
                except Exception:
                    pass
                if models:
                    models = sorted(
                        {m for m in models if _filter_anthropic(m)},
                        reverse=True) or models
                return live, models
        except Exception:
            return False, []

    async def _check_google() -> tuple:
        key = _first_key(settings.GOOGLE_API_KEY or "") or \
              _first_key(settings.GEMINI_API_KEY or "") or \
              _first_key(settings.GEMINI_API_KEY_2 or "")
        if not key:
            return False, []
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                pr = await c.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
                    headers={"Content-Type": "application/json"},
                    json={"contents": [{"parts": [{"text": "hi"}]}],
                          "generationConfig": {"maxOutputTokens": 1}})
                live = pr.status_code == 200
                mr = await c.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={key}")
                models = []
                if mr.status_code == 200:
                    for m in mr.json().get("models", []):
                        name = m.get("name", "")
                        mid = name.replace("models/", "")
                        if "generateContent" in \
                                str(m.get("supportedGenerationMethods", [])) \
                                and _filter_gemini(mid):
                            models.append(mid)
                    models = sorted(set(models), reverse=True)
                return live, models
        except Exception:
            return False, []

    async def _check_ollama() -> tuple:
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get("http://172.19.0.1:11435/api/tags")
                if r.status_code == 200:
                    data = r.json()
                    models = [m.get("name", "") for m in data.get("models", [])
                              if m.get("name")]
                    return True, models
        except Exception:
            pass
        return False, []

    async def _fetch_user_byok_providers() -> set:
        if not user_id:
            return set()
        auth_url = os.getenv("AUTH_SERVICE_URL", "http://green_auth_service:8000")
        internal_key = os.getenv("AUTH_INTERNAL_SERVICE_KEY") or os.getenv("INTERNAL_SERVICE_KEY")
        headers = {"x-user-id": user_id}
        if internal_key:
            headers["x-internal-service-key"] = internal_key
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(
                    f"{auth_url.rstrip('/')}/auth/internal/user-api-keys/{user_id}",
                    headers=headers)
                if r.status_code == 200:
                    return {k["provider"] for k in r.json().get("keys", []) if k.get("api_key")}
        except Exception:
            pass
        return set()

    # ── Run all checks in parallel ────────────────────────────────
    ((live_openai, openai_models),
     (live_groq, groq_models),
     (live_anthropic, anthropic_models),
     (live_google, google_models),
     (local_available, local_models),
     user_byok_providers) = await asyncio.gather(
        _check_openai(),
        _check_groq(),
        _check_anthropic(),
        _check_google(),
        _check_ollama(),
        _fetch_user_byok_providers(),
    )

    # Tier labels for the frontend
    tier_label = {
        ProviderTier.FAST: "fast",
        ProviderTier.BALANCED: "balanced",
        ProviderTier.QUALITY: "quality",
        ProviderTier.PREMIUM: "premium",
    }

    def _caps(key, fallback):
        p = intelligent_router.PROVIDERS.get(key)
        return p.strengths if p else fallback

    def _tier(key, fallback):
        p = intelligent_router.PROVIDERS.get(key)
        return tier_label.get(p.tier, fallback) if p else fallback

    providers = [
        {
            "id": "groq",
            "provider_key": "groq",
            "name": "Groq",
            "available": live_groq or ("groq" in user_byok_providers),
            "live": live_groq,
            "has_system_key": bool(settings.GROQ_API_KEY or settings.GROQ_API_KEY_2),
            "has_user_key": "groq" in user_byok_providers,
            "model": _pick_default("groq", groq_models),
            "models": groq_models,
            "description": "Ultra-fast inference on open-source models",
            "capabilities": _caps("groq", ["speed", "chat"]),
            "tier": _tier("groq", "fast"),
            "uses_credits": True,
            "supports_byok": True,
        },
        {
            "id": "openai",
            "provider_key": "openai",
            "name": "OpenAI",
            "available": live_openai or ("openai" in user_byok_providers),
            "live": live_openai,
            "has_system_key": bool(settings.OPENAI_API_KEY),
            "has_user_key": "openai" in user_byok_providers,
            "model": _pick_default("openai", openai_models),
            "models": openai_models,
            "description": "GPT-4o and family — strong at code, reasoning, creativity",
            "capabilities": _caps("chatgpt", ["code", "reasoning"]),
            "tier": _tier("chatgpt", "quality"),
            "uses_credits": True,
            "supports_byok": True,
        },
        {
            "id": "anthropic",
            "provider_key": "anthropic",
            "name": "Anthropic",
            "available": live_anthropic or ("anthropic" in user_byok_providers),
            "live": live_anthropic,
            "has_system_key": bool(settings.ANTHROPIC_API_KEY),
            "has_user_key": "anthropic" in user_byok_providers,
            "model": _pick_default("anthropic", anthropic_models),
            "models": anthropic_models,
            "description": "Claude — best reasoning, analysis, safety, and long-form",
            "capabilities": _caps("claude", ["reasoning", "analysis"]),
            "tier": _tier("claude", "premium"),
            "uses_credits": True,
            "supports_byok": True,
        },
        {
            "id": "google",
            "provider_key": "google",
            "name": "Gemini",
            "available": live_google or ("google" in user_byok_providers),
            "live": live_google,
            "has_system_key": bool(settings.GOOGLE_API_KEY or settings.GEMINI_API_KEY or settings.GEMINI_API_KEY_2),
            "has_user_key": "google" in user_byok_providers,
            "model": _pick_default("google", google_models),
            "models": google_models,
            "description": "Gemini — fast, multimodal, 1M context window",
            "capabilities": _caps("gemini", ["long_context", "multimodal"]),
            "tier": _tier("gemini", "balanced"),
            "uses_credits": True,
            "supports_byok": True,
        },
        {
            "id": "local",
            "provider_key": "local",
            "name": "Local LLM",
            "available": local_available,
            "live": local_available,
            "has_system_key": False,
            "has_user_key": False,
            "model": local_models[0] if local_models else None,
            "models": local_models,
            "description": "Self-hosted models via Ollama — no API key needed",
            "capabilities": ["speed", "privacy", "offline"],
            "tier": "local",
            "uses_credits": False,
            "supports_byok": False,
        },
    ]

    # Default = first AVAILABLE provider (not hardcoded)
    available_ids = [p["id"] for p in providers if p["available"]]
    first_available = available_ids[0] if available_ids else "groq"

    fallback_chain = list(available_ids)
    fallback_chain_provider_keys = list(available_ids)

    return {
        "providers": providers,
        "default": first_available,
        "fallback_chain": fallback_chain,
        "fallback_chain_provider_keys": fallback_chain_provider_keys,
    }


@router.get("/models")
async def list_models(http_request: Request, provider: Optional[str] = None):
    """List available models by fetching real data from /providers.

    No hardcoded model lists — delegates to providers_catalog which
    pings each API and returns real model lists.
    """
    catalog = await providers_catalog(http_request)
    providers_data = catalog.get("providers", []) if isinstance(catalog, dict) else catalog.body if hasattr(catalog, 'body') else []

    alias_map = {"chatgpt": "openai", "gpt": "openai", "gemini": "google", "claude": "anthropic"}

    if provider:
        normalized = provider.lower()
        key = alias_map.get(normalized, normalized)
        matched = next((p for p in providers_data if p["id"] == key), None)
        models = matched["models"] if matched else []
        return {"models": [{"id": m, "provider": key} for m in models]}

    result = []
    for p in providers_data:
        for m in p.get("models", []):
            result.append({"id": m, "provider": p["id"]})
    return {"models": result}


# ============================================================================
# AI INTENT CLASSIFICATION (for frontend IntentClassifier)
# ============================================================================

from pydantic import BaseModel
from typing import List, Dict, Any
from enum import Enum


class UserIntent(str, Enum):
    CREATE_FILE = "create_file"
    MODIFY_FILE = "modify_file"
    DELETE_FILE = "delete_file"
    RUN_COMMAND = "run_command"
    EXPLAIN_CODE = "explain_code"
    REFACTOR = "refactor"
    DEBUG = "debug"
    SEARCH = "search"
    NAVIGATE = "navigate"
    CHAT = "chat"
    UNKNOWN = "unknown"


class IntentClassificationRequest(BaseModel):
    input: str
    context: Optional[Dict[str, Any]] = None
    prompt: Optional[str] = None


class IntentClassificationResponse(BaseModel):
    intent: str
    confidence: float
    targets: List[str]
    parameters: Dict[str, Any]
    reasoning: Optional[str] = None


@router.post("/ai/classify-intent", response_model=IntentClassificationResponse)
async def classify_intent(
    request: IntentClassificationRequest,
    http_request: Request,
):
    """Classify user intent for IDE operations.
    
    Uses pattern matching first, falls back to LLM for complex cases.
    """
    import re
    
    user_input = request.input.lower()
    context = request.context or {}
    
    # Pattern-based classification (fast path)
    intent_patterns = {
        UserIntent.CREATE_FILE: [
            r'\b(create|add|make|generate|scaffold)\s+(a\s+)?(new\s+)?(file|component|page|function|class|module)',
            r'\bnew\s+(file|component|class)',
        ],
        UserIntent.MODIFY_FILE: [
            r'\b(modify|update|change|edit|fix|refactor|improve)\s+(the\s+)?(code|file|function|class)',
            r'\b(add|insert|append)\s+.+\s+(to|in)\s+',
        ],
        UserIntent.DELETE_FILE: [
            r'\b(delete|remove|drop)\s+(the\s+)?(file|function|class|component)',
        ],
        UserIntent.RUN_COMMAND: [
            r'\b(run|execute|build|test|deploy|install|start|stop)',
            r'\bnpm\s+',
            r'\bpython\s+',
            r'\bgit\s+',
        ],
        UserIntent.EXPLAIN_CODE: [
            r'\b(explain|what\s+is|what\s+does|how\s+does|tell\s+me\s+about|describe)',
            r'\bwhat\s+.+\s+mean',
        ],
        UserIntent.REFACTOR: [
            r'\b(refactor|restructure|reorganize|clean\s*up|optimize)',
            r'\bextract\s+(function|method|component)',
        ],
        UserIntent.DEBUG: [
            r'\b(debug|fix|resolve)\s+(the\s+)?(bug|error|issue|problem)',
            r'\bwhy\s+.+\s+(not\s+working|failing|broken)',
        ],
        UserIntent.SEARCH: [
            r'\b(find|search|locate|where\s+is)',
            r'\bgrep\s+',
        ],
        UserIntent.NAVIGATE: [
            r'\b(go\s+to|open|show|navigate\s+to)',
            r'\bjump\s+to',
        ],
        UserIntent.CHAT: [
            r'\b(hi|hello|hey|thanks|thank\s+you)',
            r'^(yes|no|ok|okay|sure)$',
        ],
    }
    
    # Check patterns
    detected_intent = UserIntent.UNKNOWN
    max_confidence = 0.0
    
    for intent, patterns in intent_patterns.items():
        for pattern in patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                confidence = 0.85  # Pattern match confidence
                if confidence > max_confidence:
                    max_confidence = confidence
                    detected_intent = intent
                break
    
    # Extract targets (file paths, function names, etc.)
    targets = []
    
    # Look for file paths
    file_patterns = [
        r'[\'"]([^\'\"]+\.(py|js|ts|tsx|jsx|json|md|txt|yaml|yml|css|html))[\'"]',
        r'(\S+\.(py|js|ts|tsx|jsx|json|md|txt|yaml|yml|css|html))',
    ]
    for pattern in file_patterns:
        matches = re.findall(pattern, user_input)
        targets.extend([m[0] if isinstance(m, tuple) else m for m in matches])
    
    # Look for function/class names in context
    if context.get("activeFile"):
        targets.append(context["activeFile"].get("path", ""))
    
    # Extract parameters
    parameters = {}
    
    # Look for language specifications
    lang_match = re.search(r'\b(python|javascript|typescript|react|vue|node)', user_input, re.IGNORECASE)
    if lang_match:
        parameters["language"] = lang_match.group(1).lower()
    
    # Look for specific actions
    if detected_intent == UserIntent.RUN_COMMAND:
        cmd_match = re.search(r'(npm|yarn|python|pip|git)\s+(\S+)', user_input)
        if cmd_match:
            parameters["command"] = f"{cmd_match.group(1)} {cmd_match.group(2)}"
    
    # If low confidence and we have LLM available, use it for better classification
    if max_confidence < 0.5 and settings.OPENAI_API_KEY:
        try:
            provider = get_provider("openai")
            classification_prompt = f"""Classify this user request into one of these intents:
- create_file: Creating new files or components
- modify_file: Editing existing code
- delete_file: Removing files
- run_command: Executing terminal commands
- explain_code: Asking for explanations
- refactor: Code restructuring
- debug: Fixing bugs
- search: Finding code
- navigate: Opening files
- chat: General conversation
- unknown: Cannot determine

User request: "{request.input}"

Respond with JSON: {{"intent": "...", "confidence": 0.0-1.0, "reasoning": "..."}}"""
            
            llm_request = ChatCompletionRequest(
                messages=[{"role": "user", "content": classification_prompt}],
                model="gpt-3.5-turbo",
                temperature=0.1,
                max_tokens=200,
            )
            
            response = await provider.chat_completion(llm_request)
            
            # Parse LLM response
            import json
            try:
                llm_result = json.loads(response.choices[0].message.content)
                detected_intent = UserIntent(llm_result.get("intent", "unknown"))
                max_confidence = llm_result.get("confidence", 0.7)
            except:
                pass  # Keep pattern-based result
                
        except Exception as e:
            # Fall back to pattern-based result
            pass
    
    return IntentClassificationResponse(
        intent=detected_intent.value,
        confidence=max_confidence if max_confidence > 0 else 0.5,
        targets=list(set(targets)),  # Deduplicate
        parameters=parameters,
        reasoning=f"Classified based on {'pattern matching' if max_confidence >= 0.5 else 'heuristics'}"
    )
