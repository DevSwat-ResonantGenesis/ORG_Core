#!/usr/bin/env bash
set -euo pipefail

# Build all microservice images (placeholder, will be expanded as services are added)

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

echo "Building gateway image..."
docker build -f docker/gateway.Dockerfile -t resonantgenesis/gateway:latest .
