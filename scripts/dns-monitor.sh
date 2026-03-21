#!/bin/bash

# DNS Monitoring Script for Genesis2026 Backend
# Monitors DNS resolution times and connectivity

# Configuration
LOG_FILE="/var/log/dns-monitor.log"
ALERT_THRESHOLD=5000  # 5 seconds in milliseconds
SERVICES=("resonant-db-do-user-18031534-0.g.db.ondigitalocean.com" "ml-registry-db-do-user-18031534-0.g.db.ondigitalocean.com" "sfo3.digitaloceanspaces.com")

# Create log directory
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to test DNS resolution
test_dns_resolution() {
    local hostname=$1
    local start_time=$(date +%s%3N)
    
    # Test DNS resolution
    if nslookup "$hostname" > /dev/null 2>&1; then
        local end_time=$(date +%s%3N)
        local resolution_time=$((end_time - start_time))
        
        if [ $resolution_time -gt $ALERT_THRESHOLD ]; then
            log "ALERT: DNS resolution for $hostname took ${resolution_time}ms (threshold: ${ALERT_THRESHOLD}ms)"
            return 2
        else
            log "INFO: DNS resolution for $hostname took ${resolution_time}ms"
            return 0
        fi
    else
        log "ERROR: DNS resolution failed for $hostname"
        return 1
    fi
}

# Function to test IP connectivity
test_ip_connectivity() {
    local hostname=$1
    local ip=$2
    local port=$3
    
    if nc -z "$ip" "$port" 2>/dev/null; then
        log "INFO: IP connectivity to $ip:$port successful"
        return 0
    else
        log "ERROR: IP connectivity to $ip:$port failed"
        return 1
    fi
}

# Function to test SSL connectivity
test_ssl_connectivity() {
    local hostname=$1
    local ip=$2
    local port=$3
    
    if timeout 10 openssl s_client -connect "$ip:$port" -servername "$hostname" < /dev/null > /dev/null 2>&1; then
        log "INFO: SSL connectivity to $hostname ($ip:$port) successful"
        return 0
    else
        log "ERROR: SSL connectivity to $hostname ($ip:$port) failed"
        return 1
    fi
}

# Main monitoring function
main() {
    log "Starting DNS monitoring for Genesis2026 Backend"
    
    # Test each service
    for service in "${SERVICES[@]}"; do
        log "Testing service: $service"
        
        # Test DNS resolution
        test_dns_resolution "$service"
        dns_result=$?
        
        # Test IP connectivity (fallback)
        case $service in
            *resonant-db*)
                test_ip_connectivity "$service" "24.199.117.203" "25060"
                ip_result=$?
                test_ssl_connectivity "$service" "24.199.117.203" "25060"
                ssl_result=$?
                ;;
            *ml-registry-db*)
                test_ip_connectivity "$service" "24.199.117.203" "25060"
                ip_result=$?
                test_ssl_connectivity "$service" "24.199.117.203" "25060"
                ssl_result=$?
                ;;
            *digitaloceanspaces.com*)
                test_ip_connectivity "$service" "sfo3.digitaloceanspaces.com" "443"
                ip_result=$?
                test_ssl_connectivity "$service" "sfo3.digitaloceanspaces.com" "443"
                ssl_result=$?
                ;;
        esac
        
        # Log summary
        if [ $dns_result -eq 0 ] && [ $ip_result -eq 0 ] && [ $ssl_result -eq 0 ]; then
            log "SUCCESS: All connectivity tests passed for $service"
        else
            log "FAILURE: Some connectivity tests failed for $service"
        fi
        
        echo "---" >> "$LOG_FILE"
    done
    
    log "DNS monitoring completed"
}

# Run main function
main "$@"
