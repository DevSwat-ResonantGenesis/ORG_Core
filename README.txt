# Genesis2026 Production Deployment

## Quick Start

1. Copy .env.production.template to .env.production
2. Fill in all environment variables
3. Deploy: docker compose up -d

## Files

- docker-compose.yml: Production deployment (28 containers, external DB/Redis/S3)
- .env.production.template: Environment variables template
- nginx/: Nginx reverse proxy configuration
- */: Service directories with Dockerfiles

## Requirements

- Docker & Docker Compose
- DigitalOcean Spaces (or S3-compatible storage)
- PostgreSQL managed database (15 databases)
- Redis managed database

## Deploy

docker compose up -d

## Check Status

docker compose ps
docker compose logs -f
