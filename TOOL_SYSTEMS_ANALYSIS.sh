#!/bin/bash
# ============================================================================
# TOOL SYSTEMS ANALYSIS — Full Platform Audit
# Generated: 2026-04-20
# Platform: DevSwat (dev-swat.com)
# ============================================================================
# This document maps every tool system across all services, identifies
# redundancies, classifies selection methods, and defines the unification path.
# ============================================================================

cat << 'EOF'

================================================================================
                    DEVSWAT TOOL SYSTEMS — COMPLETE ANALYSIS
================================================================================

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1: TOOL INVENTORY BY SERVICE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. RG_Chat (Resonant Chat) — 13 Tools via Neural Classifier               │
├─────────────────────────────────────────────────────────────────────────────┤
│ Tool System:     Own SkillDefinition + SkillClassifier (trained MLP)       │
│ Uses rg_tool_registry: NO                                                  │
│ Selection Method: Trained MLP classifier (all-MiniLM-L6-v2 → MLPClassifier)│
│ Persistence:     PostgreSQL (skill_classifier_models table)                │
│ Active Learning: YES — every prediction saved, model retrains              │
│                                                                             │
│ Key Files:                                                                  │
│   app/services/skills_registry.py    — SkillDefinition + BUILTIN_SKILLS    │
│   app/services/skill_classifier.py   — Neural classifier (384-dim → MLP)   │
│   app/services/skill_executor.py     — HTTP executors for each skill       │
│   app/routers/resonant_chat.py       — Orchestration pipeline              │
│                                                                             │
│ Tools (each = real HTTP executor):                                          │
│   agent_architect    → SSE proxy to RG_agent_architect                     │
│   code_visualizer    → calls RG_AST_analysis                               │
│   web_search         → Tavily search API                                   │
│   image_generation   → DALL-E                                              │
│   memory_search      → RG_Memory service                                   │
│   memory_library     → memory panel                                        │
│   state_physics      → visualization panel                                 │
│   ide_workspace      → IDE panel                                           │
│   rabbit_post        → Rabbit community API                                │
│   google_drive       → OAuth integration                                   │
│   google_calendar    → OAuth integration                                   │
│   figma              → OAuth integration                                   │
│   sigma              → OAuth integration                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. RG_agent_architect — 76+ Tools (Own System + 2 ML Classifiers)          │
├─────────────────────────────────────────────────────────────────────────────┤
│ Tool System:     Own ToolDefinition + ORCHESTRATOR_TOOLS (hardcoded)        │
│ Uses rg_tool_registry: NO                                                  │
│ Selection Method: LLM native function calling (tool_choice)                │
│ ML Models:       AgentTypeClassifier + PromptRouter (both MLP)             │
│ Persistence:     PostgreSQL (ml_models, ml_active_samples tables)          │
│                                                                             │
│ Key Files:                                                                  │
│   src/models/tools.py                — ToolDefinition model                │
│   src/tools/builtin/registry.py      — Tool registry                      │
│   src/orchestrator/orchestrator.py   — ReAct loop with tool_calls          │
│   src/builder/agent_type_classifier.py — Agent type MLP (11 types)         │
│   src/prompts/router.py             — Prompt module MLP (21 binary MLPs)   │
│                                                                             │
│ 13 Builtin Tools:                                                           │
│   web_search, scrape_page, deep_research, stock_market_data, send_email,   │
│   configure_smtp, delete_smtp, build_chart, scrape_platforms,              │
│   google_sheets, create_presentation, documents, generate_media            │
│                                                                             │
│ 28 Orchestrator Tools:                                                      │
│   build_agent, run_agent, modify_agent, delete_agent, set_trigger,         │
│   workspace_snapshot, ask_memory, store_insight, get_credits_info,         │
│   check_integrations, check_credits, get_agent_chain_status, ...           │
│                                                                             │
│ 35 OAuth Service Integrations:                                              │
│   gmail, slack, github, google_drive, discord, figma, notion, ...          │
│                                                                             │
│ Custom API Tools: User-defined via tool builder                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. RG_Agent_Engine — ~70 Tools (rg_tool_registry + local handlers)         │
├─────────────────────────────────────────────────────────────────────────────┤
│ Tool System:     Vendored rg_tool_registry copy + executor handler map     │
│ Uses rg_tool_registry: YES (stale vendored copy)                           │
│ Selection Method: LLM native function calling via rg_tool_registry         │
│ ML Models:       NONE                                                      │
│                                                                             │
│ Key Files:                                                                  │
│   app/executor.py            — Handler map (~70 tool executors)            │
│   app/rg_tool_registry/      — Vendored copy (may be stale)               │
│                                                                             │
│ Tool Categories:                                                            │
│   Search (12): web_search, fetch_url, scrape_page, deep_research,          │
│     news_search, image_search, youtube_search, reddit_search,              │
│     wikipedia, weather, stock_crypto, places_search                        │
│                                                                             │
│   Memory (4): memory_read, memory_write, memory_search, memory_stats       │
│                                                                             │
│   Community/Rabbit (12): post_create, post_list, community_create, ...     │
│                                                                             │
│   Developer (7): http_request, external_http_request, execute_code,        │
│     dev_tool, run_command, get_current_time, send_email                    │
│                                                                             │
│   Media (5): generate_image, generate_audio, generate_music,               │
│     generate_video, generate_chart                                         │
│                                                                             │
│   Integrations (8): gmail_send, gmail_read, slack_send, slack_read,        │
│     figma, google_calendar, google_drive, sigma                            │
│                                                                             │
│   Platform API (3): platform_api, discover_services, discover_api          │
│                                                                             │
│   Tool Management (5): create_tool, list_tools, delete_tool,               │
│     update_tool, auto_build_tool                                           │
│                                                                             │
│   Hash Sphere (5): hash_sphere_search, hash_sphere_anchor,                 │
│     hash_sphere_hash, hash_sphere_list_anchors, hash_sphere_resonance      │
│                                                                             │
│   Session (4): workspace_snapshot, agent_snapshot, run_snapshot,            │
│     present_options                                                         │
│                                                                             │
│ TOKEN COST: ~15,000 tokens per LLM call just for tool schemas              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. RG_Axtention_IDE (Server) — ~50 Tools (Hardcoded Dicts)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ Tool System:     Hardcoded OpenAI-format tool definition dicts             │
│ Uses rg_tool_registry: NO                                                  │
│ Selection Method: LLM native function calling (all tools sent every call)  │
│ ML Models:       NONE                                                      │
│                                                                             │
│ Key Files:                                                                  │
│   app/routers/ide_agent_loop.py  — All tool defs + executors               │
│                                                                             │
│ Core (11): file_read, file_write, file_edit, multi_edit, file_list,        │
│   grep_search, find_by_name, run_command, command_status, file_delete,     │
│   file_move                                                                │
│                                                                             │
│ Git (7): git_status, git_diff, git_log, git_commit, git_push,             │
│   git_pull, git_branch                                                     │
│                                                                             │
│ Web (5): search_web, read_url_content, browser_check, browser_preview,     │
│   read_browser_logs                                                        │
│                                                                             │
│ Code Analysis (17): 15x code_visualizer_* tools +                          │
│   graph_janitor_scan, graph_janitor_scan_github                            │
│                                                                             │
│ Planning/Memory (6): todo_list, ask_user, save_memory, read_memory,        │
│   create_memory, code_search                                               │
│                                                                             │
│ Terminal (6): terminal_create, terminal_send, terminal_read,                │
│   terminal_wait, terminal_list, terminal_close                             │
│                                                                             │
│ Workflows/Sessions (5): list_workflows, run_workflow,                       │
│   trajectory_search, save_checkpoint, load_checkpoint                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. RG_LLM_Service — 5 Tools (rg_tool_registry, minimal)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ Tool System:     Vendored rg_tool_registry copy                            │
│ Uses rg_tool_registry: YES (stale vendored copy)                           │
│ Selection Method: LLM native function calling                              │
│ ML Models:       NONE                                                      │
│                                                                             │
│ Key Files:                                                                  │
│   app/tool_executor.py       — 5 tool handlers                             │
│   app/rg_tool_registry/      — Vendored copy                               │
│                                                                             │
│ Tools: memory_search, memory_read, http_request,                           │
│   get_conversation_context, create_workflow                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 6. RG_Ed_Service — Mixed System (rg_tool_registry + own tools)             │
├─────────────────────────────────────────────────────────────────────────────┤
│ Tool System:     Vendored rg_tool_registry + own app/tools/ system         │
│ Uses rg_tool_registry: PARTIAL (vendored copy + custom extensions)         │
│ Selection Method: LLM native function calling                              │
│ ML Models:       NONE                                                      │
│                                                                             │
│ Key Files:                                                                  │
│   app/rg_tool_registry/      — Vendored copy                               │
│   app/tools/builtin.py       — Own filesystem/code tools                   │
│   app/tools/git_tools.py     — Git operations                              │
│   app/tools/docker_tools.py  — Docker operations                           │
│   app/tools/test_tools.py    — Test runners                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 7. RG_IDE (VS Code Extension) — TypeScript, Client-Side Only               │
├─────────────────────────────────────────────────────────────────────────────┤
│ Tool System:     TypeScript tool definitions + local executors              │
│ Uses rg_tool_registry: NO (different language)                             │
│ Selection Method: LLM picks via function calling (server-side)             │
│ ML Models:       NONE (relies on RG_Axtention_IDE server)                  │
│                                                                             │
│ Key Files:                                                                  │
│   extensions/resonant-ai/src/toolDefinitions.ts  — Tool schemas            │
│   extensions/resonant-ai/src/toolExecutor.ts     — Local executors          │
│   extensions/resonant-ai/src/extension.ts        — Agent stream client      │
└─────────────────────────────────────────────────────────────────────────────┘


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2: TOOL SELECTION METHODS COMPARISON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬────────────────────────────┬────────┬──────────────────┐
│ Service            │ Selection Method           │ ML?    │ Token Cost/Call   │
├────────────────────┼────────────────────────────┼────────┼──────────────────┤
│ RG_Chat            │ Trained MLP classifier     │ YES    │ ~0 (pre-filtered)│
│ RG_agent_architect │ LLM function calling       │ YES*   │ ~6,000 tokens    │
│ RG_Agent_Engine    │ LLM function calling       │ NO     │ ~15,000 tokens   │
│ RG_LLM_Service    │ LLM function calling       │ NO     │ ~1,200 tokens    │
│ RG_Axtention_IDE  │ LLM function calling       │ NO     │ ~10,000 tokens   │
│ RG_Ed_Service     │ LLM function calling       │ NO     │ ~8,000 tokens    │
└────────────────────┴────────────────────────────┴────────┴──────────────────┘
* Agent Architect has ML for prompt routing + agent type, NOT for tool selection

PERFORMANCE ANALYSIS:
  - RG_Chat: ~1-5ms for tool prediction (MLP inference, no network hop)
  - All others: 200-800ms extra per call (LLM processes tool schemas)
  - Token waste: Agent Engine alone burns ~15K tokens/call on tool definitions
  - At scale: ~$2-5/day wasted on tool schema tokens across all services


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 3: THE rg_tool_registry SITUATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CANONICAL PACKAGE: RG_Unified_Tool_Registry-Observability_Module/src/rg_tool_registry/
  Status: Valid installable Python package with pyproject.toml
  Contains: 130+ tool definitions, NativeFCClient, AgenticLoop, observability

PROBLEM: Nobody pip-installs it. Instead, files are copy-pasted into services.

VENDORED COPIES (potentially stale/diverged):
  1. RG_Agent_Engine/app/rg_tool_registry/     — STALE COPY
  2. RG_LLM_Service/app/rg_tool_registry/      — STALE COPY  
  3. RG_Ed_Service/app/rg_tool_registry/        — STALE COPY

SERVICES THAT IGNORE IT ENTIRELY:
  - RG_Chat             (own SkillDefinition system)
  - RG_agent_architect  (own ToolDefinition model)
  - RG_Axtention_IDE   (hardcoded dicts)
  - RG_IDE             (TypeScript, different language)

ROOT CAUSE: Someone vendored the package by copying files, then each copy
drifted independently as developers edited them in-place. Now 3 stale copies
exist that don't match each other OR the canonical source.

CANONICAL PACKAGE CONTENTS:
  registry.py                  — Core ToolRegistry + ToolDef (130+ definitions)
  builtin_tools.py             — All tool definitions with params/categories
  builtin_tools_ide.py         — IDE-specific tool definitions
  native_fc.py                 — NativeFCClient + AgenticLoop (multi-provider LLM FC)
  observability.py             — ToolObserver (metrics, tracing, latency)
  streaming.py                 — SSE streaming helpers
  builder.py                   — Tool builder utilities
  autonomous_tool_builder.py   — Auto-generate tool definitions
  api_catalog.py               — Platform service discovery

KEY INSIGHT: native_fc.py has NativeFCClient (multi-provider LLM function calling)
+ AgenticLoop (full ReAct loop). This was DESIGNED to unify all services' LLM+tool
calling. But every service built its own version instead.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4: TRAINED ML MODELS INVENTORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────────┐
│ MODEL 1: RG_Chat — SkillClassifier                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ Architecture: all-MiniLM-L6-v2 (384-dim) → MLPClassifier (256→128→14)     │
│ Labels: 13 skills + "none" = 14 classes (single-label)                     │
│ Training: 250+ seed samples + active learning from production              │
│ Persistence: PostgreSQL blob (skill_classifier_models table)               │
│ Active Learning: YES — skill_active_samples table, batch flush every 50    │
│ Retrain: skill_classifier.retrain() merges seed + active samples           │
│ Latency: ~1-5ms per prediction                                             │
│ Accuracy: ~93% on seed validation                                          │
│ Purpose: Routes user messages to the correct tool executor                 │
│ Status: PRODUCTION — proven, gets smarter over time                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ MODEL 2: RG_agent_architect — AgentTypeClassifier                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ Architecture: all-MiniLM-L6-v2 (384-dim) → MLPClassifier                  │
│ Labels: 11 agent types (researcher, scraper, monitor, sales, content,      │
│   code, email, data, social, integration, general)                         │
│ Training: 132 seed samples + active learning                               │
│ Persistence: PostgreSQL blob (ml_models table, DigitalOcean managed DB)    │
│ Accuracy: 95.5% on seed validation                                         │
│ Purpose: Auto-selects specialized builder prompts for agent creation       │
│ Status: PRODUCTION                                                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ MODEL 3: RG_agent_architect — PromptRouter (PromptClassifier)              │
├─────────────────────────────────────────────────────────────────────────────┤
│ Architecture: all-MiniLM-L6-v2 (384-dim) → 21 binary MLPClassifiers       │
│ Labels: 21 prompt modules (multi-label, picks top-6 above 0.3 threshold)   │
│ Training: 125 seed samples + active learning                               │
│ Persistence: PostgreSQL blob (ml_models table)                             │
│ Accuracy: 92.7% mean across all binary classifiers                         │
│ Purpose: Selects which prompt modules to inject into system prompt          │
│ Status: PRODUCTION                                                         │
└─────────────────────────────────────────────────────────────────────────────┘

SUMMARY: Only 2 services have trained ML. Only RG_Chat uses ML for TOOL
selection. Agent Architect uses ML for prompt/agent-type routing but lets
the LLM pick tools via function calling.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 5: TOOL OVERLAP & DUPLICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tools implemented in MULTIPLE services (same tool name, different executor):

  web_search:       RG_Chat, RG_agent_architect, RG_Agent_Engine
  memory_search:    RG_Chat, RG_Agent_Engine, RG_LLM_Service
  memory_read:      RG_Agent_Engine, RG_LLM_Service
  image_generation: RG_Chat, RG_Agent_Engine
  generate_image:   RG_agent_architect, RG_Agent_Engine
  google_drive:     RG_Chat, RG_Agent_Engine
  google_calendar:  RG_Chat, RG_Agent_Engine
  figma:            RG_Chat, RG_Agent_Engine
  send_email:       RG_agent_architect, RG_Agent_Engine
  scrape_page:      RG_agent_architect, RG_Agent_Engine
  deep_research:    RG_agent_architect, RG_Agent_Engine
  execute_code:     RG_Agent_Engine, RG_Ed_Service
  http_request:     RG_Agent_Engine, RG_LLM_Service

RISK: Same tool name → different behavior depending on which service handles it.
No single source of truth for "what does web_search actually do."


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 6: ARCHITECTURE PROBLEMS IDENTIFIED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROBLEM 1: NO UNIFIED TOOL SELECTION
  - 6 services, 6 different tool selection implementations
  - Only RG_Chat uses efficient ML-based selection
  - Others waste 8,000-15,000 tokens/call on tool schemas

PROBLEM 2: STALE VENDORED COPIES
  - 3 copies of rg_tool_registry that don't match each other
  - Canonical package exists but nobody installs it
  - Drift means bugs fixed in one copy don't propagate

PROBLEM 3: DUPLICATED TOOLS WITH DIVERGENT BEHAVIOR
  - web_search in 3 services → different APIs, different results
  - memory_search in 3 services → different query patterns
  - No contract guaranteeing consistent behavior

PROBLEM 4: TOKEN WASTE AT SCALE
  - Agent Engine: 70+ tool schemas = ~15,000 tokens/call
  - IDE: ~50 tools = ~10,000 tokens/call
  - Ed Service: ~30 tools = ~8,000 tokens/call
  - Most calls only need 2-3 tools max
  - Estimated waste: $2-5/day, $60-150/month

PROBLEM 5: NO ACTIVE LEARNING EXCEPT RG_Chat
  - Only RG_Chat accumulates prediction data and retrains
  - Other services make the same mistakes forever
  - No feedback loop to improve tool selection accuracy


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 7: WHY RG_CHAT'S APPROACH IS SUPERIOR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RG_Chat's SkillClassifier wins on every metric:

  1. SPEED:     ~1-5ms prediction vs 200-800ms LLM overhead
  2. COST:      ~0 tokens for tool selection vs 8,000-15,000 tokens wasted
  3. ACCURACY:  Pre-trained on domain-specific examples vs LLM guessing
  4. LEARNING:  Gets smarter every day from production predictions
  5. FOCUSED:   LLM only sees relevant context, not 70 tool schemas
  6. RELIABLE:  Deterministic MLP vs LLM hallucinating tool names
  7. OFFLINE:   Works without LLM (model runs locally, no network hop)
  8. SCALABLE:  Same 1-5ms whether you have 13 or 200 tools

The architecture pattern (sentence-transformer → MLP → tool prediction) is
proven in production with 93% accuracy and active learning. It just needs
to be expanded from 13 labels to 130+ and deployed to all services.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 8: UNIFICATION DECISION — EXPAND RG_CHAT'S CLASSIFIER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DECISION: Don't build new. Rename RG_Chat's "skills" → "tools", expand from
13 to 130+ labels using tool definitions from RG_Unified_Tool_Registry,
retrain same MLP model, vendor into all services as shared library.

WHY NOT A MICROSERVICE:
  - Adds network hop latency (~5-20ms)
  - Single point of failure (service down = all tool prediction fails)
  - Extra container to manage
  - RG_Chat's embedded approach (model in process) is already faster & safer

WHY NOT THE CANONICAL rg_tool_registry PACKAGE:
  - Has zero ML dependencies (just httpx)
  - Adding sentence-transformers + sklearn + numpy would bloat it
  - Different release cadence (model retrains weekly, definitions rarely change)
  - Clean separation: registry = WHAT tools exist, neural = WHICH tools to use

APPROACH: Shared library vendored into each service
  - Same pattern as current rg_tool_registry vendoring (but done right)
  - Each service loads model from shared PostgreSQL on startup
  - Runs predictions locally (zero network latency)
  - Active learning samples go to shared DB
  - Periodic retraining incorporates all services' data


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 9: UNIFICATION PHASES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 1: Rename skills → tools in RG_Chat
  - Pure rename, no behavior change
  - skills_registry.py → tools_registry.py
  - skill_classifier.py → tool_classifier.py
  - skill_executor.py → tool_executor.py
  - SkillDefinition → ToolDefinition
  - SkillClassifier → ToolClassifier
  - BUILTIN_SKILLS → BUILTIN_TOOLS
  - DB tables: rename skill_* → tool_*
  - All internal references updated
  - Test: service still works identically after rename

PHASE 2: Expand to 130+ tools, retrain
  - Import tool definitions from unified registry
  - Generate training data (message examples per tool)
  - Multi-label classification (user may need 2-3 tools)
  - Retrain MLP with larger hidden layers if needed
  - Hierarchical option: predict category first, then tool within category
  - Validate accuracy on expanded label set
  - Deploy updated model to RG_Chat first (prove it works)

PHASE 3: Wire RG_Agent_Engine (biggest token savings)
  - Vendor tool_classifier into Agent Engine
  - Before LLM calls: predict top 5-8 tools
  - Send ONLY those tool schemas to LLM (not all 70+)
  - Token savings: ~12,000 tokens/call
  - Active learning: Agent Engine predictions feed shared DB

PHASE 4: Wire remaining services
  - RG_LLM_Service: vendor classifier (5 tools, minimal gain but consistent)
  - RG_Axtention_IDE: vendor classifier (50 tools → top 8, big token savings)
  - RG_Ed_Service: vendor classifier (30 tools → top 5-8)
  - RG_agent_architect: keep LLM FC for orchestrator tools (complex reasoning)
    but add classifier for builtin tool pre-filtering

PHASE 5: Clean up
  - Delete vendored rg_tool_registry copies from all services
  - Delete stale tool definitions that are now in the neural classifier
  - Consolidate duplicated tool executors (one canonical web_search, etc.)
  - Update docker-compose if any services removed


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 10: TOTAL TOOL COUNT — FINAL NUMBERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

UNIQUE TOOLS ACROSS PLATFORM (deduplicated):     ~198
TOOLS IN CANONICAL REGISTRY:                     130+
TRAINED ML MODELS:                               3
SERVICES WITH ML TOOL SELECTION:                 1 (RG_Chat only)
SERVICES USING LLM FC (wasteful):                5
VENDORED COPIES OF rg_tool_registry:             3 (all stale)
ESTIMATED MONTHLY TOKEN WASTE:                   $60-150

POST-UNIFICATION TARGETS:
  - All services use neural tool prediction
  - Token waste reduced by ~80%
  - Single source of truth for tool definitions
  - Shared active learning across all services
  - Model accuracy improves from collective data


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 11: QUICK REFERENCE TABLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬───────┬─────────────────┬────────────┬────────────────┐
│ Service            │ Tools │ Registry        │ Selection  │ ML Model       │
├────────────────────┼───────┼─────────────────┼────────────┼────────────────┤
│ RG_Chat            │  13   │ Own system      │ Neural MLP │ SkillClassifier│
│ RG_agent_architect │  76+  │ Own system      │ LLM FC     │ 2 classifiers* │
│ RG_Agent_Engine    │  70   │ Vendored copy   │ LLM FC     │ None           │
│ RG_Axtention_IDE  │  50   │ Hardcoded       │ LLM FC     │ None           │
│ RG_Ed_Service     │  30   │ Vendored + own  │ LLM FC     │ None           │
│ RG_LLM_Service    │   5   │ Vendored copy   │ LLM FC     │ None           │
│ RG_IDE (client)   │  57   │ TypeScript      │ Via server │ None           │
├────────────────────┼───────┼─────────────────┼────────────┼────────────────┤
│ TOTAL UNIQUE       │ ~198  │ 3 systems       │ 2 methods  │ 3 models       │
└────────────────────┴───────┴─────────────────┴────────────┴────────────────┘
* Agent Architect ML is for prompt/agent-type routing, NOT tool selection

================================================================================
                              END OF ANALYSIS
================================================================================
EOF
