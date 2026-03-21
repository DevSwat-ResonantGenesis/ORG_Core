#!/bin/bash

# TRUE BLUE-GREEN DEPLOYMENT SCRIPT
# Zero-downtime deployment with parallel environments

PROJECT_DIR="/root/genesis2026_production_backend"
CURRENT_FILE="/tmp/current_deployment"
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

cd "$PROJECT_DIR"

log "========================================"
log "🔵🟢 TRUE BLUE-GREEN DEPLOYMENT"
log "========================================"

# Determine current and target environments
if [ ! -f "$CURRENT_FILE" ]; then
    CURRENT="none"
    TARGET="blue"
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

# Step 1: Pull latest code
log "📥 Pulling latest code from GitHub..."
git pull origin main || log "Using local code"

# Step 2: Build images with git commit hash to bust cache
log "🔨 Building Docker images for $TARGET environment..."
GIT_COMMIT=$(git rev-parse --short HEAD)
log "Git commit: $GIT_COMMIT"

# Build with build arg to bust cache only for code changes
if ! docker-compose build --parallel --build-arg GIT_COMMIT=$GIT_COMMIT 2>&1 | tee -a "$LOG_FILE"; then
    error "Failed to build images"
    exit 1
fi

# Step 3: Ensure shared services are running
log "🔧 Ensuring shared services (Redis) are running..."
docker-compose -f docker-compose.shared.yml up -d 2>&1 | tee -a "$LOG_FILE"

# Step 4: Start target environment
log "🚀 Starting $TARGET environment..."
if [ "$TARGET" = "blue" ]; then
    docker-compose -f docker-compose.blue.yml up -d 2>&1 | tee -a "$LOG_FILE"
    TARGET_PORT=8000
else
    docker-compose -f docker-compose.green.yml up -d 2>&1 | tee -a "$LOG_FILE"
    TARGET_PORT=8001
fi

# Step 5: Wait for services to be ready
log "⏳ Waiting for $TARGET environment to be ready..."
sleep 90

# Step 6: Health checks
log "🏥 Running health checks on $TARGET environment..."
MAX_RETRIES=10
RETRY_COUNT=0

# Determine gateway container name
if [ "$TARGET" = "blue" ]; then
    GATEWAY_CONTAINER="blue_gateway"
else
    GATEWAY_CONTAINER="green_gateway"
fi

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Check if container exists and is running
    if docker ps --format '{{.Names}}' | grep -q "^${GATEWAY_CONTAINER}$"; then
        # Check health endpoint inside the container
        if docker exec "$GATEWAY_CONTAINER" curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            log "✅ $TARGET environment health check passed"
            break
        fi
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    log "⏳ Health check attempt $RETRY_COUNT/$MAX_RETRIES..."
    sleep 5
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    error "$TARGET environment failed health checks"
    log "🔄 Rolling back - stopping $TARGET environment"
    if [ "$TARGET" = "blue" ]; then
        docker-compose -f docker-compose.blue.yml down
    else
        docker-compose -f docker-compose.green.yml down
    fi
    exit 1
fi

# Step 7: Ensure nginx is running
log "🔍 Checking nginx status..."
if ! docker ps --format '{{.Names}}' | grep -q "^genesis_nginx$"; then
    log "⚠️  Nginx not running, starting it now..."
    
    # Ensure genesis_network exists
    if ! docker network ls --format '{{.Name}}' | grep -q "^genesis_network$"; then
        log "Creating genesis_network..."
        docker network create genesis_network --driver bridge 2>&1 | tee -a "$LOG_FILE"
    fi
    
    # Start nginx
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
fi

# Step 8: Update nginx to point to target environment
log "🔄 Switching nginx to $TARGET environment..."

# Determine the correct backend server name
if [ "$TARGET" = "blue" ]; then
    BACKEND_SERVER="blue_gateway"
else
    BACKEND_SERVER="green_gateway"
fi

# Update nginx upstream config dynamically (zero-downtime)
log "Updating nginx upstream to $BACKEND_SERVER..."

# Create nginx upstream config
cat > /tmp/nginx-upstream.conf << EOF
upstream gateway_backend {
    server ${BACKEND_SERVER}:8000;
    keepalive 64;
}
EOF

# Copy to nginx container
docker cp /tmp/nginx-upstream.conf genesis_nginx:/etc/nginx/conf.d/upstream.conf 2>&1 | tee -a "$LOG_FILE"

# Test nginx config
if ! docker exec genesis_nginx nginx -t 2>&1 | tee -a "$LOG_FILE"; then
    error "Nginx configuration test failed"
    exit 1
fi

# Reload nginx (zero downtime - does NOT restart container!)
log "🔄 Reloading nginx configuration..."
docker exec genesis_nginx nginx -s reload 2>&1 | tee -a "$LOG_FILE"

log "✅ Traffic switched to $TARGET environment"

# Step 7: Monitor target environment
log "👀 Monitoring $TARGET environment for 30 seconds..."
sleep 30

# Check if target environment is still healthy
if docker exec "$GATEWAY_CONTAINER" curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    log "✅ $TARGET environment is stable"
else
    error "$TARGET environment became unhealthy"
    log "🔄 Rolling back to $CURRENT environment"
    
    # Rollback nginx to current environment (zero-downtime)
    if [ "$CURRENT" = "blue" ]; then
        ROLLBACK_SERVER="blue_gateway"
    elif [ "$CURRENT" = "green" ]; then
        ROLLBACK_SERVER="green_gateway"
    else
        error "No environment to rollback to"
        exit 1
    fi
    
    cat > /tmp/nginx-upstream.conf << EOF
upstream gateway_backend {
    server ${ROLLBACK_SERVER}:8000;
    keepalive 64;
}
EOF
    docker cp /tmp/nginx-upstream.conf genesis_nginx:/etc/nginx/conf.d/upstream.conf
    docker exec genesis_nginx nginx -s reload
    exit 1
fi

# Step 10: Stop old environment
if [ "$CURRENT" != "none" ]; then
    log "🛑 Stopping $CURRENT environment..."
    if [ "$CURRENT" = "blue" ]; then
        docker-compose -f docker-compose.blue.yml down
    else
        docker-compose -f docker-compose.green.yml down
    fi
    log "✅ $CURRENT environment stopped"
fi

# Step 10: Update current deployment marker
echo "$TARGET" > "$CURRENT_FILE"

log "========================================"
log "✅ BLUE-GREEN DEPLOYMENT COMPLETE!"
log "========================================"
log "Previous environment: $CURRENT"
log "Active environment: $TARGET"
log "Port: $TARGET_PORT"
log "========================================"

exit 0
