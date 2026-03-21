#!/bin/bash
# ResonantGenesis - DigitalOcean Deployment Script
# For Ubuntu 22.04 LTS Droplet

set -e

echo "=== ResonantGenesis Production Deployment ==="

# Configuration
DOMAIN="${DOMAIN:-resonantgenesis.ai}"
EMAIL="${EMAIL:-admin@resonantgenesis.ai}"
DROPLET_SIZE="s-4vcpu-8gb"  # Good for 100-200 users

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    error "Please run as root (sudo ./deploy-digitalocean.sh)"
fi

# Step 1: System Updates
log "Updating system packages..."
apt-get update && apt-get upgrade -y

# Step 2: Install Docker
log "Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    systemctl enable docker
    systemctl start docker
fi

# Step 3: Install Docker Compose
log "Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Step 4: Configure Firewall
log "Configuring firewall..."
ufw --force enable
ufw allow ssh
ufw allow http
ufw allow https
ufw allow 8000  # API
ufw allow 8080  # IDE

# Step 5: Create Swap (for memory management)
log "Creating swap space..."
if [ ! -f /swapfile ]; then
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl vm.swappiness=10
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi

# Step 6: Create application directory
log "Setting up application directory..."
mkdir -p /opt/resonantgenesis
cd /opt/resonantgenesis

# Step 7: Clone repositories (if not exists)
if [ ! -d "resonantgenesis_backend" ]; then
    log "Cloning backend repository..."
    git clone https://github.com/louienemesh/-resonantgenesis-backend.git resonantgenesis_backend
fi

if [ ! -d "resonantgenesis_frontend" ]; then
    log "Cloning frontend repository..."
    git clone https://github.com/louienemesh/resonantgenesis_frontend.git resonantgenesis_frontend
fi

if [ ! -d "resonantgenesis_IDE" ]; then
    log "Cloning IDE repository..."
    git clone https://github.com/louienemesh/resonantgenesis_IDE.git resonantgenesis_IDE
fi

# Step 8: Create environment file
log "Creating environment file..."
if [ ! -f ".env" ]; then
    cat > .env << EOF
# Database
DB_PASSWORD=$(openssl rand -base64 32)

# JWT
JWT_SECRET_KEY=$(openssl rand -base64 64)

# LLM Keys (replace with your keys)
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Stripe (replace with your keys)
STRIPE_SECRET_KEY=sk_live_your-stripe-secret
STRIPE_PUBLISHABLE_KEY=pk_live_your-stripe-publishable
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret

# GitHub
GITHUB_TOKEN=ghp_your-github-token

# Domain
DOMAIN=${DOMAIN}
EOF
    warn "Please edit /opt/resonantgenesis/.env with your actual API keys!"
fi

# Step 9: Setup Nginx configuration
log "Setting up Nginx configuration..."
mkdir -p resonantgenesis_backend/nginx/ssl
cat > resonantgenesis_backend/nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server gateway:8000;
    }

    upstream frontend {
        server frontend:80;
    }

    upstream ide {
        server ide:8080;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;
    limit_conn_zone $binary_remote_addr zone=conn:10m;

    server {
        listen 80;
        server_name _;
        
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }
        
        location / {
            return 301 https://$host$request_uri;
        }
    }

    server {
        listen 443 ssl http2;
        server_name api.resonantgenesis.ai;

        ssl_certificate /etc/nginx/ssl/live/resonantgenesis.ai/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/live/resonantgenesis.ai/privkey.pem;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        location / {
            limit_req zone=api burst=50 nodelay;
            limit_conn conn 100;
            
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

    server {
        listen 443 ssl http2;
        server_name resonantgenesis.ai www.resonantgenesis.ai;

        ssl_certificate /etc/nginx/ssl/live/resonantgenesis.ai/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/live/resonantgenesis.ai/privkey.pem;

        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }

    server {
        listen 443 ssl http2;
        server_name ide.resonantgenesis.ai;

        ssl_certificate /etc/nginx/ssl/live/resonantgenesis.ai/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/live/resonantgenesis.ai/privkey.pem;

        location / {
            proxy_pass http://ide;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
EOF

# Step 10: Build and start services
log "Building and starting services..."
cd resonantgenesis_backend
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Step 11: Setup SSL with Certbot
log "Setting up SSL certificates..."
docker-compose -f docker-compose.prod.yml run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email ${EMAIL} \
    --agree-tos \
    --no-eff-email \
    -d ${DOMAIN} \
    -d www.${DOMAIN} \
    -d api.${DOMAIN} \
    -d ide.${DOMAIN}

# Restart nginx to load certificates
docker-compose -f docker-compose.prod.yml restart nginx

# Step 12: Setup auto-restart on crash
log "Configuring auto-restart..."
cat > /etc/systemd/system/resonantgenesis.service << EOF
[Unit]
Description=ResonantGenesis Platform
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/resonantgenesis/resonantgenesis_backend
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable resonantgenesis

# Step 13: Setup log rotation
log "Configuring log rotation..."
cat > /etc/logrotate.d/resonantgenesis << EOF
/opt/resonantgenesis/*/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
EOF

# Step 14: Setup monitoring
log "Setting up basic monitoring..."
cat > /opt/resonantgenesis/monitor.sh << 'EOF'
#!/bin/bash
# Basic health monitoring script

check_service() {
    if curl -sf "http://localhost:$1/health" > /dev/null; then
        echo "✅ $2 is healthy"
    else
        echo "❌ $2 is DOWN!"
        # Restart the service
        docker-compose -f /opt/resonantgenesis/resonantgenesis_backend/docker-compose.prod.yml restart $3
    fi
}

check_service 8000 "API Gateway" "gateway"
check_service 8080 "IDE Engine" "ide"

# Check CPU and memory
CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
MEM=$(free | grep Mem | awk '{print $3/$2 * 100.0}')

echo "CPU Usage: ${CPU}%"
echo "Memory Usage: ${MEM}%"

if (( $(echo "$CPU > 80" | bc -l) )); then
    echo "⚠️ High CPU usage!"
fi

if (( $(echo "$MEM > 80" | bc -l) )); then
    echo "⚠️ High memory usage!"
fi
EOF
chmod +x /opt/resonantgenesis/monitor.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/resonantgenesis/monitor.sh >> /var/log/resonantgenesis-monitor.log 2>&1") | crontab -

log "=== Deployment Complete! ==="
echo ""
echo "Next steps:"
echo "1. Edit /opt/resonantgenesis/.env with your actual API keys"
echo "2. Run: cd /opt/resonantgenesis/resonantgenesis_backend && docker-compose -f docker-compose.prod.yml up -d"
echo "3. Access your platform at https://${DOMAIN}"
echo ""
echo "Useful commands:"
echo "  View logs: docker-compose -f docker-compose.prod.yml logs -f"
echo "  Restart: docker-compose -f docker-compose.prod.yml restart"
echo "  Monitor: /opt/resonantgenesis/monitor.sh"
