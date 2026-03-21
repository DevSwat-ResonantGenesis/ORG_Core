#!/bin/bash
# Test script for analytics endpoints
# Tests all possible analytics endpoint variations

echo "========================================="
echo "Analytics Endpoint Testing Script"
echo "========================================="
echo ""

# Configuration
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8000}"
TEST_USER_ID="${TEST_USER_ID:-test-user-123}"
AUTH_TOKEN="${AUTH_TOKEN:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local method=${2:-GET}
    local expected_status=${3:-200}
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -n "Testing ${method} ${endpoint} ... "
    
    if [ -n "$AUTH_TOKEN" ]; then
        response=$(curl -s -w "\n%{http_code}" -X ${method} \
            -H "Authorization: Bearer ${AUTH_TOKEN}" \
            -H "x-user-id: ${TEST_USER_ID}" \
            "${GATEWAY_URL}${endpoint}")
    else
        response=$(curl -s -w "\n%{http_code}" -X ${method} \
            -H "x-user-id: ${TEST_USER_ID}" \
            "${GATEWAY_URL}${endpoint}")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" == "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP ${http_code})"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Expected ${expected_status}, got ${http_code})"
        echo "Response: ${body}" | head -c 200
        echo ""
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

echo "Testing Analytics Endpoints..."
echo "================================"
echo ""

# Test 1: Direct /analytics endpoint
echo "1. Direct Analytics Endpoint"
test_endpoint "/analytics"
test_endpoint "/analytics?time_range=7d"
echo ""

# Test 2: /api/analytics endpoint
echo "2. API Analytics Endpoint"
test_endpoint "/api/analytics"
test_endpoint "/api/analytics?time_range=30d"
echo ""

# Test 3: /api/v1/analytics endpoint
echo "3. API v1 Analytics Endpoint"
test_endpoint "/api/v1/analytics"
test_endpoint "/api/v1/analytics?time_range=1d"
echo ""

# Test 4: Specific analytics sub-endpoints
echo "4. Analytics Sub-Endpoints"
test_endpoint "/analytics/usage"
test_endpoint "/api/analytics/usage"
test_endpoint "/api/v1/analytics/usage"
echo ""

test_endpoint "/analytics/quality"
test_endpoint "/api/analytics/quality"
test_endpoint "/api/v1/analytics/quality"
echo ""

test_endpoint "/analytics/topics"
test_endpoint "/api/analytics/topics"
test_endpoint "/api/v1/analytics/topics"
echo ""

test_endpoint "/analytics/memory"
test_endpoint "/api/analytics/memory"
test_endpoint "/api/v1/analytics/memory"
echo ""

# Test 5: Admin stats endpoint
echo "5. Admin Stats Endpoint"
test_endpoint "/analytics/admin/stats"
test_endpoint "/api/analytics/admin/stats"
test_endpoint "/api/v1/analytics/admin/stats"
echo ""

# Summary
echo "========================================="
echo "Test Summary"
echo "========================================="
echo "Total Tests:  ${TOTAL_TESTS}"
echo -e "Passed:       ${GREEN}${PASSED_TESTS}${NC}"
echo -e "Failed:       ${RED}${FAILED_TESTS}${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please review the output above.${NC}"
    exit 1
fi
