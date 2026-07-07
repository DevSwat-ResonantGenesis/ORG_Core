# Live Model Catalog + Owner Curation — Handoff

**Created:** 2026-07-02 23:19 UTC
**Status:** Phase 1 DONE + deployed + verified live. Phases 2–4 + follow-ups NOT started.
**Purpose:** Enable ~20 providers / ~75 models to be *organically available* from live
discovery + an owner dashboard, respecting user BYOK, never overridden by hardcoded
model IDs. This doc lets another agent resume with zero rediscovery.

> Companion record in Claude memory: `rg-model-preference-catalog`, `rg-llm-service-config`,
> `rg-memory-vector-search`, `rg-prod-deploy`.

---

## Owner's goal (verbatim intent)
- Add credits/keys for many providers/models → they appear automatically, no code edits.
- Curated from an **owner/system dashboard** (enable/disable, feature, marketplace).
- Always respect a user's own provider/model choice (BYOK); never override with a default.
- **No hardcoded model IDs** anywhere in the call path (they rot on every provider retirement).

## Decisions locked (from owner)
| Topic | Decision |
|---|---|
| No-preference default policy | **Task-based smart routing** (classify task → best available provider) |
| System key storage | **Hybrid: DB overrides env** |
| Key precedence | **Platform-first (keep current billing):** env/platform-DB → org-DB → user BYOK |
| Curation scope | **3-tier:** platform_owner (global) / org incl. enterprise / user |
| DB migrations | **Idempotent `CREATE TABLE IF NOT EXISTS`** (additive only, safe on live prod) |
| Held (do NOT delete) | `RG_core/scripts/true-blue-green-deploy-FIXED.sh` vs sibling; `RG_Memory/MEMORY_AUDIT_2026.md` |

## Identity model (confirmed from RG_Auth code)
- **User** = account; on signup gets its **own personal `Organization`** (`default_org_id`) + 7-day unlimited trial (`RG_Auth/app/routers.py:170-188`).
- **Organization** = billing/isolation unit; `plan ∈ developer|plus|enterprise` (`RG_Auth/app/models.py:88`). Personal org and enterprise org are the same table (differ by plan + member count).
- **OrgMembership** = user↔org with role `owner|admin|viewer` (`models.py:109`).
- **platform_owner** = level-6 superuser, separate login (`RG_Auth/app/owner_auth.py`, `roles.py`) — the platform operator, outside any org.
- Platform `ApiKey` is **org-scoped** (`ApiKey.org_id`); user BYOK `UserApiKey` is **per-user** (`models.py:169`).
- Roles hierarchy (`roles.py:17`): viewer0 < user1 < finance/compliance2 < ml_engineer3 < org_admin4 < platform_dev/owner5 < platform_owner6.

---

## ✅ Phase 1 — DONE (deployed + verified 2026-07-02)

### Prereq fix (was a live outage) — DEPLOYED
`rg_llm/providers.py:122` reads Anthropic system key from **`ANTHROPIC_API_KEY`**, but prod only
had **`LLM_ANTHROPIC_API_KEY`**. All 6 rg_llm-direct services fell through a dead chain
(tokenrouter 403 / openai 401 / gemini 429) → "All providers failed" → no-BYOK agent builds down.
**Fix applied:** appended `ANTHROPIC_API_KEY=<same value>` to
`/home/deploy/genesis2026_production_backend/.env.production`
(backup: `.env.production.pre_anthropic_fix.bak`) and force-recreated the 6 services.

### Code changes (committed + pushed to `main`)
| Repo | Commit | Change |
|---|---|---|
| RG_LLM_Service | `8a24490` | `/llm/providers` uncapped: replaced static-whitelist `_filter_known` with module-level `_is_chat_model(model_id)` deny-list; added `_provider_probe_cache` (120s TTL, user-agnostic); BYOK stays live. |
| RG_UnifiedLLMClient | `971f769` | `providers.TASK_PROVIDER_PREFERENCE` (task→ordered PROVIDER IDs). `client.py` complete()/stream(): no-preference (`""`/`auto`/`default`/`none`) → classify_task → first AVAILABLE provider's computed default_model; explicit user choice always wins; non-strict fallback. Added `_task_preferred_provider`; exported `resolve_api_key`. |
| RG_agent_architect | `c161241` | `src/core/llm_client.py` DEFAULT/FAST/REASONING_MODEL = `""` (was dead `tokenrouter/...`). |

### Verified live
- Catalog uncapped: **anthropic 5→10 models** (surfaces `claude-sonnet-5`, `claude-sonnet-4-6` organically); tokenrouter 72; google 30.
- Architect no-preference build succeeds via task routing (picks first keyed provider; falls back). No "All providers failed".
- `[LLM-task]` log is INFO and **suppressed** in prod (rg_llm.client logs at WARNING) — absence ≠ not firing.

### Known minor gaps (fix on next `llm_service` touch)
- Google live list leaks non-chat families `lyria` (music), `nano-banana` (image) that pass the `generateContent` check. Add these names to `_NON_CHAT_MODEL_MARKERS` in `RG_LLM_Service/app/routers.py`.
- Hardcoded image model at `RG_Chat/app/services/image_generation.py:158` (`"openai/gpt-5-image"`).

---

## ⏳ Phase 2 — 3-tier curation persistence + keys (NOT started) — Tasks #3, #4

### 2a. New DB tables (RG_Auth, idempotent CREATE TABLE IF NOT EXISTS)
Add SQLAlchemy models in `RG_Auth/app/models.py` + create tables on startup (auth uses
`Base.metadata.create_all` pattern — confirm and reuse; do NOT alter existing tables).

```
ProviderCuration:
  id UUID pk
  scope        str   # 'platform' | 'org'
  org_id       UUID  null (null for platform-scope)
  provider     str   # provider id, e.g. 'anthropic'
  is_enabled   bool  default true
  is_featured  bool  default false
  tier_override str  null
  custom_name        str null
  custom_description str null
  updated_by_user_id UUID null
  updated_at   datetime
  UNIQUE(scope, org_id, provider)

ModelOffering:            # per-model curation (marketplace + featured/default)
  id UUID pk
  scope        str        # 'platform' | 'org'
  org_id       UUID null
  provider     str
  model_id     str
  is_enabled   bool default true
  is_featured  bool default false
  is_default   bool default false   # per-capability default candidate
  marketplace_visible bool default false
  updated_by_user_id UUID null
  updated_at   datetime
  UNIQUE(scope, org_id, provider, model_id)

SystemApiKey:             # hybrid DB-over-env system/org keys
  id UUID pk
  scope        str        # 'platform' | 'org'
  org_id       UUID null
  provider     str
  encrypted_key text      # reuse RG_Auth's existing UserApiKey encryption (see models.py:169 encrypted_key + its crypto helper)
  key_prefix   str        # for masked display
  is_valid     bool default true
  last_rotated datetime
  created_by_user_id UUID
  UNIQUE(scope, org_id, provider)
```

### 2b. Key resolution — platform-first (hybrid DB-over-env)
Order per provider: **platform-DB SystemApiKey → env var → org-DB SystemApiKey → user BYOK**.
(Current `rg_llm/keys.py:resolve_api_key` does env→BYOK; keep that as the innermost fallback.)
rg_llm is a pure lib with NO DB access, so inject DB keys via the existing fetcher pattern:
- Today `UnifiedLLMClient(byok_fetcher=...)` fetches per-user BYOK. Extend the fetcher (or add a
  `system_key_fetcher`) so services pass a resolved `{provider: key}` for platform+org tiers too.
- Simplest: an auth-service internal endpoint `GET /auth/internal/resolved-keys?user_id=&org_id=`
  returning the merged platform+org+user keys already in precedence order; services pass it as
  `user_keys` to rg_llm (env still tried first inside resolve_api_key → matches platform-first).
- To honor **DB-over-env** for the platform tier, either (a) load platform SystemApiKey rows into
  each container's env at boot, or (b) have `resolve_api_key` consult an injected system-key map
  before env. Prefer (b): add an optional `system_keys` param to `resolve_api_key`/`build_provider_chain`.

### 2c. Owner/org endpoints (build on `owner_auth.py` + `roles.py`)
- `platform_owner` (require_owner dependency exists):
  - `GET/POST /owner/providers/curated` — list/enable/disable/feature providers (ProviderCuration scope=platform)
  - `GET/POST /owner/models/offerings` — curate ModelOffering (feature/default/marketplace)
  - `GET/POST/DELETE /owner/system-keys` — add/rotate/list (masked) platform SystemApiKey
- `org_admin` (role level ≥4, scoped to their org_id):
  - `GET/POST /org/{org_id}/providers` — org allow-list (ProviderCuration scope=org)
  - `GET/POST /org/{org_id}/system-keys` — org keys
- **Wire curation into the catalog:** in `RG_LLM_Service/app/routers.py` `providers_catalog`,
  after building the live `providers` list, intersect/annotate with ProviderCuration + ModelOffering:
  effective = live ∩ platform-enabled ∩ org-allowed(for the requesting user's org); add
  `featured`, `curated_name`, `marketplace_visible` flags. Fetch curation from auth via an internal
  endpoint (cache with the same 120s TTL). Keep user BYOK providers always visible to that user.

## ⏳ Phase 3 — Owner dashboard UI (NOT started) — Task #5
`ORG_Frontend` (React + Vite). Existing infra to reuse:
- `src/hooks/useLLMProviders.ts`, `src/api/providers.ts` (`fetchLiveProviders()` → `/resonant-chat/providers`), `ProviderSelector.tsx` (polls live status).
- Owner auth already exists (`/owner/auth/login`).
Build owner pages:
- Provider grid: enable/disable toggle, live status, has_system_key, key entry/rotate.
- Model catalog table (per provider): feature / default / marketplace toggles (ModelOffering).
- System-key management (masked, add/rotate).
- Deploy note ([[rg-prod-deploy]]): system nginx serves `/var/www/frontend`; build writes to
  `dist` then **must** `rsync -a --delete dist/ /var/www/frontend/`. Update `scripts/inject-og-pages.mjs`
  only if adding public routes.

## ⏳ Phase 4 — Deploy + live-verify (NOT started) — Task #6
Staged rollout (owner chose staged + verify each):
1. Apply DB tables (idempotent) — run via `docker run --rm -i postgres:15-alpine psql '<conn>'` or auth startup.
2. Deploy auth (endpoints) → verify owner can enable/disable a provider.
3. Deploy llm_service (curation-aware catalog) → verify catalog reflects curation.
4. Deploy frontend → rsync to `/var/www/frontend`.
Verify: (a) adding a provider key surfaces its models with no code change; (b) owner disable hides a
provider/model; (c) org allow-list restricts members; (d) user BYOK still wins + can use a
non-platform-funded provider; (e) no-preference uses task routing.

---

## Follow-ups (tracked) — do any independently
- **#7 (quick win):** redact provider secrets in `rg_llm` logs. `RG_UnifiedLLMClient/src/rg_llm/client.py`
  lines ~223, ~407 log full failure URLs incl. Gemini `?key=...`; also returned in `fallback_chain` reason
  (~219). Add `_scrub_secrets(s)` (regex `key=[^&\s]+`, `sk-[A-Za-z0-9-]+`, `AIza[0-9A-Za-z_-]+`) applied to
  `last_error`/`str(e)` before logging/returning. Mounted lib → restart 7 services, no rebuild.
- **#8:** memory extract returns HTTP 500 (unhandled `ValueError: badly formed hexadecimal UUID`) on
  non-UUID `user_id`; `/memory/ingest` silently nulls it. Validate `user_id` in `RG_Memory` extract/ingest
  routes → 422. Rebuild `memory_service`.
- **#9:** expand cleanup sweep to remaining ~30 RG_* repos (report-as-.sh, stale md/txt, .DS_Store,
  backups, tracked caches). Policy: auto-delete safe, `git rm` (recoverable), ask on ambiguous code-level dead code.
- **#10:** full SDK green-path test: register throwaway user+org, mint real `RG-<prefix>.<secret>` key
  (`POST /auth/api-keys`, needs user JWT), run SDK ingest/recall against `https://resonant.dev-swat.com/api/v1`
  for a true 200, then clean up.

---

## Deploy runbook + gotchas (learned this session)
- **Prod:** `ssh root@64.23.166.35`; compose at `/home/deploy/genesis2026_production_backend/docker-compose.unified.yml`. Requires explicit user authorization of the host in-conversation (auto-mode classifier blocks agent-inferred IPs).
- **Repos on server** under `/home/deploy/<Repo>`; `git pull --ff-only origin main`. Check `git status` first (server repos sometimes carry local-only fixes). Push from THIS Mac's SSH remotes (`git@github-devswat:DevSwat-ResonantGenesis/<repo>.git`); server's embedded `ghp_` tokens are read-only. `RG_core` → remote redirects to `ORG_Core.git` (works; URL stale).
- **rg_llm is volume-mounted** read-only into 7 services from `/home/deploy/RG_UnifiedLLMClient/src/rg_llm` → pull + **restart** (no rebuild) picks it up. `llm_service` and `agent_architect` bake their own code → **rebuild** needed for their own changes.
- **Rebuild/restart:** `docker compose -f docker-compose.unified.yml build <svc>` then `up -d --force-recreate --no-deps <svc>`. Long builds: use `ssh -o ServerAliveInterval=30`; build continues server-side if pipe drops.
- **Health:** containers have no host-curl; `docker exec <svc> curl localhost:8000/health` or `docker inspect -f '{{.State.Health.Status}}'`. **`agent_engine_service` has NO curl** — use `memory_service` as the in-network HTTP client (`docker exec memory_service curl http://<svc>:8000/...`).
- **Secrets:** never print key values; copy server-side (`grep|cut` into a var, don't echo). Compose `env_file: ./.env.production` values are literal (no `${}` interpolation across env_file).
- **Test-data cleanup:** memory — throwaway UUID user + `source` tag; FK-safe DELETE across
  `memory_embeddings/chunks/facts/edges/anchors/records` via `docker exec -i memory_service python -`
  using `app.db.engine`. Agent — `DELETE http://agent_engine_service:8000/agents/{id}` → `archived`.

## Service call map (current)
- Chat entry `POST /message/stream` (`RG_Chat/app/routers/resonant_chat.py`) → memory `POST memory_service:8000/memory/hash-sphere/extract` → architect `POST agent_architect:8000/api/message/stream` (`tool_executor.py:1488`) → LLM via `rg_llm`.
- Architect build: `Orchestrator` → `BuildPipeline` (6 phases) → `Builder.build()` → `agent_engine_service:8000/agents/`.
- SDK (`RG_Memory/sdk`): base `https://resonant.dev-swat.com/api/v1`, `Authorization: Bearer RG-...`; gateway validates via `auth_service /auth/api-keys/verify` (`RG_Gateway/app/auth_middleware.py`).
- Public edge: nginx routes `/api/`, `/api/v1/`, `/api/resonant-chat/` → gateway `:8001`. Bare `/memory/...` publicly = 405.
