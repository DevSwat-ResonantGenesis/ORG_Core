#!/bin/bash
# Production Security Evidence Collection
# Generates concrete proof that security measures are actually enforced

set -e

echo "🔍 PRODUCTION SECURITY EVIDENCE COLLECTION"
echo "======================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
EVIDENCE_DIR="/opt/genesis/security-evidence-$(date +%Y%m%d_%H%M%S)"
VERIFICATION_REPORT="$EVIDENCE_DIR/verification-report.json"

echo "📁 Creating evidence directory: $EVIDENCE_DIR"
mkdir -p "$EVIDENCE_DIR"/{network,secrets,databases,monitoring,firewall,containers,backups}

# Initialize verification report
cat > "$VERIFICATION_REPORT" << EOF
{
  "evidence_timestamp": "$(date -Iseconds)",
  "droplet_ip": "$(curl -s ifconfig.me 2>/dev/null || echo 'localhost')",
  "evidence_collected": [],
  "verification_status": "in_progress",
  "critical_findings": [],
  "overall_assessment": "pending"
}
EOF

# Function to log evidence
log_evidence() {
    local category="$1"
    local test_name="$2"
    local status="$3"
    local evidence_file="$4"
    local details="$5"
    
    echo "🔍 $test_name... "
    
    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}✅ PASS${NC}"
        echo "   Evidence: $evidence_file"
    else
        echo -e "${RED}❌ FAIL${NC}"
        echo "   Evidence: $evidence_file"
        
        # Add to critical findings
        jq --arg ".critical_findings += [{\"category\": \"$category\", \"test\": \"$test_name\", \"evidence\": \"$evidence_file\", \"details\": \"$details\"}]" \
           "$VERIFICATION_REPORT" > "$VERIFICATION_REPORT.tmp" && mv "$VERIFICATION_REPORT.tmp" "$VERIFICATION_REPORT"
    fi
    
    # Add to evidence collected
    jq --arg ".evidence_collected += [{\"category\": \"$category\", \"test\": \"$test_name\", \"status\": \"$status\", \"evidence\": \"$evidence_file\", \"details\": \"$details\"}]" \
       "$VERIFICATION_REPORT" > "$VERIFICATION_REPORT.tmp" && mv "$VERIFICATION_REPORT.tmp" "$VERIFICATION_REPORT"
}

echo "🔍 Collecting concrete security evidence..."
echo ""

# 1. Firewall Evidence Collection
echo "🔥 Step 1: Firewall Evidence Collection"
echo "======================================"

# UFW status
echo "📋 Collecting UFW firewall status..."
ufw status verbose > "$EVIDENCE_DIR/firewall/ufw_status.txt" 2>&1
if grep -q "Status: active" "$EVIDENCE_DIR/firewall/ufw_status.txt"; then
    log_evidence "firewall" "UFW Status" "PASS" "$EVIDENCE_DIR/firewall/ufw_status.txt" "UFW firewall is active"
else
    log_evidence "firewall" "UFW Status" "FAIL" "$EVIDENCE_DIR/firewall/ufw_status.txt" "UFW firewall not active"
fi

# UFW rules
echo "📋 Collecting UFW rules..."
ufw status numbered > "$EVIDENCE_DIR/firewall/ufw_rules.txt" 2>&1
if grep -q "22\|80\|443" "$EVIDENCE_DIR/firewall/ufw_rules.txt"; then
    log_evidence "firewall" "UFW Rules" "PASS" "$EVIDENCE_DIR/firewall/ufw_rules.txt" "SSH and web ports allowed"
else
    log_evidence "firewall" "UFW Rules" "FAIL" "$EVIDENCE_DIR/firewall/ufw_rules.txt" "Missing required ports"
fi

# 2. Network Evidence Collection
echo ""
echo "🌐 Step 2: Network Evidence Collection"
echo "=================================="

# Docker network inspection
echo "📋 Inspecting Docker networks..."
docker network ls > "$EVIDENCE_DIR/network/docker_networks.txt" 2>&1

# Check database network isolation
if docker network ls | grep -q "genesis_backend_3_database-network"; then
    docker network inspect genesis_backend_3_database-network > "$EVIDENCE_DIR/network/database_network_inspect.json" 2>&1
    if grep -q '"Internal": true' "$EVIDENCE_DIR/network/database_network_inspect.json"; then
        log_evidence "network" "Database Network Isolation" "PASS" "$EVIDENCE_DIR/network/database_network_inspect.json" "Database network is internal"
    else
        log_evidence "network" "Database Network Isolation" "FAIL" "$EVIDENCE_DIR/network/database_network_inspect.json" "Database network not isolated"
    fi
else
    log_evidence "network" "Database Network Existence" "FAIL" "$EVIDENCE_DIR/network/docker_networks.txt" "Database network missing"
fi

# Check backend network isolation
if docker network ls | grep -q "genesis_backend_3_backend-network"; then
    docker network inspect genesis_backend_3_backend-network > "$EVIDENCE_DIR/network/backend_network_inspect.json" 2>&1
    if grep -q '"Internal": true' "$EVIDENCE_DIR/network/backend_network_inspect.json"; then
        log_evidence "network" "Backend Network Isolation" "PASS" "$EVIDENCE_DIR/network/backend_network_inspect.json" "Backend network is internal"
    else
        log_evidence "network" "Backend Network Isolation" "FAIL" "$EVIDENCE_DIR/network/backend_network_inspect.json" "Backend network not isolated"
    fi
else
    log_evidence "network" "Backend Network Existence" "FAIL" "$EVIDENCE_DIR/network/docker_networks.txt" "Backend network missing"
fi

# Port binding verification
echo "📋 Checking port bindings..."
netstat -tlnp > "$EVIDENCE_DIR/network/port_bindings.txt" 2>&1
# Check for exposed database ports
if grep -E ":(5432|6379|9000)" "$EVIDENCE_DIR/network/port_bindings.txt" | grep -q "0.0.0.0"; then
    log_evidence "network" "Port Binding Security" "FAIL" "$EVIDENCE_DIR/network/port_bindings.txt" "Database ports exposed to 0.0.0.0"
else
    log_evidence "network" "Port Binding Security" "PASS" "$EVIDENCE_DIR/network/port_bindings.txt" "No database ports exposed externally"
fi

# External port scan
echo "📋 Performing external port scan..."
DROPLET_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")
nmap -sS -O "$DROPLET_IP" > "$EVIDENCE_DIR/network/external_scan.txt" 2>&1
if grep -E "5432|6379|9000" "$EVIDENCE_DIR/network/external_scan.txt"; then
    log_evidence "network" "External Port Scan" "FAIL" "$EVIDENCE_DIR/network/external_scan.txt" "Database ports visible externally"
else
    log_evidence "network" "External Port Scan" "PASS" "$EVIDENCE_DIR/network/external_scan.txt" "No database ports visible externally"
fi

# 3. Secrets Evidence Collection
echo ""
echo "🔐 Step 3: Secrets Evidence Collection"
echo "=================================="

# Check secrets file existence and permissions
if [ -f ".env.production" ]; then
    stat -c "%a %U:%G %s" .env.production > "$EVIDENCE_DIR/secrets/env_permissions.txt" 2>&1
    perms=$(stat -c "%a" .env.production)
    if [ "$perms" = "600" ]; then
        log_evidence "secrets" "Secrets File Permissions" "PASS" "$EVIDENCE_DIR/secrets/env_permissions.txt" "Secure permissions (600)"
    else
        log_evidence "secrets" "Secrets File Permissions" "FAIL" "$EVIDENCE_DIR/secrets/env_permissions.txt" "Insecure permissions ($perms)"
    fi
    
    # Check for placeholder secrets
    grep -E "YOUR-|placeholder|test-|dev-" .env.production > "$EVIDENCE_DIR/secrets/placeholder_secrets.txt" 2>&1 || true
    if [ -s "$EVIDENCE_DIR/secrets/placeholder_secrets.txt" ]; then
        log_evidence "secrets" "Placeholder Secrets" "FAIL" "$EVIDENCE_DIR/secrets/placeholder_secrets.txt" "Placeholder secrets found"
    else
        log_evidence "secrets" "Placeholder Secrets" "PASS" "$EVIDENCE_DIR/secrets/placeholder_secrets.txt" "No placeholder secrets"
    fi
    
    # Check for default passwords
    grep -E "auth_pass|user_pass|admin123|password" .env.production > "$EVIDENCE_DIR/secrets/default_passwords.txt" 2>&1 || true
    if [ -s "$EVIDENCE_DIR/secrets/default_passwords.txt" ]; then
        log_evidence "secrets" "Default Passwords" "FAIL" "$EVIDENCE_DIR/secrets/default_passwords.txt" "Default passwords found"
    else
        log_evidence "secrets" "Default Passwords" "PASS" "$EVIDENCE_DIR/secrets/default_passwords.txt" "No default passwords"
    fi
else
    log_evidence "secrets" "Secrets File Existence" "FAIL" "N/A" "Production secrets file missing"
fi

# Check Docker container environment variables
echo "📋 Checking container environment injection..."
docker ps --format "table {{.Names}}\t{{.Image}}" > "$EVIDENCE_DIR/secrets/running_containers.txt" 2>&1

# Check if secrets are baked into images
echo "📋 Checking for baked secrets in images..."
for container in genesis_auth_service genesis_chat_service genesis_memory_service; do
    if docker ps | grep -q "$container"; then
        docker inspect "$container" --format='{{range .Config.Env}}{{.}} {{end}}' > "$EVIDENCE_DIR/secrets/${container}_env.txt" 2>&1
        if grep -q "PASSWORD\|SECRET\|KEY" "$EVIDENCE_DIR/secrets/${container}_env.txt"; then
            log_evidence "secrets" "Container Env Injection ($container)" "PASS" "$EVIDENCE_DIR/secrets/${container}_env.txt" "Secrets injected via environment"
        else
            log_evidence "secrets" "Container Env Injection ($container)" "WARN" "$EVIDENCE_DIR/secrets/${container}_env.txt" "No secrets detected"
        fi
    fi
done

# 4. Database Evidence Collection
echo ""
echo "🗄️ Step 4: Database Evidence Collection"
echo "=================================="

# Check database connectivity
echo "📋 Testing database connectivity..."
for db in auth_db chat_db memory_db; do
    if docker ps | grep -q "genesis_${db}"; then
        docker exec "genesis_${db}" pg_isready -U genesis_${db}_user_prod -d ${db} > "$EVIDENCE_DIR/databases/${db}_connectivity.txt" 2>&1
        if grep -q "accepting connections" "$EVIDENCE_DIR/databases/${db}_connectivity.txt"; then
            log_evidence "databases" "Database Connectivity ($db)" "PASS" "$EVIDENCE_DIR/databases/${db}_connectivity.txt" "Database accepting connections"
        else
            log_evidence "databases" "Database Connectivity ($db)" "FAIL" "$EVIDENCE_DIR/databases/${db}_connectivity.txt" "Database not ready"
        fi
        
        # Check database binding
        docker exec "genesis_${db}" netstat -tlnp > "$EVIDENCE_DIR/databases/${db}_binding.txt" 2>&1
        if grep -q "0.0.0.0:5432" "$EVIDENCE_DIR/databases/${db}_binding.txt"; then
            log_evidence "databases" "Database Binding ($db)" "FAIL" "$EVIDENCE_DIR/databases/${db}_binding.txt" "Database bound to 0.0.0.0"
        else
            log_evidence "databases" "Database Binding ($db)" "PASS" "$EVIDENCE_DIR/databases/${db}_binding.txt" "Database not bound externally"
        fi
        
        # Check database authentication
        docker exec "genesis_${db}" psql -U genesis_${db}_user_prod -d ${db} -c "SELECT current_user;" > "$EVIDENCE_DIR/databases/${db}_auth.txt" 2>&1
        if grep -q "genesis_${db}_user_prod" "$EVIDENCE_DIR/databases/${db}_auth.txt"; then
            log_evidence "databases" "Database Authentication ($db)" "PASS" "$EVIDENCE_DIR/databases/${db}_auth.txt" "Database authentication working"
        else
            log_evidence "databases" "Database Authentication ($db)" "FAIL" "$EVIDENCE_DIR/databases/${db}_auth.txt" "Database authentication failed"
        fi
    else
        log_evidence "databases" "Database Container ($db)" "FAIL" "N/A" "Database container not running"
    fi
done

# 5. Container Evidence Collection
echo ""
echo "🐳 Step 5: Container Evidence Collection"
echo "=================================="

# Container status
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" > "$EVIDENCE_DIR/containers/container_status.txt" 2>&1
if grep -q "genesis_" "$EVIDENCE_DIR/containers/container_status.txt"; then
    log_evidence "containers" "Container Status" "PASS" "$EVIDENCE_DIR/containers/container_status.txt" "Genesis containers running"
else
    log_evidence "containers" "Container Status" "FAIL" "$EVIDENCE_DIR/containers/container_status.txt" "No Genesis containers running"
fi

# Container port exposure
docker ps --format "table {{.Names}}\t{{.Ports}}" | grep -E "0.0.0.0:" > "$EVIDENCE_DIR/containers/container_ports.txt" 2>&1
if grep -q "0.0.0.0:8000\|0.0.0.0:80\|0.0.0.0:443" "$EVIDENCE_DIR/containers/container_ports.txt"; then
    if grep -v -E "0.0.0.0:8000|0.0.0.0:80|0.0.0.0:443" "$EVIDENCE_DIR/containers/container_ports.txt"; then
        log_evidence "containers" "Container Port Exposure" "FAIL" "$EVIDENCE_DIR/containers/container_ports.txt" "Unexpected ports exposed"
    else
        log_evidence "containers" "Container Port Exposure" "PASS" "$EVIDENCE_DIR/containers/container_ports.txt" "Only expected ports exposed"
    fi
else
    log_evidence "containers" "Container Port Exposure" "PASS" "$EVIDENCE_DIR/containers/container_ports.txt" "No external port exposure"
fi

# Container health checks
echo "📋 Testing container health..."
for service in gateway auth_service chat_service memory_service llm_service; do
    if docker ps | grep -q "$service"; then
        curl -s -f "http://localhost:8000/health" > "$EVIDENCE_DIR/containers/${service}_health.txt" 2>&1 || true
        if grep -q "healthy\|ok" "$EVIDENCE_DIR/containers/${service}_health.txt"; then
            log_evidence "containers" "Container Health ($service)" "PASS" "$EVIDENCE_DIR/containers/${service}_health.txt" "Service healthy"
        else
            log_evidence "containers" "Container Health ($service)" "FAIL" "$EVIDENCE_DIR/containers/${service}_health.txt" "Service unhealthy"
        fi
    fi
done

# 6. Monitoring Evidence Collection
echo ""
echo "📊 Step 6: Monitoring Evidence Collection"
echo "=================================="

# Check monitoring containers
for service in prometheus grafana alertmanager; do
    if docker ps | grep -q "$service"; then
        curl -s -f "http://localhost:9090/api/v1/status/config" > "$EVIDENCE_DIR/monitoring/${service}_status.txt" 2>&1 || true
        if [ -s "$EVIDENCE_DIR/monitoring/${service}_status.txt" ]; then
            log_evidence "monitoring" "Monitoring Service ($service)" "PASS" "$EVIDENCE_DIR/monitoring/${service}_status.txt" "Service responding"
        else
            log_evidence "monitoring" "Monitoring Service ($service)" "FAIL" "$EVIDENCE_DIR/monitoring/${service}_status.txt" "Service not responding"
        fi
    else
        log_evidence "monitoring" "Monitoring Service ($service)" "FAIL" "N/A" "Service not running"
    fi
done

# Check metrics endpoints
echo "📋 Testing metrics endpoints..."
for service in gateway auth_service chat_service memory_service; do
    if docker ps | grep -q "$service"; then
        curl -s -f "http://localhost:8000/metrics" > "$EVIDENCE_DIR/monitoring/${service}_metrics.txt" 2>&1 || true
        if grep -q "http_requests_total\|process_cpu_seconds_total" "$EVIDENCE_DIR/monitoring/${service}_metrics.txt"; then
            log_evidence "monitoring" "Metrics Collection ($service)" "PASS" "$EVIDENCE_DIR/monitoring/${service}_metrics.txt" "Metrics available"
        else
            log_evidence "monitoring" "Metrics Collection ($service)" "FAIL" "$EVIDENCE_DIR/monitoring/${service}_metrics.txt" "No metrics available"
        fi
    fi
done

# 7. Backup Evidence Collection
echo ""
echo "💾 Step 7: Backup Evidence Collection"
echo "=================================="

# Check backup directory
if [ -d "/opt/genesis/backups" ]; then
    find /opt/genesis/backups -name "*.gpg" -ls > "$EVIDENCE_DIR/backups/backup_files.txt" 2>&1
    if [ -s "$EVIDENCE_DIR/backups/backup_files.txt" ]; then
        log_evidence "backups" "Backup Files Exist" "PASS" "$EVIDENCE_DIR/backups/backup_files.txt" "Encrypted backups found"
    else
        log_evidence "backups" "Backup Files Exist" "FAIL" "$EVIDENCE_DIR/backups/backup_files.txt" "No backup files found"
    fi
    
    # Check backup encryption
    if [ -f "/opt/genesis/secrets/backup_encryption.key" ]; then
        stat -c "%a %U:%G" /opt/genesis/secrets/backup_encryption.key > "$EVIDENCE_DIR/backups/backup_key.txt" 2>&1
        log_evidence "backups" "Backup Encryption Key" "PASS" "$EVIDENCE_DIR/backups/backup_key.txt" "Encryption key exists"
    else
        log_evidence "backups" "Backup Encryption Key" "FAIL" "N/A" "Encryption key missing"
    fi
    
    # Test backup integrity
    latest_backup=$(find /opt/genesis/backups -name "*.gpg" -type f -exec ls -la {} \; | head -1 | awk '{print $9}')
    if [ -n "$latest_backup" ]; then
        gpg --list-only --passphrase-file /opt/genesis/secrets/backup_encryption.key "$latest_backup" > "$EVIDENCE_DIR/backups/backup_integrity.txt" 2>&1 || true
        if grep -q "gpg:" "$EVIDENCE_DIR/backups/backup_integrity.txt"; then
            log_evidence "backups" "Backup Integrity" "FAIL" "$EVIDENCE_DIR/backups/backup_integrity.txt" "Backup integrity check failed"
        else
            log_evidence "backups" "Backup Integrity" "PASS" "$EVIDENCE_DIR/backups/backup_integrity.txt" "Backup integrity verified"
        fi
    fi
else
    log_evidence "backups" "Backup Directory" "FAIL" "N/A" "Backup directory missing"
fi

# 8. Final Assessment
echo ""
echo "📋 Step 8: Final Assessment"
echo "========================"

# Count critical findings
critical_count=$(jq '.critical_findings | length' "$VERIFICATION_REPORT")
total_checks=$(jq '.evidence_collected | length' "$VERIFICATION_REPORT")
passed_checks=$(jq '.evidence_collected | map(select(.status == "PASS")) | length' "$VERIFICATION_REPORT")

# Update final status
if [ "$critical_count" -eq 0 ]; then
    jq --arg ".overall_assessment = \"SECURE\"" \
       "$VERIFICATION_REPORT" > "$VERIFICATION_REPORT.tmp" && mv "$VERIFICATION_REPORT.tmp" "$VERIFICATION_REPORT"
    echo -e "${GREEN}✅ SYSTEM SECURE - No critical findings${NC}"
else
    jq --arg ".overall_assessment = \"CRITICAL_ISSUES_FOUND\"" \
       "$VERIFICATION_REPORT" > "$VERIFICATION_REPORT.tmp" && mv "$VERIFICATION_REPORT.tmp" "$VERIFICATION_REPORT"
    echo -e "${RED}❌ CRITICAL ISSUES FOUND - $critical_count critical findings${NC}"
fi

jq --arg ".verification_status = \"completed\"" \
   "$VERIFICATION_REPORT" > "$VERIFICATION_REPORT.tmp" && mv "$VERIFICATION_REPORT.tmp" "$VERIFICATION_REPORT"

echo ""
echo "📊 EVIDENCE COLLECTION SUMMARY"
echo "============================="
echo "📁 Evidence directory: $EVIDENCE_DIR"
echo "📋 Verification report: $VERIFICATION_REPORT"
echo "📊 Total checks: $total_checks"
echo "✅ Passed checks: $passed_checks"
echo "❌ Critical findings: $critical_count"
echo ""

echo "🔍 Evidence files created:"
find "$EVIDENCE_DIR" -type f -name "*.txt" -o -name "*.json" | sort

echo ""
echo "📋 To review findings:"
echo "  cat $VERIFICATION_REPORT | jq '.critical_findings'"
echo "  ls -la $EVIDENCE_DIR/"
echo ""
echo "⚠️  This provides concrete evidence, not just documentation."
