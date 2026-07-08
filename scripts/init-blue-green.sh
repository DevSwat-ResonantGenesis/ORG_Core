#!/bin/bash
set -e

# Blue-Green Deployment Initialization Script
# Sets up the blue-green deployment infrastructure

PROJECT_DIR="/root/genesis2026_production_backend"
CURRENT_FILE="/tmp/current_deployment"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

cd "$PROJECT_DIR"

log "========================================"
log "BLUE-GREEN DEPLOYMENT INITIALIZATION"
log "========================================"

# Step 1: Create shared network
log "📡 Creating shared network..."
docker network create shared-network 2>/dev/null || log "Network already exists"

# Step 2: Start shared resources (Redis)
log "🚀 Starting shared Redis..."
docker-compose -f docker-compose.shared.yml up -d

# Step 3: Wait for Redis to be ready
log "⏳ Waiting for Redis to be ready..."
sleep 10

# Step 4: Copy current docker-compose to blue
log "📋 Creating blue environment configuration..."
cp docker-compose.yml docker-compose.blue.yml

# Modify blue to use blue network and container names
sed -i 's/name: genesis_backend_3/name: genesis_backend_blue/g' docker-compose.blue.yml
sed -i 's/container_name: genesis_nginx/container_name: genesis_nginx_blue/g' docker-compose.blue.yml
sed -i 's/- app-network/- blue-network\n    - shared-network/g' docker-compose.blue.yml

# Add blue network definition
cat >> docker-compose.blue.yml << 'EOFBLUE'

networks:
  blue-network:
    name: blue-network
    driver: bridge
  shared-network:
    external: true
EOFBLUE

# Step 5: Create green environment
log "�� Creating green environment configuration..."
cp docker-compose.yml docker-compose.green.yml

# Modify green to use green network and different ports
sed -i 's/name: genesis_backend_3/name: genesis_backend_green/g' docker-compose.green.yml
sed -i 's/container_name: genesis_nginx/container_name: genesis_nginx_green/g' docker-compose.green.yml
sed -i 's/"8000:8000"/"8001:8000"/g' docker-compose.green.yml
sed -i 's/- app-network/- green-network\n    - shared-network/g' docker-compose.green.yml

# Add green network definition
cat >> docker-compose.green.yml << 'EOFGREEN'

networks:
  green-network:
    name: green-network
    driver: bridge
  shared-network:
    external: true
EOFGREEN

# Step 6: Update nginx configuration for blue-green
log "🔧 Updating nginx configuration..."
cat > nginx/nginx-blue-green.conf << 'EOFNGINX'
# Blue-Green Deployment Nginx Configuration

upstream backend_gateway {
    server genesis_backend_blue-gateway-1:8000;
}

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss application/rss+xml font/truetype font/opentype application/vnd.ms-fontobject image/svg+xml;

    server {
        listen 80;
        server_name dev-swat.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name dev-swat.com;

        # SSL Configuration
        ssl_certificate /etc/letsencrypt/live/dev-swat.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/dev-swat.com/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # Security Headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;

        # API Gateway
        location /api/ {
            proxy_pass http://backend_gateway;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_buffering off;
            proxy_request_buffering off;
        }

        location /health {
            proxy_pass http://backend_gateway/health;
            proxy_set_header Host $host;
        }

        # Frontend
        location / {
            root /usr/share/nginx/html;
            try_files $uri $uri/ /index.html;
            expires 1h;
            add_header Cache-Control "public, must-revalidate";
        }

        # Static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            root /usr/share/nginx/html;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
EOFNGINX

# Step 7: Set blue as initial environment
log "🔵 Setting blue as initial active environment..."
echo "blue" > "$CURRENT_FILE"

# Step 8: Start blue environment
log "🚀 Starting blue environment..."
docker-compose -f docker-compose.blue.yml up -d

log "⏳ Waiting for blue environment to be ready..."
sleep 45

# Step 9: Verify blue environment
log "🏥 Verifying blue environment..."
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    log "✅ Blue environment is healthy"
else
    log "⚠️ Blue environment health check failed (this is normal on first start)"
fi

log "========================================"
log "✅ BLUE-GREEN DEPLOYMENT INITIALIZED"
log "========================================"
log ""
log "Next steps:"
log "1. Verify blue environment: curl http://localhost:8000/health"
log "2. Deploy to green: ./scripts/deploy-blue-green.sh"
log "3. Check status: ./scripts/status.sh"
log "4. Rollback if needed: ./scripts/rollback.sh"
log ""
log "========================================"
