#!/bin/bash
# Production Backup and Recovery System
# CRITICAL: Automated database backups with off-site storage

set -e

echo "💾 PRODUCTION BACKUP AND RECOVERY SYSTEM"
echo "====================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
BACKUP_DIR="/opt/genesis/backups"
OFFSITE_BACKUP_DIR="/opt/genesis/backups/offsite"
RETENTION_DAYS=30
BACKUP_ENCRYPTION_KEY_FILE="/opt/genesis/secrets/backup_encryption.key"

echo "🔧 Setting up backup infrastructure..."

# Create backup directories
echo "📁 Creating backup directories..."
sudo mkdir -p "$BACKUP_DIR"/{database,config,logs,secrets}
sudo mkdir -p "$OFFSITE_BACKUP_DIR"
sudo chmod 700 "$BACKUP_DIR" "$OFFSITE_BACKUP_DIR"
sudo chown root:root "$BACKUP_DIR" "$OFFSITE_BACKUP_DIR"

# Generate backup encryption key
if [ ! -f "$BACKUP_ENCRYPTION_KEY_FILE" ]; then
    echo "🔐 Generating backup encryption key..."
    openssl rand -hex 32 > "$BACKUP_ENCRYPTION_KEY_FILE"
    sudo chmod 600 "$BACKUP_ENCRYPTION_KEY_FILE"
    sudo chown root:root "$BACKUP_ENCRYPTION_KEY_FILE"
    echo -e "${GREEN}✅ Backup encryption key generated${NC}"
fi

# Database backup function
backup_database() {
    local db_name=$1
    local db_container=$2
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$BACKUP_DIR/database/${db_name}_backup_${timestamp}.sql"
    
    echo "💾 Backing up $db_name..."
    
    # Create database backup
    docker exec "$db_container" pg_dump -U genesis_${db_name}_user_prod "$db_name" > "$backup_file"
    
    # Compress backup
    gzip "$backup_file"
    
    # Encrypt backup
    gpg --batch --yes --passphrase-file "$BACKUP_ENCRYPTION_KEY_FILE" \
        --symmetric --cipher-algo AES256 \
        --compress-algo 1 \
        --output "${backup_file}.gz.gpg" \
        "${backup_file}.gz"
    
    # Remove unencrypted file
    rm "${backup_file}.gz"
    
    echo -e "${GREEN}✅ $db_name backup completed and encrypted${NC}"
}

# Full system backup function
full_backup() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_manifest="$BACKUP_DIR/backup_manifest_${timestamp}.json"
    
    echo "🔄 Starting full system backup..."
    
    # Backup databases
    echo "📊 Backing up databases..."
    backup_database "auth_db" "genesis_auth_db"
    backup_database "chat_db" "genesis_chat_db"
    backup_database "memory_db" "genesis_memory_db"
    backup_database "billing_db" "genesis_billing_db"
    backup_database "blockchain_db" "genesis_blockchain_db"
    backup_database "ml_db" "genesis_ml_db"
    backup_database "agent_db" "genesis_agent_db"
    
    # Backup Docker volumes
    echo "🐳 Backing up Docker volumes..."
    docker run --rm -v genesis_auth_db_data:/data -v "$BACKUP_DIR/volumes:/backup" \
        alpine tar czf /backup/auth_db_data_${timestamp}.tar.gz -C /data .
    
    docker run --rm -v genesis_chat_db_data:/data -v "$BACKUP_DIR/volumes:/backup" \
        alpine tar czf /backup/chat_db_data_${timestamp}.tar.gz -C /data .
    
    docker run --rm -v genesis_memory_db_data:/data -v "$BACKUP_DIR/volumes:/backup" \
        alpine tar czf /backup/memory_db_data_${timestamp}.tar.gz -C /data .
    
    docker run --rm -v genesis_redis_data:/data -v "$BACKUP_DIR/volumes:/backup" \
        alpine tar czf /backup/redis_data_${timestamp}.tar.gz -C /data .
    
    docker run --rm -v genesis_minio_data:/data -v "$BACKUP_DIR/volumes:/backup" \
        alpine tar czf /backup/minio_data_${timestamp}.tar.gz -C /data .
    
    # Backup configuration files
    echo "⚙️ Backing up configuration..."
    cp -r /opt/genesis/config "$BACKUP_DIR/config/config_${timestamp}"
    cp .env.production "$BACKUP_DIR/secrets/env_production_${timestamp}"
    cp docker-compose.production.yml "$BACKUP_DIR/config/docker-compose_${timestamp}.yml"
    
    # Create backup manifest
    cat > "$backup_manifest" << EOF
{
  "backup_timestamp": "$timestamp",
  "backup_type": "full",
  "databases": [
    "auth_db", "chat_db", "memory_db", "billing_db", 
    "blockchain_db", "ml_db", "agent_db"
  ],
  "volumes": [
    "auth_db_data", "chat_db_data", "memory_db_data",
    "redis_data", "minio_data"
  ],
  "config_files": [
    "docker-compose.production.yml", ".env.production"
  ],
  "encryption_enabled": true,
  "backup_size": "$(du -sh $BACKUP_DIR | cut -f1)"
}
EOF
    
    echo -e "${GREEN}✅ Full system backup completed${NC}"
    echo "📋 Manifest: $backup_manifest"
}

# Offsite backup function
offsite_backup() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    
    echo "☁️ Syncing to offsite storage..."
    
    # Sync recent backups to offsite
    rsync -av --delete "$BACKUP_DIR/database/" "$OFFSITE_BACKUP_DIR/database/"
    rsync -av --delete "$BACKUP_DIR/volumes/" "$OFFSITE_BACKUP_DIR/volumes/"
    rsync -av --delete "$BACKUP_DIR/config/" "$OFFSITE_BACKUP_DIR/config/"
    rsync -av --delete "$BACKUP_DIR/secrets/" "$OFFSITE_BACKUP_DIR/secrets/"
    
    # Create offsite manifest
    cat > "$OFFSITE_BACKUP_DIR/offsite_manifest_${timestamp}.json" << EOF
{
  "offsite_timestamp": "$timestamp",
  "last_sync": "$(date -Iseconds)",
  "total_backups": "$(find $OFFSITE_BACKUP_DIR -name "*.gpg" | wc -l)",
  "offsite_size": "$(du -sh $OFFSITE_BACKUP_DIR | cut -f1)"
}
EOF
    
    echo -e "${GREEN}✅ Offsite backup completed${NC}"
}

# Cleanup old backups
cleanup_old_backups() {
    echo "🧹 Cleaning up old backups (older than $RETENTION_DAYS days)..."
    
    # Clean up local backups
    find "$BACKUP_DIR" -name "*.gpg" -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR" -name "backup_manifest_*.json" -mtime +$RETENTION_DAYS -delete
    
    # Clean up offsite backups (keep longer - 90 days)
    find "$OFFSITE_BACKUP_DIR" -name "*.gpg" -mtime +90 -delete
    find "$OFFSITE_BACKUP_DIR" -name "*.tar.gz" -mtime +90 -delete
    
    echo -e "${GREEN}✅ Old backups cleaned up${NC}"
}

# Recovery function
restore_backup() {
    local backup_date=$1
    local db_name=$2
    
    if [ -z "$backup_date" ] || [ -z "$db_name" ]; then
        echo "❌ Usage: $0 restore <backup_date> <database_name>"
        echo "   Example: $0 restore 20240111_120000 auth_db"
        exit 1
    fi
    
    local backup_file="$BACKUP_DIR/database/${db_name}_backup_${backup_date}.sql.gz.gpg"
    
    if [ ! -f "$backup_file" ]; then
        echo "❌ Backup file not found: $backup_file"
        exit 1
    fi
    
    echo "🔄 Restoring $db_name from $backup_date..."
    
    # Decrypt backup
    gpg --batch --yes --passphrase-file "$BACKUP_ENCRYPTION_KEY_FILE" \
        --output "$BACKUP_DIR/database/${db_name}_restore_${backup_date}.sql.gz" \
        "$backup_file"
    
    # Decompress
    gunzip "$BACKUP_DIR/database/${db_name}_restore_${backup_date}.sql.gz"
    
    # Restore database
    docker exec -i genesis_${db_name}_db psql -U genesis_${db_name}_user_prod \
        -c "DROP DATABASE IF EXISTS ${db_name};" \
        -c "CREATE DATABASE ${db_name};" \
        -c "\c ${db_name}" < "$BACKUP_DIR/database/${db_name}_restore_${backup_date}.sql"
    
    # Clean up restore file
    rm "$BACKUP_DIR/database/${db_name}_restore_${backup_date}.sql"
    
    echo -e "${GREEN}✅ $db_name restored from $backup_date${NC}"
}

# Point-in-time recovery
point_in_time_recovery() {
    local target_time=$1
    
    echo "🕐 Point-in-time recovery to: $target_time"
    
    # Find closest backup before target time
    local backup_file=$(find "$BACKUP_DIR/database" -name "*.gpg" -type f \
        -exec ls -la {} \; | grep "$target_time" | head -1 | awk '{print $9}')
    
    if [ -z "$backup_file" ]; then
        echo "❌ No backup found before $target_time"
        exit 1
    fi
    
    echo "📋 Found backup: $backup_file"
    
    # Extract database name from filename
    local db_name=$(echo "$backup_file" | grep -o '[^_]*_db' | sed 's/_db//' | sed 's#.*/##')
    
    # Extract backup date from filename
    local backup_date=$(echo "$backup_file" | grep -o '[0-9]\{8\}_[0-9]\{6\}')
    
    echo "🔄 Restoring $db_name to state from $backup_date..."
    restore_backup "$backup_date" "$db_name"
}

# Verify backup integrity
verify_backup() {
    local backup_file=$1
    
    echo "🔍 Verifying backup integrity: $backup_file"
    
    if [ ! -f "$backup_file" ]; then
        echo "❌ Backup file not found: $backup_file"
        return 1
    fi
    
    # Check GPG integrity
    if gpg --list-only --passphrase-file "$BACKUP_ENCRYPTION_KEY_FILE" "$backup_file" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backup integrity verified${NC}"
        return 0
    else
        echo -e "${RED}❌ Backup integrity check failed${NC}"
        return 1
    fi
}

# Main execution
case "${1:-help}" in
    "full")
        full_backup
        offsite_backup
        cleanup_old_backups
        ;;
    "database")
        if [ -z "$2" ]; then
            echo "❌ Usage: $0 database <database_name>"
            echo "   Available databases: auth_db, chat_db, memory_db, billing_db, blockchain_db, ml_db, agent_db"
            exit 1
        fi
        backup_database "$2" "genesis_${2}"
        ;;
    "offsite")
        offsite_backup
        ;;
    "restore")
        restore_backup "$2" "$3"
        ;;
    "pitr")
        point_in_time_recovery "$2"
        ;;
    "verify")
        if [ -z "$2" ]; then
            echo "❌ Usage: $0 verify <backup_file>"
            exit 1
        fi
        verify_backup "$2"
        ;;
    "cleanup")
        cleanup_old_backups
        ;;
    "status")
        echo "📊 Backup Status"
        echo "==============="
        echo "Local backups: $(find $BACKUP_DIR -name "*.gpg" | wc -l)"
        echo "Offsite backups: $(find $OFFSITE_BACKUP_DIR -name "*.gpg" | wc -l)"
        echo "Backup directory size: $(du -sh $BACKUP_DIR | cut -f1)"
        echo "Offsite directory size: $(du -sh $OFFSITE_BACKUP_DIR | cut -f1)"
        echo "Last backup: $(find $BACKUP_DIR -name "*.gpg" -type f -exec ls -la {} \; | head -1 | awk '{print $6, $7, $8}')"
        ;;
    "help"|*)
        echo "💾 Production Backup System"
        echo "======================="
        echo ""
        echo "Commands:"
        echo "  $0 full                    - Full system backup with offsite sync"
        echo "  $0 database <db_name>      - Backup specific database"
        echo "  $0 offsite                 - Sync to offsite storage"
        echo "  $0 restore <date> <db>     - Restore database from backup"
        echo "  $0 pitr <timestamp>        - Point-in-time recovery"
        echo "  $0 verify <backup_file>    - Verify backup integrity"
        echo "  $0 cleanup                 - Clean up old backups"
        echo "  $0 status                  - Show backup status"
        echo ""
        echo "Examples:"
        echo "  $0 full"
        echo "  $0 database auth_db"
        echo "  $0 restore 20240111_120000 auth_db"
        echo "  $0 pitr '2024-01-11 12:00:00'"
        echo "  $0 verify /opt/genesis/backups/database/auth_db_backup_20240111_120000.sql.gz.gpg"
        ;;
esac
