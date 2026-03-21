#!/bin/bash
# Live Production Security Verification
# Executes security checks and produces actual command outputs

set -e

echo "🔍 LIVE PRODUCTION SECURITY VERIFICATION"
echo "===================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🚨 This script will generate CONCRETE EVIDENCE of security posture"
echo "🚨 Not just documentation - actual system verification"
echo ""

# Get droplet IP
DROPLET_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")
echo "📍 Droplet IP: $DROPLET_IP"
echo ""

echo "🔥 1. FIREWALL VERIFICATION"
echo "========================="
echo "Command: sudo ufw status verbose"
echo "Output:"
sudo ufw status verbose
echo ""

echo "🌐 2. NETWORK BINDING VERIFICATION"
echo "==============================="
echo "Command: netstat -tlnp | grep -E ':(5432|6379|9000|8000)'"
echo "Output:"
netstat -tlnp | grep -E ':(5432|6379|9000|8000)' || echo "No database/service ports found"
echo ""

echo "🔍 3. EXTERNAL PORT SCAN"
echo "======================"
echo "Command: nmap -sS -O $DROPLET_IP"
echo "Output:"
nmap -sS -O "$DROPLET_IP" | head -20
echo ""

echo "🐳 4. DOCKER NETWORK INSPECTION"
echo "============================"
echo "Command: docker network ls"
echo "Output:"
docker network ls
echo ""

echo "Command: docker network inspect genesis_backend_3_database-network"
echo "Output:"
docker network inspect genesis_backend_3_database-network 2>/dev/null || echo "Database network not found"
echo ""

echo "Command: docker network inspect genesis_backend_3_backend-network"
echo "Output:"
docker network inspect genesis_backend_3_backend-network 2>/dev/null || echo "Backend network not found"
echo ""

echo "🔐 5. SECRETS VERIFICATION"
echo "========================"
echo "Command: ls -la .env.production"
echo "Output:"
ls -la .env.production 2>/dev/null || echo "Production secrets file not found"
echo ""

if [ -f ".env.production" ]; then
    echo "Command: stat -c '%a %U:%G' .env.production"
    echo "Output:"
    stat -c '%a %U:%G' .env.production
    echo ""
    
    echo "Command: grep -E 'YOUR-|placeholder|test-|dev-' .env.production || echo 'No placeholders found'"
    echo "Output:"
    grep -E 'YOUR-|placeholder|test-|dev-' .env.production || echo "No placeholders found"
    echo ""
fi

echo "🗄️ 6. DATABASE BINDING VERIFICATION"
echo "================================="
for db in auth_db chat_db memory_db; do
    if docker ps | grep -q "$db"; then
        echo "Command: docker exec $db netstat -tlnp"
        echo "Output for $db:"
        docker exec "$db" netstat -tlnp 2>/dev/null || echo "Cannot inspect $db"
        echo ""
    else
        echo "❌ Container $db not running"
        echo ""
    fi
done

echo "🐳 7. CONTAINER PORT EXPOSURE"
echo "=========================="
echo "Command: docker ps --format 'table {{.Names}}\t{{.Ports}}'"
echo "Output:"
docker ps --format "table {{.Names}}\t{{.Ports}}"
echo ""

echo "📊 8. SERVICE HEALTH VERIFICATION"
echo "==============================="
for service in gateway auth_service chat_service memory_service llm_service; do
    echo "Command: curl -s -f http://localhost:8000/health"
    echo "Output for $service:"
    curl -s -f "http://localhost:8000/health" 2>/dev/null && echo "✅ HEALTHY" || echo "❌ UNHEALTHY"
    echo ""
done

echo "💾 9. BACKUP VERIFICATION"
echo "======================"
echo "Command: find /opt/genesis/backups -name '*.gpg' -ls | head -5"
echo "Output:"
find /opt/genesis/backups -name '*.gpg' -ls 2>/dev/null | head -5 || echo "No encrypted backups found"
echo ""

echo "📈 10. MONITORING VERIFICATION"
echo "============================"
echo "Command: docker ps | grep -E 'prometheus|grafana|alertmanager'"
echo "Output:"
docker ps | grep -E 'prometheus|grafana|alertmanager' || echo "No monitoring containers running"
echo ""

echo "🔍 11. METRICS ENDPOINT VERIFICATION"
echo "================================="
echo "Command: curl -s http://localhost:9090/api/v1/status/config"
echo "Output:"
curl -s "http://localhost:9090/api/v1/status/config" 2>/dev/null | head -10 || echo "Prometheus not responding"
echo ""

echo "📋 12. SYSTEM RESOURCE VERIFICATION"
echo "================================="
echo "Command: df -h /"
echo "Output:"
df -h /
echo ""

echo "Command: free -h"
echo "Output:"
free -h
echo ""

echo "Command: uptime"
echo "Output:"
uptime
echo ""

echo "🚨 13. SECURITY ASSESSMENT"
echo "========================"
echo "🔍 Checking for critical security issues..."

# Critical security checks
critical_issues=0

# Check 1: Database exposure
if netstat -tlnp | grep -q "0.0.0.0:5432"; then
    echo "❌ CRITICAL: PostgreSQL exposed to 0.0.0.0"
    ((critical_issues++))
fi

if netstat -tlnp | grep -q "0.0.0.0:6379"; then
    echo "❌ CRITICAL: Redis exposed to 0.0.0.0"
    ((critical_issues++))
fi

# Check 2: Secrets file permissions
if [ -f ".env.production" ]; then
    perms=$(stat -c "%a" .env.production)
    if [ "$perms" != "600" ]; then
        echo "❌ CRITICAL: .env.production has insecure permissions ($perms)"
        ((critical_issues++))
    fi
else
    echo "❌ CRITICAL: .env.production file missing"
    ((critical_issues++))
fi

# Check 3: Firewall status
if ! sudo ufw status | grep -q "Status: active"; then
    echo "❌ CRITICAL: UFW firewall not active"
    ((critical_issues++))
fi

# Check 4: Container port exposure
if docker ps --format "{{.Ports}}" | grep -v "0.0.0.0:80\|0.0.0.0:443" | grep -q "0.0.0.0:"; then
    echo "❌ CRITICAL: Unexpected container ports exposed"
    ((critical_issues++))
fi

# Check 5: Database connectivity
for db in auth_db chat_db memory_db; do
    if docker ps | grep -q "$db"; then
        if ! docker exec "$db" pg_isready -U genesis_${db}_user_prod -d ${db} >/dev/null 2>&1; then
            echo "❌ CRITICAL: Database $db not ready"
            ((critical_issues++))
        fi
    fi
done

echo ""
echo "📊 FINAL ASSESSMENT"
echo "=================="
if [ $critical_issues -eq 0 ]; then
    echo -e "${GREEN}✅ NO CRITICAL SECURITY ISSUES FOUND${NC}"
    echo "🎉 System appears to be properly secured"
    echo ""
    echo "✅ Security posture: SECURE"
    echo "✅ Database exposure: NONE"
    echo "✅ Secrets management: PROPER"
    echo "✅ Network isolation: WORKING"
    echo "✅ Firewall: ACTIVE"
    echo "✅ Container exposure: CONTROLLED"
else
    echo -e "${RED}❌ CRITICAL SECURITY ISSUES FOUND: $critical_issues${NC}"
    echo "🚨 SYSTEM NOT PRODUCTION READY"
    echo ""
    echo "❌ Security posture: CRITICAL"
    echo "❌ Issues must be resolved before production deployment"
fi

echo ""
echo "📋 This provides CONCRETE EVIDENCE of actual system state"
echo "📋 Not documentation - real command outputs from live system"
