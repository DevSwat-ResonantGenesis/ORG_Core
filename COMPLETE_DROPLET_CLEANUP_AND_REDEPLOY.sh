#!/bin/bash

# ============================================================
# COMPLETE DROPLET CLEANUP AND REDEPLOYMENT SCRIPT
# ============================================================
# This script will:
# 1. Stop all services
# 2. Remove all Docker containers, images, volumes, networks
# 3. Clean up all configuration files
# 4. Clear caches and temporary files
# 5. Deploy fresh from local version
# ============================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# ============================================================
# SECTION 1: STOP ALL SERVICES
# ============================================================
stop_all_services() {
    log "Stopping all services..."
    
    # Stop Docker Compose services
    cd /root/genesis2026_production_backend
    if [ -f "docker-compose.yml" ]; then
        docker-compose down --remove-orphans || true
    fi
    
    # Stop nginx
    systemctl stop nginx || true
    
    # Kill any remaining Python processes
    pkill -f "uvicorn" || true
    pkill -f "python" || true
    
    log "All services stopped"
}

# ============================================================
# SECTION 2: CLEANUP DOCKER ENVIRONMENT
# ============================================================
cleanup_docker() {
    log "Cleaning up Docker environment..."
    
    # Remove all containers
    info "Removing all containers..."
    docker rm -f $(docker ps -aq) 2>/dev/null || true
    
    # Remove all images
    info "Removing all Docker images..."
    docker rmi -f $(docker images -q) 2>/dev/null || true
    
    # Remove all volumes
    warning "Removing all Docker volumes (this will delete data!)..."
    docker volume rm -f $(docker volume ls -q) 2>/dev/null || true
    
    # Remove all networks
    info "Removing all Docker networks..."
    docker network rm -f $(docker network ls -q) 2>/dev/null || true
    
    # Prune Docker system
    docker system prune -a -f --volumes || true
    
    log "Docker environment cleaned"
}

# ============================================================
# SECTION 3: CLEANUP CONFIGURATION FILES
# ============================================================
cleanup_config_files() {
    log "Cleaning up configuration files..."
    
    # Remove nginx configuration
    rm -rf /etc/nginx/*
    rm -rf /var/log/nginx/*
    
    # Remove application directories
    rm -rf /root/genesis2026_production_backend
    rm -rf /var/www/frontend
    rm -rf /var/backups/frontend
    
    # Clean up temporary files
    rm -rf /tmp/*
    rm -rf /var/tmp/*
    
    # Clean up logs
    rm -rf /var/log/*/*
    
    log "Configuration files cleaned"
}

# ============================================================
# SECTION 4: CLEANUP SYSTEM CACHE
# ============================================================
cleanup_system_cache() {
    log "Cleaning up system cache..."
    
    # Clear package cache
    apt-get clean
    apt-get autoclean
    apt-get autoremove -y
    
    # Clear systemd cache
    journalctl --vacuum-time=3days
    systemctl daemon-reload
    
    # Clear Python cache
    find /root -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    
    log "System cache cleaned"
}

# ============================================================
# SECTION 5: RESET TO CLEAN STATE
# ============================================================
reset_to_clean_state() {
    log "Resetting to clean state..."
    
    # Create necessary directories
    mkdir -p /root/genesis2026_production_backend
    mkdir -p /var/www/frontend
    mkdir -p /var/backups/frontend
    mkdir -p /var/log/nginx
    mkdir -p /etc/nginx
    
    # Set permissions
    chown -R www-data:www-data /var/www/frontend
    chown -R www-data:www-data /var/backups/frontend
    
    log "Clean state prepared"
}

# ============================================================
# SECTION 6: DEPLOY FROM LOCAL VERSION
# ============================================================
deploy_from_local() {
    log "Deploying from local version..."
    
    # Copy local backend to server
    info "Copying backend files from local to server..."
    rsync -avz --delete \
        "/Users/devswat/Genesis2026 /genesis2026_production_backend/" \
        root@dev-swat.com:/root/genesis2026_production_backend/
    
    # Copy local frontend build to server
    info "Copying frontend build from local to server..."
    rsync -avz --delete \
        "/Users/devswat/Genesis2026 /genesis2026_production_frontend/dist/" \
        root@dev-swat.com:/var/www/frontend/
    
    # Copy nginx configuration
    info "Copying nginx configuration..."
    cp /root/genesis2026_production_backend/nginx/nginx-production-https.conf /etc/nginx/nginx.conf
    
    # Set up environment file
    cp /root/genesis2026_production_backend/.env.production /root/genesis2026_production_backend/.env
    
    # Build and start services
    cd /root/genesis2026_production_backend
    
    info "Building Docker images..."
    docker-compose build
    
    info "Starting services..."
    docker-compose up -d
    
    # Start nginx
    systemctl start nginx
    systemctl enable nginx
    
    log "Deployment completed"
}

# ============================================================
# SECTION 7: VERIFICATION
# ============================================================
verify_deployment() {
    log "Verifying deployment..."
    
    # Check if services are running
    sleep 10
    
    info "Checking Docker containers..."
    docker ps
    
    info "Checking nginx status..."
    systemctl status nginx --no-pager | head -10
    
    info "Checking frontend access..."
    curl -I https://dev-swat.com/ | head -5
    
    info "Checking API access..."
    curl -I https://dev-swat.com/health | head -5
    
    log "Deployment verification completed"
}

# ============================================================
# MAIN EXECUTION
# ============================================================
main() {
    log "Starting complete droplet cleanup and redeployment..."
    
    # Confirmation prompt
    echo -e "${RED}WARNING: This will completely wipe your droplet and redeploy from local version!${NC}"
    echo -e "${RED}All data will be lost. Are you sure you want to continue? (yes/no)${NC}"
    read -r confirmation
    
    if [[ $confirmation != "yes" ]]; then
        error "Operation cancelled by user"
        exit 1
    fi
    
    # Execute cleanup and redeployment
    stop_all_services
    cleanup_docker
    cleanup_config_files
    cleanup_system_cache
    reset_to_clean_state
    deploy_from_local
    verify_deployment
    
    log "Complete droplet cleanup and redeployment finished successfully!"
    echo -e "${GREEN}🎉 Your droplet has been cleaned and redeployed from local version!${NC}"
}

# Run main function
main "$@"
