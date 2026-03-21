#!/bin/bash

echo "=== CRITICAL SERVICES HEALTH CHECK ==="

if curl -sf http://localhost:80 > /dev/null; then
  echo "✅ Nginx (Frontend): UP"
else
  echo "❌ Nginx (Frontend): DOWN"
fi

if curl -sf http://localhost:8000/health > /dev/null; then
  echo "✅ Gateway (API): UP"
else
  echo "❌ Gateway (API): DOWN"
fi

cd /root/genesis2026_production_backend
if docker-compose ps | grep auth_service | grep -q "Up"; then
  echo "✅ Auth Service: UP"
else
  echo "❌ Auth Service: DOWN"
fi

echo ""
echo "=== ALL SERVICES STATUS ==="
docker-compose ps
