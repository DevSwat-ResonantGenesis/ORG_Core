#!/bin/bash

# WebSocket Health Check Script for Self-Healing
# Monitors WebSocket connections and triggers healing

echo "=== WebSocket Health Check ==="

# Configuration
GATEWAY_URL="http://localhost:8000"
WEBSOCKET_ENDPOINTS=(
    "/ws/credits/test_user"
    "/ws/chat/test_chat"
    "/ws/ide/test_session"
    "/ws/agent/test_session"
    "/ws/ed/test_connection"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to test WebSocket endpoint
test_websocket_endpoint() {
    local endpoint=$1
    local url="${GATEWAY_URL}${endpoint}"
    
    # Test WebSocket upgrade request
    response=$(curl -s -i -H "Upgrade: websocket" \
                    -H "Connection: Upgrade" \
                    -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
                    -H "Sec-WebSocket-Version: 13" \
                    "$url" 2>/dev/null)
    
    if echo "$response" | grep -q "101 Switching Protocols"; then
        echo -e "${GREEN}✅ WebSocket $endpoint: UP${NC}"
        return 0
    else
        echo -e "${RED}❌ WebSocket $endpoint: DOWN${NC}"
        return 1
    fi
}

# Function to check WebSocket service health
check_websocket_service_health() {
    local service=$1
    
    if docker-compose ps "$service" | grep -q "Up"; then
        echo -e "${GREEN}✅ $service: UP${NC}"
        return 0
    else
        echo -e "${RED}❌ $service: DOWN${NC}"
        return 1
    fi
}

# Function to trigger WebSocket healing
trigger_websocket_healing() {
    local service=$1
    local endpoint=$2
    
    echo -e "${YELLOW}🔧 Triggering WebSocket healing for $service ($endpoint)${NC}"
    
    # Restart the service
    docker-compose restart "$service"
    
    # Wait for service to be ready
    sleep 10
    
    # Re-test the endpoint
    if test_websocket_endpoint "$endpoint"; then
        echo -e "${GREEN}✅ WebSocket healing successful for $service${NC}"
    else
        echo -e "${RED}❌ WebSocket healing failed for $service${NC}"
    fi
}

# Main health check
main() {
    local failed_endpoints=()
    
    # Check WebSocket endpoints
    echo "Testing WebSocket endpoints..."
    for endpoint in "${WEBSOCKET_ENDPOINTS[@]}"; do
        if ! test_websocket_endpoint "$endpoint"; then
            failed_endpoints+=("$endpoint")
        fi
    done
    
    # Check WebSocket service health
    echo ""
    echo "Checking WebSocket services..."
    check_websocket_service_health "gateway"
    check_websocket_service_health "chat_service"
    check_websocket_service_health "ide_service"
    check_websocket_service_health "agent_engine_service"
    check_websocket_service_health "ed_service"
    
    # Trigger healing for failed endpoints
    if [ ${#failed_endpoints[@]} -gt 0 ]; then
        echo ""
        echo -e "${YELLOW}🔧 Triggering WebSocket healing...${NC}"
        
        for endpoint in "${failed_endpoints[@]}"; do
            # Determine service from endpoint
            if [[ "$endpoint" == *"/credits/"* ]]; then
                trigger_websocket_healing "gateway" "$endpoint"
            elif [[ "$endpoint" == *"/chat/"* ]]; then
                trigger_websocket_healing "chat_service" "$endpoint"
            elif [[ "$endpoint" == *"/ide/"* ]]; then
                trigger_websocket_healing "ide_service" "$endpoint"
            elif [[ "$endpoint" == *"/agent/"* ]]; then
                trigger_websocket_healing "agent_engine_service" "$endpoint"
            elif [[ "$endpoint" == *"/ed/"* ]]; then
                trigger_websocket_healing "ed_service" "$endpoint"
            fi
        done
    else
        echo ""
        echo -e "${GREEN}✅ All WebSocket endpoints healthy${NC}"
    fi
    
    echo ""
    echo "=== WebSocket Health Check Complete ==="
}

# Run main function
main "$@"
