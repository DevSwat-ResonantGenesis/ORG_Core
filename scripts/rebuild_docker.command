#!/bin/bash
# Double-click this file to rebuild Docker containers

cd "/Users/devswat/Resonanat genesis  2026 /resonantgenesis_backend "

echo "🛑 Stopping containers..."
docker-compose down

echo "🔨 Rebuilding memory_service and chat_service..."
docker-compose build memory_service chat_service

echo "🚀 Starting all containers..."
docker-compose up -d

echo ""
echo "✅ Done! Containers rebuilt with memory improvements."
echo ""
echo "Press any key to close..."
read -n 1
