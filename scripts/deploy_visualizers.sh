#!/bin/bash

# Deploy Hash Sphere and Code Visualizer services to Digital Ocean
# Usage: ./scripts/deploy_visualizers.sh

set -e

echo "🚀 Deploying Hash Sphere and Code Visualizer services..."

# Configuration
DROPLET_IP="${DROPLET_IP:-your-droplet-ip}"
DROPLET_USER="${DROPLET_USER:-root}"
BACKEND_PATH="/root/resonantgenesis_backend"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Step 1: Building services locally...${NC}"

# Build Docker images
docker-compose build hash_sphere_service code_visualizer_service

echo -e "${GREEN}✓ Services built${NC}"

echo -e "${YELLOW}Step 2: Pushing to repository...${NC}"

# Commit and push changes
git add hash_sphere_service/ code_visualizer_service/ docker-compose.yml
git commit -m "Add Hash Sphere and Code Visualizer services" || true
git push origin main

echo -e "${GREEN}✓ Changes pushed${NC}"

echo -e "${YELLOW}Step 3: Deploying to droplet...${NC}"

# SSH to droplet and deploy
ssh ${DROPLET_USER}@${DROPLET_IP} << 'ENDSSH'
cd /root/resonantgenesis_backend

# Pull latest changes
git pull origin main

# Build and start services
docker-compose up -d --build hash_sphere_service code_visualizer_service

# Check status
docker-compose ps hash_sphere_service code_visualizer_service

echo "Services deployed!"
ENDSSH

echo -e "${GREEN}✓ Deployment complete!${NC}"
echo ""
echo "Services available at:"
echo "  - Hash Sphere: http://${DROPLET_IP}:8091"
echo "  - Code Visualizer: http://${DROPLET_IP}:8092"
