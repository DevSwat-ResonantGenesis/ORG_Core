#!/bin/bash
# Production Secrets Management Setup
# CRITICAL: Secure secrets handling for production deployment

set -e

echo "🔐 PRODUCTION SECRETS MANAGEMENT"
echo "=============================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SEEDS_FILE=".env.production"
SECRETS_BACKUP_DIR="/opt/genesis/secrets-backup"

echo "🔒 Setting up production secrets management..."

# Function to generate cryptographically secure secret
generate_secure_secret() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# Function to generate secure password with complexity
generate_secure_password() {
    # Generate password with at least 32 chars including special chars
    local password=""
    password=$(openssl rand -base64 48 | tr -d "=+/" | cut -c1-32)
    # Add special characters to ensure complexity
    echo "${password}!@#"
}

# Function to validate secret strength
validate_secret_strength() {
    local secret="$1"
    local name="$2"
    
    if [ ${#secret} -lt 20 ]; then
        echo -e "${RED}❌ $name too short (min 20 chars)${NC}"
        return 1
    fi
    
    if [[ "$secret" =~ ^(.)\1{5,} ]]; then
        echo -e "${RED}❌ $name has repeating characters${NC}"
        return 1
    fi
    
    if [[ "$secret" =~ (password|admin|test|dev|123|qwerty) ]]; then
        echo -e "${RED}❌ $name contains common words${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ $name strength validated${NC}"
    return 0
}

# Create secrets backup directory
echo "📁 Creating secure backup directory..."
sudo mkdir -p "$SECRETS_BACKUP_DIR"
sudo chmod 700 "$SECRETS_BACKUP_DIR"
sudo chown root:root "$SECRETS_BACKUP_DIR"

# Backup existing secrets if they exist
if [ -f "$SEEDS_FILE" ]; then
    echo "💾 Backing up existing secrets..."
    local timestamp=$(date +%Y%m%d_%H%M%S)
    sudo cp "$SEEDS_FILE" "$SECRETS_BACKUP_DIR/env.production.backup.$timestamp"
    sudo chmod 600 "$SECRETS_BACKUP_DIR/env.production.backup.$timestamp"
    echo -e "${GREEN}✅ Existing secrets backed up${NC}"
fi

# Generate production secrets file
echo "🔧 Generating production secrets..."

cat > "$SEEDS_FILE" << EOF
# ============================================
# PRODUCTION SEEDS FILE - HIGH SECURITY
# Generated: $(date)
# Environment: production
# WARNING: Never commit to version control
# ============================================

# ============================================
# DATABASE CREDENTIALS (UNIQUE, STRONG)
# ============================================
AUTH_DB_USER=genesis_auth_user_prod
AUTH_DB_PASSWORD=$(generate_secure_password)

CHAT_DB_USER=genesis_chat_user_prod  
CHAT_DB_PASSWORD=$(generate_secure_password)

MEMORY_DB_USER=genesis_memory_user_prod
MEMORY_DB_PASSWORD=$(generate_secure_password)

BILLING_DB_USER=genesis_billing_user_prod
BILLING_DB_PASSWORD=$(generate_secure_password)

BLOCKCHAIN_DB_USER=genesis_blockchain_user_prod
BLOCKCHAIN_DB_PASSWORD=$(generate_secure_password)

ML_DB_USER=genesis_ml_user_prod
ML_DB_PASSWORD=$(generate_secure_password)

AGENT_DB_USER=genesis_agent_user_prod
AGENT_DB_PASSWORD=$(generate_secure_password)

# ============================================
# AUTHENTICATION SECRETS (HIGH ENTROPY)
# ============================================
AUTH_JWT_SECRET_KEY=genesis_jwt_prod_$(generate_secure_secret)_$(date +%Y)
AUTH_API_KEY_SALT=genesis_salt_prod_$(generate_secure_secret)_$(date +%Y)
AUTH_INTERNAL_SERVICE_KEY=genesis_internal_prod_$(generate_secure_secret)_$(date +%Y)

# ============================================
# ENCRYPTION KEYS (256-BIT MINIMUM)
# ============================================
SEED_ENCRYPTION_KEY=genesis_seed_$(generate_secure_secret)_$(date +%Y)
MASTER_ENCRYPTION_KEY=genesis_master_$(generate_secure_secret)_$(date +%Y)
ENCRYPTION_SALT=genesis_salt_$(generate_secure_secret)_$(date +%Y)

# ============================================
# SERVICE PASSWORDS (UNIQUE, STRONG)
# ============================================
REDIS_PASSWORD=genesis_redis_$(generate_secure_password)_$(date +%Y)
MINIO_ROOT_USER=genesis_minio_admin
MINIO_ROOT_PASSWORD=genesis_minio_$(generate_secure_password)_$(date +%Y)

# ============================================
# EXTERNAL API KEYS (SET YOUR REAL VALUES)
# ============================================
OPENAI_API_KEY=sk-YOUR-OPENAI-PRODUCTION-KEY-HERE
ANTHROPIC_API_KEY=sk-ant-YOUR-ANTHROPIC-PRODUCTION-KEY-HERE
GOOGLE_API_KEY=YOUR-GOOGLE-PRODUCTION-API-KEY-HERE
GROQ_API_KEY=gsk-YOUR-GROQ-PRODUCTION-KEY-HERE
MISTRAL_API_KEY=YOUR-MISTRAL-PRODUCTION-KEY-HERE
TOGETHER_API_KEY=YOUR-TOGETHER-PRODUCTION-KEY-HERE
PERPLEXITY_API_KEY=YOUR-PERPLEXITY-PRODUCTION-KEY-HERE
DEEPSEEK_API_KEY=YOUR-DEEPSEEK-PRODUCTION-KEY-HERE
FIREWORKS_API_KEY=YOUR-FIREWORKS-PRODUCTION-KEY-HERE
OPENROUTER_API_KEY=YOUR-OPENROUTER-PRODUCTION-KEY-HERE
COHERE_API_KEY=YOUR-COHERE-PRODUCTION-KEY-HERE
ANYSCALE_API_KEY=YOUR-ANYSCALE-PRODUCTION-KEY-HERE
TAVILY_API_KEY=tvly-YOUR-TAVILY-PRODUCTION-KEY-HERE
SERPAPI_KEY=YOUR-SERPAPI-PRODUCTION-KEY-HERE

# ============================================
# EMAIL CONFIGURATION (PRODUCTION SMTP)
# ============================================
AUTH_SMTP_HOST=smtp.gmail.com
AUTH_SMTP_PORT=587
AUTH_SMTP_USER=your-production-email@resonantgenesis.ai
AUTH_SMTP_PASSWORD=YOUR-GMAIL-APP-PASSWORD-HERE
AUTH_SENDGRID_API_KEY=SG.YOUR_SENDGRID_KEY

# ============================================
# DOMAIN CONFIGURATION (PRODUCTION)
# ============================================
AUTH_FRONTEND_URL=https://resonantgenesis.ai
AUTH_COOKIE_DOMAIN=.resonantgenesis.ai
AUTH_EMAIL_FROM_ADDRESS=noreply@resonantgenesis.ai
AUTH_EMAIL_FROM_NAME=ResonantGenesis

# ============================================
# OWNER ACCOUNT (PRODUCTION CREDENTIALS)
# ============================================
OWNER_EMAIL=admin@resonantgenesis.ai
OWNER_PASSWORD=genesis_owner_$(generate_secure_password)_$(date +%Y)
OWNER_JWT_SECRET=genesis_owner_jwt_$(generate_secure_secret)_$(date +%Y)

# ============================================
# MONITORING (PRODUCTION CREDENTIALS)
# ============================================
GRAFANA_ADMIN_PASSWORD=genesis_grafana_$(generate_secure_password)_$(date +%Y)

# ============================================
# ENVIRONMENT CONFIGURATION
# ============================================
AUTH_ENVIRONMENT=production
GATEWAY_ENVIRONMENT=production

# ============================================
# SECURITY SETTINGS
# ============================================
# Session management
SESSION_TIMEOUT_MINUTES=30
MAX_LOGIN_ATTEMPTS=5
ACCOUNT_LOCKOUT_MINUTES=15

# Rate limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=100
RATE_LIMIT_BURST=20

# SSL/TLS
SSL_CERT_PATH=/etc/letsencrypt/live/resonantgenesis.ai/fullchain.pem
SSL_KEY_PATH=/etc/letsencrypt/live/resonantgenesis.ai/privkey.pem

# Backup configuration
BACKUP_ENCRYPTION_KEY=genesis_backup_$(generate_secure_secret)_$(date +%Y)
BACKUP_RETENTION_DAYS=30
EOF

# Set secure permissions
chmod 600 "$SEEDS_FILE"
echo -e "${GREEN}✅ Production secrets generated with secure permissions (600)${NC}"

# Validate generated secrets
echo ""
echo "🔍 Validating generated secrets..."

# Validate key secrets
validate_secret_strength "$(grep AUTH_JWT_SECRET_KEY "$SEEDS_FILE" | cut -d'=' -f2)" "JWT Secret"
validate_secret_strength "$(grep MASTER_ENCRYPTION_KEY "$SEEDS_FILE" | cut -d'=' -f2)" "Master Encryption Key"
validate_secret_strength "$(grep REDIS_PASSWORD "$SEEDS_FILE" | cut -d'=' -f2)" "Redis Password"
validate_secret_strength "$(grep MINIO_ROOT_PASSWORD "$SEEDS_FILE" | cut -d'=' -f2)" "MinIO Password"

# Create secrets rotation script
echo ""
echo "🔄 Creating secrets rotation script..."

cat > scripts/rotate-production-secrets.sh << 'EOF'
#!/bin/bash
# Production Secrets Rotation Script
# Run this regularly to maintain security

set -e

SEEDS_FILE=".env.production"
BACKUP_DIR="/opt/genesis/secrets-backup"

echo "🔄 Rotating production secrets..."

# Backup current secrets
timestamp=$(date +%Y%m%d_%H%M%S)
sudo cp "$SEEDS_FILE" "$BACKUP_DIR/env.production.before_rotation.$timestamp"

# Generate new secrets for sensitive values
NEW_JWT_SECRET="genesis_jwt_prod_$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)_$(date +%Y)"
NEW_MASTER_KEY="genesis_master_$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)_$(date +%Y)"
NEW_REDIS_PASS="genesis_redis_$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)_$(date +%Y)"

# Update secrets file
sed -i.bak "s/AUTH_JWT_SECRET_KEY=.*/AUTH_JWT_SECRET_KEY=$NEW_JWT_SECRET/" "$SEEDS_FILE"
sed -i.bak "s/MASTER_ENCRYPTION_KEY=.*/MASTER_ENCRYPTION_KEY=$NEW_MASTER_KEY/" "$SEEDS_FILE"
sed -i.bak "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=$NEW_REDIS_PASS/" "$SEEDS_FILE"

echo "✅ Secrets rotated. Restart services with:"
echo "   docker compose -f docker-compose.production.yml restart"

# Clean up backup files after successful rotation
rm "$SEEDS_FILE.bak"
EOF

chmod +x scripts/rotate-production-secrets.sh

# Create secrets validation script
echo ""
echo "🔍 Creating secrets validation script..."

cat > scripts/validate-production-secrets.sh << 'EOF'
#!/bin/bash
# Production Secrets Validation Script

SEEDS_FILE=".env.production"

echo "🔍 Validating production secrets..."

# Check file exists and permissions
if [ ! -f "$SEEDS_FILE" ]; then
    echo "❌ .env.production not found"
    exit 1
fi

perms=$(stat -c "%a" "$SEEDS_FILE")
if [ "$perms" != "600" ]; then
    echo "❌ .env.production has insecure permissions: $perms (should be 600)"
    exit 1
fi

# Check for placeholder values
if grep -q "YOUR-\|placeholder\|test-\|dev-" "$SEEDS_FILE"; then
    echo "❌ Placeholder secrets found:"
    grep "YOUR-\|placeholder\|test-\|dev-" "$SEEDS_FILE"
    exit 1
fi

# Check for default passwords
if grep -q "auth_pass\|user_pass\|admin123" "$SEEDS_FILE"; then
    echo "❌ Default passwords found"
    exit 1
fi

# Check secret strength
while IFS= read -r line; do
    if [[ "$line" =~ ^[A-Z_]+_PASSWORD= ]]; then
        password=$(echo "$line" | cut -d'=' -f2)
        if [ ${#password} -lt 20 ]; then
            echo "❌ Password too short: $line"
            exit 1
        fi
    fi
done < "$SEEDS_FILE"

echo "✅ All secrets validation checks passed"
EOF

chmod +x scripts/validate-production-secrets.sh

# Create Docker secrets management
echo ""
echo "🐳 Creating Docker secrets configuration..."

cat > docker-compose.secrets.yml << 'EOF'
version: '3.8'

secrets:
  auth_jwt_secret:
    file: ./.env.production
    environment: AUTH_JWT_SECRET_KEY
  
  master_encryption_key:
    file: ./.env.production
    environment: MASTER_ENCRYPTION_KEY
  
  redis_password:
    file: ./.env.production
    environment: REDIS_PASSWORD
  
  minio_root_password:
    file: ./.env.production
    environment: MINIO_ROOT_PASSWORD

services:
  # Example of using secrets in services
  auth_service:
    secrets:
      - auth_jwt_secret
    environment:
      AUTH_JWT_SECRET_KEY: /run/secrets/auth_jwt_secret
EOF

echo ""
echo "📋 PRODUCTION SECRETS SETUP COMPLETE"
echo "=================================="

echo -e "${GREEN}✅ Production secrets generated${NC}"
echo -e "${GREEN}✅ Secure permissions set (600)${NC}"
echo -e "${GREEN}✅ Backup directory created${NC}"
echo -e "${GREEN}✅ Rotation script created${NC}"
echo -e "${GREEN}✅ Validation script created${NC}"
echo ""

echo "🔐 SECURITY MEASURES IMPLEMENTED:"
echo "  • Cryptographically secure passwords"
echo "  • Unique credentials for each service"
echo "  • High-entropy encryption keys"
echo "  • Secure file permissions (600)"
echo "  • Automated backup system"
echo "  • Rotation procedures"
echo "  • Validation scripts"
echo ""

echo "⚠️  IMPORTANT NEXT STEPS:"
echo "  1. Update placeholder API keys with real values"
echo "  2. Set up email SMTP credentials"
echo "  3. Store backup securely (password manager, vault)"
echo "  4. Schedule regular secret rotation"
echo "  5. Test validation script: ./scripts/validate-production-secrets.sh"
echo ""

echo "🔒 NEVER:"
echo "  • Commit .env.production to version control"
echo "  • Share secrets via email/chat"
echo "  • Store secrets in plain text"
echo "  • Use same secrets across environments"
