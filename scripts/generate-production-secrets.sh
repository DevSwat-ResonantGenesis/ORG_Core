#!/bin/bash
# Production Secrets Generator
# Generates cryptographically secure secrets for production deployment

set -e

echo "🔐 Generating Production Secrets..."
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SEEDS_FILE=".env.production.secure"

# Check if seeds file exists
if [ -f "$SEEDS_FILE" ]; then
    echo -e "${YELLOW}⚠️  Warning: $SEEDS_FILE already exists${NC}"
    echo "This will overwrite existing secrets."
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 1
    fi
fi

echo "🔧 Generating cryptographically secure secrets..."

# Function to generate secure random string
generate_secret() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# Generate the seeds file
cat > "$SEEDS_FILE" << EOF
# ============================================
# PRODUCTION SEEDS FILE - DO NOT COMMIT TO GIT
# ============================================
# Generated on: $(date)
# For: Genesis2026 Production Deployment

# ============================================
# DATABASE CREDENTIALS (Strong, Unique)
# ============================================
AUTH_DB_USER=genesis_auth_user_prod
AUTH_DB_PASSWORD=genesis_auth_secure_$(date +%Y)_$(generate_secret)

CHAT_DB_USER=genesis_chat_user_prod  
CHAT_DB_PASSWORD=genesis_chat_secure_$(date +%Y)_$(generate_secret)

MEMORY_DB_USER=genesis_memory_user_prod
MEMORY_DB_PASSWORD=genesis_memory_secure_$(date +%Y)_$(generate_secret)

# ============================================
# AUTHENTICATION SECRETS
# ============================================
AUTH_JWT_SECRET_KEY=genesis_jwt_secret_$(date +%Y)_$(generate_secret)
AUTH_API_KEY_SALT=genesis_salt_$(date +%Y)_$(generate_secret)
AUTH_INTERNAL_SERVICE_KEY=genesis_internal_$(date +%Y)_$(generate_secret)

# ============================================
# ENCRYPTION KEYS
# ============================================
SEED_ENCRYPTION_KEY=genesis_seed_encrypt_$(date +%Y)_$(generate_secret)
MASTER_ENCRYPTION_KEY=genesis_master_encrypt_$(date +%Y)_$(generate_secret)
ENCRYPTION_SALT=genesis_encrypt_salt_$(date +%Y)_$(generate_secret)

# ============================================
# SERVICE PASSWORDS
# ============================================
REDIS_PASSWORD=genesis_redis_secure_$(date +%Y)_$(generate_secret)
MINIO_ROOT_USER=genesis_minio_admin
MINIO_ROOT_PASSWORD=genesis_minio_secure_$(date +%Y)_$(generate_secret)

# ============================================
# EXTERNAL API KEYS (Set these values)
# ============================================
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
GOOGLE_API_KEY=your-google-api-key-here
GROQ_API_KEY=gsk_your-groq-key-here
MISTRAL_API_KEY=your-mistral-key-here
TOGETHER_API_KEY=your-together-key-here
PERPLEXITY_API_KEY=your-perplexity-key-here
DEEPSEEK_API_KEY=your-deepseek-key-here
FIREWORKS_API_KEY=your-fireworks-key-here
OPENROUTER_API_KEY=your-openrouter-key-here
COHERE_API_KEY=your-cohere-key-here
ANYSCALE_API_KEY=your-anyscale-key-here
TAVILY_API_KEY=tvly-your-tavily-key-here
SERPAPI_KEY=your-serpapi-key-here

# ============================================
# EMAIL CONFIGURATION
# ============================================
AUTH_SMTP_HOST=smtp.gmail.com
AUTH_SMTP_PORT=587
AUTH_SMTP_USER=your-email@gmail.com
AUTH_SMTP_PASSWORD=your-app-password-here
AUTH_SENDGRID_API_KEY=SG.YOUR_SENDGRID_KEY

# ============================================
# DOMAIN CONFIGURATION
# ============================================
AUTH_FRONTEND_URL=https://resonantgenesis.ai
AUTH_COOKIE_DOMAIN=.resonantgenesis.ai
AUTH_EMAIL_FROM_ADDRESS=noreply@resonantgenesis.ai
AUTH_EMAIL_FROM_NAME=ResonantGenesis

# ============================================
# OWNER ACCOUNT (Set these values)
# ============================================
OWNER_EMAIL=admin@resonantgenesis.ai
OWNER_PASSWORD=genesis_admin_secure_$(date +%Y)_$(generate_secret)
OWNER_JWT_SECRET=genesis_owner_jwt_$(date +%Y)_$(generate_secret)

# ============================================
# MONITORING
# ============================================
GRAFANA_ADMIN_PASSWORD=genesis_grafana_secure_$(date +%Y)_$(generate_secret)

# ============================================
# ENVIRONMENT
# ============================================
AUTH_ENVIRONMENT=production
EOF

# Set secure permissions
chmod 600 "$SEEDS_FILE"

echo ""
echo -e "${GREEN}✅ Production secrets generated successfully!${NC}"
echo ""
echo "📁 File created: $SEEDS_FILE"
echo "🔒 Permissions set to: 600 (read/write for owner only)"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT SECURITY NOTES:${NC}"
echo "1. Never commit this file to Git"
echo "2. Store it securely (password manager, vault)"
echo "3. Update the placeholder API keys with real values"
echo "4. Set up proper backup for this file"
echo ""
echo "🚀 Next steps:"
echo "1. Edit $SEEDS_FILE to add your real API keys"
echo "2. Deploy with: docker compose -f docker-compose.production.secure.yml --env-file $SEEDS_FILE up -d"
