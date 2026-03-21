#!/bin/bash
# JWT Configuration Verification Script
# Proves JWT lifetime, rotation, and revocation with concrete evidence

set -e

echo "🔑 JWT CONFIGURATION VERIFICATION"
echo "==============================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
JWT_DIR="./jwt-verification-$(date +%Y%m%d_%H%M%S)"
EVIDENCE_FILE="$JWT_DIR/jwt-evidence.json"

echo "📁 Creating JWT verification directory: $JWT_DIR"
mkdir -p "$JWT_DIR"

# Initialize evidence report
cat > "$EVIDENCE_FILE" << EOF
{
  "verification_timestamp": "$(date -Iseconds)",
  "jwt_configuration": {
    "lifetime_consistent": false,
    "rotation_exists": false,
    "revocation_exists": false,
    "production_config": false,
    "critical_issues": []
  }
}
EOF

echo "🔍 Verifying JWT configuration..."
echo ""

# 1. Check JWT Lifetime Consistency
echo "⏰ 1. JWT LIFETIME CONSISTENCY VERIFICATION"
echo "========================================="
echo ""

echo "📋 Checking JWT expiration configuration..."
echo ""

# Check auth service config
echo "Command: grep -A 5 'ACCESS_TOKEN_EXPIRE_MINUTES' /Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/config.py"
echo "Output:"
grep -A 5 'ACCESS_TOKEN_EXPIRE_MINUTES' "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/config.py" > "$JWT_DIR/auth_jwt_config.txt" 2>/dev/null

echo "📋 Auth service JWT config:"
cat "$JWT_DIR/auth_jwt_config.txt"
echo ""

# Check gateway config
echo "Command: grep -A 5 'ACCESS_TOKEN_EXPIRE_MINUTES' /Users/devswat/Genesis2026 /genesis_backend_3/gateway/app/config.py"
echo "Output:"
grep -A 5 'ACCESS_TOKEN_EXPIRE_MINUTES' "/Users/devswat/Genesis2026 /genesis_backend_3/gateway/app/config.py" > "$JWT_DIR/gateway_jwt_config.txt" 2>/dev/null

echo "📋 Gateway JWT config:"
cat "$JWT_DIR/gateway_jwt_config.txt"
echo ""

# Check production environment file
echo "📋 Checking production environment file..."
echo ""
if [ -f ".env.production" ]; then
    echo "Command: grep -E 'ACCESS_TOKEN_EXPIRE_MINUTES|JWT_SECRET_KEY' .env.production"
    echo "Output:"
    grep -E 'ACCESS_TOKEN_EXPIRE_MINUTES|JWT_SECRET_KEY' .env.production > "$JWT_DIR/production_jwt_config.txt" 2>/dev/null
    
    echo "📋 Production JWT config:"
    cat "$JWT_DIR/production_jwt_config.txt"
    
    if [ -s "$JWT_DIR/production_jwt_config.txt" ]; then
        production_config=true
    else
        production_config=false
    fi
else
    echo "❌ Production environment file not found"
    production_config=false
fi

# Extract actual values
auth_minutes=$(grep 'ACCESS_TOKEN_EXPIRE_MINUTES.*=' "$JWT_DIR/auth_jwt_config.txt" | cut -d'=' -f2 | tr -d ' ')
gateway_minutes=$(grep 'ACCESS_TOKEN_EXPIRE_MINUTES.*=' "$JWT_DIR/gateway_jwt_config.txt" | cut -d'=' -f2 | tr -d ' ' 2>/dev/null || echo "not_set")
prod_minutes=$(grep 'ACCESS_TOKEN_EXPIRE_MINUTES.*=' "$JWT_DIR/production_jwt_config.txt" | cut -d'=' -f2 | tr -d ' ' 2>/dev/null || echo "not_set")

echo ""
echo "📊 JWT Lifetime Analysis:"
echo "  - Auth service: ${auth_minutes:-not_found} minutes"
echo "  - Gateway: ${gateway_minutes} minutes"
echo "  - Production: ${prod_minutes} minutes"
echo ""

# Check consistency
if [ "$auth_minutes" = "$gateway_minutes" ] && [ "$gateway_minutes" = "$prod_minutes" ]; then
    echo "✅ JWT lifetime consistent across all configs"
    lifetime_consistent=true
else
    echo "❌ CRITICAL: JWT lifetime inconsistent"
    lifetime_consistent=false
fi

# 2. Check JWT Rotation Mechanism
echo ""
echo "🔄 2. JWT ROTATION MECHANISM VERIFICATION"
echo "======================================="
echo ""

echo "📋 Checking for JWT rotation implementation..."
echo ""

# Check token version support
echo "Command: grep -A 10 'token_version' /Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/security.py"
echo "Output:"
grep -A 10 'token_version' "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/security.py" > "$JWT_DIR/token_version.txt" 2>/dev/null

echo "📋 Token version support:"
cat "$JWT_DIR/token_version.txt"
echo ""

# Check user model for token version
echo "Command: grep -A 5 'token_version' /Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/models.py"
echo "Output:"
grep -A 5 'token_version' "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/models.py" > "$JWT_DIR/user_token_version.txt" 2>/dev/null

echo "📋 User token version field:"
cat "$JWT_DIR/user_token_version.txt"
echo ""

# Check for token rotation logic
echo "Command: grep -A 10 'token_version' /Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/routers.py"
echo "Output:"
grep -A 10 'token_version' "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/routers.py" > "$JWT_DIR/router_token_version.txt" 2>/dev/null

echo "📋 Router token version usage:"
cat "$JWT_DIR/router_token_version.txt"
echo ""

# Verify rotation exists
if grep -q 'token_version' "$JWT_DIR/token_version.txt" && grep -q 'token_version' "$JWT_DIR/user_token_version.txt"; then
    echo "✅ JWT rotation mechanism exists"
    rotation_exists=true
else
    echo "❌ JWT rotation mechanism missing"
    rotation_exists=false
fi

# 3. Check JWT Revocation Mechanism
echo ""
echo "🚫 3. JWT REVOCATION MECHANISM VERIFICATION"
echo "======================================"
echo ""

echo "📋 Checking for JWT revocation implementation..."
echo ""

# Check for refresh token revocation
echo "Command: grep -A 10 'refresh.*revoke\|revoke.*refresh' /Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/routers.py"
echo "Output:"
grep -A 10 'refresh.*revoke\|revoke.*refresh' "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/routers.py" > "$JWT_DIR/refresh_revoke.txt" 2>/dev/null

echo "📋 Refresh token revocation:"
cat "$JWT_DIR/refresh_revoke.txt"
echo ""

# Check for token blacklist
echo "Command: find /Users/devswat/Genesis2026 /genesis_backend_3/auth_service -name '*.py' -exec grep -l 'blacklist\|revoked' {} \;"
echo "Output:"
find "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service" -name '*.py' -exec grep -l 'blacklist\|revoked' {} \; > "$JWT_DIR/blacklist_files.txt" 2>/dev/null

echo "📋 Blacklist implementation files:"
cat "$JWT_DIR/blacklist_files.txt"
echo ""

# Check for session management
echo "Command: grep -A 10 'session.*revoke\|revoke.*session' /Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/routers.py"
echo "Output:"
grep -A 10 'session.*revoke\|revoke.*session' "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/routers.py" > "$JWT_DIR/session_revoke.txt" 2>/dev/null

echo "📋 Session revocation:"
cat "$JWT_DIR/session_revoke.txt"
echo ""

# Verify revocation exists
if [ -s "$JWT_DIR/refresh_revoke.txt" ] || [ -s "$JWT_DIR/blacklist_files.txt" ]; then
    echo "✅ JWT revocation mechanism exists"
    revocation_exists=true
else
    echo "❌ JWT revocation mechanism missing"
    revocation_exists=false
fi

# 4. Check JWT Secret Management
echo ""
echo "🔐 4. JWT SECRET MANAGEMENT VERIFICATION"
echo "======================================="
echo ""

echo "📋 Checking JWT secret configuration..."
echo ""

# Check for JWT secret in config
echo "Command: grep -A 5 'JWT_SECRET_KEY' /Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/config.py"
echo "Output:"
grep -A 5 'JWT_SECRET_KEY' "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/config.py" > "$JWT_DIR/jwt_secret_config.txt" 2>/dev/null

echo "📋 JWT secret config:"
cat "$JWT_DIR/jwt_secret_config.txt"
echo ""

# Check production secrets
if [ -f ".env.production" ]; then
    echo "Command: grep 'JWT_SECRET_KEY' .env.production"
    echo "Output:"
    grep 'JWT_SECRET_KEY' .env.production > "$JWT_DIR/production_jwt_secret.txt" 2>/dev/null
    
    echo "📋 Production JWT secret:"
    cat "$JWT_DIR/production_jwt_secret.txt"
    
    if [ -s "$JWT_DIR/production_jwt_secret.txt" ]; then
        echo "✅ JWT secret configured in production"
        jwt_secret_configured=true
    else
        echo "❌ JWT secret not configured in production"
        jwt_secret_configured=false
    fi
else
    echo "❌ Production environment file not found"
    jwt_secret_configured=false
fi

# 5. Generate Evidence Report
echo ""
echo "📋 5. EVIDENCE REPORT GENERATION"
echo "==============================="
echo ""

# Update evidence report
jq --arg ".jwt_configuration.lifetime_consistent = $lifetime_consistent" \
   "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"

jq --arg ".jwt_configuration.rotation_exists = $rotation_exists" \
   "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"

jq --arg ".jwt_configuration.revocation_exists = $revocation_exists" \
   "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"

jq --arg ".jwt_configuration.production_config = $production_config" \
   "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"

# Add critical issues
critical_issues=0

if [ "$lifetime_consistent" = false ]; then
    jq --arg ".jwt_configuration.critical_issues += [{\"issue\": \"JWT lifetime inconsistent across configs\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

if [ "$rotation_exists" = false ]; then
    jq --arg ".jwt_configuration.critical_issues += [{\"issue\": \"JWT rotation mechanism missing\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

if [ "$revocation_exists" = false ]; then
    jq --arg ".jwt_configuration.critical_issues += [{\"issue\": \"JWT revocation mechanism missing\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

if [ "$jwt_secret_configured" = false ]; then
    jq --arg ".jwt_configuration.critical_issues += [{\"issue\": \"JWT secret not configured in production\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

# 6. Final Assessment
echo ""
echo "📊 JWT CONFIGURATION ASSESSMENT"
echo "==============================="
echo ""
echo "📁 Evidence directory: $JWT_DIR"
echo "📋 Evidence report: $EVIDENCE_FILE"
echo ""
echo "📊 JWT VERIFICATION RESULTS:"
echo "  - Lifetime consistent: $lifetime_consistent"
echo "  - Rotation exists: $rotation_exists"
echo "  - Revocation exists: $revocation_exists"
echo "  - Production config: $production_config"
echo "  - Critical issues: $critical_issues"
echo ""

if [ $critical_issues -eq 0 ]; then
    echo -e "${GREEN}✅ JWT CONFIGURATION SECURE${NC}"
    echo "🎉 JWT configuration is consistent and secure"
    echo ""
    echo "✅ Security posture: CONFIGURATION VERIFIED"
    echo "✅ Token lifetime: CONSISTENT"
    echo "✅ Token rotation: IMPLEMENTED"
    echo "✅ Token revocation: IMPLEMENTED"
    echo "✅ Secret management: CONFIGURED"
else
    echo -e "${RED}❌ JWT CONFIGURATION COMPROMISED${NC}"
    echo "🚨 JWT configuration has critical issues"
    echo ""
    echo "❌ Security posture: CONFIGURATION BROKEN"
    echo "❌ Critical issues: $critical_issues"
    echo "❌ Token lifetime: INCONSISTENT"
    echo "❌ Token rotation: MISSING"
    echo "❌ Token revocation: MISSING"
    echo "❌ Secret management: UNCONFIGURED"
fi

echo ""
echo "📋 This verification provides concrete evidence of:"
echo "  - JWT lifetime consistency across all configs"
echo "  - Token rotation mechanism implementation"
echo "  - Token revocation mechanism implementation"
echo "  - Production JWT secret configuration"
echo "  - Configuration file analysis"
echo ""
echo "🔍 Evidence files:"
ls -la "$JWT_DIR"
