#!/bin/bash
# Master Test Runner for ResonantGenesis Backend
# Runs all integration tests across all services
# Author: Agent 7 - ResonantGenesis Team
# Created: February 21, 2026

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================="
echo "ResonantGenesis Backend - Master Test Suite"
echo -e "==========================================${NC}"
echo ""

# Set test environment
export TESTING=true
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Track results
PASSED=0
FAILED=0
SKIPPED=0

# Function to run tests for a service
run_service_tests() {
    local service_name=$1
    local test_dir=$2
    
    echo -e "${YELLOW}------------------------------------------"
    echo "Testing: $service_name"
    echo -e "------------------------------------------${NC}"
    
    if [ -d "$test_dir" ]; then
        export PYTHONPATH="$PROJECT_ROOT/$service_name:$PYTHONPATH"
        if pytest "$test_dir" -v --tb=short 2>/dev/null; then
            echo -e "${GREEN}✅ $service_name tests PASSED${NC}"
            ((PASSED++))
        else
            echo -e "${RED}❌ $service_name tests FAILED${NC}"
            ((FAILED++))
        fi
    else
        echo -e "${YELLOW}⚠️ $service_name tests SKIPPED (no test directory)${NC}"
        ((SKIPPED++))
    fi
    echo ""
}

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "Installing pytest..."
    pip install pytest pytest-asyncio httpx pytest-cov
fi

# Parse command line arguments
case "${1:-all}" in
    "gateway")
        run_service_tests "gateway" "$PROJECT_ROOT/gateway/tests"
        ;;
    "auth")
        run_service_tests "auth_service" "$PROJECT_ROOT/auth_service/tests"
        ;;
    "blockchain")
        run_service_tests "blockchain_service" "$PROJECT_ROOT/blockchain_service/tests"
        ;;
    "coverage")
        echo "Running all tests with coverage..."
        pip install pytest-cov 2>/dev/null || true
        pytest "$PROJECT_ROOT/gateway/tests" "$PROJECT_ROOT/auth_service/tests" "$PROJECT_ROOT/blockchain_service/tests" \
            -v --cov=gateway/app --cov=auth_service/app --cov=blockchain_service/app \
            --cov-report=term-missing --cov-report=html
        ;;
    "quick")
        echo "Running quick smoke tests..."
        pytest "$PROJECT_ROOT/gateway/tests" "$PROJECT_ROOT/auth_service/tests" "$PROJECT_ROOT/blockchain_service/tests" \
            -v -k "health or Health" --tb=short
        ;;
    "all"|*)
        echo "Running all service tests..."
        echo ""
        
        # Gateway tests
        run_service_tests "gateway" "$PROJECT_ROOT/gateway/tests"
        
        # Auth service tests
        run_service_tests "auth_service" "$PROJECT_ROOT/auth_service/tests"
        
        # Blockchain service tests
        run_service_tests "blockchain_service" "$PROJECT_ROOT/blockchain_service/tests"
        
        # Summary
        echo -e "${BLUE}=========================================="
        echo "Test Summary"
        echo -e "==========================================${NC}"
        echo -e "${GREEN}Passed: $PASSED${NC}"
        echo -e "${RED}Failed: $FAILED${NC}"
        echo -e "${YELLOW}Skipped: $SKIPPED${NC}"
        echo ""
        
        if [ $FAILED -gt 0 ]; then
            echo -e "${RED}❌ Some tests failed!${NC}"
            exit 1
        else
            echo -e "${GREEN}✅ All tests passed!${NC}"
        fi
        ;;
esac

echo ""
echo -e "${BLUE}=========================================="
echo "Test run completed!"
echo -e "==========================================${NC}"
