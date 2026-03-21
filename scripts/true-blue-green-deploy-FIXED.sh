#!/bin/bash

# TRUE BLUE-GREEN DEPLOYMENT SCRIPT - FIXED VERSION
# Zero-downtime deployment with parallel environments
# CRITICAL FIXES:
# 1. Never stops working environment until new one is proven healthy
# 2. Health checks via Docker network (not localhost)
# 3. Better error handling and logging

PROJECT_DIR="/root/genesis2026_production_backend"
CURRENT_FILE="/root/genesis2026_production_backend/.current-deployment"
LOG_FILE="/var/log/blue-green-deployment.log"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

cd "$PROJECT_DIR"

log "========================================"
log "🔵🟢 TRUE BLUE-GREEN DEPLOYMENT (FIXED)"
log "========================================"

# Determine current and target environments
if [ ! -f "$CURRENT_FILE" ]; then
    CURRENT="none"
    TARGET="blue"
    log "⚠️  No current deployment marker found - first deployment"
else
    CURRENT=$(cat "$CURRENT_FILE")
    if [ "$CURRENT" = "blue" ]; then
        TARGET="green"
    else
        TARGET="blue"
    fi
fi

log "Current environment: $CURRENT"
log "Target environment: $TARGET"

# Verify current environment is actually running
if [ "$CURRENT" != "none" ]; then
    if [ "$CURRENT" = "blue" ]; then
        CURRENT_GATEWAY="blue_gateway"
    else
        CURRENT_GATEWAY="green_gateway"
    fi
    
    if docker ps --format '{{.Names}}' | grep -q "^${CURRENT_GATEWAY}$"; then
        log "✅ Current environment ($CURRENT) is running"
    else
        warn "Current environment ($CURRENT) is NOT running - will start fresh"
        CURRENT="none"
    fi
fi

# Step 1: Pull latest code
log "📥 Pulling latest code from GitHub..."
git pull origin main 2>&1 | tee -a "$LOG_FILE" || log "Using local code"

# Step 2: Build images with git commit hash to bust cache
log "🔨 Building Docker images for $TARGET environment..."
GIT_COMMIT=$(git rev-parse --short HEAD)
log "Git commit: $GIT_COMMIT"

if ! docker-compose build --parallel --build-arg GIT_COMMIT=$GIT_COMMIT 2>&1 | tee -a "$LOG_FILE"; then
    error "Failed to build images"
    exit 1
fi

# Step 3: Ensure shared services are running
log "🔧 Ensuring shared services (Redis) are running..."
docker-compose -f docker-compose.shared.yml up -d 2>&1 | tee -a "$LOG_FILE"

# Step 4: Ensure genesis_network exists
log "🌐 Ensuring genesis_network exists..."
if ! docker network ls --format '{{.Name}}' | grep -q "^genesis_network$"; then
    log "Creating genesis_network..."
    docker network create genesis_network --driver bridge 2>&1 | tee -a "$LOG_FILE"
fi

# Step 5: Ensure nginx is running
log "🔍 Ensuring nginx is running..."
if ! docker ps --format '{{.Names}}' | grep -q "^genesis_nginx$"; then
    log "⚠️  Nginx not running, starting it now..."
    
    docker run -d \
        --name genesis_nginx \
        --network genesis_network \
        -p 80:80 -p 443:443 \
        -v /root/genesis2026_production_backend/nginx/nginx-production-https.conf:/etc/nginx/nginx.conf:ro \
        -v /var/www/frontend:/usr/share/nginx/html:ro \
        -v /etc/letsencrypt:/etc/letsencrypt:ro \
        -v /var/www/certbot:/var/www/certbot:ro \
        nginx:alpine 2>&1 | tee -a "$LOG_FILE"
    
    sleep 3
    log "✅ Nginx started"
else
    log "✅ Nginx already running"
fi

# Step 6: Start target environment (OLD ENVIRONMENT STILL RUNNING!)
log "🚀 Starting $TARGET environment..."
log "⚠️  NOTE: $CURRENT environment will keep running until $TARGET is healthy"

if [ "$TARGET" = "blue" ]; then
    docker-compose -f docker-compose.blue.yml up -d 2>&1 | tee -a "$LOG_FILE"
    TARGET_GATEWAY="blue_gateway"
else
    docker-compose -f docker-compose.green.yml up -d 2>&1 | tee -a "$LOG_FILE"
    TARGET_GATEWAY="green_gateway"
fi

# Step 7: Wait for services to be ready
log "⏳ Waiting for $TARGET environment to be ready (60 seconds)..."
sleep 60

# Step 8: Health check target environment via Docker network
log "🏥 Running health checks on $TARGET environment..."
log "🔍 Checking via Docker network (not localhost)"

MAX_ATTEMPTS=20
ATTEMPT=0
HEALTH_CHECK_PASSED=false

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    ATTEMPT=$((ATTEMPT + 1))
    log "⏳ Health check attempt $ATTEMPT/$MAX_ATTEMPTS..."
    
    # Check if gateway container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${TARGET_GATEWAY}$"; then
        warn "Gateway container not running yet"
        sleep 10
        continue
    fi
    
    # Check health via Docker network from nginx container
    if docker exec genesis_nginx curl -sf http://${TARGET_GATEWAY}:8000/health > /dev/null 2>&1; then
        HEALTH_CHECK_PASSED=true
        log "✅ Gateway health check passed!"
        break
    else
        warn "Health check failed, retrying..."
    fi
    
    sleep 10
done

# Step 9: Handle health check result
if [ "$HEALTH_CHECK_PASSED" = false ]; then
    error "$TARGET environment failed health checks after $MAX_ATTEMPTS attempts"
    
    # Show gateway logs for debugging
    log "📋 Gateway logs (last 30 lines):"
    docker logs ${TARGET_GATEWAY} 2>&1 | tail -30 | tee -a "$LOG_FILE"
    
    # CRITICAL: Stop only the NEW environment, keep OLD running
    log "🔄 Rolling back - stopping $TARGET environment ONLY"
    log "✅ $CURRENT environment will continue serving traffic"
    
    if [ "$TARGET" = "blue" ]; then
        docker-compose -f docker-compose.blue.yml down 2>&1 | tee -a "$LOG_FILE"
    else
        docker-compose -f docker-compose.green.yml down 2>&1 | tee -a "$LOG_FILE"
    fi
    
    error "Deployment failed - $CURRENT environment still active"
    exit 1
fi

log "✅ $TARGET environment health check passed"

# Step 10: Update nginx to point to target environment
log "🔄 Switching nginx to $TARGET environment..."

# Create nginx upstream config
cat > /tmp/nginx-upstream.conf << EOF
upstream backend {
    server ${TARGET_GATEWAY}:8000;
}
EOF

# Copy to nginx container
if ! docker cp /tmp/nginx-upstream.conf genesis_nginx:/etc/nginx/conf.d/upstream.conf 2>&1 | tee -a "$LOG_FILE"; then
    error "Failed to copy nginx config"
    exit 1
fi

# Test nginx config
if ! docker exec genesis_nginx nginx -t 2>&1 | tee -a "$LOG_FILE"; then
    error "Nginx configuration test failed"
    exit 1
fi

# Reload nginx (zero downtime!)
log "🔄 Reloading nginx..."
if ! docker exec genesis_nginx nginx -s reload 2>&1 | tee -a "$LOG_FILE"; then
    error "Failed to reload nginx"
    exit 1
fi

log "✅ Traffic switched to $TARGET environment"

# Step 11: Monitor target environment for stability
log "👀 Monitoring $TARGET environment for 30 seconds..."
sleep 30

# Final health check via Docker network
if docker exec genesis_nginx curl -sf http://${TARGET_GATEWAY}:8000/health > /dev/null 2>&1; then
    log "✅ $TARGET environment is stable after traffic switch"
else
    error "$TARGET environment became unhealthy after traffic switch"
    
    # Rollback to current environment if it exists
    if [ "$CURRENT" != "none" ]; then
        log "🔄 Rolling back to $CURRENT environment"
        
        if [ "$CURRENT" = "blue" ]; then
            ROLLBACK_GATEWAY="blue_gateway"
        else
            ROLLBACK_GATEWAY="green_gateway"
        fi
        
        cat > /tmp/nginx-upstream.conf << EOF
upstream backend {
    server ${ROLLBACK_GATEWAY}:8000;
}
EOF
        docker cp /tmp/nginx-upstream.conf genesis_nginx:/etc/nginx/conf.d/upstream.conf
        docker exec genesis_nginx nginx -s reload
        
        log "✅ Rolled back to $CURRENT environment"
    fi
    
    exit 1
fi

# Step 12: Stop old environment (ONLY after new one is proven stable)
if [ "$CURRENT" != "none" ]; then
    log "🛑 Stopping $CURRENT environment (new environment is stable)..."
    
    if [ "$CURRENT" = "blue" ]; then
        docker-compose -f docker-compose.blue.yml down 2>&1 | tee -a "$LOG_FILE"
    else
        docker-compose -f docker-compose.green.yml down 2>&1 | tee -a "$LOG_FILE"
    fi
    
    log "✅ $CURRENT environment stopped"
else
    log "ℹ️  No previous environment to stop (first deployment)"
fi

# Step 13: Update current deployment marker
echo "$TARGET" > "$CURRENT_FILE"
log "✅ Updated deployment marker: $TARGET"

# Step 14: Final verification
log "🔍 Final verification..."
if docker exec genesis_nginx curl -sf http://${TARGET_GATEWAY}:8000/health > /dev/null 2>&1; then
    log "✅ Final health check passed"
else
    error "Final health check failed - but deployment marked as complete"
fi

log "========================================"
log "✅ BLUE-GREEN DEPLOYMENT COMPLETE!"
log "========================================"
log "Previous environment: $CURRENT"
log "Active environment: $TARGET"
log "Gateway: ${TARGET_GATEWAY}:8000"
log "Deployment marker: $(cat $CURRENT_FILE)"
log "========================================"

exit 0
