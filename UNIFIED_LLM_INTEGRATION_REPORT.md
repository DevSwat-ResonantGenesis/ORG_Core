# Unified LLM Client — Integration Report

**Date:** 2026-03-15  
**Repo:** `RG_UnifiedLLMClient` → `shared_libs/rg_llm`  
**Scope:** 7 files across 2 services wired to `UnifiedLLMClient`

---

## Summary

Replaced **8 separate direct-call LLM implementations** across the backend with a single `UnifiedLLMClient` from `rg_llm`. Total net code reduction: **~600 lines removed**, replaced with ~120 lines of unified client calls.

---

## Files Modified

### 1. `agent_engine_service/app/executor.py`
- **Replaced:** `_call_llm_direct()`, `_resolve_provider_chain()`, 4 provider constants dicts
- **With:** `_llm_client.complete(LLMRequest(...))` in `_get_next_action()`
- **BYOK:** `_fetch_user_byok_keys()` preserved, passed as `byok_fetcher` to client
- **Impact:** ~166 lines → ~83 lines

### 2. `agent_engine_service/app/planner.py`
- **Replaced:** `_call_llm_json()` — 52-line function with 4 provider branches (OpenAI, Groq, Anthropic, Gemini)
- **With:** 14-line function using `_llm_client.complete()` with `response_format={"type": "json_object"}`
- **Import:** Lazy import from `executor._llm_client` and `LLMRequest`

### 3. `agent_engine_service/app/routers_agentic_chat.py`
- **Replaced:** Hardcoded provider constants (GROQ_API_KEY, OPENAI_API_KEY, etc.) → derived from `rg_llm.providers.BUILTIN_PROVIDERS`
- **Replaced:** `_call_llm_json_mode()` (55-line direct Groq call) → 15-line `_llm_client.complete()` call
- **Kept:** `_call_llm_with_tools()` — 360-line function with complex Anthropic/Gemini tool message formatting retained, but now sources URLs/keys from rg_llm
- **Rationale:** The tool-calling loop's Anthropic message conversion (OpenAI tool_calls → tool_use blocks, role merging) is too intertwined to safely abstract yet

### 4. `agent_engine_service/app/routers_public_chat.py`
- **Replaced:** Direct `httpx.AsyncClient.post()` to Groq API in the tool-calling loop
- **With:** `_llm_client.complete(LLMRequest(provider="groq", ...))` 
- **Impact:** Eliminated raw HTTP call, JSON mode still used for prompt-based tool calling

### 5. `chat_service/app/routers/ide_completions.py`
- **Replaced:** `PROVIDER_CONFIGS`, `_get_provider_config()`, `_stream_openai_compatible()`, `_convert_messages_for_anthropic()`, `_stream_anthropic()` — 370+ lines of streaming code
- **With:** `_llm_client.stream(LLMRequest(...))` + SSE event conversion (40 lines)
- **BYOK:** `_get_user_keys()` fetches BYOK via `user_api_key_service`, passed as `user_keys`
- **Impact:** 501 → 134 lines (**73% reduction**)

### 6. `chat_service/app/domain/provider/facade.py`
- **Replaced:** `route_query()` (via `MultiAIRouter`), `route_query_stream()` + `_stream_groq()`, `_stream_openai()`, `_stream_anthropic()` — all direct httpx streaming functions
- **With:** `_llm_client.complete()` for non-streaming, `_llm_client.stream()` for streaming
- **Kept:** `_stream_local()` (local LLM tunnel via gateway — special case, not an API provider)
- **Kept:** `MultiAIRouter` instance for `get_router_for_internal_use()` backward compat
- **Impact:** 345 → 185 lines (**46% reduction**)
- **Callers unchanged:** `resonant_chat.py`, `streaming.py`, `websocket.py`, `debate_engine.py`, `hallucination_detector.py`, `autonomous_error_correction.py`, `multi_provider_chunking.py` — all use `route_query()` / `route_query_stream()` with same signatures

### 7. `docker-compose.unified.yml`
- **Added:** `./shared_libs/rg_llm:/app/rg_llm:ro` volume mount to `chat_service` and `agent_engine_service`
- **PYTHONPATH:** Already set to `/app` so `import rg_llm` resolves

---

## What's NOT Migrated (and Why)

| Component | Reason |
|---|---|
| `_call_llm_with_tools()` in agentic_chat | Complex multi-turn tool conversation formatting per provider (Anthropic role merging, Gemini functionResponse). Needs client enhancement for tool-conversation support. |
| `multi_ai_router.py` in llm_service | Kept as legacy fallback. Used only by `get_router_for_internal_use()` in facade. |
| `gateway/app/voice_ws.py` | OpenAI audio endpoints (STT/TTS) — not general LLM calls |
| `gateway/app/services/local_llm.py` | Local Ollama/LM Studio — special tunnel, not API provider |
| `memory_service/app/embeddings.py` | Embedding calls (Nomic/OpenAI) — different API shape |
| `gateway/app/user_routes.py` | API key validation pings — not LLM completions |

---

## Architecture After Migration

```
┌─────────────────────────────────────────────────────┐
│                   rg_llm (shared_libs)              │
│  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌─────────┐  │
│  │ client.py│ │models.py │ │keys.py │ │providers│  │
│  │ complete │ │LLMRequest│ │BYOK    │ │12 provs │  │
│  │ stream   │ │LLMResp   │ │resolve │ │URLs/keys│  │
│  └────┬─────┘ └──────────┘ └────────┘ └─────────┘  │
│       │                                              │
└───────┼──────────────────────────────────────────────┘
        │
        ├── executor.py          (_llm_client.complete)
        ├── planner.py           (imports from executor)
        ├── routers_agentic_chat (_llm_client for JSON mode + provider configs)
        ├── routers_public_chat  (_llm_client.complete for Groq)
        ├── ide_completions.py   (_llm_client.stream)
        └── facade.py            (_llm_client.complete + .stream)
              │
              ├── resonant_chat.py      (unchanged — calls facade)
              ├── streaming.py          (unchanged — calls facade)
              ├── debate_engine.py      (unchanged — calls facade)
              ├── hallucination_det.py  (unchanged — calls facade)
              └── error_correction.py   (unchanged — calls facade)
```

---

## Key Benefits Achieved

1. **Single source of truth** for provider URLs, models, and API keys (`rg_llm.providers`)
2. **BYOK dual-key resolution** everywhere (user key → system key per provider)
3. **Provider fallback chains** with attempt tracking and token usage
4. **JSON mode** handled uniformly via `response_format` parameter
5. **Streaming** unified — no more separate `_stream_groq` / `_stream_openai` / `_stream_anthropic`
6. **~600 lines of duplicated provider-specific HTTP code eliminated**

---

## Deployment Notes

- `shared_libs/rg_llm/` is mounted read-only into containers
- No new pip dependencies — `rg_llm` only requires `httpx` (already in all services)
- All function signatures preserved — no downstream code changes needed
- `PYTHONPATH=/app` already set in docker-compose for both services
