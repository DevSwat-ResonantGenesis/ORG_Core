#!/bin/bash
set -e

# Emergency Rollback Script
# Instantly switches back to previous environment

PROJECT_DIR="/root/genesis2026_production_backend"
CURRENT_FILE="/tmp/current_deployment"
LOG_FILE="/var/log/blue-green-deployment.log"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

if [ ! -f "$CURRENT_FILE" ]; then
    error "No deployment information found"
    exit 1
fi

CURRENT_ENV=$(cat "$CURRENT_FILE")
PREVIOUS_ENV=$([ "$CURRENT_ENV" == "blue" ] && echo "green" || echo "blue")

log "========================================"
log "🚨 EMERGENCY ROLLBACK INITIATED"
log "========================================"
log "Rolling back from $CURRENT_ENV to $PREVIOUS_ENV..."

cd "$PROJECT_DIR"

# Check if previous environment is running
if ! docker ps | grep -q "gateway_$PREVIOUS_ENV"; then
    log "⚠️ Previous environment ($PREVIOUS_ENV) is not running!"
    log "Starting $PREVIOUS_ENV environment..."
    docker-compose -f docker-compose.$PREVIOUS_ENV.yml up -d
    sleep 30
fi

# Switch nginx back
log "🔄 Switching nginx to $PREVIOUS_ENV..."

if [ "$PREVIOUS_ENV" == "blue" ]; then
    sed -i 's/server gateway_green:8000/server gateway_blue:8000/g' nginx/nginx-production-https.conf
else
    sed -i 's/server gateway_blue:8000/server gateway_green:8000/g' nginx/nginx-production-https.conf
fi

# Test and reload nginx
if docker exec genesis_nginx nginx -t 2>&1 | grep -q "successful"; then
    docker exec genesis_nginx nginx -s reload
    log "✅ Nginx reloaded successfully"
else
    error "Nginx configuration test failed!"
    exit 1
fi

# Update marker
echo "$PREVIOUS_ENV" > "$CURRENT_FILE"

log "========================================"
log "✅ ROLLBACK COMPLETE"
log "========================================"
log "🌐 Active environment: $PREVIOUS_ENV"
log "========================================"

# Verify
sleep 5
if curl -sf https://dev-swat.com/health > /dev/null 2>&1; then
    log "✅ Frontend is accessible after rollback"
else
    error "Frontend is not accessible after rollback!"
    exit 1
fi
