#!/bin/bash

# Multi-Compose Production Deployment Script
# Deploys all necessary compose files in correct order

set -e

echo "=========================================="
echo "🚀 MULTI-COMPOSE PRODUCTION DEPLOYMENT"
echo "=========================================="
echo ""

# Configuration
COMPOSE_FILES=(
    "docker-compose.production.yml"
    "docker-compose.services.shared-redis.yml"
    "docker-compose.shared-redis.yml"
    "docker-compose.dns-enhanced.yml"
    "docker-compose.self-healing.yml"
)

BLUE_GREEN_FILES=(
    "docker-compose.blue.enhanced.yml"
    "docker-compose.green.enhanced.yml"
)

ALL_COMPOSE_FILES=(
    "docker-compose.production.yml"
    "docker-compose.services.shared-redis.yml"
    "docker-compose.shared-redis.yml"
    "docker-compose.dns-enhanced.yml"
    "docker-compose.self-healing.yml"
    "docker-compose.blue.enhanced.yml"
    "docker-compose.green.enhanced.yml"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "SUCCESS")
            echo -e "${GREEN}✅ $message${NC}"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠️  $message${NC}"
            ;;
        "ERROR")
            echo -e "${RED}❌ $message${NC}"
            ;;
        "INFO")
            echo -e "${BLUE}ℹ️  $message${NC}"
            ;;
    esac
}

# Function to check if compose file exists
check_compose_file() {
    local file=$1
    if [ -f "$file" ]; then
        print_status "SUCCESS" "Found $file"
        return 0
    else
        print_status "ERROR" "Missing $file"
        return 1
    fi
}

# Function to deploy compose files
deploy_compose_files() {
    local files=("$@")
    local compose_args=""
    
    print_status "INFO" "Building compose arguments..."
    for file in "${files[@]}"; do
        if check_compose_file "$file"; then
            compose_args="$compose_args -f $file"
        else
            print_status "ERROR" "Cannot deploy without $file"
            exit 1
        fi
    done
    
    print_status "INFO" "Deploying with compose files: ${files[*]}"
    
    # Pull latest images
    print_status "INFO" "Pulling latest images..."
    eval "docker-compose $compose_args pull"
    
    # Deploy services
    print_status "INFO" "Starting deployment..."
    eval "docker-compose $compose_args up -d"
    
    # Wait for services to be ready
    print_status "INFO" "Waiting for services to be ready..."
    sleep 30
    
    # Check deployment status
    print_status "INFO" "Checking deployment status..."
    eval "docker-compose $compose_args ps"
    
    print_status "SUCCESS" "Deployment completed!"
}

# Function to deploy blue-green
deploy_blue_green() {
    local color=$1
    
    print_status "INFO" "Deploying $color environment..."
    
    local files=(
        "docker-compose.${color}.yml"
        "docker-compose.production.yml"
        "docker-compose.services.yml"
        "docker-compose.dns-enhanced.yml"
        "docker-compose.self-healing.yml"
    )
    
    deploy_compose_files "${files[@]}"
}

# Function to verify deployment
verify_deployment() {
    print_status "INFO" "Verifying deployment..."
    
    # Check if core services are running
    local core_services=("gateway" "auth_service" "redis" "cascade_control_plane")
    
    for service in "${core_services[@]}"; do
        if docker-compose ps | grep -q "$service.*Up"; then
            print_status "SUCCESS" "$service is running"
        else
            print_status "ERROR" "$service is not running"
        fi
    done
    
    # Check health endpoints
    print_status "INFO" "Testing health endpoints..."
    
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        print_status "SUCCESS" "Gateway health check passed"
    else
        print_status "WARNING" "Gateway health check failed"
    fi
    
    if curl -sf http://localhost:8095/health > /dev/null 2>&1; then
        print_status "SUCCESS" "Cascade health check passed"
    else
        print_status "WARNING" "Cascade health check failed"
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  production        Deploy full production environment"
    echo "  blue             Deploy blue environment (original)"
    echo "  green            Deploy green environment (original)"
    echo "  blue-enhanced    Deploy blue environment (enhanced)"
    echo "  green-enhanced   Deploy green environment (enhanced)"
    echo "  enhanced         Deploy with all enhancements"
    echo "  complete         Deploy with ALL compose files"
    echo "  verify           Verify current deployment"
    echo "  status           Show deployment status"
    echo "  logs             Show deployment logs"
    echo "  stop             Stop all services"
    echo "  restart          Restart all services"
    echo "  list             List all available compose files"
    echo ""
    echo "Examples:"
    echo "  $0 production        # Deploy full production"
    echo "  $0 blue-enhanced    # Deploy enhanced blue environment"
    echo "  $0 green-enhanced   # Deploy enhanced green environment"
    echo "  $0 enhanced         # Deploy with all enhancements"
    echo "  $0 complete         # Deploy with ALL compose files"
    echo "  $0 verify           # Verify deployment"
    echo "  $0 list             # List all compose files"
}

# Main deployment logic
case "${1:-production}" in
    "production")
        print_status "INFO" "Starting full production deployment..."
        deploy_compose_files "${COMPOSE_FILES[@]}"
        verify_deployment
        ;;
    "blue")
        print_status "INFO" "Starting blue environment deployment..."
        deploy_blue_green "blue"
        verify_deployment
        ;;
    "green")
        print_status "INFO" "Starting green environment deployment..."
        deploy_blue_green "green"
        verify_deployment
        ;;
    "blue-enhanced")
        print_status "INFO" "Starting enhanced blue environment deployment..."
        deploy_compose_files "docker-compose.blue.enhanced.yml" "docker-compose.production.yml" "docker-compose.services.yml" "docker-compose.dns-enhanced.yml" "docker-compose.self-healing.yml"
        verify_deployment
        ;;
    "green-enhanced")
        print_status "INFO" "Starting enhanced green environment deployment..."
        deploy_compose_files "docker-compose.green.enhanced.yml" "docker-compose.production.yml" "docker-compose.services.yml" "docker-compose.dns-enhanced.yml" "docker-compose.self-healing.yml"
        verify_deployment
        ;;
    "enhanced")
        print_status "INFO" "Starting enhanced deployment..."
        deploy_compose_files "${COMPOSE_FILES[@]}"
        verify_deployment
        ;;
    "complete")
        print_status "INFO" "Starting complete deployment with ALL compose files..."
        deploy_compose_files "${ALL_COMPOSE_FILES[@]}"
        verify_deployment
        ;;
    "list")
        print_status "INFO" "Available Docker Compose files:"
        echo ""
        echo "Core Files:"
        echo "  - docker-compose.original.backup.yml (original - archived)"
        echo "  - docker-compose.production.yml (core infrastructure - NO CORS)"
        echo "  - docker-compose.services.shared-redis.yml (all microservices with shared Redis)"
        echo "  - docker-compose.shared-redis.yml (shared Redis for blue-green)"
        echo ""
        echo "Environment Files:"
        echo "  - docker-compose.blue.enhanced.yml (blue environment - NO CORS)"
        echo "  - docker-compose.green.enhanced.yml (green environment - NO CORS)"
        echo ""
        echo "Enhancement Files:"
        echo "  - docker-compose.dns-enhanced.yml (DNS enhancement)"
        echo "  - docker-compose.self-healing.yml (self-healing)"
        echo ""
        echo "Usage:"
        echo "  - Production: production.yml + services.shared-redis.yml + shared-redis.yml + dns-enhanced.yml + self-healing.yml"
        echo "  - Blue-Enhanced: blue.enhanced.yml + production.yml + services.shared-redis.yml + shared-redis.yml + dns-enhanced.yml + self-healing.yml"
        echo "  - Green-Enhanced: green.enhanced.yml + production.yml + services.shared-redis.yml + shared-redis.yml + dns-enhanced.yml + self-healing.yml"
        echo "  - Complete: ALL compose files"
        echo ""
        echo "Recommendation:"
        echo "  - Use blue-enhanced/green-enhanced for blue-green deployment"
        echo "  - Shared Redis provides session persistence across environments"
        echo "  - Enhanced files include DNS, self-healing, health checks"
        echo "  - Nginx handles all CORS (NO CORS in Gateway)"
        echo "  - PURE SET: Only 8 files for enterprise production"
        echo "  - Original files archived as backup"
        ;;
    "verify")
        print_status "INFO" "Verifying current deployment..."
        verify_deployment
        ;;
    "status")
        print_status "INFO" "Showing deployment status..."
        docker-compose -f docker-compose.production.yml ps
        ;;
    "logs")
        print_status "INFO" "Showing deployment logs..."
        docker-compose -f docker-compose.production.yml logs -f
        ;;
    "stop")
        print_status "INFO" "Stopping all services..."
        docker-compose -f docker-compose.production.yml down
        ;;
    "restart")
        print_status "INFO" "Restarting all services..."
        docker-compose -f docker-compose.production.yml restart
        ;;
    "help"|"--help"|"-h")
        show_usage
        ;;
    *)
        print_status "ERROR" "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "✅ MULTI-COMPOSE DEPLOYMENT COMPLETE"
echo "=========================================="
echo ""
print_status "INFO" "Next steps:"
echo "1. Run './scripts/health_check.sh' to verify health"
echo "2. Run './scripts/websocket_health_check.sh' to test WebSocket"
echo "3. Run './scripts/dns-test.sh' to test DNS resolution"
echo "4. Run './scripts/start_autonomous.sh' to enable self-healing"
echo ""
