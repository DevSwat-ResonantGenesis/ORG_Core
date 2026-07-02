# Action Plan — Infra Restore & Frontier TrainingNet (2026-07-01)

Captured from owner request. Not yet executed — queued while the hash-sphere
memory work continues. Server: `ssh root@64.23.166.35`; unified compose at
`/home/deploy/genesis2026_production_backend/docker-compose.unified.yml`.

## 1. Fold orphan containers back into the unified deployment
These run today from a separate/legacy compose and show as "orphan containers"
on every unified deploy (risking accidental `--remove-orphans` wipes):
- `discord_bridge_service`  → context `/home/deploy/RG_Discord_Bridge`
- `openclaw_service`        → context `/home/deploy/RG_OpenClaw`
- `public_guest_chat_service` → context `/home/deploy/RG_Public-Guest-Agentic_Chat`

Steps: add each as a service block in `docker-compose.unified.yml` (build
context, env_file `./.env.production`, network `app-network`, restart policy,
healthcheck) exactly mirroring their current runtime env; `docker compose up -d`
the three; confirm no more orphan warnings; add their repos to
`deploy-unified.sh` REPOS so they pull on deploy.

## 2. OpenClaw connector page + extension downloader (frontend)
Restore the OpenClaw connector UI in `ORG_Frontend` with a download button for
the browser/desktop extension.
- Find the prior OpenClaw page/route (search ORG_Frontend history + RG_OpenClaw
  for the extension artifact / release URL).
- Restore route (e.g. `/openclaw` or `/connect`), wire the "Download extension"
  button to the packaged artifact (host in RG_Storage/Spaces or GitHub release).
- Verify `openclaw_service` endpoints the page calls are reachable via gateway.

## 3. Miner page + downloader (frontend + RG_miner_app)
Let users see and download the miner.
- `RG_miner_app` is in git but NOT cloned/deployed on the server. It's the P2P
  distributed-training client (microbatch_engine, moe_architecture, real_trainer,
  webrtc_client, server.py).
- Package a downloadable miner build (installer / zip / release), host it.
- Restore/build a "Miner" page in ORG_Frontend: shows network/mining status
  (from `mining_service` / `lighthouse_service`) + download button.
- Decide: does the miner run as an on-server container too, or purely a
  client download for external nodes? (It's a node app → likely download-only,
  plus optionally 1 seed node on-server.)

## 4. Frontier-LLM Training Blockchain — verify it actually works
The TrainingNet stack (chain + mining + lighthouse) is deployed & healthy, but
verify it's doing real work for frontier-model training:
- `external_blockchain_service` (RG_TrainingNet_Chain), `mining_service`
  (RG_TrainingNet_Mining), `lighthouse_service` (RG_TrainingNet_Lighthouse) are
  Up/healthy.
- Also deploy the `mining_public` / `mining_internal` split from
  `RG_TrainingNet_Mining/docker-compose.production.yml` (unified only runs one
  `mining_service`).
- Verify: are training jobs/microbatches being mined? Is the chain anchoring to
  Base Sepolia (spec: at least hourly)? Are miners rewarded? Is a frontier model
  actually being trained/aggregated (MoE)? Add health/status checks + a smoke
  test that submits a microbatch and confirms it lands on-chain.

## 5. Also-not-deployed backend services (separate, non-blockchain)
Present on server with Dockerfiles but not in unified compose or running:
`RG_Integrations`, `RG_Platform_API`, `RG_System_Agents`. Decide per-service
whether to wire into unified + deploy, or archive.
