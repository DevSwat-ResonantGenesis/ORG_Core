#!/bin/bash
# ════════════════════════════════════════════════════════════════════════
# MARKETPLACE SYSTEMS ANALYSIS — Full Architecture Audit
# Generated: 2026-04-22
# ════════════════════════════════════════════════════════════════════════

# ┌─────────────────────────────────────────────────────────────────────┐
# │  THREE SEPARATE "PUBLISH" SYSTEMS EXIST                            │
# │  They are NOT connected to each other in a meaningful way          │
# └─────────────────────────────────────────────────────────────────────┘

# ═══════════════════════════════════════════════════════════════════════
# SYSTEM 1: DSID NODE PUBLISH (AgentPublishPage / nodeApi)
# ═══════════════════════════════════════════════════════════════════════
#
# Frontend:    /network/publish (AgentPublishPage.tsx)
# API:         POST /dsid/agents/publish → RG_DSID_Node
# Service:     RG_DSID_Node (container: dsid_node)
#
# WHAT IT DOES:
#   - User manually fills in name, description, code, category, trust tier
#   - Computes SHA-256 manifest_hash + code_checksum client-side
#   - Publishes to DSID Node blockchain network
#   - Records agent on the DSID chain with manifest hash
#
# WHAT IT DOES NOT:
#   [x] Does NOT read the user's existing Agent Engine agents
#   [x] Does NOT transfer system_prompt, model, tools, or any config
#   [x] Does NOT create a marketplace listing
#   [x] Agent code is pasted manually — NOT from Agent Engine
#   [x] The "Agent" published here is a DSID-chain concept, NOT an Agent Engine agent
#   [x] Cannot be executed through the platform — it's just a manifest record
#
# VERDICT: This is a BLOCKCHAIN REGISTRATION system, not a marketplace.
#          It registers agent manifests on-chain for cryptographic verification.
#          Completely disconnected from Agent Engine agents.

# ═══════════════════════════════════════════════════════════════════════
# SYSTEM 2: RG_MARKETPLACE SERVICE (The new marketplace we restored)
# ═══════════════════════════════════════════════════════════════════════
#
# Frontend:    /network/marketplace (AgentMarketplacePage.tsx)
# API:         POST /marketplace/listings → RG_Marketplace
# Service:     RG_Marketplace (container: marketplace_service, port 8000)
# Database:    MARKETPLACE_DATABASE_URL (DigitalOcean managed PG)
#
# WHAT IT STORES:
#   - AgentListing: name, tagline, description, category, tags, price,
#     agent_config (JSON), required_tools, status (draft/published),
#     downloads, rating_average, rating_count, publisher_id
#   - AgentVersion: version history per listing
#   - AgentPurchase: buyer_id, listing_id, price_paid, status
#   - AgentReview: rating, title, content, verified_purchase flag
#   - PublisherProfile: display_name, bio, stripe_account_id
#   - MarketplaceCategory: category taxonomy
#
# PUBLISH FLOW:
#   1. POST /marketplace/listings (creates draft with agent_config JSON)
#   2. POST /marketplace/listings/{id}/publish (sets status=published)
#
# PURCHASE FLOW (when a user "buys" an agent):
#   - Free agent: instantly completes, increments downloads, records on blockchain
#   - Paid agent (no Stripe): credits publisher wallet via Agent Engine, awards RGT tokens
#   - Paid agent (Stripe): creates Stripe checkout session with publisher as connected account
#   - Returns: { status, purchase_id, agent_config }
#
# CRITICAL GAPS:
#   [x] Purchase returns raw agent_config JSON — but NOTHING creates the agent
#       in the buyer's Agent Engine account
#   [x] No "clone agent" or "fork agent" endpoint exists
#   [x] No mechanism to transfer system_prompt, tools, schedules, triggers,
#       memory, or any live agent state to the buyer
#   [x] agent_config is just a static JSON blob — it can be stale or incomplete
#   [x] No frontend UI to CREATE a listing (only browse/search/detail exists)
#   [x] No frontend "Buy" or "Get Agent" button exists
#   [x] The marketplace page currently fetches from DSID Node API (nodeApi.ts),
#       NOT from RG_Marketplace service!
#
# VERDICT: The service has a complete backend (CRUD, purchases, reviews,
#          Stripe, blockchain recording) but NO frontend integration for
#          creating listings or purchasing agents. And critically — purchasing
#          an agent does NOT create it in the buyer's account.

# ═══════════════════════════════════════════════════════════════════════
# SYSTEM 3: AGENT ENGINE PUBLISH (/{agent_id}/publish endpoint)
# ═══════════════════════════════════════════════════════════════════════
#
# API:         POST /agents/{agent_id}/publish → RG_Agent_Engine
# Service:     RG_Agent_Engine (container: agent_engine_service)
#
# WHAT IT DOES:
#   - Takes an EXISTING Agent Engine agent (with full config)
#   - publish_internal_marketplace=true → calls RG_Marketplace to create listing
#     with agent_config containing: agent_id, model, tools, system_prompt,
#     temperature, max_tokens
#   - publish_decentralized=true → publishes manifest to blockchain
#   - Sets agent.published_to_marketplace = True
#   - Also has: /{agent_id}/marketplace-publish (toggle)
#   - Also has: /{agent_id}/marketplace-unpublish
#   - Also has: /marketplace endpoint (list all published agents)
#
# THIS IS THE REAL BRIDGE between Agent Engine ↔ Marketplace
# BUT:
#   [x] No frontend button calls this endpoint!
#   [x] The AgentsPanel has a "publish" button but it calls the DSID
#       Node API (publishAgentAPI from nodeApi.ts), NOT Agent Engine's
#       /{agent_id}/publish
#   [x] The publish payload in AgentsPanel builds a manual manifest from
#       scratch — it does NOT use the agent's actual config
#
# VERDICT: The backend wiring EXISTS but the frontend is calling the
#          wrong API. The Agent Engine has the correct publish-to-marketplace
#          flow but nobody invokes it.

# ═══════════════════════════════════════════════════════════════════════
# WHAT HAPPENS WHEN USER BUYS AN AGENT? (Current: NOTHING useful)
# ═══════════════════════════════════════════════════════════════════════
#
# Current flow:
#   1. User browses marketplace → sees listing
#   2. User clicks "purchase" → API returns { agent_config: {...} }
#   3. ...nothing. The agent_config is returned but not used.
#
# What SHOULD happen:
#   1. User browses marketplace → sees listing with full details
#   2. User clicks "Get Agent" (free) or "Buy Agent" (paid)
#   3. Backend creates a NEW AgentDefinition in buyer's account:
#      - Copies: name, description, system_prompt, model, temperature,
#        max_tokens, tools, tool_config, safety_config
#      - Sets: user_id = buyer's user_id
#      - Sets: agent_source = "marketplace"
#      - Links: original_listing_id or parent_agent_id for attribution
#   4. Agent appears in buyer's Agent Management page
#   5. Buyer can customize, run, schedule — it's THEIR agent now

# ═══════════════════════════════════════════════════════════════════════
# WHAT ABOUT "RENTING" / NFT-LIKE USAGE? (100 users, 1 agent)
# ═══════════════════════════════════════════════════════════════════════
#
# CURRENT STATE: Does NOT exist.
#
# The Agent Engine model is: 1 agent = 1 owner (user_id).
# There's no concept of:
#   [x] Shared agent execution (multiple users → same agent)
#   [x] Per-user memory isolation on a shared agent
#   [x] Usage-based access (pay-per-run, rental periods)
#   [x] NFT-gated agent access
#
# WHAT WOULD BE NEEDED:
#   1. Agent Engine: "shared agent" model — original stays with publisher,
#      other users get access_token/license to invoke it
#   2. Execution routing: when User B runs Publisher A's agent, the session
#      is created under User B but references Publisher A's agent definition
#   3. Memory isolation: each user gets their own memory namespace
#      (already partially possible via user_id on memory service)
#   4. Billing: pay-per-execution or subscription model
#      (marketplace purchase flow has this structure but isn't wired)
#   5. RGT token gating: require RGT stake or NFT ownership to access
#
# This is a Phase 2+ feature. Not built yet.

# ═══════════════════════════════════════════════════════════════════════
# WHERE DOES THE MARKETPLACE PAGE ACTUALLY FETCH FROM?
# ═══════════════════════════════════════════════════════════════════════
#
# CORRECTED TRACE (Apr 22, 2026):
#
# 1. AgentMarketplacePage.tsx calls: searchAgents() from nodeApi.ts
# 2. nodeApi.ts calls: GET /api/v1/node/agents  (NODE_API_BASE = /api/v1/node)
# 3. Nginx proxies /api/v1/* → Gateway (localhost:8001)
# 4. Gateway node_routes.py handles /node/agents →
#    calls Agent Engine GET /agents/marketplace?limit=50
# 5. Agent Engine returns agents where published_to_marketplace=True
# 6. node_routes.py maps them via _agent_to_marketplace() → thin shape
#
# *** DSID Node IS NOT IN THIS PATH AT ALL ***
#
# node_routes.py only uses DSID Node (BLOCKCHAIN_URL) for:
#   - /node/status → chain status info
#   - /node/executions/history → execution history
#
# DSID Node (container: dsid_node, port 8081):
#   - Running and healthy on server (Up 3 days)
#   - Serves LOCAL_AGENTS: 5 hardcoded test agents (Hello World, Code Analyzer, etc)
#   - Its /agents endpoint returns these 5 local agents only
#   - It is NOT called by the marketplace page
#   - It is a STANDALONE decentralized node, not part of the marketplace flow
#   - Git: git@github-devswat:DevSwat-ResonantGenesis/RG_DSID_Node.git (3 commits)
#   - Server: /home/deploy/RG_DSID_Node (exists, cloned)
#
# BOTH APIs return EMPTY now:
#   - GET /api/v1/node/agents → {"agents":[], "count":0}
#     (Agent Engine has 0 agents with published_to_marketplace=True)
#   - GET /marketplace/marketplace/listings → []
#     (RG_Marketplace has 0 published listings — we wiped them)
#
# THE REAL PROBLEM:
#   The marketplace page fetches from Agent Engine (via node_routes.py)
#   which has a THIN data shape — no ratings, reviews, downloads, tags.
#   It should instead fetch from RG_Marketplace which has the RICH model:
#   ratings, reviews, purchases, categories, publisher profiles, Stripe.

# ═══════════════════════════════════════════════════════════════════════
# SUMMARY: 3 SYSTEMS — PARTIAL WIRING
# ═══════════════════════════════════════════════════════════════════════
#
# System 1 (DSID Node — RG_DSID_Node):
#   Container: dsid_node (port 8081) — UP, healthy
#   Git: DevSwat-ResonantGenesis/RG_DSID_Node.git
#   Server: /home/deploy/RG_DSID_Node
#   Backend: ✅ Runs, has 5 hardcoded LOCAL_AGENTS + DSID identity endpoints
#   Frontend: ✅ Has publish form (/network/publish) + AgentPublishPage.tsx
#   Purpose: Standalone decentralized node — agent execution sandbox + chain
#   Connected to marketplace: ❌ NOT in the marketplace data path
#   Status: Works but isolated — a blockchain identity/execution service
#
# System 2 (RG_Marketplace Service):
#   Container: marketplace_service (port 8000) — UP, healthy
#   Git: DevSwat-ResonantGenesis/RG_Marketplace.git
#   Server: /home/deploy/RG_Marketplace
#   Backend: ✅ Full CRUD, purchases, reviews, Stripe, blockchain recording
#   Frontend: ⚠️  Browse-only (no create listing, no buy button)
#   Data: ❌ 0 listings (we wiped the test data)
#   Purpose: Agent store/catalog with rich commerce model
#   Connected to Agent Engine: ⚠️  Agent Engine CAN push listings to it
#   Connected to frontend: ❌ Frontend reads from node_routes, NOT here
#
# System 3 (Agent Engine publish endpoints):
#   Container: agent_engine_service (port 8000)
#   Backend: ✅ POST /{agent_id}/publish → creates listing in RG_Marketplace
#   Backend: ✅ GET /agents/marketplace → returns published_to_marketplace agents
#   Frontend: ❌ No button calls /{agent_id}/publish
#   Purpose: Bridge — the only system that connects agents to marketplace
#   Status: The bridge works but nobody triggers it from the UI
#
# DATA FLOW (current, broken):
#   Frontend → /api/v1/node/agents → Gateway node_routes.py → Agent Engine
#   /agents/marketplace → 0 agents (none published) → empty marketplace page
#
# DATA FLOW (correct, planned):
#   User clicks "Publish" on agent card → Agent Engine /{id}/publish
#   → creates listing in RG_Marketplace → listing appears
#   Frontend → fetches from /marketplace/marketplace/listings → rich data
#   User clicks "Get Agent" → RG_Marketplace purchase → clone to buyer

# ═══════════════════════════════════════════════════════════════════════
# TODO: MAKE IT ACTUALLY WORK
# ═══════════════════════════════════════════════════════════════════════

# ── Phase 1: Fix the Publish Flow ──
# [x] 1.1 Marketplace page redesigned (compact, branded, split-view)
# [x] 1.2 Shop icon in header (fixed size)
# [x] 1.3 Deleted fake/test marketplace listings
# [ ] 1.4 Switch AgentMarketplacePage to fetch from RG_Marketplace API
#          instead of DSID Node API
# [x] 1.5 Add "Publish to Marketplace" button on Agent cards (AgentsPanel)
#          → Shop icon, calls Agent Engine POST /{agent_id}/publish with
#          publish_internal_marketplace=true. Orange dot shows published state.
# [ ] 1.6 Add publish confirmation dialog (set category, price, tags)
# [x] 1.7 Show "Published" badge on agent cards that are marketplace-listed
#          → Orange dot indicator + published CSS class on shop button

# ── Phase 2: Fix the Purchase/Acquisition Flow ──
# [ ] 2.1 Add "Get Agent" / "Buy" button on marketplace detail panel
# [ ] 2.2 Create Agent Engine endpoint: POST /agents/clone-from-marketplace
#          → accepts listing_id, fetches agent_config from marketplace,
#          creates new AgentDefinition in buyer's account
# [ ] 2.3 Wire purchase flow: marketplace purchase → auto-clone to buyer
# [ ] 2.4 Show "Acquired from Marketplace" badge on cloned agents
# [ ] 2.5 Track attribution: parent_listing_id on cloned agents

# ── Phase 3: Agent Rental / Shared Execution (Future) ──
# [ ] 3.1 Design shared agent execution model
# [ ] 3.2 Per-user memory isolation for shared agents
# [ ] 3.3 Pay-per-execution billing via marketplace
# [ ] 3.4 Usage analytics dashboard for publishers
# [ ] 3.5 RGT token gating for premium agents

# ── Phase 4: Unify the Three Systems ──
# [ ] 4.1 DSID Node registration should auto-trigger on marketplace publish
# [ ] 4.2 Marketplace listings should display DSID verification badge
# [ ] 4.3 Single "Publish" button that does: Agent Engine → Marketplace + DSID
# [ ] 4.4 Remove/deprecate standalone /network/publish page
#          (replace with agent card "Publish" button)

# ═══════════════════════════════════════════════════════════════════════
# FILE INVENTORY
# ═══════════════════════════════════════════════════════════════════════
#
# RG_Agent_Engine/app/models.py          — AgentDefinition (published_to_marketplace field)
# RG_Agent_Engine/app/routers.py         — /{agent_id}/publish, /marketplace, /marketplace-publish
# RG_Marketplace/app/routers.py          — Marketplace CRUD, purchases, reviews, Stripe
# RG_Marketplace/app/models.py           — AgentListing, AgentPurchase, AgentReview, PublisherProfile
# ORG_Frontend/src/pages/Network/AgentMarketplacePage.tsx — Browse UI (reads from WRONG API)
# ORG_Frontend/src/pages/Network/Marketplace.module.css   — New branded CSS
# ORG_Frontend/src/pages/Network/AgentPublishPage.tsx     — DSID publish form (standalone)
# ORG_Frontend/src/services/nodeApi.ts    — DSID Node API client (used by marketplace page, WRONG)
# ORG_Frontend/src/pages/Agents/components/Panels/AgentsPanel/index.tsx — Agent cards + inline publish
# RG_Gateway/app/auth_middleware.py       — Public marketplace routes
# RG_Gateway/app/routers.py              — Marketplace proxy routes
