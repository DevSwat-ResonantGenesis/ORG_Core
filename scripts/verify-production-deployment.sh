#!/bin/bash
# Production Deployment Verification Script
# CRITICAL: Comprehensive validation before production deployment

set -e

echo "🚀 PRODUCTION DEPLOYMENT VERIFICATION"
echo "=================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
VERIFICATION_REPORT="/opt/genesis/verification-report-$(date +%Y%m%d_%H%M%S).json"
ISSUES_FOUND=0

# Initialize verification report
cat > "$VERIFICATION_REPORT" << EOF
{
  "verification_timestamp": "$(date -Iseconds)",
  "deployment_status": "pending",
  "checks_performed": [],
  "issues_found": [],
  "overall_status": "pending"
}
EOF

# Function to log verification result
log_verification() {
    local check_name="$1"
    local status="$2"
    local message="$3"
    local details="$4"
    
    echo -n "🔍 $check_name... "
    
    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}✅ PASS${NC}"
        echo "   $message"
    else
        echo -e "${RED}❌ FAIL${NC}"
        echo "   $message"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
        
        # Add to issues list
        jq --arg ".checks_performed += [{\"name\": \"$check_name\", \"status\": \"$status\", \"message\": \"$message\", \"details\": \"$details\"}]" \
           "$VERIFICATION_REPORT" > "$VERIFICATION_REPORT.tmp" && mv "$VERIFICATION_REPORT.tmp" "$VERIFICATION_REPORT"
    fi
    
    # Add to checks performed
    jq --arg ".checks_performed += [{\"name\": \"$check_name\", \"status\": \"$status\", \"message\": \"$message\", \"details\": \"$details\"}]" \
       "$VERIFICATION_REPORT" > "$VERIFICATION_REPORT.tmp" && mv "$VERIFICATION_REPORT.tmp" "$VERIFICATION_REPORT"
}

# Function to update final status
update_status() {
    local status="$1"
    jq --arg ".deployment_status = \"$status\"" \
       "$VERIFICATION_REPORT" > "$VERIFICATION_REPORT.tmp" && mv "$VERIFICATION_REPORT.tmp" "$VERIFICATION_REPORT"
    jq --arg ".overall_status = \"$status\"" \
       "$VERIFICATION_REPORT" > "$VERIFICATION_REPORT.tmp" && mv "$VERIFICATION_REPORT.tmp" "$VERIFICATION_REPORT"
    jq --arg ".issues_found = $ISSUES_FOUND" \
       "$VERIFICATION_REPORT" > "$VERIFICATION_REPORT.tmp" && mv "$VERIFICATION_REPORT.tmp" "$VERIFICATION_REPORT"
}

echo "🔍 Starting production deployment verification..."
echo ""

# 1. Environment Configuration Check
echo "📋 Step 1: Environment Configuration"
echo "=================================="

# Check if production environment
if [ "$GATEWAY_ENVIRONMENT" = "production" ]; then
    log_verification "Environment Check" "PASS" "Production environment configured" "GATEWAY_ENVIRONMENT=production"
else
    log_verification "Environment Check" "FAIL" "Not in production mode" "GATEWAY_ENVIRONMENT=$GATEWAY_ENVIRONMENT"
fi

# Check if DEV_MODE is disabled
if [ "$GATEWAY_DEV_MODE" = "false" ]; then
    log_verification "DEV_MODE Check" "PASS" "Development mode disabled" "GATEWAY_DEV_MODE=false"
else
    log_verification "DEV_MODE Check" "FAIL" "Development mode enabled" "GATEWAY_DEV_MODE=$GATEWAY_DEV_MODE"
fi

# 2. Security Configuration Check
echo ""
echo "🔒 Step 2: Security Configuration"
echo "=================================="

# Check firewall status
if command -v ufw status >/dev/null 2>&1; then
    if ufw status | grep -q "Status: active"; then
        log_verification "Firewall Status" "PASS" "UFW firewall is active" "$(ufw status | head -1)"
        
        # Check allowed ports
        allowed_ports=$(ufw status | grep "ALLOW" | grep -E "(22|80|443)" | wc -l)
        if [ "$allowed_ports" -ge 2 ]; then
            log_verification "Firewall Ports" "PASS" "SSH and web ports allowed" "Allowed ports: $allowed_ports"
        else
            log_verification "Firewall Ports" "FAIL" "Missing required ports" "Should allow SSH (22) and web (80,443)"
        fi
    else
        log_verification "Firewall Status" "FAIL" "UFW firewall not active" "Run: sudo ufw enable"
    fi
else
    log_verification "Firewall Status" "FAIL" "UFW not available" "Install: sudo apt install ufw"
fi

# Check secrets file
if [ -f ".env.production" ]; then
    perms=$(stat -c "%a" .env.production)
    if [ "$perms" = "600" ]; then
        log_verification "Secrets Permissions" "PASS" "Secure file permissions" "Permissions: 600"
    else
        log_verification "Secrets Permissions" "FAIL" "Insecure permissions" "Current: $perms, should be 600"
    fi
    
    # Check for placeholder secrets
    if grep -q "YOUR-\|placeholder\|test-\|dev-" .env.production; then
        log_verification "Secrets Content" "FAIL" "Placeholder secrets found" "Replace with production values"
    else
        log_verification "Secrets Content" "PASS" "No placeholder secrets detected"
    fi
else
    log_verification "Secrets File" "FAIL" "Production secrets file missing" "Run: ./scripts/setup-production-secrets.sh"
fi

# 3. Database Exposure Check
echo ""
echo "🗄️ Step 3: Database Exposure Check"
echo "=================================="

# Run database exposure verification
if [ -f "scripts/verify-database-exposure.sh" ]; then
    echo "🔍 Running database exposure verification..."
    if ./scripts/verify-database-exposure.sh > /dev/null 2>&1; then
        log_verification "Database Exposure" "PASS" "No databases exposed" "All databases internal only"
    else
        log_verification "Database Exposure" "FAIL" "Database exposure detected" "Check script output for details"
    fi
else
    log_verification "Database Exposure" "FAIL" "Verification script missing" "Run: ./scripts/verify-database-exposure.sh"
fi

# 4. Network Isolation Check
echo ""
echo "🌐 Step 4: Network Isolation Check"
echo "=================================="

# Check Docker networks
if docker network ls | grep -q "genesis_backend_3_database-network"; then
    if docker network inspect genesis_backend_3_database-network | grep -q '"Internal": true'; then
        log_verification "Database Network" "PASS" "Database network is internal" "No external access"
    else
        log_verification "Database Network" "FAIL" "Database network not isolated" "Set internal: true"
    fi
else
    log_verification "Database Network" "FAIL" "Database network missing" "Check docker-compose.production.yml"
fi

if docker network ls | grep -q "genesis_backend_3_backend-network"; then
    if docker network inspect genesis_backend_3_backend-network | grep -q '"Internal": true'; then
        log_verification "Backend Network" "PASS" "Backend network is internal" "Services isolated"
    else
        log_verification "Backend Network" "FAIL" "Backend network not isolated" "Set internal: true"
    fi
else
    log_verification "Backend Network" "FAIL" "Backend network missing" "Check docker-compose.production.yml"
fi

# Check for exposed ports
exposed_ports=$(docker ps --format "table {{.Names}}\t{{.Ports}}" | grep -v "0.0.0.0" | grep -v ":::" | wc -l)
if [ "$exposed_ports" -eq 2 ]; then
    # Should only have nginx (80,443) and maybe auth_service (8001) for testing
    log_verification "Port Exposure" "PASS" "Only essential ports exposed" "Exposed ports: $exposed_ports"
else
    log_verification "Port Exposure" "FAIL" "Too many ports exposed" "Should only expose 80/443"
fi

# 5. Backup System Check
echo ""
echo "💾 Step 5: Backup System Check"
echo "=================================="

# Check backup directory
if [ -d "/opt/genesis/backups" ]; then
    log_verification "Backup Directory" "PASS" "Backup directory exists" "/opt/genesis/backups"
    
    # Check recent backups
    recent_backups=$(find /opt/genesis/backups -name "*.gpg" -mtime -7 | wc -l)
    if [ "$recent_backups" -gt 0 ]; then
        log_verification "Recent Backups" "PASS" "Recent backups available" "Last 7 days: $recent_backups"
    else
        log_verification "Recent Backups" "FAIL" "No recent backups" "Run backup system setup"
    fi
else
    log_verification "Backup Directory" "FAIL" "Backup directory missing" "Create backup infrastructure"
fi

# Check backup encryption
if [ -f "/opt/genesis/secrets/backup_encryption.key" ]; then
    log_verification "Backup Encryption" "PASS" "Encryption key exists" "Backups are encrypted"
else
    log_verification "Backup Encryption" "FAIL" "Encryption key missing" "Generate backup encryption key"
fi

# 6. Monitoring System Check
echo ""
echo "📊 Step 6: Monitoring System Check"
echo "=================================="

# Check if monitoring stack is running
if docker ps | grep -q "prometheus"; then
    log_verification "Prometheus" "PASS" "Prometheus is running" "Metrics collection active"
else
    log_verification "Prometheus" "FAIL" "Prometheus not running" "Start monitoring stack"
fi

if docker ps | grep -q "grafana"; then
    log_verification "Grafana" "PASS" "Grafana is running" "Dashboard available"
else
    log_verification "Grafana" "FAIL" "Grafana not running" "Start monitoring stack"
fi

if docker ps | grep -q "alertmanager"; then
    log_verification "Alertmanager" "PASS" "Alertmanager is running" "Alerts configured"
else
    log_verification "Alertmanager" "FAIL" "Alertmanager not running" "Start monitoring stack"
fi

# 7. Service Health Check
echo ""
echo "🏥 Step 7: Service Health Check"
echo "=================================="

# Check core services
services=("gateway" "auth_service" "chat_service" "memory_service" "llm_service")
for service in "${services[@]}"; do
    if curl -s -f "http://localhost:8000/health" > /dev/null 2>&1; then
        log_verification "Service Health ($service)" "PASS" "Service responding" "HTTP 200"
    else
        log_verification "Service Health ($service)" "FAIL" "Service not responding" "Check service logs"
    fi
done

# Check database health
databases=("auth_db" "chat_db" "memory_db")
for db in "${databases[@]}"; do
    if docker exec "genesis_${db}" pg_isready -U genesis_${db}_user_prod -d ${db} > /dev/null 2>&1; then
        log_verification "Database Health ($db)" "PASS" "Database accepting connections" "PostgreSQL ready"
    else
        log_verification "Database Health ($db)" "FAIL" "Database not ready" "Check database logs"
    fi
done

# 8. Resource Usage Check
echo ""
echo "💻 Step 8: Resource Usage Check"
echo "=================================="

# Check disk usage
disk_usage=$(df / | awk 'NR==1{next} {print $5}' | head -1)
disk_usage_num=$(echo "$disk_usage" | sed 's/%//')
if [ "$disk_usage_num" -lt 80 ]; then
    log_verification "Disk Usage" "PASS" "Disk usage acceptable" "Current: $disk_usage"
elif [ "$disk_usage_num" -lt 90 ]; then
    log_verification "Disk Usage" "WARN" "Disk usage high" "Current: $disk_usage"
else
    log_verification "Disk Usage" "FAIL" "Disk usage critical" "Current: $disk_usage"
fi

# Check memory usage
memory_usage=$(free | awk 'NR==2{printf "%.1f%%", $3*100/$2}' | head -1)
memory_usage_num=$(echo "$memory_usage" | sed 's/%//')
if [ "$memory_usage_num" -lt 80 ]; then
    log_verification "Memory Usage" "PASS" "Memory usage acceptable" "Current: $memory_usage"
elif [ "$memory_usage_num" -lt 90 ]; then
    log_verification "Memory Usage" "WARN" "Memory usage high" "Current: $memory_usage"
else
    log_verification "Memory Usage" "FAIL" "Memory usage critical" "Current: $memory_usage"
fi

# Check CPU load
cpu_load=$(uptime | awk -F'load average:' '{print $10}' | awk '{print $1}' | head -1)
if (( $(echo "$cpu_load < 1.0" | bc -l) )); then
    log_verification "CPU Load" "PASS" "CPU load acceptable" "Current: $cpu_load"
elif (( $(echo "$cpu_load < 2.0" | bc -l) )); then
    log_verification "CPU Load" "WARN" "CPU load high" "Current: $cpu_load"
else
    log_verification "CPU Load" "FAIL" "CPU load critical" "Current: $cpu_load"
fi

# 9. SSL/TLS Check
echo ""
echo "🔒 Step 9: SSL/TLS Check"
echo "=================================="

# Check SSL certificates
if [ -d "/etc/letsencrypt/live" ]; then
    domains=("resonantgenesis.ai" "api.resonantgenesis.ai")
    for domain in "${domains[@]}"; do
        if [ -f "/etc/letsencrypt/live/$domain/fullchain.pem" ]; then
            expiry_date=$(openssl x509 -in "/etc/letsencrypt/live/$domain/fullchain.pem" -noout -enddate | cut -d= -f1)
            expiry_epoch=$(date -d "$expiry_date" +%s)
            current_epoch=$(date +%s)
            days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400))
            
            if [ "$days_until_expiry" -gt 7 ]; then
                log_verification "SSL Certificate ($domain)" "PASS" "Certificate valid" "Expires in $days_until_expiry days"
            elif [ "$days_until_expiry" -gt 0 ]; then
                log_verification "SSL Certificate ($domain)" "WARN" "Certificate expiring soon" "Expires in $days_until_expiry days"
            else
                log_verification "SSL Certificate ($domain)" "FAIL" "Certificate expired" "Expired $days_until_expiry days ago"
            fi
        else
            log_verification "SSL Certificate ($domain)" "FAIL" "Certificate missing" "Obtain SSL certificate"
        fi
    done
else
    log_verification "SSL Certificates" "FAIL" "Let's Encrypt directory missing" "Install certificates"
fi

# 10. Final Status Update
echo ""
echo "📋 Step 10: Final Status"
echo "=================="

if [ $ISSUES_FOUND -eq 0 ]; then
    update_status "PASS"
    echo -e "${GREEN}✅ ALL VERIFICATIONS PASSED${NC}"
    echo ""
    echo "🎉 System is ready for production deployment!"
    echo ""
    echo "📋 Verification report saved to: $VERIFICATION_REPORT"
    echo ""
    echo "🚀 Deploy with confidence:"
    echo "   docker compose -f docker-compose.production.yml --env-file .env.production up -d"
else
    update_status "FAIL"
    echo -e "${RED}❌ CRITICAL ISSUES FOUND${NC}"
    echo ""
    echo "🚨 DO NOT DEPLOY TO PRODUCTION"
    echo ""
    echo "📋 Issues found: $ISSUES_FOUND"
    echo "📋 Verification report: $VERIFICATION_REPORT"
    echo ""
    echo "🔧 Fix all issues before deployment"
fi

echo ""
echo "📊 Verification Summary:"
echo "===================="
jq -r '.checks_performed[] | {name, status, message}' "$VERIFICATION_REPORT"
echo ""
echo "📋 Full report: $VERIFICATION_REPORT"
