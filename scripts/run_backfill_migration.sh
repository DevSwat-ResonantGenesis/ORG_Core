#!/bin/bash
# =============================================================================
# Hash Sphere Memory Backfill Migration Runner
# =============================================================================
# This script runs the backfill migration inside the memory_service container
# to ensure proper database connectivity and dependencies.
#
# Usage:
#   ./run_backfill_migration.sh              # Run migration
#   ./run_backfill_migration.sh --dry-run    # Test without changes
#   ./run_backfill_migration.sh --force      # Reprocess all records
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=============================================="
echo "Hash Sphere Memory Backfill Migration"
echo "=============================================="
echo "Project directory: $PROJECT_DIR"
echo "Arguments: $@"
echo "=============================================="

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose not found"
    exit 1
fi

# Change to project directory
cd "$PROJECT_DIR"

# Copy the migration script to memory_service
echo "Copying migration script to memory_service container..."
docker cp scripts/backfill_memory_hash_xyz.py resonantgenesis_backend-memory_service-1:/app/backfill_memory_hash_xyz.py

# Run the migration inside the container
echo "Running migration..."
docker exec -it resonantgenesis_backend-memory_service-1 python /app/backfill_memory_hash_xyz.py \
    --database-url "postgresql+asyncpg://postgres:postgres@memory_db:5432/memory_db" \
    "$@"

echo "=============================================="
echo "Migration complete!"
echo "=============================================="
