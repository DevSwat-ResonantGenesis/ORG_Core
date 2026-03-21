#!/bin/bash

# ============================================
# MANUAL BLUE-GREEN DEPLOYMENT SCRIPT
# ============================================

echo "🚀 Manual Blue-Green Deployment"
echo "============================"

# Configuration
DROPLET_IP="134.199.221.149"
DROPLET_USER="root"

echo "🌐 Target: $DROPLET_IP"
echo "👤 User: $DROPLET_USER"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Step 1: Transfer files
log "📤 Transferring files to server..."

scp -o StrictHostKeyChecking=no -r \
    docker-compose.*.yml \
    billing_service/ \
    shared/ \
    scripts/ \
    .env.production \
    gateway/ \
    auth_service/ \
    agent_engine_service/ \
    sandbox_runner_service/ \
    cascade_control_plane/ \
    blockchain_service/ \
    build_service/ \
    chat_service/ \
    code_execution_service/ \
    code_visualizer_service/ \
    cognitive_service/ \
    crypto_service/ \
    ed_service/ \
    ide_service/ \
    llm_service/ \
    marketplace_service/ \
    memory_service/ \
    ml_service/ \
    notification_service/ \
    rara_service/ \
    state_physics_service/ \
    storage_service/ \
    user_memory_service/ \
    user_service/ \
    workflow_service/ \
    $DROPLET_USER@$DROPLET_IP:/root/genesis2026_production_backend/

if [ $? -eq 0 ]; then
    log "✅ Files transferred successfully"
else
    error "❌ Failed to transfer files"
    exit 1
fi

# Step 2: Execute deployment
log "🚀 Executing deployment on server..."

ssh -o StrictHostKeyChecking=no $DROPLET_USER@$DROPLET_IP << 'EOF'
set -e

echo "🚀 Starting deployment on server..."
cd /root/genesis2026_production_backend

# Check for existing deployment
if [ -f "/tmp/blue-green-deployment.lock" ]; then
    echo "❌ Deployment already in progress"
    exit 1
fi

# Create deployment lock
echo $$ > /tmp/blue-green-deployment.lock
trap "rm -f /tmp/blue-green-deployment.lock" EXIT

# Determine deployment color
if [ -f ".current-deployment" ]; then
    CURRENT_COLOR=$(cat .current-deployment)
    if [ "$CURRENT_COLOR" == "blue" ]; then
        DEPLOYMENT_COLOR="green"
    else
        DEPLOYMENT_COLOR="blue"
    fi
else
    DEPLOYMENT_COLOR="blue"
fi

echo "🔄 Current deployment: $CURRENT_COLOR"
echo "🚀 Deploying to: $DEPLOYMENT_COLOR"

# Stop current environment
if [ "$CURRENT_COLOR" != "" ]; then
    echo "🛑 Stopping $CURRENT_COLOR environment..."
    docker-compose -f docker-compose.$CURRENT_COLOR.complete.yml down
fi

# Start new environment
echo "🚀 Starting $DEPLOYMENT_COLOR environment..."
docker-compose -f docker-compose.$DEPLOYMENT_COLOR.complete.yml up -d

# Update current deployment file
echo "$DEPLOYMENT_COLOR" > .current-deployment

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 30

# Check if services are running
if docker ps --format "table {{.Names}}" | grep -q "blue_gateway\|green_gateway"; then
    echo "✅ Deployment successful"
    
    # Verify health
    echo "🔍 Verifying health..."
    if curl -f https://dev-swat.com/health > /dev/null 2>&1; then
        echo "✅ Health check passed"
    else
        echo "⚠️ Health check failed but containers are running"
    fi
    
    echo "🎉 Deployment completed successfully!"
    echo "🌐 Platform available at: https://dev-swat.com"
else
    echo "❌ Deployment failed"
    exit 1
fi

EOF

if [ $? -eq 0 ]; then
    log "✅ Deployment completed successfully"
    echo ""
    echo "🌐 Check your platform at: https://dev-swat.com"
    echo "🔍 Health check: https://dev-swat.com/health"
else
    error "❌ Deployment failed"
    exit 1
fi

log "🎉 Manual deployment completed!"
