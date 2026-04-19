#!/bin/bash
set -euo pipefail

# ============================================
# UNIFIED PRODUCTION DEPLOYMENT
# Single docker-compose.unified.yml — no blue/green
# ============================================

DROPLET_IP="dev-swat.com"
DROPLET_USER="deploy"
DEPLOY_DIR="/home/deploy"
COMPOSE_DIR="/home/deploy/genesis2026_production_backend"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()     { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn()    { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠️${NC} $1"; }
error()   { echo -e "${RED}[$(date '+%H:%M:%S')] ❌${NC} $1"; }
section() { echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; }

# ============================================
# REPOS TO PULL ON SERVER
# ============================================
REPOS=(
    "RG_Gateway"
    "RG_Auth"
    "RG_Billing"
    "RG_Chat"
    "RG_LLM_Service"
    "RG_Memory"
    "RG_User_Service"
    "RG_Workflow"
    "RG_Storage"
    "RG_Notifications"
    "RG_Crypto"
    "RG_Blockchain"
    "RG_Code_Execution"
    "RG_Agent_Engine"
    "RG_agent_architect"
    "RG_Sandbox_Runner"
    "RG_AST_analysis"
    "RG_Internal_Invarients_SIM"
    "RG_Users_Invarients_SIM"
    "RG_Ed_Service"
    "RG_Mining"
    "RG_lighthouse"
    "RG_external_blockchain"
)

# ============================================
# SERVICES TO HEALTH-CHECK AFTER DEPLOY
# ============================================
HEALTH_SERVICES=(
    "gateway:8001"
    "chat_service:8000"
    "llm_service:8000"
    "agent_engine_service:8000"
    "agent_architect:8000"
    "auth_service:8000"
    "billing_service:8000"
    "memory_service:8000"
)

section "UNIFIED PRODUCTION DEPLOYMENT"
echo "Target: $DROPLET_USER@$DROPLET_IP"
echo "Compose: docker-compose.unified.yml"
echo ""

# ============================================
# STEP 1: Push RG_core (docker-compose + scripts)
# ============================================
section "STEP 1: Push RG_core to GitHub"
cd "$(dirname "$0")"
if git diff --quiet && git diff --cached --quiet; then
    log "RG_core already up to date"
else
    warn "RG_core has uncommitted changes — commit first"
    exit 1
fi
git push origin main 2>&1 | tail -2
log "RG_core pushed"

# ============================================
# STEP 2: SSH to server, pull all repos
# ============================================
section "STEP 2: Pull all repos on server"

ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 $DROPLET_USER@$DROPLET_IP << 'PULL_EOF'
set -e
cd /home/deploy

echo "📥 Pulling all repos..."
FAILED=""
for repo in RG_Gateway RG_Auth RG_Billing RG_Chat RG_LLM_Service RG_Memory RG_User_Service \
            RG_Workflow RG_Storage RG_Notifications RG_Crypto RG_Blockchain RG_Code_Execution \
            RG_Agent_Engine RG_agent_architect RG_Sandbox_Runner RG_AST_analysis \
            RG_Internal_Invarients_SIM RG_Users_Invarients_SIM RG_Ed_Service \
            RG_Mining RG_lighthouse RG_external_blockchain; do
    if [ -d "$repo" ]; then
        echo -n "  $repo ... "
        cd "$repo"
        if git pull --ff-only origin main 2>/dev/null; then
            echo "✅"
        else
            echo "⚠️ (trying reset)"
            git fetch origin main && git reset --hard origin/main && echo "  ✅ (reset)"
            FAILED="$FAILED $repo(reset)"
        fi
        cd /home/deploy
    else
        echo "  $repo ... ❌ NOT FOUND"
        FAILED="$FAILED $repo(missing)"
    fi
done

# Also pull RG_core (contains docker-compose)
echo -n "  ORG_Core (RG_core) ... "
cd /home/deploy/genesis2026_production_backend
git pull --ff-only origin main 2>/dev/null && echo "✅" || (git fetch origin main && git reset --hard origin/main && echo "✅ (reset)")

if [ -n "$FAILED" ]; then
    echo ""
    echo "⚠️ Issues: $FAILED"
fi
echo "📥 All repos pulled"
PULL_EOF

log "All repos pulled on server"

# ============================================
# STEP 3: Build and deploy with unified compose
# ============================================
section "STEP 3: Build & Deploy (docker-compose.unified.yml)"

ssh -o StrictHostKeyChecking=no $DROPLET_USER@$DROPLET_IP << 'DEPLOY_EOF'
set -e
cd /home/deploy/genesis2026_production_backend

# Lock
if [ -f "/tmp/deploy.lock" ]; then
    PID=$(cat /tmp/deploy.lock)
    if kill -0 "$PID" 2>/dev/null; then
        echo "❌ Deployment already in progress (PID $PID)"
        exit 1
    fi
fi
echo $$ > /tmp/deploy.lock
trap "rm -f /tmp/deploy.lock" EXIT

echo "🏗️  Building and deploying..."

# Stop old blue/green if running
for f in docker-compose.blue.complete.yml docker-compose.green.complete.yml; do
    if [ -f "$f" ]; then
        echo "🛑 Stopping old $f..."
        docker-compose -f "$f" down --remove-orphans 2>/dev/null || true
    fi
done

# Deploy unified
docker-compose -f docker-compose.unified.yml pull --ignore-pull-failures 2>/dev/null || true
docker-compose -f docker-compose.unified.yml build --parallel 2>&1 | tail -5
docker-compose -f docker-compose.unified.yml up -d --remove-orphans 2>&1 | tail -10

echo "unified" > .current-deployment
echo "⏳ Waiting 30s for services to start..."
sleep 30

# Health checks
echo ""
echo "🔍 Health checks:"
HEALTHY=0
TOTAL=0
for svc_port in gateway:8001 chat_service:8000 llm_service:8000 agent_engine_service:8000 \
                agent_architect:8000 auth_service:8000 billing_service:8000 memory_service:8000 \
                shared_redis:6379; do
    SVC=$(echo "$svc_port" | cut -d: -f1)
    PORT=$(echo "$svc_port" | cut -d: -f2)
    TOTAL=$((TOTAL + 1))
    
    if [ "$SVC" = "shared_redis" ]; then
        if docker exec "$SVC" redis-cli ping 2>/dev/null | grep -q PONG; then
            echo "  ✅ $SVC"
            HEALTHY=$((HEALTHY + 1))
        else
            echo "  ❌ $SVC"
        fi
    else
        if docker exec "$SVC" python -c "import urllib.request; urllib.request.urlopen('http://localhost:$PORT/health', timeout=5)" 2>/dev/null; then
            echo "  ✅ $SVC"
            HEALTHY=$((HEALTHY + 1))
        else
            echo "  ⚠️  $SVC (may still be starting)"
        fi
    fi
done

echo ""
echo "📊 $HEALTHY/$TOTAL services healthy"

# Show running containers
echo ""
echo "🐳 Running containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -30

echo ""
echo "🎉 Deployment complete!"
echo "🌐 https://dev-swat.com"
DEPLOY_EOF

log "Deployment completed"
section "DONE"
echo "🌐 Platform: https://dev-swat.com"
echo "🔍 Health:   https://dev-swat.com/health"
