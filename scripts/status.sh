#!/bin/bash

# Blue-Green Deployment Status Script

CURRENT_FILE="/tmp/current_deployment"
PROJECT_DIR="/root/genesis2026_production_backend"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo "========================================"
echo "BLUE-GREEN DEPLOYMENT STATUS"
echo "========================================"

if [ -f "$CURRENT_FILE" ]; then
    CURRENT_ENV=$(cat "$CURRENT_FILE")
    echo -e "Current Active Environment: ${GREEN}$CURRENT_ENV${NC}"
else
    echo -e "${RED}No deployment information found${NC}"
    exit 1
fi

echo ""
echo "Blue Environment:"
if docker ps | grep -q "gateway_blue"; then
    echo -e "  Status: ${GREEN}RUNNING${NC}"
    echo "  Containers: $(docker ps --filter "name=_blue" --format "{{.Names}}" | wc -l)"
else
    echo -e "  Status: ${RED}STOPPED${NC}"
fi

echo ""
echo "Green Environment:"
if docker ps | grep -q "gateway_green"; then
    echo -e "  Status: ${GREEN}RUNNING${NC}"
    echo "  Containers: $(docker ps --filter "name=_green" --format "{{.Names}}" | wc -l)"
else
    echo -e "  Status: ${RED}STOPPED${NC}"
fi

echo ""
echo "Nginx Configuration:"
if grep -q "gateway_blue" $PROJECT_DIR/nginx/nginx-production-https.conf; then
    echo -e "  Routing to: ${BLUE}BLUE${NC}"
elif grep -q "gateway_green" $PROJECT_DIR/nginx/nginx-production-https.conf; then
    echo -e "  Routing to: ${GREEN}GREEN${NC}"
else
    echo -e "  Routing to: ${RED}UNKNOWN${NC}"
fi

echo ""
echo "Frontend Status:"
if curl -sf https://dev-swat.com/health > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅ Accessible${NC}"
else
    echo -e "  ${RED}❌ Not Accessible${NC}"
fi

echo "========================================"
