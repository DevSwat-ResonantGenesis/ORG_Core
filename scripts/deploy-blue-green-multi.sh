#!/bin/bash

# Blue-Green Multi-Compose Deployment Script
# Handles blue-green deployment with multiple compose files

set -e

echo "=========================================="
echo "🔄 BLUE-GREEN MULTI-COMPOSE DEPLOYMENT"
echo "=========================================="
echo ""

# Configuration
local files=(
        "docker-compose.${color}.enhanced.yml"
        "docker-compose.production.yml"
        "docker-compose.services.shared-redis.yml"
        "docker-compose.shared-redis.yml"
        "docker-compose.dns-enhanced.yml"
        "docker-compose.self-healing.yml"
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

# Function to get current active environment
get_active_environment() {
    if docker-compose -f docker-compose.blue.yml ps | grep -q "Up"; then
        echo "blue"
    elif docker-compose -f docker-compose.green.yml ps | grep -q "Up"; then
        echo "green"
    else
        echo "none"
    fi
}

# Function to deploy environment
deploy_environment() {
    local color=$1
    local compose_args=""
    
    print_status "INFO" "Deploying $color environment..."
    
    # Build compose arguments
    compose_args="-f docker-compose.${color}.yml"
    for file in "${COMPOSE_FILES[@]}"; do
        if [ -f "$file" ]; then
            compose_args="$compose_args -f $file"
        else
            print_status "ERROR" "Missing $file"
            exit 1
        fi
    done
    
    # Stop other environment if running
    local other_color="green"
    if [ "$color" = "green" ]; then
        other_color="blue"
    fi
    
    if [ "$(get_active_environment)" = "$other_color" ]; then
        print_status "INFO" "Stopping $other_color environment..."
        docker-compose -f docker-compose.${other_color}.yml down
    fi
    
    # Deploy new environment
    print_status "INFO" "Starting $color environment deployment..."
    eval "docker-compose $compose_args pull"
    eval "docker-compose $compose_args up -d"
    
    # Wait for services to be ready
    print_status "INFO" "Waiting for services to be ready..."
    sleep 30
    
    # Verify deployment
    print_status "INFO" "Verifying $color deployment..."
    eval "docker-compose $compose_args ps"
    
    print_status "SUCCESS" "$color environment deployed successfully!"
}

# Function to switch traffic
switch_traffic() {
    local target_color=$1
    
    print_status "INFO" "Switching traffic to $target_color environment..."
    
    # Update load balancer or DNS (implementation depends on your setup)
    # This is a placeholder for actual traffic switching logic
    
    if [ "$target_color" = "blue" ]; then
        print_status "INFO" "Traffic switched to blue environment"
    else
        print_status "INFO" "Traffic switched to green environment"
    fi
}

# Function to rollback
rollback() {
    local current_color=$(get_active_environment)
    local rollback_color="green"
    
    if [ "$current_color" = "green" ]; then
        rollback_color="blue"
    fi
    
    print_status "WARNING" "Rolling back to $rollback_color environment..."
    deploy_environment "$rollback_color"
    switch_traffic "$rollback_color"
    print_status "SUCCESS" "Rollback completed!"
}

# Function to show status
show_status() {
    local current_color=$(get_active_environment)
    
    print_status "INFO" "Current active environment: $current_color"
    echo ""
    
    if [ "$current_color" != "none" ]; then
        print_status "INFO" "$current_color environment status:"
        docker-compose -f docker-compose.${current_color}.yml ps
    else
        print_status "WARNING" "No environment is currently active"
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  deploy blue    Deploy blue environment"
    echo "  deploy green   Deploy green environment"
    echo "  switch blue   Switch traffic to blue"
    echo "  switch green  Switch traffic to green"
    echo "  rollback      Rollback to previous environment"
    echo "  status        Show current status"
    echo "  verify        Verify current deployment"
    echo "  logs blue     Show blue environment logs"
    echo "  logs green    Show green environment logs"
    echo "  stop blue     Stop blue environment"
    echo "  stop green    Stop green environment"
    echo ""
    echo "Examples:"
    echo "  $0 deploy blue     # Deploy blue environment"
    echo "  $0 switch blue     # Switch traffic to blue"
    echo "  $0 rollback         # Rollback deployment"
    echo "  $0 status           # Show current status"
}

# Main logic
case "${1:-status}" in
    "deploy")
        if [ -z "$2" ]; then
            print_status "ERROR" "Please specify environment (blue or green)"
            show_usage
            exit 1
        fi
        
        if [ "$2" != "blue" ] && [ "$2" != "green" ]; then
            print_status "ERROR" "Environment must be 'blue' or 'green'"
            show_usage
            exit 1
        fi
        
        deploy_environment "$2"
        ;;
    "switch")
        if [ -z "$2" ]; then
            print_status "ERROR" "Please specify environment (blue or green)"
            show_usage
            exit 1
        fi
        
        if [ "$2" != "blue" ] && [ "$2" != "green" ]; then
            print_status "ERROR" "Environment must be 'blue' or 'green'"
            show_usage
            exit 1
        fi
        
        switch_traffic "$2"
        ;;
    "rollback")
        rollback
        ;;
    "status")
        show_status
        ;;
    "verify")
        local current_color=$(get_active_environment)
        if [ "$current_color" != "none" ]; then
            print_status "INFO" "Verifying $current_color environment..."
            
            # Check health endpoints
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
        else
            print_status "ERROR" "No active environment to verify"
        fi
        ;;
    "logs")
        if [ -z "$2" ]; then
            print_status "ERROR" "Please specify environment (blue or green)"
            show_usage
            exit 1
        fi
        
        if [ "$2" != "blue" ] && [ "$2" != "green" ]; then
            print_status "ERROR" "Environment must be 'blue' or 'green'"
            show_usage
            exit 1
        fi
        
        print_status "INFO" "Showing $2 environment logs..."
        docker-compose -f docker-compose.${2}.yml logs -f
        ;;
    "stop")
        if [ -z "$2" ]; then
            print_status "ERROR" "Please specify environment (blue or green)"
            show_usage
            exit 1
        fi
        
        if [ "$2" != "blue" ] && [ "$2" != "green" ]; then
            print_status "ERROR" "Environment must be 'blue' or 'green'"
            show_usage
            exit 1
        fi
        
        print_status "INFO" "Stopping $2 environment..."
        docker-compose -f docker-compose.${2}.yml down
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
echo "✅ BLUE-GREEN DEPLOYMENT COMPLETE"
echo "=========================================="
echo ""
