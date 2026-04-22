#!/bin/bash
# ============================================================================
# PLAN: Neural Tools Unification
# ============================================================================
# 
# GOAL: Expand RG_Chat's proven neural SkillClassifier into a unified
#       ToolClassifier that covers ALL 130+ platform tools, then wire
#       every service to use it. Eventually delete redundant tool systems.
#
# PRINCIPLE: Don't build new. Rename + expand what already works.
#
# RG_Chat's SkillClassifier = best performing system in production.
# It's actually a tool classifier, just mislabeled as "skills."
#
# ============================================================================
# CURRENT STATE (Apr 19, 2026)
# ============================================================================
#
# Service              | Tools | Selection Method                  | Neural?
# ---------------------|-------|-----------------------------------|--------
# RG_Chat              | 13    | Trained MLP (all-MiniLM-L6-v2)   | YES
# RG_agent_architect   | 28    | LLM function calling              | YES (type+prompt classifiers)
# RG_Agent_Engine      | ~70   | LLM function calling (registry)   | NO
# RG_LLM_Service       | 5     | LLM function calling (registry)   | NO
# RG_Axtention_IDE     | ~50   | LLM function calling (hardcoded)  | NO
# RG_Ed_Service        | ~30   | LLM function calling (registry)   | NO
#
# RG_Unified_Tool_Registry = 130+ tool definitions (nobody wires to it)
# RG_Chat SkillClassifier = only neural model, mislabeled as "skills"
#
# ============================================================================
# PHASE 1: RENAME skills → tools IN RG_CHAT
# ============================================================================
# 
# No logic changes. Pure rename. Everything still works the same.
#
# TODO 1.1: Rename files
#   [ ] app/services/skill_classifier.py    → app/services/tool_classifier.py
#   [ ] app/services/skill_executor.py      → app/services/tool_executor.py
#   [ ] app/services/skill_training_data.py → app/services/tool_training_data.py
#   [ ] app/services/skill_classifier.py    → app/services/tool_classifier.py
#   [ ] app/services/skills_registry.py     → app/services/tools_registry.py
#   [ ] app/services/skills.py              → (check if exists, rename)
#
# TODO 1.2: Rename classes + variables (find/replace across RG_Chat)
#   [ ] SkillClassifier      → ToolClassifier
#   [ ] SkillDefinition       → ToolDefinition
#   [ ] SkillCategory         → ToolCategory
#   [ ] SkillExecutor         → ToolExecutor
#   [ ] ClassifierPrediction  → (keep or rename to ToolPrediction)
#   [ ] ALL_SKILLS            → ALL_TOOLS
#   [ ] SKILL_TO_IDX          → TOOL_TO_IDX
#   [ ] IDX_TO_SKILL          → IDX_TO_TOOL
#   [ ] BUILTIN_SKILLS        → BUILTIN_TOOLS
#   [ ] skill_classifier      → tool_classifier  (global singleton)
#   [ ] skills_registry       → tools_registry   (global singleton)
#   [ ] skill_executor        → tool_executor    (global singleton)
#   [ ] skill_id              → tool_id          (everywhere)
#   [ ] detected_skill        → detected_tool    (resonant_chat.py)
#   [ ] enabled_skill_ids     → enabled_tool_ids (resonant_chat.py)
#   [ ] _SKILL_TOOL_*         → _TOOL_*          (resonant_chat.py)
#
# TODO 1.3: Rename DB tables (migration)
#   [ ] skill_classifier_models → tool_classifier_models
#   [ ] skill_active_samples    → tool_active_samples
#   NOTE: Or just keep old table names and add alias. Less risk.
#
# TODO 1.4: Update all imports across RG_Chat
#   [ ] resonant_chat.py — all skill_* imports
#   [ ] main.py — preload_skill_classifier
#   [ ] services/__init__.py
#   [ ] Any other files importing skill modules
#
# TODO 1.5: Test — service still works, classifier still predicts correctly
#   [ ] Run locally or in staging
#   [ ] Verify /chat endpoint works
#   [ ] Verify classifier predictions unchanged
#
# ============================================================================
# PHASE 2: EXPAND TO 130+ TOOLS
# ============================================================================
#
# Add all tools from RG_Unified_Tool_Registry as classifier labels.
# Generate training data. Retrain model.
#
# TODO 2.1: Import tool definitions from canonical registry
#   [ ] Read RG_Unified_Tool_Registry-Observability_Module/src/rg_tool_registry/builtin_tools.py
#   [ ] Extract all tool names + descriptions + categories
#   [ ] Map each tool to a classifier label
#
# TODO 2.2: Expand ALL_TOOLS list
#   [ ] Keep existing 13 tools (they still work)
#   [ ] Add all 130+ tools from registry as new labels
#   [ ] Group by category for hierarchical training if needed:
#       - search: web_search, news_search, image_search, youtube_search, etc.
#       - memory: memory_read, memory_write, memory_search, memory_stats
#       - code: execute_code, run_command, code_visualizer, etc.
#       - media: generate_image, generate_audio, generate_video, etc.
#       - integration: gmail_send, gmail_read, slack_send, google_drive, etc.
#       - community: create_rabbit_post, list_rabbit_communities, etc.
#       - platform: platform_api, discover_services, discover_api
#       - agent: build_agent, run_agent, modify_agent, delete_agent, etc.
#
# TODO 2.3: Generate training data for each tool
#   [ ] 20-50 example messages per tool (diverse phrasings)
#   [ ] Use existing skill_training_data.py as template
#   [ ] Include context-aware examples (multi-turn)
#   [ ] Include negative examples (general chat = None)
#   [ ] Consider multi-label: "search news and save to memory" → [news_search, memory_write]
#
# TODO 2.4: Decide: single-label vs multi-label classification
#   [ ] Current SkillClassifier = single-label (1 skill per message)
#   [ ] For 130+ tools, multi-label is better (user might need 2-3 tools)
#   [ ] If multi-label: switch from MLPClassifier to MultiOutputClassifier
#       or use sigmoid outputs instead of softmax
#   [ ] If single-label: keep existing architecture, just more labels
#   RECOMMENDATION: Start single-label (simpler), add multi-label later
#
# TODO 2.5: Architecture adjustments for 130+ labels
#   [ ] Increase hidden layers: (256, 128) → (512, 256, 128) maybe
#   [ ] More training data needed (130 labels × 30 examples = 3,900 minimum)
#   [ ] Consider hierarchical: predict CATEGORY first, then TOOL within category
#       - This would be two-stage: CategoryClassifier → ToolClassifier
#       - Matches how tools are organized in builtin_tools.py
#   [ ] Cross-validation to verify accuracy doesn't drop
#
# TODO 2.6: Retrain and save to DB
#   [ ] Train with expanded data
#   [ ] Verify accuracy ≥ 80% on cross-validation
#   [ ] Save new model to PostgreSQL (new version)
#   [ ] Active learning still works (predictions logged to DB)
#
# TODO 2.7: Test expanded classifier
#   [ ] Test with messages for new tools
#   [ ] Test existing 13 tools still work correctly
#   [ ] Test confidence thresholds
#   [ ] Compare prediction quality vs LLM function calling
#
# ============================================================================
# PHASE 3: WIRE AGENT ENGINE TO USE NEURAL TOOLS
# ============================================================================
#
# Agent Engine currently sends 70+ tool schemas to LLM every call.
# Instead: neural classifier pre-filters → send only top 5-8 tools to LLM.
#
# TODO 3.1: Vendor the tool_classifier into RG_Agent_Engine
#   [ ] Copy tool_classifier.py + training_data.py into app/
#   [ ] Add sentence-transformers, sklearn to requirements.txt
#   [ ] Load model from shared PostgreSQL on startup
#
# TODO 3.2: Integrate into executor.py
#   [ ] Before LLM call: predict top tools from user message
#   [ ] Filter tool schemas to only predicted tools + always-on tools
#   [ ] Send filtered tools to LLM via native function calling
#   [ ] Log prediction for active learning
#
# TODO 3.3: Test — agent runs still work with filtered tools
#   [ ] Test various agent goals
#   [ ] Verify correct tools are predicted
#   [ ] Measure token savings (should be 60-80% reduction)
#   [ ] Measure latency improvement
#
# ============================================================================
# PHASE 4: WIRE REMAINING SERVICES
# ============================================================================
#
# TODO 4.1: RG_agent_architect
#   [ ] Vendor tool_classifier
#   [ ] Pre-filter ORCHESTRATOR_TOOLS before LLM call
#   [ ] Keep existing AgentTypeClassifier + PromptRouter (they serve different purposes)
#
# TODO 4.2: RG_LLM_Service
#   [ ] Vendor tool_classifier
#   [ ] Pre-filter tools in agent.py before LLM call
#
# TODO 4.3: RG_Axtention_IDE
#   [ ] Vendor tool_classifier
#   [ ] Pre-filter _build_tool_definitions() output before LLM call
#   [ ] Keep all tools defined (client still needs them), just filter what LLM sees
#
# TODO 4.4: RG_Ed_Service
#   [ ] Vendor tool_classifier
#   [ ] Pre-filter tools
#
# ============================================================================
# PHASE 5: CLEANUP REDUNDANT TOOL SYSTEMS
# ============================================================================
#
# Once neural classifier is proven in all services, clean up:
#
# TODO 5.1: Delete vendored rg_tool_registry copies
#   [ ] RG_Agent_Engine/app/rg_tool_registry/  (use neural classifier instead)
#   [ ] RG_LLM_Service/app/rg_tool_registry/
#   [ ] RG_Ed_Service/app/rg_tool_registry/
#   NOTE: Only delete AFTER neural classifier is proven working
#
# TODO 5.2: Consolidate tool definitions
#   [ ] All tool definitions live in ONE place (the training data + classifier)
#   [ ] Tool executors/handlers stay in each service (they do the actual work)
#   [ ] Tool SELECTION is neural, tool EXECUTION is local
#
# TODO 5.3: Update RG_Unified_Tool_Registry-Observability_Module
#   [ ] Keep as canonical tool DEFINITION source
#   [ ] Add neural classifier module alongside existing code
#   [ ] Or deprecate if classifier replaces all its functions
#
# ============================================================================
# RISKS AND MITIGATIONS
# ============================================================================
#
# RISK: 130+ labels too many for MLP → accuracy drops
# MITIGATION: Hierarchical classification (category → tool), more training data
#
# RISK: Rename breaks RG_Chat in production
# MITIGATION: Do rename + retrain in staging first, keep old DB tables as alias
#
# RISK: Services can't load model (missing deps, DB access)
# MITIGATION: Graceful fallback — if classifier unavailable, send ALL tools to LLM (current behavior)
#
# RISK: Active learning data from different services conflicts
# MITIGATION: Add service_id column to active samples table, train per-service or unified
#
# ============================================================================
# ORDER OF OPERATIONS
# ============================================================================
#
# 1. Phase 1 (rename) — low risk, no behavior change
# 2. Phase 2 (expand + retrain) — medium risk, test thoroughly
# 3. Phase 3 (wire Agent Engine) — high impact, biggest token savings
# 4. Phase 4 (wire remaining) — incremental
# 5. Phase 5 (cleanup) — only after everything proven
#
# ESTIMATED EFFORT:
#   Phase 1: 1-2 hours (mechanical rename)
#   Phase 2: 4-8 hours (training data generation + architecture tuning)
#   Phase 3: 2-3 hours (integration + testing)
#   Phase 4: 3-4 hours (repeat for each service)
#   Phase 5: 1-2 hours (delete old code)
#
# ============================================================================
echo "This is a plan file. Read it, don't run it."
echo "Start with Phase 1: rename skills → tools in RG_Chat"
