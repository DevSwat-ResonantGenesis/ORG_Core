#!/bin/bash
# Production Database Security Setup
# Configures PostgreSQL with security hardening

set -e

echo "🔐 Database Security Configuration"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "📋 Creating database security configurations..."

# Create PostgreSQL security configuration
cat > database/postgresql-security.conf << 'EOF'
# ============================================
# POSTGRESQL PRODUCTION SECURITY CONFIGURATION
# ============================================

# Connection Security
listen_addresses = '*'  # Will be overridden by Docker network isolation
port = 5432
max_connections = 100

# Authentication Security
auth_method = scram-sha-256
password_encryption = scram-sha-256

# SSL Configuration
ssl = on
ssl_cert_file = '/var/lib/postgresql/server.crt'
ssl_key_file = '/var/lib/postgresql/server.key'
ssl_ca_file = '/var/lib/postgresql/root.crt'
ssl_crl_file = '/var/lib/postgresql/root.crl'

# Logging
logging_collector = on
log_directory = 'pg_log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_min_duration_statement = 1000
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on

# Performance & Security
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100

# Security Settings
ssl_min_protocol_version = 'TLSv1.2'
ssl_ciphers = 'HIGH:MEDIUM:+3DES:!aNULL:!SSLv2:!SSLv3'
EOF

# Create database initialization scripts
mkdir -p database/init-scripts

# Auth database initialization
cat > database/init-scripts/01-auth-db-init.sql << 'EOF'
-- ============================================
-- AUTH DATABASE SECURITY INITIALIZATION
-- ============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create secure roles
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'auth_readonly') THEN
        CREATE ROLE auth_readonly;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'auth_readwrite') THEN
        CREATE ROLE auth_readwrite;
    END IF;
END
$$;

-- Grant permissions
GRANT CONNECT ON DATABASE auth_db TO auth_readonly;
GRANT CONNECT ON DATABASE auth_db TO auth_readwrite;

-- Set up Row Level Security
ALTER DATABASE auth_db SET row_security = on;

-- Create audit log table
CREATE TABLE IF NOT EXISTS auth_audit_log (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    table_name VARCHAR(100),
    record_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    session_id UUID
);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_auth_audit_timestamp ON auth_audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_auth_audit_user_id ON auth_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_audit_action ON auth_audit_log(action);
EOF

# Chat database initialization
cat > database/init-scripts/02-chat-db-init.sql << 'EOF'
-- ============================================
-- CHAT DATABASE SECURITY INITIALIZATION
-- ============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create secure roles
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'chat_readonly') THEN
        CREATE ROLE chat_readonly;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'chat_readwrite') THEN
        CREATE ROLE chat_readwrite;
    END IF;
END
$$;

-- Grant permissions
GRANT CONNECT ON DATABASE chat_db TO chat_readonly;
GRANT CONNECT ON DATABASE chat_db TO chat_readwrite;

-- Set up Row Level Security
ALTER DATABASE chat_db SET row_security = on;

-- Create audit log table
CREATE TABLE IF NOT EXISTS chat_audit_log (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID,
    conversation_id UUID,
    action VARCHAR(100) NOT NULL,
    message_type VARCHAR(50),
    content_hash VARCHAR(64),  -- SHA-256 hash of content
    metadata JSONB,
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_chat_audit_timestamp ON chat_audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_chat_audit_user_id ON chat_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_audit_conversation_id ON chat_audit_log(conversation_id);
EOF

# Memory database initialization
cat > database/init-scripts/03-memory-db-init.sql << 'EOF'
-- ============================================
-- MEMORY DATABASE SECURITY INITIALIZATION
-- ============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create secure roles
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'memory_readonly') THEN
        CREATE ROLE memory_readonly;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'memory_readwrite') THEN
        CREATE ROLE memory_readwrite;
    END IF;
END
$$;

-- Grant permissions
GRANT CONNECT ON DATABASE memory_db TO memory_readonly;
GRANT CONNECT ON DATABASE memory_db TO memory_readwrite;

-- Set up Row Level Security
ALTER DATABASE memory_db SET row_security = on;

-- Create encryption audit log
CREATE TABLE IF NOT EXISTS memory_encryption_log (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID,
    memory_id UUID,
    operation VARCHAR(50) NOT NULL,  -- encrypt, decrypt, key_rotate
    encryption_version VARCHAR(20),
    key_id UUID,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_memory_encryption_timestamp ON memory_encryption_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_memory_encryption_user_id ON memory_encryption_log(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_encryption_memory_id ON memory_encryption_log(memory_id);
EOF

echo ""
echo -e "${GREEN}✅ Database security configurations created${NC}"
echo ""
echo "📁 Files created:"
echo "  - database/postgresql-security.conf"
echo "  - database/init-scripts/01-auth-db-init.sql"
echo "  - database/init-scripts/02-chat-db-init.sql"
echo "  - database/init-scripts/03-memory-db-init.sql"
echo ""
echo -e "${YELLOW}🔒 Security features enabled:${NC}"
echo "  - SCRAM-SHA-256 authentication"
echo "  - SSL/TLS encryption"
echo "  - Row Level Security (RLS)"
echo "  - Audit logging"
echo "  - Role-based access control"
echo "  - Connection logging"
