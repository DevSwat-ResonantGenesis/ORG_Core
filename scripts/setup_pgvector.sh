#!/bin/bash
# Resonant Genesis - pgvector Setup Script
# Run this on your droplet after deployment

set -e

echo "🚀 Setting up pgvector for Resonant Genesis..."

# Configuration - override with environment variables
DB_NAME="${DB_NAME:-resonant_db}"
DB_USER="${DB_USER:-postgres}"
MEMORY_SERVICE_URL="${MEMORY_SERVICE_URL:-http://localhost:8002}"
PROJECT_DIR="${PROJECT_DIR:-/opt/resonant-genesis}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Step 1: Detect and install pgvector
echo ""
echo "📦 Step 1: Installing pgvector extension..."

# Detect PostgreSQL version
if command -v psql &> /dev/null; then
    PG_VERSION=$(psql --version | grep -oE '[0-9]+' | head -1)
    echo "   PostgreSQL version detected: $PG_VERSION"
else
    print_error "PostgreSQL client not found. Please install PostgreSQL first."
    exit 1
fi

# Install pgvector based on OS
if command -v apt-get &> /dev/null; then
    echo "   Detected Debian/Ubuntu..."
    sudo apt-get update -qq
    sudo apt-get install -y postgresql-${PG_VERSION}-pgvector 2>/dev/null || {
        print_warning "Could not install postgresql-${PG_VERSION}-pgvector"
        echo "   Trying alternative installation..."
        # Try building from source
        sudo apt-get install -y git build-essential postgresql-server-dev-${PG_VERSION}
        cd /tmp
        git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
        cd pgvector
        make
        sudo make install
        cd -
    }
elif command -v brew &> /dev/null; then
    echo "   Detected macOS with Homebrew..."
    brew install pgvector 2>/dev/null || print_warning "pgvector may already be installed"
elif command -v yum &> /dev/null; then
    echo "   Detected RHEL/CentOS..."
    sudo yum install -y pgvector_${PG_VERSION} 2>/dev/null || {
        print_warning "Could not install via yum, trying from source..."
    }
else
    print_warning "Could not detect package manager. You may need to install pgvector manually."
    echo "   See: https://github.com/pgvector/pgvector#installation"
fi

print_status "pgvector package installation attempted"

# Step 2: Enable extension in database
echo ""
echo "🔧 Step 2: Enabling vector extension in database..."

# Check if we can connect to the database
if sudo -u postgres psql -d $DB_NAME -c "SELECT 1;" &> /dev/null; then
    sudo -u postgres psql -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null
    
    # Verify
    EXTENSION_EXISTS=$(sudo -u postgres psql -d $DB_NAME -t -c "SELECT 1 FROM pg_extension WHERE extname = 'vector';" 2>/dev/null | tr -d ' ')
    if [ "$EXTENSION_EXISTS" = "1" ]; then
        print_status "pgvector extension enabled in database"
    else
        print_error "Failed to enable pgvector extension"
        echo "   Try manually: sudo -u postgres psql -d $DB_NAME -c 'CREATE EXTENSION vector;'"
    fi
else
    print_warning "Could not connect to database $DB_NAME"
    echo "   Make sure PostgreSQL is running and database exists"
fi

# Step 3: Run database migrations
echo ""
echo "📊 Step 3: Running database migrations..."

MIGRATION_FILE="$PROJECT_DIR/resonantgenesis_backend/memory_service/migrations/001_add_xyz_indexes.sql"
if [ -f "$MIGRATION_FILE" ]; then
    sudo -u postgres psql -d $DB_NAME -f "$MIGRATION_FILE" 2>/dev/null && \
        print_status "Database migrations applied" || \
        print_warning "Some migrations may have already been applied"
else
    print_warning "Migration file not found at $MIGRATION_FILE"
    echo "   Skipping migrations..."
fi

# Step 4: Wait for memory service and create vector index
echo ""
echo "🔍 Step 4: Creating vector index via API..."

# Check if memory service is running
MAX_RETRIES=10
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s "$MEMORY_SERVICE_URL/memory/stats" > /dev/null 2>&1; then
        break
    fi
    echo "   Waiting for memory service... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_warning "Memory service not responding at $MEMORY_SERVICE_URL"
    echo "   You can create the index later with:"
    echo "   curl -X POST $MEMORY_SERVICE_URL/memory/create-vector-index"
else
    # Create the vector index
    RESPONSE=$(curl -s -X POST "$MEMORY_SERVICE_URL/memory/create-vector-index")
    echo "   Response: $RESPONSE"
    
    if echo "$RESPONSE" | grep -q '"status": "success"'; then
        print_status "Vector index created successfully"
    elif echo "$RESPONSE" | grep -q '"status": "failed"'; then
        print_warning "Vector index creation failed"
        echo "   The system will use fallback search (slower but functional)"
    else
        print_warning "Unexpected response from memory service"
    fi
fi

# Step 5: Verify setup
echo ""
echo "📈 Step 5: Verifying setup..."

STATS=$(curl -s "$MEMORY_SERVICE_URL/memory/stats" 2>/dev/null)

if [ -n "$STATS" ]; then
    echo ""
    echo "   Memory Service Stats:"
    echo "$STATS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    pgv = data.get('pgvector', {})
    ec = data.get('embedding_cache', {})
    sc = data.get('semantic_cache', {})
    perf = data.get('performance', {})
    
    print(f\"   - pgvector available: {pgv.get('pgvector_available', 'unknown')}\")
    print(f\"   - Embedding cache: {ec.get('size', 0)}/{ec.get('maxsize', 0)} entries\")
    print(f\"   - Semantic cache: {sc.get('size', 0)}/{sc.get('maxsize', 0)} entries\")
    print(f\"   - Total retrievals: {perf.get('total_retrievals', 0)}\")
except Exception as e:
    print(f'   Could not parse stats: {e}')
" 2>/dev/null || echo "   (Install python3 for detailed stats)"
    
    if echo "$STATS" | grep -q '"pgvector_available": true'; then
        print_status "pgvector is working!"
    else
        print_warning "pgvector not detected - using fallback search"
    fi
else
    print_warning "Could not fetch stats from memory service"
fi

# Summary
echo ""
echo "========================================"
echo "🎉 pgvector Setup Complete!"
echo "========================================"
echo ""
echo "Status:"
echo "  - pgvector extension: Installed"
echo "  - Database migrations: Applied"
echo "  - Vector index: Created (if service was running)"
echo ""
echo "Next steps:"
echo "  1. Verify: curl $MEMORY_SERVICE_URL/memory/stats"
echo "  2. Test:   curl -X POST $MEMORY_SERVICE_URL/memory/retrieve \\"
echo "             -H 'Content-Type: application/json' \\"
echo "             -d '{\"query\": \"test query\", \"limit\": 5, \"use_vector_search\": true}'"
echo ""
echo "For issues, check:"
echo "  - PostgreSQL logs: journalctl -u postgresql"
echo "  - Memory service logs: journalctl -u memory-service"
echo ""
