#!/bin/bash

# DNS Testing Script for Genesis2026 Backend
# Tests hostname resolution and provides recommendations

# Configuration
SERVICES=(
    "resonant-db-do-user-18031534-0.g.db.ondigitalocean.com:25060:24.199.117.203"
    "ml-registry-db-do-user-18031534-0.g.db.ondigitalocean.com:25060:24.199.117.203"
    "sfo3.digitaloceanspaces.com:443:sfo3.digitaloceanspaces.com"
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

# Function to test DNS resolution
test_dns() {
    local hostname=$1
    local port=$2
    local ip=$3
    
    print_status "INFO" "Testing DNS resolution for $hostname"
    
    # Test DNS resolution
    if nslookup "$hostname" > /dev/null 2>&1; then
        local resolved_ip=$(nslookup "$hostname" | grep -A1 "Name:" | tail -1 | awk '{print $2}')
        print_status "SUCCESS" "DNS resolution successful: $hostname -> $resolved_ip"
        
        # Test connectivity
        if nc -z "$ip" "$port" 2>/dev/null; then
            print_status "SUCCESS" "IP connectivity successful: $ip:$port"
        else
            print_status "ERROR" "IP connectivity failed: $ip:$port"
        fi
        
        # Test SSL
        if timeout 10 openssl s_client -connect "$ip:$port" -servername "$hostname" < /dev/null > /dev/null 2>&1; then
            print_status "SUCCESS" "SSL connectivity successful: $hostname ($ip:$port)"
        else
            print_status "ERROR" "SSL connectivity failed: $hostname ($ip:$port)"
        fi
    else
        print_status "ERROR" "DNS resolution failed for $hostname"
        print_status "INFO" "Falling back to IP address: $ip:$port"
        
        # Test IP connectivity
        if nc -z "$ip" "$port" 2>/dev/null; then
            print_status "SUCCESS" "IP connectivity successful: $ip:$port"
        else
            print_status "ERROR" "IP connectivity failed: $ip:$port"
        fi
    fi
}

# Function to test DNS resolution time
test_dns_time() {
    local hostname=$1
    local iterations=5
    local total_time=0
    
    print_status "INFO" "Testing DNS resolution time for $hostname ($iterations iterations)"
    
    for i in $(seq 1 $iterations); do
        local start_time=$(date +%s%3N)
        if nslookup "$hostname" > /dev/null 2>&1; then
            local end_time=$(date +%s%3N)
            local resolution_time=$((end_time - start_time))
            total_time=$((total_time + resolution_time))
            print_status "INFO" "Iteration $i: ${resolution_time}ms"
        else
            print_status "ERROR" "DNS resolution failed on iteration $i"
            return 1
        fi
    done
    
    local average_time=$((total_time / iterations))
    if [ $average_time -lt 1000 ]; then
        print_status "SUCCESS" "Average DNS resolution time: ${average_time}ms"
    elif [ $average_time -lt 5000 ]; then
        print_status "WARNING" "Average DNS resolution time: ${average_time}ms (slow)"
    else
        print_status "ERROR" "Average DNS resolution time: ${average_time}ms (very slow)"
    fi
}

# Function to provide recommendations
provide_recommendations() {
    print_status "INFO" "DNS Configuration Recommendations:"
    echo ""
    print_status "INFO" "1. Current Configuration:"
    echo "   - Using IP addresses in database URLs (working)"
    echo "   - SSL required for all database connections"
    echo "   - HTTPS required for Spaces"
    echo ""
    print_status "INFO" "2. DNS Configuration Options:"
    echo "   - Option A: Keep current IP-based configuration (recommended)"
    echo "   - Option B: Use DNS-enhanced Docker Compose (flexible)"
    echo "   - Option C: Configure custom DNS servers"
    echo ""
    print_status "INFO" "3. Monitoring Recommendations:"
    echo "   - Run DNS monitoring script periodically"
    echo "   - Monitor DNS resolution times"
    echo "   - Keep IP addresses as fallback"
    echo "   - Test hostname resolution regularly"
    echo ""
    print_status "INFO" "4. Production Recommendations:"
    echo "   - Use IP addresses for critical services"
    echo "   - Configure multiple DNS servers"
    echo "   - Monitor DNS resolution performance"
    echo "   - Have backup connection methods"
}

# Main function
main() {
    echo "=========================================="
    echo "🔍 DNS Testing for Genesis2026 Backend"
    echo "=========================================="
    echo ""
    
    # Test each service
    for service in "${SERVICES[@]}"; do
        IFS=':' read -r hostname port ip <<< "$service"
        echo ""
        echo "Testing: $hostname"
        echo "------------------------"
        test_dns "$hostname" "$port" "$ip"
        test_dns_time "$hostname"
        echo ""
    done
    
    # Provide recommendations
    provide_recommendations
    
    echo ""
    echo "=========================================="
    echo "✅ DNS Testing Complete"
    echo "=========================================="
}

# Run main function
main "$@"
