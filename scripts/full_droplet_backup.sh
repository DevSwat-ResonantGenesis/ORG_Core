#!/bin/bash
# =============================================================================
# Genesis 2026 — Full Droplet Backup Script
# Creates a complete backup of everything needed to deploy to a new droplet.
# Run as: sudo bash /home/deploy/genesis2026_production_backend/scripts/full_droplet_backup.sh
# =============================================================================

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_ROOT="/home/deploy/droplet_backup_${TIMESTAMP}"
LOG="${BACKUP_ROOT}/backup.log"

mkdir -p "${BACKUP_ROOT}"
exec > >(tee -a "$LOG") 2>&1

echo "============================================="
echo "  Genesis 2026 Full Droplet Backup"
echo "  Started: $(date)"
echo "  Output:  ${BACKUP_ROOT}"
echo "============================================="

# -------------------------------------------------
# 1. ENVIRONMENT FILES & SECRETS
# -------------------------------------------------
echo ""
echo "[1/10] Backing up environment files and secrets..."
mkdir -p "${BACKUP_ROOT}/env"
cp /home/deploy/genesis2026_production_backend/.env* "${BACKUP_ROOT}/env/" 2>/dev/null || true
# Capture all env vars loaded into containers
docker inspect --format='{{.Name}} {{range .Config.Env}}{{println .}}{{end}}' $(docker ps -q) > "${BACKUP_ROOT}/env/container_env_dump.txt" 2>/dev/null || true
echo "  ✓ Environment files backed up"

# -------------------------------------------------
# 2. DOCKER COMPOSE & SERVICE CONFIGS
# -------------------------------------------------
echo ""
echo "[2/10] Backing up Docker Compose and service configs..."
mkdir -p "${BACKUP_ROOT}/docker"
cp /home/deploy/genesis2026_production_backend/docker-compose*.yml "${BACKUP_ROOT}/docker/" 2>/dev/null || true
# Save current container list and their images
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' > "${BACKUP_ROOT}/docker/running_containers.txt"
docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.ID}}' > "${BACKUP_ROOT}/docker/images.txt"
docker network ls > "${BACKUP_ROOT}/docker/networks.txt"
docker volume ls > "${BACKUP_ROOT}/docker/volumes.txt"
echo "  ✓ Docker config backed up"

# -------------------------------------------------
# 3. MANAGED DATABASE DUMP (DigitalOcean PostgreSQL)
# -------------------------------------------------
echo ""
echo "[3/10] Dumping managed PostgreSQL database..."
mkdir -p "${BACKUP_ROOT}/database"

# Extract DB connection from env
DB_URL=$(grep '^DATABASE_URL=' /home/deploy/genesis2026_production_backend/.env.production | head -1 | cut -d= -f2-)
# Parse components (handle asyncpg:// or postgresql://)
DB_URL_CLEAN=$(echo "$DB_URL" | sed 's|postgresql+asyncpg://|postgresql://|')
DB_USER=$(echo "$DB_URL_CLEAN" | sed 's|postgresql://\([^:]*\):.*|\1|')
DB_PASS=$(echo "$DB_URL_CLEAN" | sed 's|postgresql://[^:]*:\([^@]*\)@.*|\1|')
DB_HOST=$(echo "$DB_URL_CLEAN" | sed 's|.*@\([^:]*\):.*|\1|')
DB_PORT=$(echo "$DB_URL_CLEAN" | sed 's|.*:\([0-9]*\)/.*|\1|')
DB_NAME=$(echo "$DB_URL_CLEAN" | sed 's|.*/\([^?]*\).*|\1|')

# Use a container that has psql/pg_dump available, or install it
if docker exec auth_service which pg_dump >/dev/null 2>&1; then
    echo "  Using auth_service container for pg_dump..."
    docker exec auth_service bash -c "PGPASSWORD='${DB_PASS}' pg_dump -h '${DB_HOST}' -p '${DB_PORT}' -U '${DB_USER}' -d '${DB_NAME}' --no-owner --no-acl -Fc" > "${BACKUP_ROOT}/database/managed_db.dump" 2>/dev/null
    echo "  ✓ Managed DB dump: $(du -h ${BACKUP_ROOT}/database/managed_db.dump | cut -f1)"
else
    # Fallback: dump via Python/SQLAlchemy schema + data
    echo "  pg_dump not available in containers, using alternative method..."
    docker exec auth_service python3 -c "
import asyncio, os, json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text, inspect

async def main():
    db = os.getenv('DATABASE_URL', '')
    if 'asyncpg' not in db:
        db = db.replace('postgresql://', 'postgresql+asyncpg://')
    engine = create_async_engine(db)
    async with AsyncSession(engine) as s:
        # Get all table names
        r = await s.execute(text(\"SELECT tablename FROM pg_tables WHERE schemaname = 'public'\"))
        tables = [row[0] for row in r.fetchall()]
        print(json.dumps({'tables': tables, 'count': len(tables)}))
asyncio.run(main())
" > "${BACKUP_ROOT}/database/table_list.json"
    echo "  ✓ Table list saved (pg_dump not available for full dump)"
    echo "  ⚠ MANUAL STEP: Run pg_dump from a machine with PostgreSQL client installed:"
    echo "    PGPASSWORD='<password>' pg_dump -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} --no-owner -Fc > managed_db.dump"
fi

# -------------------------------------------------
# 4. RABBIT LOCAL DATABASE DUMP
# -------------------------------------------------
echo ""
echo "[4/10] Dumping Rabbit local PostgreSQL..."
if docker ps --format '{{.Names}}' | grep -q rabbit_db; then
    docker exec rabbit_db pg_dump -U rabbit -d rabbit_db -Fc > "${BACKUP_ROOT}/database/rabbit_db.dump" 2>/dev/null || true
    echo "  ✓ Rabbit DB dump: $(du -h ${BACKUP_ROOT}/database/rabbit_db.dump 2>/dev/null | cut -f1 || echo 'N/A')"
else
    echo "  ⚠ rabbit_db container not running"
fi

# -------------------------------------------------
# 5. DOCKER VOLUMES
# -------------------------------------------------
echo ""
echo "[5/10] Backing up Docker volumes..."
mkdir -p "${BACKUP_ROOT}/volumes"

for vol in $(docker volume ls -q); do
    echo "  Backing up volume: ${vol}..."
    docker run --rm \
        -v "${vol}:/source:ro" \
        -v "${BACKUP_ROOT}/volumes:/backup" \
        alpine tar czf "/backup/${vol}.tar.gz" -C /source . 2>/dev/null || echo "  ⚠ Failed to backup volume ${vol}"
done
echo "  ✓ Volumes backed up: $(ls ${BACKUP_ROOT}/volumes/*.tar.gz 2>/dev/null | wc -l) volumes"

# -------------------------------------------------
# 6. DOCKER IMAGES (save as tarballs)
# -------------------------------------------------
echo ""
echo "[6/10] Saving Docker images..."
mkdir -p "${BACKUP_ROOT}/images"

# Only save custom-built images (not base images like postgres, redis, alpine)
for img in $(docker images --format '{{.Repository}}:{{.Tag}}' | grep 'genesis2026'); do
    safe_name=$(echo "$img" | tr '/:' '_')
    echo "  Saving image: ${img}..."
    docker save "$img" | gzip > "${BACKUP_ROOT}/images/${safe_name}.tar.gz" 2>/dev/null || echo "  ⚠ Failed to save ${img}"
done
echo "  ✓ Images saved: $(ls ${BACKUP_ROOT}/images/*.tar.gz 2>/dev/null | wc -l) images"

# -------------------------------------------------
# 7. NGINX CONFIGURATION
# -------------------------------------------------
echo ""
echo "[7/10] Backing up Nginx configuration..."
mkdir -p "${BACKUP_ROOT}/nginx"
cp -r /etc/nginx/nginx.conf "${BACKUP_ROOT}/nginx/" 2>/dev/null || true
cp -r /etc/nginx/sites-available/ "${BACKUP_ROOT}/nginx/sites-available/" 2>/dev/null || true
cp -r /etc/nginx/sites-enabled/ "${BACKUP_ROOT}/nginx/sites-enabled/" 2>/dev/null || true
cp -r /etc/nginx/snippets/ "${BACKUP_ROOT}/nginx/snippets/" 2>/dev/null || true
cp -r /etc/nginx/conf.d/ "${BACKUP_ROOT}/nginx/conf.d/" 2>/dev/null || true
echo "  ✓ Nginx config backed up"

# -------------------------------------------------
# 8. SSL CERTIFICATES (Let's Encrypt)
# -------------------------------------------------
echo ""
echo "[8/10] Backing up SSL certificates..."
mkdir -p "${BACKUP_ROOT}/ssl"
cp -rL /etc/letsencrypt/ "${BACKUP_ROOT}/ssl/letsencrypt/" 2>/dev/null || true
echo "  ✓ SSL certs backed up"
echo "  NOTE: On a new droplet, you may need to re-issue certs with certbot"

# -------------------------------------------------
# 9. FRONTEND BUILD
# -------------------------------------------------
echo ""
echo "[9/10] Backing up frontend..."
mkdir -p "${BACKUP_ROOT}/frontend"
tar czf "${BACKUP_ROOT}/frontend/frontend_dist.tar.gz" -C /var/www/frontend . 2>/dev/null || true
# Also backup the source
tar czf "${BACKUP_ROOT}/frontend/frontend_source.tar.gz" \
    --exclude='node_modules' \
    --exclude='.git' \
    -C /home/deploy/genesis2026_frontend_production_2 . 2>/dev/null || true
echo "  ✓ Frontend backed up"

# -------------------------------------------------
# 10. BACKEND SOURCE CODE
# -------------------------------------------------
echo ""
echo "[10/10] Backing up backend source..."
mkdir -p "${BACKUP_ROOT}/backend"
tar czf "${BACKUP_ROOT}/backend/backend_source.tar.gz" \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='node_modules' \
    -C /home/deploy/genesis2026_production_backend . 2>/dev/null || true
echo "  ✓ Backend source backed up"

# -------------------------------------------------
# GENERATE RESTORE GUIDE
# -------------------------------------------------
echo ""
echo "Generating restore guide..."

cat > "${BACKUP_ROOT}/RESTORE_GUIDE.md" << 'GUIDE'
# Genesis 2026 — Droplet Restore Guide

## Prerequisites
- Fresh Ubuntu 22.04+ droplet
- Docker & Docker Compose installed
- Nginx installed
- `deploy` user created with sudo access
- Domain DNS pointing to new droplet IP

## Restore Steps

### 1. Copy backup to new droplet
```bash
scp -r droplet_backup_YYYYMMDD_HHMMSS deploy@NEW_IP:/home/deploy/
```

### 2. Restore backend source
```bash
mkdir -p /home/deploy/genesis2026_production_backend
cd /home/deploy/genesis2026_production_backend
tar xzf /home/deploy/droplet_backup_*/backend/backend_source.tar.gz
```

### 3. Restore environment files
```bash
cp /home/deploy/droplet_backup_*/env/.env* /home/deploy/genesis2026_production_backend/
# IMPORTANT: Update DATABASE_URL if using a new managed DB
# IMPORTANT: Update any IP-specific configs
```

### 4. Restore Docker images (faster than rebuilding)
```bash
for img in /home/deploy/droplet_backup_*/images/*.tar.gz; do
  gunzip -c "$img" | docker load
done
```

### 5. Restore Docker volumes
```bash
for vol_file in /home/deploy/droplet_backup_*/volumes/*.tar.gz; do
  vol_name=$(basename "$vol_file" .tar.gz)
  docker volume create "$vol_name"
  docker run --rm -v "${vol_name}:/dest" -v "$(dirname $vol_file):/backup:ro" \
    alpine sh -c "cd /dest && tar xzf /backup/$(basename $vol_file)"
done
```

### 6. Restore databases
```bash
# Managed DB (if using same DigitalOcean DB):
# Already connected, no restore needed.
# If new DB:
pg_restore -h NEW_DB_HOST -p 25060 -U doadmin -d defaultdb --no-owner managed_db.dump

# Rabbit local DB:
docker-compose -f docker-compose.unified.yml up -d rabbit_db
sleep 10
docker exec -i rabbit_db pg_restore -U rabbit -d rabbit_db < /home/deploy/droplet_backup_*/database/rabbit_db.dump
```

### 7. Start all services
```bash
cd /home/deploy/genesis2026_production_backend
docker-compose -f docker-compose.unified.yml up -d
```

### 8. Restore Nginx
```bash
sudo cp /home/deploy/droplet_backup_*/nginx/nginx.conf /etc/nginx/
sudo cp -r /home/deploy/droplet_backup_*/nginx/sites-available/* /etc/nginx/sites-available/
sudo cp -r /home/deploy/droplet_backup_*/nginx/sites-enabled/* /etc/nginx/sites-enabled/
# Update server_name and IP if needed
sudo nginx -t && sudo systemctl restart nginx
```

### 9. Restore SSL (or re-issue)
```bash
# Option A: Copy existing certs (same domain)
sudo cp -r /home/deploy/droplet_backup_*/ssl/letsencrypt/* /etc/letsencrypt/

# Option B: Re-issue certs (recommended for new droplet)
sudo certbot --nginx -d dev-swat.com -d resonantgenesis.xyz
```

### 10. Restore frontend
```bash
sudo mkdir -p /var/www/frontend
sudo tar xzf /home/deploy/droplet_backup_*/frontend/frontend_dist.tar.gz -C /var/www/frontend/
```

### 11. Verify
```bash
# Check all containers running
docker ps

# Test gateway
curl -s http://localhost:8001/api/v1/auth/providers | head -c 200

# Test frontend
curl -s -o /dev/null -w '%{http_code}' https://dev-swat.com/
```

## Important Notes
- Update `.env.production` DATABASE_URL if pointing to a new managed DB
- Update DNS A records for dev-swat.com and resonantgenesis.xyz
- The managed PostgreSQL on DigitalOcean is EXTERNAL — it persists regardless of droplet
- Redis data is ephemeral (cache) — losing it is OK
- Blockchain node data is in a Docker volume — restore it or let it re-sync
GUIDE

echo "  ✓ Restore guide generated"

# -------------------------------------------------
# FINAL SUMMARY
# -------------------------------------------------
echo ""
echo "============================================="
echo "  Backup Complete!"
echo "  Location: ${BACKUP_ROOT}"
echo "  Size: $(du -sh ${BACKUP_ROOT} | cut -f1)"
echo "  Time: $(date)"
echo "============================================="
echo ""
echo "Contents:"
du -sh ${BACKUP_ROOT}/*/ 2>/dev/null | sed 's|.*/||'
echo ""
echo "To download this backup to your local machine:"
echo "  scp -r deploy@dev-swat.com:${BACKUP_ROOT} ~/Desktop/"
echo ""
echo "To create a compressed archive:"
echo "  cd /home/deploy && tar czf droplet_backup_${TIMESTAMP}.tar.gz droplet_backup_${TIMESTAMP}/"
