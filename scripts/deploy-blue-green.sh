#!/bin/bash

# Simplified Rolling Update Deployment
# Uses existing images, no rebuild needed

PROJECT_DIR="/root/genesis2026_production_backend"
LOG_FILE="/var/log/blue-green-deployment.log"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

cd "$PROJECT_DIR"

log "========================================"
log "ROLLING UPDATE DEPLOYMENT"
log "========================================"

# Step 1: Pull latest code
log "📥 Pulling latest code from GitHub..."
git pull origin main || log "Using local code"

# Step 2: Pull pre-built images (don't fail if images are local)
log "📦 Pulling pre-built images..."
docker-compose pull 2>&1 | tee -a "$LOG_FILE" || true

# Step 3: Rolling update - restart services one by one
log "🔄 Performing rolling update of services..."

# List of backend services
SERVICES=("gateway" "auth_service" "llm_service" "blockchain_service" "crypto_service" 
          "chat_service" "memory_service" "user_service" "ml_service" "workflow_service"
          "marketplace_service" "billing_service" "notification_service" "storage_service"
          "build_service" "code_execution_service" "ide_service" "agent_engine_service"
          "cascade_control_plane" "code_visualizer_service" "rara_service" 
          "state_physics_service" "user_memory_service" "node_service" "ed_service"
          "cognitive_service")

FAILED_SERVICES=()
UPDATED_COUNT=0

for service in "${SERVICES[@]}"; do
    log "🔄 Updating $service..."
    
    if docker-compose up -d --no-deps --force-recreate "$service" 2>&1 | tee -a "$LOG_FILE"; then
        log "✅ $service updated"
        ((UPDATED_COUNT++))
        sleep 2
    else
        error "❌ Failed to update $service"
        FAILED_SERVICES+=("$service")
    fi
done

# Step 4: Health checks
log "🏥 Running health checks..."
sleep 10

HEALTH_PASSED=false
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    log "✅ Gateway health check passed"
    HEALTH_PASSED=true
else
    error "Gateway health check failed"
fi

log "========================================"
log "✅ DEPLOYMENT COMPLETE!"
log "========================================"
log "Updated services: $UPDATED_COUNT/${#SERVICES[@]}"
log "Failed services: ${#FAILED_SERVICES[@]}"
if [ ${#FAILED_SERVICES[@]} -gt 0 ]; then
    log "Failed: ${FAILED_SERVICES[*]}"
fi
log "========================================"

# Exit with appropriate code
if [ "$HEALTH_PASSED" = true ] && [ ${#FAILED_SERVICES[@]} -eq 0 ]; then
    exit 0
else
    exit 1
fi
