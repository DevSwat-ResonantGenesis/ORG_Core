#!/bin/bash
set -e

cd /Users/devswat/resonantgenesis_backend

case "$1" in
  infra)
    echo "Starting infrastructure only (DBs + MinIO)..."
    docker compose up -d auth_db user_db chat_db cog_db wf_db ml_db memory_db minio
    ;;
  memory)
    echo "Starting memory_service..."
    docker compose up -d memory_service
    ;;
  auth)
    echo "Starting auth_service..."
    docker compose up -d auth_service
    ;;
  user)
    echo "Starting user_service..."
    docker compose up -d user_service
    ;;
  chat)
    echo "Starting chat_service..."
    docker compose up -d chat_service
    ;;
  memory)
    echo "Starting memory_service..."
    docker compose up -d memory_service
    ;;
  cognitive)
    echo "Starting cognitive_service..."
    docker compose up -d cognitive_service
    ;;
  workflow)
    echo "Starting workflow_service..."
    docker compose up -d workflow_service
    ;;
  ml)
    echo "Starting ml_service..."
    docker compose up -d ml_service
    ;;
  storage)
    echo "Starting storage_service..."
    docker compose up -d storage_service
    ;;
  llm)
    echo "Starting llm_service..."
    docker compose up -d llm_service
    ;;
  redis)
    echo "Starting redis..."
    docker compose up -d redis
    ;;
  gateway)
    echo "Starting gateway..."
    docker compose up -d gateway
    ;;
  *)
    echo "Starting full microservice stack..."
    docker compose up --build
    ;;
esac
