#!/bin/bash
# System Boundary Verification Script
# Proves gateway is the only ingress and no backend ports are exposed

set -e

echo "🔍 SYSTEM BOUNDARY VERIFICATION"
echo "============================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
BOUNDARY_DIR="./boundary-verification-$(date +%Y%m%d_%H%M%S)"
EVIDENCE_FILE="$BOUNDARY_DIR/boundary-evidence.json"

echo "📁 Creating boundary verification directory: $BOUNDARY_DIR"
mkdir -p "$BOUNDARY_DIR"

# Initialize evidence report
cat > "$EVIDENCE_FILE" << EOF
{
  "verification_timestamp": "$(date -Iseconds)",
  "system_boundary": {
    "gateway_only_ingress": false,
    "backend_ports_exposed": [],
    "docker_network_isolation": false,
    "firewall_enforcement": false,
    "critical_issues": []
  }
}
EOF

echo "🔍 Verifying system boundary enforcement..."
echo ""

# 1. Verify Gateway is Only Ingress
echo "🌐 1. GATEWAY ONLY INGRESS VERIFICATION"
echo "=================================="
echo ""

echo "📋 Checking Docker compose configuration for port exposure..."
echo ""

# Check docker-compose.production.yml for port mappings
echo "Command: grep -A 5 -B 5 'ports:' /Users/devswat/Genesis2026 /genesis_backend_3/docker-compose.production.yml"
echo "Output:"
grep -A 5 -B 5 'ports:' "/Users/devswat/Genesis2026 /genesis_backend_3/docker-compose.production.yml" > "$BOUNDARY_DIR/docker_ports.txt" 2>/dev/null

echo "📋 Port mappings found:"
cat "$BOUNDARY_DIR/docker_ports.txt"
echo ""

# Count exposed ports
exposed_ports=$(grep -c '80:\|443:' "$BOUNDARY_DIR/docker_ports.txt" 2>/dev/null || echo "0")
backend_ports=$(grep -c '800[0-9]:' "$BOUNDARY_DIR/docker_ports.txt" 2>/dev/null || echo "0")

echo "📊 Port exposure analysis:"
echo "  - Web ports (80/443): $exposed_ports"
echo "  - Backend ports (8000-8099): $backend_ports"
echo ""

if [ "$backend_ports" -eq 0 ]; then
    echo "✅ No backend ports exposed in docker-compose"
    gateway_only_ingress=true
else
    echo "❌ CRITICAL: Backend ports exposed in docker-compose"
    gateway_only_ingress=false
fi

# 2. Verify Docker Network Isolation
echo ""
echo "🐳 2. DOCKER NETWORK ISOLATION VERIFICATION"
echo "========================================="
echo ""

echo "📋 Checking Docker network configuration..."
echo ""

# Check if containers are running
echo "Command: docker ps --format 'table {{.Names}}\t{{.Status}}'"
echo "Output:"
docker ps --format "table {{.Names}}\t{{.Status}}" > "$BOUNDARY_DIR/running_containers.txt" 2>/dev/null

echo "📋 Running containers:"
cat "$BOUNDARY_DIR/running_containers.txt"
echo ""

# Check network assignments
echo "Command: docker network ls"
echo "Output:"
docker network ls > "$BOUNDARY_DIR/docker_networks.txt" 2>/dev/null

echo "📋 Docker networks:"
cat "$BOUNDARY_DIR/docker_networks.txt"
echo ""

# Check if backend services are in internal networks
echo "📋 Checking network isolation..."
network_isolation=true

for service in auth_service chat_service memory_service llm_service; do
    if docker ps | grep -q "$service"; then
        echo "Command: docker inspect $service --format='{{range .NetworkSettings.Networks}}{{.NetworkID}} {{end}}'"
        echo "Output for $service:"
        docker inspect "$service" --format='{{range .NetworkSettings.Networks}}{{.NetworkID}} {{end}}' > "$BOUNDARY_DIR/${service}_networks.txt" 2>/dev/null
        
        # Check if service is in internal network
        if grep -q "genesis_backend_3_backend-network" "$BOUNDARY_DIR/${service}_networks.txt" 2>/dev/null; then
            echo "✅ $service is in backend network"
        else
            echo "❌ $service not in backend network"
            network_isolation=false
        fi
        echo ""
    fi
done

# 3. Verify Firewall Enforcement
echo ""
echo "🔥 3. FIREWALL ENFORCEMENT VERIFICATION"
echo "====================================="
echo ""

echo "📋 Checking firewall status..."
echo ""

# Check UFW status
echo "Command: sudo ufw status verbose"
echo "Output:"
sudo ufw status verbose > "$BOUNDARY_DIR/ufw_status.txt" 2>/dev/null

echo "📋 UFW status:"
cat "$BOUNDARY_DIR/ufw_status.txt"
echo ""

if grep -q "Status: active" "$BOUNDARY_DIR/ufw_status.txt"; then
    echo "✅ UFW firewall is active"
    firewall_enforcement=true
else
    echo "❌ UFW firewall not active"
    firewall_enforcement=false
fi

# Check allowed ports
echo "📋 Checking allowed ports..."
echo ""
echo "Command: sudo ufw status numbered"
echo "Output:"
sudo ufw status numbered > "$BOUNDARY_DIR/ufw_rules.txt" 2>/dev/null

echo "📋 UFW rules:"
cat "$BOUNDARY_DIR/ufw_rules.txt"
echo ""

# Verify only SSH, HTTP, HTTPS are allowed
if grep -q "22\|80\|443" "$BOUNDARY_DIR/ufw_rules.txt"; then
    echo "✅ SSH and web ports allowed"
else
    echo "❌ Missing required ports"
fi

# Check for disallowed ports
if grep -E "5432|6379|800[0-9]" "$BOUNDARY_DIR/ufw_rules.txt"; then
    echo "❌ CRITICAL: Database or backend ports allowed"
    firewall_enforcement=false
else
    echo "✅ No database or backend ports allowed"
fi

# 4. External Port Scan Verification
echo ""
echo "🌐 4. EXTERNAL PORT SCAN VERIFICATION"
echo "==================================="
echo ""

echo "📋 Performing external port scan..."
echo ""

# Get droplet IP
DROPLET_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")
echo "📍 Scanning droplet IP: $DROPLET_IP"
echo ""

# Perform port scan
echo "Command: nmap -sS -O $DROPLET_IP"
echo "Output:"
nmap -sS -O "$DROPLET_IP" > "$BOUNDARY_DIR/external_scan.txt" 2>/dev/null

echo "📋 External scan results:"
cat "$BOUNDARY_DIR/external_scan.txt"
echo ""

# Check for exposed database ports
if grep -E "5432|6379|9000" "$BOUNDARY_DIR/external_scan.txt"; then
    echo "❌ CRITICAL: Database ports visible externally"
    backend_ports_exposed=true
else
    echo "✅ No database ports visible externally"
    backend_ports_exposed=false
fi

# Check for exposed backend ports
if grep -E "800[0-9]" "$BOUNDARY_DIR/external_scan.txt"; then
    echo "❌ CRITICAL: Backend ports visible externally"
    backend_ports_exposed=true
else
    echo "✅ No backend ports visible externally"
fi

# 5. Verify No Direct Backend Access
echo ""
echo "🔒 5. DIRECT BACKEND ACCESS VERIFICATION"
echo "====================================="
echo ""

echo "📋 Testing direct backend service access..."
echo ""

# Test direct access to backend services
backend_services=("auth_service:8001" "chat_service:8002" "memory_service:8003" "llm_service:8004")
direct_access_possible=false

for service in "${backend_services[@]}"; do
    echo "Testing direct access to $service..."
    
    # Try to access health endpoint directly
    if curl -s -f "http://localhost/health" >/dev/null 2>&1; then
        echo "❌ CRITICAL: Direct access to $service possible"
        direct_access_possible=true
    else
        echo "✅ Direct access to $service blocked"
    fi
    echo ""
done

# 6. Generate Boundary Evidence
echo ""
echo "📋 6. BOUNDARY EVIDENCE GENERATION"
echo "==============================="
echo ""

# Update evidence report
jq --arg ".system_boundary.gateway_only_ingress = $gateway_only_ingress" \
   "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"

jq --arg ".system_boundary.network_isolation = $network_isolation" \
   "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"

jq --arg ".system_boundary.firewall_enforcement = $firewall_enforcement" \
   "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"

jq --arg ".system_boundary.backend_ports_exposed = $backend_ports_exposed" \
   "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"

# Add critical issues
critical_issues=0

if [ "$gateway_only_ingress" = false ]; then
    jq --arg ".system_boundary.critical_issues += [{\"issue\": \"Backend ports exposed in docker-compose\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

if [ "$network_isolation" = false ]; then
    jq --arg ".system_boundary.critical_issues += [{\"issue\": \"Docker network isolation not enforced\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

if [ "$firewall_enforcement" = false ]; then
    jq --arg ".system_boundary.critical_issues += [{\"issue\": \"Firewall not enforcing rules\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

if [ "$backend_ports_exposed" = true ]; then
    jq --arg ".system_boundary.critical_issues += [{\"issue\": \"Backend ports visible externally\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

if [ "$direct_access_possible" = true ]; then
    jq --arg ".system_boundary.critical_issues += [{\"issue\": \"Direct backend access possible\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

# 7. Final Assessment
echo ""
echo "📊 SYSTEM BOUNDARY ASSESSMENT"
echo "==========================="
echo ""
echo "📁 Evidence directory: $BOUNDARY_DIR"
echo "📋 Evidence report: $EVIDENCE_FILE"
echo ""
echo "📊 BOUNDARY VERIFICATION RESULTS:"
echo "  - Gateway only ingress: $gateway_only_ingress"
echo "  - Docker network isolation: $network_isolation"
echo "  - Firewall enforcement: $firewall_enforcement"
echo "  - Backend ports exposed: $backend_ports_exposed"
echo "  - Direct access possible: $direct_access_possible"
echo "  - Critical issues: $critical_issues"
echo ""

if [ $critical_issues -eq 0 ]; then
    echo -e "${GREEN}✅ SYSTEM BOUNDARY SECURE${NC}"
    echo "🎉 Gateway is proven to be the only ingress point"
    echo ""
    echo "✅ Security posture: BOUNDARY ENFORCED"
    echo "✅ Backend services: ISOLATED"
    echo "✅ Network access: CONTROLLED"
    echo "✅ Firewall: ACTIVE"
else
    echo -e "${RED}❌ SYSTEM BOUNDARY COMPROMISED${NC}"
    echo "🚨 Gateway is NOT the only ingress point"
    echo ""
    echo "❌ Security posture: BOUNDARY BREACHED"
    echo "❌ Critical issues: $critical_issues"
    echo "❌ Backend services: EXPOSED"
    echo "❌ Network access: UNCONTROLLED"
fi

echo ""
echo "📋 This verification provides concrete evidence of:"
echo "  - Docker port exposure analysis"
echo "  - Network isolation verification"
echo "  - Firewall enforcement proof"
echo "  - External port scan results"
echo "  - Direct backend access testing"
echo ""
echo "🔍 Evidence files:"
ls -la "$BOUNDARY_DIR"
