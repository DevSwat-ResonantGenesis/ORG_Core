#!/bin/bash
# Resonant Genesis - Start Local Development Services
# This script starts all required backend services for local development

set -e

echo "🚀 Starting Resonant Genesis Backend Services..."
echo ""

# Kill any existing services
echo "🧹 Cleaning up existing processes..."
pkill -f "uvicorn" 2>/dev/null || true
sleep 2

# Base directory
BASE_DIR="/Users/devswat/Resonanat genesis  2026 /resonantgenesis_backend "

# Common environment variables for local development
export PYTHONPATH="."
export DATABASE_URL="postgresql+asyncpg://devswat:@localhost:5432/postgres"

# Start Memory Service (port 8002)
echo "📦 Starting Memory Service on port 8002..."
cd "$BASE_DIR/memory_service"
MEMORY_POSTGRES_HOST=localhost \
MEMORY_POSTGRES_USER=devswat \
MEMORY_POSTGRES_PASSWORD="" \
MEMORY_POSTGRES_DB=postgres \
python3 -m uvicorn app.main:app --port 8002 --reload &
MEMORY_PID=$!
sleep 3

# Start Chat Service (port 8001)
echo "💬 Starting Chat Service on port 8001..."
cd "$BASE_DIR/chat_service"
CHAT_POSTGRES_HOST=localhost \
CHAT_POSTGRES_USER=devswat \
CHAT_POSTGRES_PASSWORD="" \
CHAT_POSTGRES_DB=postgres \
CHAT_MEMORY_SERVICE_URL="http://localhost:8002" \
python3 -m uvicorn app.main:app --port 8001 --reload &
CHAT_PID=$!
sleep 3

# Start Billing Service (port 8004)
echo "💳 Starting Billing Service on port 8004..."
cd "$BASE_DIR/billing_service"
python3 -m uvicorn app.main:app --port 8004 --reload &
BILLING_PID=$!
sleep 3

# Start Gateway (port 8000)
echo "🌐 Starting Gateway on port 8000..."
cd "$BASE_DIR/gateway"
GATEWAY_DEV_MODE=true \
GATEWAY_AUTH_URL="http://localhost:8005" \
GATEWAY_USER_URL="http://localhost:8005" \
GATEWAY_CHAT_URL="http://localhost:8001" \
GATEWAY_MEMORY_URL="http://localhost:8002" \
GATEWAY_BILLING_URL="http://localhost:8004" \
GATEWAY_AGENT_ENGINE_URL="http://localhost:8006" \
python3 -m uvicorn app.main:app --port 8000 --reload &
GATEWAY_PID=$!
sleep 3

echo ""
echo "✅ Services Started!"
echo ""
echo "Service Status:"
echo "  Gateway:  http://localhost:8000 (PID: $GATEWAY_PID)"
echo "  Chat:     http://localhost:8001 (PID: $CHAT_PID)"
echo "  Memory:   http://localhost:8002 (PID: $MEMORY_PID)"
echo "  Billing:  http://localhost:8004 (PID: $BILLING_PID)"
echo ""
echo "To stop all services: pkill -f uvicorn"
echo ""

# Wait for all background processes
wait
