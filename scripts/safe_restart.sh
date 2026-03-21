#!/bin/bash
set -e

SERVICE_NAME=$1

if [ -z "$SERVICE_NAME" ]; then
  echo "Usage: ./safe_restart.sh <service_name>"
  exit 1
fi

cd /root/genesis2026_production_backend

if ! docker-compose ps | grep -q "$SERVICE_NAME"; then
  echo "Error: Service $SERVICE_NAME not found"
  exit 1
fi

PROTECTED_SERVICES=("nginx" "gateway" "auth_service")
if [[ " ${PROTECTED_SERVICES[@]} " =~ " ${SERVICE_NAME} " ]]; then
  echo "⚠️  WARNING: $SERVICE_NAME is a protected service!"
  echo "Are you sure you want to restart it? (yes/no)"
  read -r response
  if [ "$response" != "yes" ]; then
    echo "Aborted"
    exit 0
  fi
fi

echo "🔄 Safely restarting $SERVICE_NAME..."

docker-compose stop "$SERVICE_NAME"
docker-compose rm -f "$SERVICE_NAME"
docker-compose build "$SERVICE_NAME"
docker-compose up -d "$SERVICE_NAME"

sleep 10

if docker-compose ps | grep "$SERVICE_NAME" | grep -q "Up"; then
  echo "✅ $SERVICE_NAME restarted successfully"
else
  echo "❌ $SERVICE_NAME failed to start"
  docker-compose logs "$SERVICE_NAME" --tail=50
  exit 1
fi
