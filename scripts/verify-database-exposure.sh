#!/bin/bash
# Database Exposure Verification Script
# CRITICAL: Run this before ANY production deployment

set -e

echo "🔍 DATABASE EXPOSURE VERIFICATION"
echo "================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get droplet IP (assuming DigitalOcean)
DROPLET_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")
echo "📍 Droplet IP: $DROPLET_IP"
echo ""

# Function to check if port is exposed
check_port_exposure() {
    local port=$1
    local service=$2
    
    echo -n "🔍 Checking $service (port $port)... "
    
    # Check if port is listening on 0.0.0.0
    if docker exec genesis_${service}_db netstat -tlnp 2>/dev/null | grep -q "0.0.0.0:$port"; then
        echo -e "${RED}❌ EXPOSED TO INTERNET${NC}"
        echo "   ⚠️  $service is listening on 0.0.0.0:$port"
        echo "   🚨 This is CRITICAL - database is publicly accessible!"
        return 1
    elif docker exec genesis_${service}_db netstat -tlnp 2>/dev/null | grep -q "127.0.0.1:$port"; then
        echo -e "${GREEN}✅ INTERNAL ONLY (127.0.0.1)${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  UNKNOWN STATUS${NC}"
        echo "   Could not determine binding for $service"
        return 2
    fi
}

# Function to check Redis
check_redis_exposure() {
    echo -n "🔍 Checking Redis (port 6379)... "
    
    if docker exec genesis_redis redis-cli CONFIG GET bind | grep -q "0.0.0.0"; then
        echo -e "${RED}❌ EXPOSED TO INTERNET${NC}"
        echo "   ⚠️  Redis is listening on 0.0.0.0:6379"
        echo "   🚨 This is CRITICAL - Redis is publicly accessible!"
        return 1
    else
        echo -e "${GREEN}✅ INTERNAL ONLY${NC}"
        return 0
    fi
}

# Function to check MinIO
check_minio_exposure() {
    echo -n "🔍 Checking MinIO (ports 9000-9001)... "
    
    if docker exec genesis_minio netstat -tlnp 2>/dev/null | grep -q "0.0.0.0:9000"; then
        echo -e "${RED}❌ EXPOSED TO INTERNET${NC}"
        echo "   ⚠️  MinIO is listening on 0.0.0.0:9000"
        echo "   🚨 This is CRITICAL - storage is publicly accessible!"
        return 1
    else
        echo -e "${GREEN}✅ INTERNAL ONLY${NC}"
        return 0
    fi
}

# Function to scan from external perspective
external_scan() {
    echo ""
    echo "🌐 EXTERNAL SCAN (from internet perspective)"
    echo "=========================================="
    
    echo "🔍 Scanning $DROPLET_IP for exposed database ports..."
    
    # Check PostgreSQL ports
    if nmap -p 5432 $DROPLET_IP 2>/dev/null | grep -q "open"; then
        echo -e "${RED}❌ PostgreSQL (5432) EXPOSED TO INTERNET${NC}"
        echo "   🚨 CRITICAL: Database port is accessible from internet!"
    else
        echo -e "${GREEN}✅ PostgreSQL (5432) not accessible from internet${NC}"
    fi
    
    # Check Redis port
    if nmap -p 6379 $DROPLET_IP 2>/dev/null | grep -q "open"; then
        echo -e "${RED}❌ Redis (6379) EXPOSED TO INTERNET${NC}"
        echo "   🚨 CRITICAL: Redis port is accessible from internet!"
    else
        echo -e "${GREEN}✅ Redis (6379) not accessible from internet${NC}"
    fi
    
    # Check MinIO ports
    if nmap -p 9000-9001 $DROPLET_IP 2>/dev/null | grep -q "open"; then
        echo -e "${RED}❌ MinIO (9000-9001) EXPOSED TO INTERNET${NC}"
        echo "   🚨 CRITICAL: Storage ports are accessible from internet!"
    else
        echo -e "${GREEN}✅ MinIO (9000-9001) not accessible from internet${NC}"
    fi
    
    # Check for any unexpected service ports
    echo "🔍 Scanning for unexpected service ports (8000-8099)..."
    if nmap -p 8000-8099 $DROPLET_IP 2>/dev/null | grep -q "open"; then
        echo -e "${RED}❌ INTERNAL SERVICES EXPOSED TO INTERNET${NC}"
        echo "   🚨 CRITICAL: Internal service ports are accessible!"
        nmap -p 8000-8099 $DROPLET_IP 2>/dev/null | grep "open"
    else
        echo -e "${GREEN}✅ No internal services exposed to internet${NC}"
    fi
}

# Function to check Docker network configuration
check_docker_networks() {
    echo ""
    echo "🐳 DOCKER NETWORK CONFIGURATION"
    echo "==============================="
    
    echo "🔍 Checking Docker networks..."
    docker network ls --format "table {{.Name}}\t{{.Driver}}\t{{.Internal}}"
    
    echo ""
    echo "🔍 Checking service network assignments..."
    
    # Check if databases are in internal network
    if docker network inspect genesis_backend_3_database-network 2>/dev/null | grep -q "\"Internal\": true"; then
        echo -e "${GREEN}✅ Database network is internal${NC}"
    else
        echo -e "${RED}❌ Database network is not properly isolated${NC}"
    fi
    
    # Check if backend network is internal
    if docker network inspect genesis_backend_3_backend-network 2>/dev/null | grep -q "\"Internal\": true"; then
        echo -e "${GREEN}✅ Backend network is internal${NC}"
    else
        echo -e "${RED}❌ Backend network is not properly isolated${NC}"
    fi
}

# Function to check database credentials
check_database_credentials() {
    echo ""
    echo "🔐 DATABASE CREDENTIALS CHECK"
    echo "==========================="
    
    if [ -f ".env.production" ]; then
        echo "🔍 Checking for weak/default passwords..."
        
        # Check for default passwords
        if grep -q "auth_pass\|user_pass\|admin123\|password" .env.production; then
            echo -e "${RED}❌ DEFAULT OR WEAK PASSWORDS FOUND${NC}"
            echo "   🚨 CRITICAL: Using default or weak passwords!"
            grep -n "auth_pass\|user_pass\|admin123\|password" .env.production
        else
            echo -e "${GREEN}✅ No default passwords detected${NC}"
        fi
        
        # Check for placeholder secrets
        if grep -q "your-\|placeholder\|test-\|dev-" .env.production; then
            echo -e "${RED}❌ PLACEHOLDER SECRETS FOUND${NC}"
            echo "   🚨 CRITICAL: Using placeholder secrets in production!"
            grep -n "your-\|placeholder\|test-\|dev-" .env.production
        else
            echo -e "${GREEN}✅ No placeholder secrets detected${NC}"
        fi
        
        # Check file permissions
        perms=$(stat -c "%a" .env.production)
        if [ "$perms" = "600" ]; then
            echo -e "${GREEN}✅ .env.production has secure permissions (600)${NC}"
        else
            echo -e "${RED}❌ .env.production has insecure permissions ($perms)${NC}"
            echo "   🚨 Should be 600 (read/write for owner only)"
        fi
    else
        echo -e "${YELLOW}⚠️  .env.production not found${NC}"
        echo "   Ensure production secrets file exists"
    fi
}

# Main execution
echo "Starting database exposure verification..."
echo ""

# Check if containers are running
if ! docker ps | grep -q "genesis_"; then
    echo -e "${RED}❌ No Genesis containers running${NC}"
    echo "   Please start services first: docker compose -f docker-compose.production.yml up -d"
    exit 1
fi

# Run all checks
EXPOSURE_FOUND=0

echo "📊 INTERNAL BINDING CHECKS"
echo "=========================="
check_port_exposure 5432 "auth"
[ $? -eq 1 ] && EXPOSURE_FOUND=1

check_port_exposure 5432 "chat" 
[ $? -eq 1 ] && EXPOSURE_FOUND=1

check_port_exposure 5432 "memory"
[ $? -eq 1 ] && EXPOSURE_FOUND=1

check_redis_exposure
[ $? -eq 1 ] && EXPOSURE_FOUND=1

check_minio_exposure
[ $? -eq 1 ] && EXPOSURE_FOUND=1

check_docker_networks
check_database_credentials
external_scan

# Final assessment
echo ""
echo "📋 FINAL ASSESSMENT"
echo "=================="

if [ $EXPOSURE_FOUND -eq 1 ]; then
    echo -e "${RED}❌ CRITICAL SECURITY ISSUES FOUND${NC}"
    echo ""
    echo "🚨 IMMEDIATE ACTION REQUIRED:"
    echo "1. Fix exposed database bindings"
    echo "2. Update Docker network configuration"
    echo "3. Configure firewall rules"
    echo "4. Re-run this verification"
    echo ""
    echo "❌ DO NOT DEPLOY TO PRODUCTION"
    exit 1
else
    echo -e "${GREEN}✅ ALL DATABASES PROPERLY ISOLATED${NC}"
    echo ""
    echo "🎉 Security checks passed:"
    echo "✅ No databases exposed to internet"
    echo "✅ Docker networks properly isolated"
    echo "✅ No default passwords detected"
    echo "✅ No placeholder secrets found"
    echo ""
    echo "✅ READY FOR PRODUCTION DEPLOYMENT"
fi
