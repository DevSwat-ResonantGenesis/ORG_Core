# LLM Provider Infrastructure — Deep Analysis

**Date:** 2026-03-18  
**Scope:** Every LLM call path across the entire Genesis 2026 platform

---

## Executive Summary

The platform has **3 separate LLM routing engines** and **4 direct-call implementations**, totaling **7 distinct code paths** that call LLM providers. Each was built independently at different times, with different patterns, different BYOK handling, and different fallback logic.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FRONTEND / CLIENTS                              │
├──────────┬──────────┬──────────┬───────────┬───────────────────────┤
│ Resonant │ Streaming│ WebSocket│ Agentic   │ Resonant IDE          │
│ Chat     │ Chat     │ Chat     │ Chat      │ (Local App)           │
│ (web)    │ (web)    │ (web)    │ (web)     │                       │
└────┬─────┴────┬─────┴────┬─────┴─────┬─────┴──────────┬────────────┘
     │          │          │           │                │
     ▼          ▼          ▼           ▼                ▼
┌─────────────────────────┐  ┌─────────────────┐  ┌──────────────────┐
│     GATEWAY (nginx)     │  │    GATEWAY       │  │    GATEWAY       │
│  /api/v1/resonant-chat  │  │ /api/v1/agents-os│  │  /api/v1/ide/*   │
└────┬──────┬─────┬───────┘  └────────┬────────┘  └────────┬─────────┘
     │      │     │                   │                    │
     ▼      ▼     ▼                   ▼                    ▼
┌────────────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│    chat_service        │  │ agent_engine_svc  │  │   chat_service   │
│  (Docker container)    │  │ (Docker container)│  │  ide_completions │
└────────────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## The 3 Routing Engines

### ENGINE 1: `chat_service` — MultiAIRouter (ASYNC)
- **Location:** `chat_service/app/domain/provider/multi_ai_router.py`
- **Type:** Async `httpx.AsyncClient` + `AsyncOpenAI`
- **Providers:** OpenAI, Groq, Anthropic, Gemini
- **Called via:** `facade.py` → `route_query()` / `route_query_stream()`
- **Callers:**
  - `resonant_chat.py` — main chat (fallback after agent spawn fails)
  - `resonant_chat.py` — error correction lambda
  - `resonant_chat.py` — `/internal/route-query` endpoint (for cross-service use)
  - `streaming.py` — streaming chat (via `route_query_stream()`)
  - `streaming.py` — fallback non-streaming path
  - `websocket.py` — WebSocket chat
  - `debate_engine.py` — Agent A, Agent B, Evaluator (3 calls per debate)
  - `agent_engine.py` — in-process agent execution
  - `autonomous_agent_executor.py` — autonomous agent loop
  - `hallucination_detector.py` — judge LLM call
  - `multi_provider_chunking.py` — chunk processing
  - `autonomous_error_correction.py` — error correction
- **BYOK:** Yes — via `set_user_api_keys()` on router instance
- **Intelligent Routing:** Yes — `intelligent_router.py` scores providers by task complexity, cost, speed, quality
- **Fallback Order:** Groq → OpenAI → Anthropic → Gemini (Groq hardcoded first as "only provider with working quota")
- **Models:** Hardcoded per provider (e.g. `llama-3.3-70b-versatile` for Groq)
- **Streaming:** Yes — separate `_stream_groq()`, `_stream_openai()`, `_stream_anthropic()` in `facade.py`

### ENGINE 2: `llm_service` — MultiAIRouter (SYNC)
- **Location:** `llm_service/app/multi_provider/multi_ai_router.py`
- **Type:** **SYNC** `httpx.Client` + sync `OpenAI` (NOT async!)
- **Providers:** OpenAI, Groq, Anthropic, Gemini
- **Exposed at:** `POST /llm/chat/completions`
- **Callers (via HTTP):**
  - ~~`agent_engine_service/app/executor.py`~~ (was — NOW BYPASSED with direct calls)
  - ~~`agent_engine_service/app/planner.py`~~ (was — NOW BYPASSED with direct calls)
  - Any service that calls `http://llm_service:8000/llm/chat/completions`
- **Critical Issues:**
  - **SYNC httpx** blocks the event loop (not async)
  - **Strips parameters:** `response_format`, `temperature`, `tools` are all ignored
  - **Hardcoded Groq first** in fallback order regardless of requested provider
  - **No BYOK forwarding** when called via HTTP (keys don't pass through)
  - **Model is ignored** — always uses the provider's hardcoded default
- **Status:** ⚠️ LEGACY — agent_engine now bypasses it. Still exists as a Docker service.

### ENGINE 3: `chat_service` — ProviderRegistry
- **Location:** `chat_service/app/services/provider_registry.py`
- **Type:** Async `httpx.AsyncClient`
- **Providers:** 11 providers (OpenAI, Anthropic, Google, Groq, Mistral, Together, Perplexity, DeepSeek, Fireworks, OpenRouter, Cohere, Anyscale)
- **Features:** Dynamic provider config, runtime addition, BYOK support, env-based config
- **Status:** 🟡 Built but NOT wired into any active call path. Appears to be a future replacement for MultiAIRouter.

---

## The 4 Direct-Call Implementations

### DIRECT 1: `agent_engine_service/app/routers_agentic_chat.py` — Agentic Chat
- **Type:** Async `httpx.AsyncClient`, direct provider API calls
- **Providers:** OpenAI, Groq, Anthropic, Gemini
- **Features:**
  - Native tool calling (OpenAI format + Anthropic format)
  - JSON mode for structured output
  - SSE streaming to frontend
  - BYOK key fetching from auth service
  - Provider fallback chain
- **Called by:** Frontend "AI Assistant" / Agentic Chat panel
- **Users:** Registered users with auth tokens
- **Models:** `gpt-4o`, `llama-3.3-70b-versatile`, `claude-sonnet-4-20250514`, `gemini-2.0-flash`
- **BYOK:** Yes — fetches from auth service, tries BYOK first

### DIRECT 2: `agent_engine_service/app/executor.py` — Autonomous Agent Executor
- **Type:** Async `httpx.AsyncClient`, direct provider API calls (NEW — just implemented)
- **Providers:** OpenAI, Groq, Anthropic, Gemini
- **Features:**
  - `_call_llm_direct()` — full parameter control (model, temperature, response_format, max_tokens)
  - `_fetch_user_byok_keys()` — BYOK from auth service
  - `_resolve_provider_chain()` — tries BYOK AND system keys per provider
  - JSON response format enforced
  - Token usage tracking
- **Called by:** Autonomous agent loop (`_get_next_action()`)
- **Previously:** Called `llm_service` via HTTP (broken, now bypassed)

### DIRECT 3: `agent_engine_service/app/planner.py` — Agent Planner
- **Type:** Async `httpx.AsyncClient`, direct provider API calls (NEW — just implemented)
- **Providers:** Same as executor (imports config from executor)
- **Features:** `_call_llm_json()` — direct calls with JSON output
- **Called by:** `create_plan()`, `revise_plan()`, `GoalDecomposer.decompose()`
- **Previously:** Called `llm_service` via HTTP (broken, now bypassed)

### DIRECT 4: `chat_service/app/routers/ide_completions.py` — IDE Completions
- **Type:** Async `httpx.AsyncClient`, direct provider API calls
- **Providers:** Groq, OpenAI, Anthropic, Google (Gemini), DeepSeek, Mistral
- **Features:**
  - SSE streaming with tool_calls support
  - OpenAI-compatible format for all providers except Anthropic
  - Anthropic has separate `_stream_anthropic()` handler
  - BYOK key fetching from `user_api_key_service`
  - Provider picker from IDE UI (preferred_provider)
- **Called by:** Resonant IDE local app
- **Users:** Authenticated IDE users
- **Models:** Provider-specific defaults, user can override

### DIRECT 5: `agent_engine_service/app/routers_public_chat.py` — Public/Guest Chat
- **Type:** Async `httpx.AsyncClient`, direct to Groq only
- **Providers:** Groq ONLY (hardcoded)
- **Features:** Rate-limited per IP, no auth required
- **Called by:** Guest/unauthenticated chat widget
- **Models:** `llama-3.3-70b-versatile` (hardcoded)
- **BYOK:** No — uses platform Groq key only

---

## Additional LLM-Adjacent Paths

### Voice (STT/TTS)
- **Location:** `gateway/app/voice_ws.py`
- **Type:** Direct `httpx.AsyncClient` to OpenAI
- **Endpoints:** `api.openai.com/v1/audio/transcriptions` (Whisper), `api.openai.com/v1/audio/speech` (TTS)
- **Not an LLM routing path** — single provider, audio only

### Local LLM (Ollama)
- **Location:** `gateway/app/services/local_llm.py`
- **Type:** Ollama local API → Groq fallback
- **Providers:** Ollama (localhost:11434) → Groq API fallback
- **Status:** Available but rarely used in production

### Embeddings
- **Location:** `memory_service/app/embeddings.py`, `user_memory_service/app/embedding.py`
- **Type:** Nomic Embed v1.5 (local, torch) → OpenAI API fallback → hash fallback
- **Provider:** Local model first, OpenAI `text-embedding-3-small` as fallback
- **Not an LLM chat path** — embedding generation only

### API Key Validation
- **Location:** `gateway/app/user_routes.py`, `llm_service/app/routers.py`
- **Type:** Validation pings to all 4 providers
- **Not an LLM chat path** — tests key validity only

---

## Complete Call-Path Matrix

| Surface | Service | Routing Method | Providers | BYOK | Streaming | Tools |
|---------|---------|---------------|-----------|------|-----------|-------|
| **Resonant Chat** (web) | chat_service | MultiAIRouter (async) via facade | OpenAI, Groq, Anthropic, Gemini | ✅ | Via facade `_stream_*()` | ❌ (agent handles) |
| **Streaming Chat** (web) | chat_service | facade `route_query_stream()` | OpenAI, Groq, Anthropic | ✅ | ✅ SSE | ❌ |
| **WebSocket Chat** | chat_service | MultiAIRouter (async) via facade | OpenAI, Groq, Anthropic, Gemini | ✅ | WebSocket | ❌ |
| **Debate Engine** | chat_service | MultiAIRouter (async) | Groq preferred | ✅ | ❌ | ❌ |
| **Hallucination Judge** | chat_service | MultiAIRouter (async) | Groq (hardcoded) | ❌ | ❌ | ❌ |
| **Agentic Chat** (web) | agent_engine_svc | Direct httpx calls | OpenAI, Groq, Anthropic, Gemini | ✅ | ✅ SSE | ✅ Native |
| **Autonomous Agents** | agent_engine_svc | Direct httpx calls (NEW) | OpenAI, Groq, Anthropic, Gemini | ✅ | ❌ | Via executor tools |
| **Agent Planner** | agent_engine_svc | Direct httpx calls (NEW) | OpenAI, Groq, Anthropic, Gemini | ❌ (system only) | ❌ | ❌ |
| **Public/Guest Chat** | agent_engine_svc | Direct httpx to Groq | Groq ONLY | ❌ | ✅ SSE | ❌ |
| **IDE Completions** | chat_service | Direct httpx calls | Groq, OpenAI, Anthropic, Gemini, DeepSeek, Mistral | ✅ | ✅ SSE | ✅ Native |
| **Voice STT/TTS** | gateway | Direct httpx to OpenAI | OpenAI only | ❌ | ❌ | ❌ |
| **Local LLM** | gateway | Ollama → Groq fallback | Ollama, Groq | ❌ | ❌ | ❌ |
| **`/llm/chat/completions`** | llm_service | MultiAIRouter (SYNC) | OpenAI, Groq, Anthropic, Gemini | Partial | ❌ | ❌ |

---

## BYOK Key Flow Map

```
User saves API key in Settings
         │
         ▼
┌─────────────────────────┐
│  auth_service DB        │
│  user_api_keys table    │
└────┬────────────────────┘
     │
     │ Fetched at request time via:
     │
     ├──→ chat_service: resonant_chat.py fetches from auth_service
     │    → passes to MultiAIRouter via set_user_api_keys()
     │    → also passes to facade.route_query(user_api_keys=...)
     │
     ├──→ agent_engine_svc: routers_agentic_chat.py fetches from auth_service
     │    → uses directly in httpx calls (BYOK first, system fallback)
     │
     ├──→ agent_engine_svc: executor.py _fetch_user_byok_keys()
     │    → fetches from http://auth_service:8000 at session start
     │    → cached for all steps in session
     │    → passed through _resolve_provider_chain() (BYOK → system per provider)
     │
     ├──→ chat_service: ide_completions.py
     │    → uses user_api_key_service.get_provider_key()
     │    → BYOK checked first, then server env key
     │
     └──→ llm_service: routers.py
          → accepts user_api_keys in request body
          → passes to SYNC MultiAIRouter (but params get stripped)
```

---

## Key Problems Identified

### 1. THREE separate MultiAIRouter implementations
- `chat_service/app/domain/provider/multi_ai_router.py` — **ASYNC**, actively used
- `llm_service/app/multi_provider/multi_ai_router.py` — **SYNC**, legacy, broken
- Both have nearly identical code but diverged over time

### 2. llm_service is essentially dead weight
- Its only unique value was the `/llm/chat/completions` HTTP endpoint
- Agent engine was the main caller — now bypasses it with direct calls
- Still runs as a Docker container consuming resources
- Its SYNC `httpx.Client` blocks the event loop

### 3. No unified provider abstraction
Each direct-call implementation maintains its own:
- Provider URL constants
- Model defaults
- Fallback order
- BYOK resolution
- Anthropic-specific handling (different API format)
- Gemini-specific handling (different API format)

### 4. Hardcoded models everywhere
| Location | Groq Model | OpenAI Model | Anthropic Model |
|----------|-----------|--------------|-----------------|
| chat_service MultiAIRouter | `llama-3.3-70b-versatile` | via OpenAI SDK | `claude-3-haiku-20240307` |
| llm_service MultiAIRouter | `llama-3.3-70b-versatile` | via OpenAI SDK | same |
| agentic_chat.py | `llama-3.3-70b-versatile` | `gpt-4o` | `claude-sonnet-4-20250514` |
| executor.py | `llama-3.3-70b-versatile` | `gpt-4o` | `claude-sonnet-4-20250514` |
| ide_completions.py | `llama-3.3-70b-versatile` | `gpt-4o` | `claude-sonnet-4-20250514` |
| public_chat.py | `llama-3.3-70b-versatile` | N/A | N/A |
| facade.py streaming | `llama-3.3-70b-versatile` | `gpt-4o-mini` | `claude-3-haiku-20240307` |

### 5. Inconsistent Groq-first bias
The `chat_service` MultiAIRouter and `llm_service` both hardcode Groq as the first fallback ("only provider with working quota"). This was a workaround for expired OpenAI keys but is now baked into the architecture.

---

## Architectural Critique — Each Path Explained

### ENGINE 1: chat_service MultiAIRouter (ASYNC)

**Why it exists:**  
This was the original "brain" of Resonant Chat. When the platform started, there was only one product — the chat page. This router was built to handle provider selection, BYOK, and fallback for that single surface. Over time, every new chat feature (streaming, websocket, debate, hallucination checking, error correction) was plugged into the same router because it was already there.

**What's GOOD:**
- ✅ **Async** — doesn't block the event loop, proper for a high-concurrency web service
- ✅ **BYOK support** — `set_user_api_keys()` correctly prioritizes user keys over system keys
- ✅ **Intelligent routing** — `_select_provider()` uses task complexity analysis to pick the optimal provider (cost vs quality vs speed)
- ✅ **Facade pattern** — callers use `route_query()` from `facade.py`, not the router directly. Clean separation.
- ✅ **Vision support** — images can be passed to OpenAI and Gemini
- ✅ **Fallback chain with metadata** — tracks which providers were tried and whether fallback occurred

**What's WRONG:**
- ❌ **Groq-first hardcoded bias** — line 161: `"groq" not in available_providers and has_groq: available_providers.append("groq")` is always first in fallback. This was a temporary workaround ("only provider with working quota") that became permanent. Groq is fast but low quality compared to Claude/GPT-4o for complex tasks.
- ❌ **Models hardcoded per provider** — Groq always uses `llama-3.3-70b-versatile`, OpenAI uses whatever the SDK defaults to. Users can't pick models.
- ❌ **No tool calling support** — the router returns plain text only. This is why agentic chat had to be built separately.
- ❌ **No JSON mode** — no `response_format` parameter. Agents need structured JSON output but this router can't provide it.
- ❌ **Streaming is in facade, not router** — `facade.py` has completely separate `_stream_groq()`, `_stream_openai()`, `_stream_anthropic()` functions that duplicate all the provider-specific logic. Two places to update when anything changes.
- ❌ **Shared mutable state** — `set_user_api_keys()` mutates the router instance. If two concurrent requests hit the same instance, one user's BYOK keys could leak to another. The facade mitigates this by creating fresh instances per request, but `_internal_router` is still shared.
- ❌ **Anthropic model outdated** — still uses `claude-3-haiku-20240307` while newer paths use `claude-sonnet-4-20250514`

**VERDICT: 🟡 Works fine for basic chat. Cannot support agents, tools, or structured output. Keep for Resonant Chat only.**

---

### ENGINE 2: llm_service MultiAIRouter (SYNC)

**Why it exists:**  
This was built as a centralized "LLM gateway" — the idea was that every service (chat, agents, memory, etc.) would call one HTTP endpoint (`/llm/chat/completions`) instead of each making their own provider calls. Good idea in theory.

**What's GOOD:**
- ✅ **Single endpoint** — one HTTP API that any service can call without importing provider code
- ✅ **OpenAI-compatible API format** — callers send standard chat completion requests
- ✅ **Provider health checking** — `/llm/providers/status` endpoint pings all providers

**What's WRONG:**
- ❌ **SYNC httpx.Client** — this is the #1 killer. Every LLM call (which takes 2-30 seconds) **blocks the entire event loop**. In a FastAPI app, this means ONE slow Anthropic call blocks ALL other requests to the service. This alone makes it unusable at scale.
- ❌ **Strips critical parameters** — when `executor.py` sent `response_format: {"type": "json_object"}`, `temperature: 0.3`, `model: "gpt-4o"` — the llm_service ignored ALL of them. It used its own hardcoded model, default temperature, and no response_format. The agent engine literally could not control what model or format was used.
- ❌ **HTTP overhead for internal calls** — agent_engine makes 5-50 LLM calls per agent session. Each one was: serialize → HTTP → deserialize → route → provider call → serialize → HTTP → deserialize. Adds 50-200ms latency per call for zero benefit.
- ❌ **BYOK keys don't survive the HTTP hop** — even though `user_api_keys` is in the request schema, the routing logic inside the llm_service often ignores them or uses them incorrectly (calls `set_user_api_keys()` on a shared instance → race condition).
- ❌ **No streaming support** — the `/chat/completions` endpoint returns full responses only. A separate `/chat/completions/stream` endpoint exists but has different bugs.
- ❌ **No tool calling** — the request schema doesn't even have a `tools` field.
- ❌ **Duplicate code** — its MultiAIRouter is a copy-paste of chat_service's MultiAIRouter, now diverged. Bug fixes in one don't propagate to the other.

**VERDICT: 🔴 BROKEN. Should be RETIRED. No active callers remain after our executor/planner fix. Consuming Docker resources for nothing.**

---

### ENGINE 3: ProviderRegistry

**Why it exists:**  
Someone (likely an agent) built this as a forward-looking replacement for MultiAIRouter. It supports 11 providers via a clean `ProviderConfig` dataclass, allows runtime addition of new providers, and has BYOK built in.

**What's GOOD:**
- ✅ **Clean architecture** — `ProviderConfig` dataclass with all provider metadata (URL, models, API type, vision support, headers)
- ✅ **11 providers out of the box** — OpenAI, Anthropic, Google, Groq, Mistral, Together, Perplexity, DeepSeek, Fireworks, OpenRouter, Cohere, Anyscale
- ✅ **Dynamic config** — providers can be added via `PROVIDER_CONFIG_JSON` env var or `add_provider()` at runtime
- ✅ **API type abstraction** — `ProviderType` enum (OPENAI_COMPATIBLE, ANTHROPIC, GOOGLE, CUSTOM) handles format differences cleanly
- ✅ **Async calls** — uses `httpx.AsyncClient`
- ✅ **BYOK** — `get_api_key()` checks user keys first, then env keys

**What's WRONG:**
- ❌ **NOT WIRED IN** — nothing calls it. It's dead code sitting in `provider_registry.py`. No router, no service, no endpoint uses it.
- ❌ **No streaming** — `call_provider()` returns full response only
- ❌ **No tool calling** — doesn't pass `tools` or handle `tool_calls` in responses
- ❌ **No JSON mode** — doesn't support `response_format`
- ❌ **No fallback chain** — `call_provider()` calls exactly one provider, no fallback
- ❌ **No intelligent routing** — no task analysis, just calls what you ask for
- ❌ **Outdated models** — lists `claude-3-haiku-20240307`, `gemini-1.5-flash` — months behind

**VERDICT: 🟡 Great SKELETON but incomplete. Needs streaming, tools, JSON mode, and fallback to be production-ready. Best candidate as the foundation for a unified client.**

---

### DIRECT 1: Agentic Chat (`routers_agentic_chat.py`)

**Why it exists:**  
The Agentic Chat (AI Assistant) needs **native tool calling** — the LLM must return `tool_calls` in its response, the frontend executes them, and results loop back. Neither MultiAIRouter nor llm_service supports tool calling. So this was built from scratch with direct API calls.

**What's GOOD:**
- ✅ **Native tool calling** — full OpenAI-format `tools` parameter + Anthropic tool format
- ✅ **Multi-loop execution** — LLM can call multiple tools across multiple loops
- ✅ **SSE streaming** — streams text chunks AND tool_calls to frontend in real-time
- ✅ **BYOK** — fetches user keys from auth service, tries them first
- ✅ **Provider fallback** — if preferred provider fails, tries next in chain
- ✅ **JSON mode** — `_call_llm_json_mode()` for structured output
- ✅ **Tool limiting for Groq** — `_limit_tools_for_groq()` reduces tool count since Groq has lower tool limits

**What's WRONG:**
- ❌ **~5800 lines in one file** — `routers_agentic_chat.py` is massive. Mixing HTTP routing, LLM calling, tool definitions, skill registry, conversation management all in one file.
- ❌ **Duplicates all provider logic** — has its own `PROVIDER_URLS`, `PROVIDER_MODELS`, `PROVIDER_KEYS`, `_call_llm_with_tools()`. All copy-paste from ide_completions and executor.
- ❌ **BYOK + system key fallback is incomplete** — `_resolve_provider()` returns one key per provider (BYOK OR system, not both). If BYOK fails, system key for SAME provider is skipped (same bug we just fixed in executor).
- ❌ **No per-provider BYOK+system dual try** — exact same bug as executor had before our fix
- ❌ **Hardcoded conversation summary uses Groq** — line ~128: summary always goes to Groq regardless of user preference

**VERDICT: 🟢 Architecturally CORRECT for its purpose (tool calling needs direct calls). But needs the BYOK dual-key fix and should extract shared LLM client code.**

---

### DIRECT 2: Autonomous Agent Executor (`executor.py`)

**Why it exists:**  
Autonomous agents run multi-step loops: plan → decide action → execute tool → observe → repeat. Each step needs an LLM call with **JSON response format** (structured action output), **specific model/temperature**, and **BYOK keys**. The old llm_service stripped all these parameters, so agents always got wrong model + unstructured text = broken.

**What's GOOD:**
- ✅ **Full parameter control** — model, temperature, max_tokens, response_format all forwarded correctly
- ✅ **JSON mode enforced** — agents get structured `{"action": "...", "tool": "...", "parameters": {...}}` output
- ✅ **BYOK dual-key resolution** (AFTER our fix) — tries BYOK key first, then system key, for EACH provider
- ✅ **Token tracking** — logs tokens used per step for billing
- ✅ **Provider chain** — respects agent's configured provider, falls back to others

**What's WRONG:**
- ❌ **Duplicates provider logic** — has its own `DIRECT_PROVIDER_URLS`, `DIRECT_PROVIDER_KEYS`, `DIRECT_PROVIDER_MODELS`, `_call_llm_direct()`. Same code as agentic_chat and ide_completions.
- ❌ **No streaming** — agents don't stream intermediate LLM output to the user. Long steps appear "stuck."
- ❌ **Keys fetched once at session start** — if a key expires mid-session (unlikely but possible), it won't refresh

**VERDICT: 🟢 Architecturally CORRECT. The direct-call approach was the RIGHT fix. Shares duplicate code with other direct implementations.**

---

### DIRECT 3: Agent Planner (`planner.py`)

**Why it exists:**  
The planner decomposes goals into steps before the executor runs them. It needs LLM calls with JSON output. Was calling llm_service (broken), now calls providers directly.

**What's GOOD:**
- ✅ **Imports config from executor** — doesn't duplicate constants (reuses `DIRECT_PROVIDER_KEYS`, etc.)
- ✅ **JSON extraction with regex fallback** — if LLM doesn't return clean JSON, tries to extract it with regex
- ✅ **Graceful degradation** — if planning fails, returns a single-step plan with the original goal

**What's WRONG:**
- ❌ **No BYOK** — uses system keys only (doesn't receive user_keys)
- ❌ **Separate `_call_llm_json()` method** — duplicates the provider call loop from executor's `_call_llm_direct()`
- ❌ **No streaming** — blocking call for what can be a 5-10 second planning step

**VERDICT: 🟡 Functional but should use executor's `_call_llm_direct()` instead of its own copy. Should receive BYOK keys.**

---

### DIRECT 4: IDE Completions (`ide_completions.py`)

**Why it exists:**  
The Resonant IDE (local Electron app) needs a Cascade-like experience: LLM returns tool_calls, the IDE executes them locally (file read/write, grep, run command), results loop back. This is fundamentally different from web chat because tools run on the USER'S MACHINE, not server-side. The server just proxies LLM calls.

**What's GOOD:**
- ✅ **Cleanest implementation** — ~500 lines, single responsibility, well-structured
- ✅ **Most providers** — 6 providers including DeepSeek and Mistral (more than any other path)
- ✅ **Full tool calling** — native OpenAI-format + separate Anthropic handler
- ✅ **SSE streaming** — chunks, tool_calls, done, error events
- ✅ **BYOK via user_api_key_service** — clean integration, checked first
- ✅ **No tool execution** — correctly delegates all tool execution to the client. Server is pure LLM proxy.
- ✅ **response_format support** — passes through to provider

**What's WRONG:**
- ❌ **Duplicates provider call logic** — `_stream_openai_compatible()` and `_stream_anthropic()` are yet another copy of the same pattern
- ❌ **No fallback chain** — if preferred provider fails, returns error instead of trying next provider
- ❌ **Single BYOK attempt** — if BYOK key is expired, falls through to server key but doesn't try BYOK for other providers

**VERDICT: 🟢 Best-designed implementation. Clean, focused, correct. Should be the TEMPLATE for unifying all other paths.**

---

### DIRECT 5: Public/Guest Chat (`routers_public_chat.py`)

**Why it exists:**  
Guests (unauthenticated visitors) need a basic chat to experience the platform before signing up. Can't use BYOK (no account), can't use expensive models (no billing), must be rate-limited to prevent abuse.

**What's GOOD:**
- ✅ **Single provider (Groq)** — cheapest/fastest, perfect for guest demo
- ✅ **Rate limiting** — per-IP limits prevent abuse
- ✅ **No auth required** — accessible to anyone
- ✅ **SSE streaming** — responsive UX even for guests
- ✅ **Simple** — minimal code, minimal attack surface

**What's WRONG:**
- ❌ **Zero fallback** — if Groq is down, guests get nothing. Should at least try Gemini (also free-tier friendly).
- ❌ **Hardcoded everything** — model, provider, API URL all hardcoded. If Groq deprecates the model, requires code change.
- ❌ **No conversation memory** — each message is independent, no context window

**VERDICT: 🟢 Architecturally CORRECT for its purpose. Simple by design. Just add a Gemini fallback.**

---

## Summary Scorecard

| Path | Architecture | BYOK | Streaming | Tools | JSON Mode | Should Keep? |
|------|-------------|------|-----------|-------|-----------|-------------|
| **chat_service MultiAIRouter** | 🟡 Good for chat | ✅ | ✅ | ❌ | ❌ | ✅ For basic chat only |
| **llm_service MultiAIRouter** | 🔴 Broken | ❌ | ❌ | ❌ | ❌ | ❌ **RETIRE** |
| **ProviderRegistry** | 🟡 Skeleton | ✅ | ❌ | ❌ | ❌ | 🔄 Finish & use as foundation |
| **Agentic Chat** | 🟢 Correct | ✅ | ✅ | ✅ | ✅ | ✅ Fix BYOK dual-key |
| **Executor** | 🟢 Correct | ✅ | ❌ | ✅ | ✅ | ✅ Already fixed |
| **Planner** | 🟡 Works | ❌ | ❌ | ❌ | ✅ | ✅ Wire BYOK |
| **IDE Completions** | 🟢 Best design | ✅ | ✅ | ✅ | ✅ | ✅ Add fallback chain |
| **Public Chat** | 🟢 Correct | N/A | ✅ | ❌ | ❌ | ✅ Add Gemini fallback |

### The Core Problem

**Every path that needs tools, JSON mode, or streaming had to build its own direct-call implementation** because neither MultiAIRouter (Engine 1) nor llm_service (Engine 2) supports these features. This is why you ended up with 5 separate direct-call implementations that all do the same thing slightly differently.

### The Ideal Architecture

```
┌──────────────────────────────────────────────────────────┐
│                 UnifiedLLMClient                          │
│                                                          │
│  • All providers (OpenAI, Groq, Anthropic, Gemini, ...)  │
│  • Streaming + non-streaming                             │
│  • Native tool calling (OpenAI + Anthropic format)       │
│  • JSON mode (response_format)                           │
│  • BYOK dual-key (BYOK first → system fallback)          │
│  • Provider fallback chain                               │
│  • Token tracking + billing hooks                        │
│  • Async httpx only                                      │
│  • Single source of truth for models + URLs              │
│                                                          │
│  Used by: resonant_chat, agentic_chat, executor,         │
│           planner, ide_completions, public_chat,          │
│           debate_engine, hallucination_detector           │
└──────────────────────────────────────────────────────────┘
```

One client. Every surface imports it. No duplication. No divergence.

---

## Recommendations

### Short-term (no breaking changes)
1. **Retire `llm_service`** — nothing actively calls it anymore. Remove the Docker container to save resources.
2. **Update expired OpenAI key** — currently 401 on production, forcing all fallbacks to Groq.
3. **Centralize model constants** — create a shared `provider_config.py` imported by all services.

### Medium-term (architectural)
4. **Unify direct-call implementations** — extract a shared `LLMClient` class that handles all 4 providers with BYOK, fallback, streaming, tools, JSON mode. Use it in executor, planner, agentic_chat, ide_completions.
5. **Wire in ProviderRegistry** — `provider_registry.py` already supports 11 providers dynamically. Replace the hardcoded configs with it.
6. **Remove MultiAIRouter from chat_service** — replace with the unified client.

### Long-term (platform)
7. **Single LLM gateway service** — one service that ALL others call, with proper async, full parameter forwarding, BYOK, streaming, tools. Essentially what `llm_service` was supposed to be but done right.
8. **Admin dashboard** — show which providers are active, key health, usage per provider, cost tracking.

---

## Service-to-Service Dependency Graph

```
                    ┌──────────────┐
                    │   Frontend   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   Gateway    │
                    │   (nginx +   │
                    │   FastAPI)   │
                    └──┬───┬───┬───┘
                       │   │   │
          ┌────────────┘   │   └─────────────┐
          ▼                ▼                  ▼
┌─────────────────┐ ┌──────────────┐ ┌───────────────┐
│  chat_service   │ │ agent_engine │ │ Other services │
│                 │ │   _service   │ │ (memory, auth, │
│ • resonant_chat │ │              │ │  billing, etc) │
│ • streaming     │ │ • agentic    │ └───────────────┘
│ • websocket     │ │   chat       │
│ • ide_complete  │ │ • executor   │
│ • debate_engine │ │ • planner    │
│ • hallucination │ │ • public_chat│
│ • agent_engine  │ └──────────────┘
│ • chunking      │        │
│ • error_correct │        │ (bypassed)
└────────┬────────┘        │
         │                 ▼
         │          ┌──────────────┐
         │          │ llm_service  │ ← LEGACY, no active callers
         │          │ (SYNC httpx) │
         │          └──────────────┘
         │
    ┌────▼────────────────────────────────┐
    │         LLM PROVIDERS               │
    │                                     │
    │  OpenAI   Groq   Anthropic  Gemini  │
    │  DeepSeek Mistral  (IDE only)       │
    └─────────────────────────────────────┘
```

---

*Generated by deep infrastructure trace of all `.py` files containing LLM provider API calls across genesis2026_production_backend.*
