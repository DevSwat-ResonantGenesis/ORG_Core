# RG_core — Production Infrastructure & Deployment

> **Part of the [ResonantGenesis](https://dev-swat.com) platform** — Central deployment hub for the entire microservices platform.

[![Status: Production](https://img.shields.io/badge/Status-Production-brightgreen.svg)]()
[![License: RG Source Available](https://img.shields.io/badge/License-RG%20Source%20Available-blue.svg)](LICENSE.txt)

---

## What This Repo Is

This is the **infrastructure-only** repo. It does NOT contain any service code — each microservice lives in its own standalone repository. This repo contains:

- The **single production `docker-compose.unified.yml`** that orchestrates all 30+ containers
- **Deploy scripts** for blue-green deployment, rollback, and manual deploys
- **Nginx configs** for the reverse proxy
- **Terraform/Helm/DigitalOcean** infrastructure-as-code
- **Ops scripts** for DB backups, security audits, health checks, superuser creation, etc.
- **`.env.production.template`** with all required environment variables (118 lines)

This repo was formerly the monorepo (`genesis2026_production_backend`) that contained all service code. On **April 19, 2026**, 215K lines of dead duplicated code were nuked, leaving only the infrastructure files.

---

## GitHub Repository

```
git@github-devswat:DevSwat-ResonantGenesis/genesis2026_production_backend.git
```

> Note: GitHub shows a redirect notice to `ORG_Core.git` — both URLs work.

**Server clone path**: `/home/deploy/genesis2026_production_backend/`
**Local clone path**: `/Users/louie/CascadeProjects/RG/RG_core/`

---

## What It Deploys

`docker-compose.unified.yml` (910 lines) defines **30 services** + Redis + volumes + network:

### Active Services (running in production)
| Container | Repo | Port | Description |
|---|---|---|---|
| `gateway` | RG_Gateway | 8000 | API Gateway — routes all traffic to services |
| `auth_service` | RG_Auth | 8000 | Authentication, JWT, MFA, RBAC, orgs |
| `billing_service` | RG_Billing | 8000 | Subscriptions, credits, Stripe, pricing |
| `chat_service` | RG_Chat | 8000 | ResonantChat — 68-module AI pipeline |
| `agent_engine_service` | RG_Agent_Engine | 8000 | Agent orchestration, tool execution |
| `agent_engine_celery_worker` | RG_Agent_Engine | — | Async task worker (Celery) |
| `agent_architect` | RG_agent_architect | 8000 | Agent builder, prompt classifier |
| `memory_service` | RG_Memory | 8000 | Semantic Memory Universe |
| `llm_service` | RG_LLM_Service | 8000 | LLM provider abstraction |
| `mining_service` | RG_TrainingNet_Mining | 8000 | Distributed ML training + RGT mining |
| `blockchain_service` | RG_DSID_Blockchain | 8000 | DSID-P blockchain protocol |
| `dsid_node` | RG_DSID_Node | 8081 | DSID external chain node (Base Sepolia) |
| `external_blockchain_service` | RG_TrainingNet_Chain | 8000 | Training network chain (Raft consensus) |
| `crypto_service` | RG_Crypto | 8000 | Crypto identity + wallet |
| `notification_service` | RG_Notifications | 8000 | Push/email notifications |
| `user_service` | RG_User_Service | 8000 | User profiles, preferences, dashboard |
| `ed_service` | RG_Ed_Service | 8000 | Education service |
| `ide_service` | RG_Axtention_IDE | 8000 | IDE backend — agentic loop |
| `storage_service` | RG_Storage | 8000 | File/object storage |
| `code_execution_service` | RG_Code_Execution | 8002 | Sandboxed code execution |
| `sandbox_runner_service` | RG_Sandbox_Runner | 8000 | Sandbox container runner |
| `workflow_service` | RG_Workflow | 8000 | Workflow execution engine |
| `rg_ast_analysis` | RG_AST_analysis | 8000 | Code Visualizer — AST/SAST |
| `rg_internal_invarients_sim` | RG_Internal_Invarients_SIM | 8000 | Internal governance sim |
| `rg_users_invarients_sim` | RG_Users_Invarients_SIM | 8000 | User-facing invariants |
| `lighthouse_service` | RG_TrainingNet_Lighthouse | 8000 | Peer discovery + network beacon |
| `shared_redis` | (official image) | 6379 | Shared Redis cache |

### Ghost Services (in compose but repos don't exist — pending cleanup)
| Container | Status |
|---|---|
| `blockchain_node` | No repo, not running |
| `build_service` | No repo, not running |
| `cognitive_service` | No repo, not running |
| `discord_bridge` | No repo, not running |
| `ml_service` | No repo, not running |
| `marketplace_service` | No repo, not running |
| `user_memory_service` | No repo, not running |
| `v8_api_service` | No repo, not running |
| `openclaw_service` | No repo, not running |

---

## Dependencies (External Infrastructure)

| Resource | Provider | Used By |
|---|---|---|
| **PostgreSQL** | DigitalOcean Managed DB (`resonant-db`) | All services share one cluster, each has its own DB/tables |
| **Redis** | Docker `shared_redis` container | Gateway, Chat, Auth, Agent Engine (sessions, cache, rate limiting) |
| **DigitalOcean Spaces** | S3-compatible object storage | Storage service, file uploads |
| **Stripe** | Payment processing | Billing service |
| **GitHub Actions** | CI/CD | Auto-deploy on push (via `deploy-unified.sh`) |

---

## File Structure

```
RG_core/
├── docker-compose.unified.yml    # THE production compose file (910 lines, 30+ services)
├── .env.production.template       # All env vars template (118 lines) — NEVER commit real secrets
├── deploy-unified.sh              # Main deploy script (used by CI/CD)
├── manual-deploy.sh               # Manual deploy helper
├── run_all_tests.sh               # Cross-service test runner
├── pytest.ini                     # Pytest config
├── VERSION                        # Current version (1.0.3)
├── README.txt                     # This file
│
├── scripts/                       # 55 ops/deploy/utility scripts
│   ├── deploy-production.sh       # Production deploy
│   ├── deploy-blue-green.sh       # Blue-green deploy
│   ├── rollback.sh                # Rollback to previous version
│   ├── build_all.sh               # Build all Docker images
│   ├── health_check.sh            # Health check all services
│   ├── status.sh                  # Show service status
│   ├── safe_restart.sh            # Safe rolling restart
│   ├── full_droplet_backup.sh     # Full server backup
│   ├── create_superuser.py        # Create platform superuser
│   ├── create_owner_account.py    # Create owner account
│   ├── setup_stripe_products.py   # Initialize Stripe products/prices
│   ├── generate-production-secrets.sh  # Generate all secrets
│   ├── setup-ssl-certificates.sh  # SSL cert setup
│   ├── setup-firewall.sh          # Server firewall rules
│   ├── verify-production-*.sh     # Production verification scripts
│   └── ... (55 total)
│
├── deploy/                        # Infrastructure-as-code
│   ├── terraform/                 # Terraform configs
│   ├── helm/                      # Helm charts
│   ├── digitalocean/              # DO-specific configs
│   └── README.md
│
├── docker/                        # Extra Dockerfiles
│   ├── gateway.Dockerfile         # Gateway custom Dockerfile
│   └── postgres-replication/      # PostgreSQL replication config
│
├── nginx/                         # Nginx reverse proxy
│   ├── sites-available/           # Nginx site configs
│   └── blockchain_code_routes.conf
│
└── config/                        # Service configs
    └── websocket_self_healing.yaml
```

---

## How Deployment Works

### Server Path
All service repos are cloned at `/home/deploy/{repo_name}` on the production server.
The compose file references them as build contexts:

```yaml
# Example from docker-compose.unified.yml
agent_engine_service:
  build:
    context: /home/deploy/RG_Agent_Engine    # ← standalone repo, NOT inside RG_core
    dockerfile: Dockerfile
```

**CRITICAL**: Build contexts point to `/home/deploy/{repo_name}`, NOT `/home/deploy/genesis2026_production_backend/{repo_name}`. Each service is its own repo at the top level.

### Deploy Flow
```
Local edit → git push → SSH to server → git pull in service repo →
  docker build + docker restart (or deploy-unified.sh for full redeploy)
```

### Manual Deploy (single service)
```bash
ssh deploy@dev-swat.com
cd /home/deploy/{service_repo}
git pull origin main
sudo docker build -t {container_name} .
sudo docker stop {container_name} && sudo docker rm {container_name}
sudo docker run -d --name {container_name} --restart unless-stopped \
  --network genesis2026_production_backend_app-network \
  --env-file /home/deploy/genesis2026_production_backend/.env.production \
  {container_name}:latest
```

### Full Redeploy (all services)
```bash
ssh deploy@dev-swat.com
cd /home/deploy/genesis2026_production_backend
./deploy-unified.sh
```

---

## Environment Variables (.env.production)

The `.env.production.template` contains 118 lines of required variables, grouped:

| Group | Examples |
|---|---|
| **Database** | `AUTH_DATABASE_URL`, `BILLING_DATABASE_URL`, `USER_DATABASE_URL`, ... |
| **Redis** | `REDIS_URL` |
| **JWT/Auth** | `JWT_SECRET_KEY`, `OWNER_SECRET_KEY`, `SERVICE_API_KEY` |
| **Stripe** | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` |
| **LLM Providers** | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY` |
| **Storage** | `SPACES_KEY`, `SPACES_SECRET`, `SPACES_BUCKET`, `SPACES_REGION` |
| **Internal Secrets** | `INTERNAL_API_SECRET` (cross-service auth) |
| **Email** | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` |

---

## Quick Start

```bash
# 1. Clone
git clone git@github-devswat:DevSwat-ResonantGenesis/genesis2026_production_backend.git RG_core

# 2. Configure
cp .env.production.template .env.production
# Edit .env.production with real values

# 3. Deploy
docker compose -f docker-compose.unified.yml up -d

# 4. Check status
docker compose -f docker-compose.unified.yml ps
docker compose -f docker-compose.unified.yml logs -f
```

---

## Version History

| Version | Date | Notes |
|---|---|---|
| 1.0.3 | Current | Nuclear cleanup — 215K lines of dead monorepo code removed |
| 1.0.0 | Jan 2026 | Initial microservices split from monorepo |

---

**Organization**: [DevSwat-ResonantGenesis](https://github.com/DevSwat-ResonantGenesis) | **Platform**: [dev-swat.com](https://dev-swat.com)
