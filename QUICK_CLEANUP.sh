#!/bin/bash

# QUICK CLEANUP - Less destructive version
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0;32m'

log() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"
}

echo -e "${YELLOW}QUICK CLEANUP - Removes containers, images, volumes${NC}"
echo -e "${RED}This will delete all Docker data but keep configs${NC}"

# Stop services
cd /root/genesis2026_production_backend
docker-compose down || true
systemctl stop nginx || true

# Remove containers and images
docker rm -f $(docker ps -aq) 2>/dev/null || true
docker rmi -f $(docker images -q) 2>/dev/null || true

# Remove volumes (data will be lost!)
docker volume rm -f $(docker volume ls -q) 2>/dev/null || true

# Clean Docker
docker system prune -a -f --volumes || true

# Clean frontend and redeploy
rm -rf /var/www/frontend/*
rsync -avz "/Users/devswat/Genesis2026 /genesis2026_production_frontend/dist/" /var/www/frontend/

# Restart services
docker-compose up -d
systemctl start nginx

log "Quick cleanup completed!"
