#!/bin/bash
# Comprehensive Production Security Verification
# Addresses all adversarial concerns with concrete evidence

set -e

echo "🔍 COMPREHENSIVE PRODUCTION SECURITY VERIFICATION"
echo "==============================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
PROD_DIR="./production-security-$(date +%Y%m%d_%H%M%S)"
EVIDENCE_FILE="$PROD_DIR/production-evidence.json"

echo "📁 Creating production security verification directory: $PROD_DIR"
mkdir -p "$PROD_DIR"

# Initialize evidence report
cat > "$EVIDENCE_FILE" << EOF
{
  "verification_timestamp": "$(date -Iseconds)",
  "production_security": {
    "password_hash_fixed": false,
    "cors_restricted": false,
    "jwt_lifetime_fixed": false,
    "gateway_boundary_verified": false,
    "public_endpoints_safe": false,
    "overall_status": "NOT_PRODUCTION_READY",
    "critical_issues": []
  }
}
EOF

echo "🔍 Verifying production security requirements..."
echo ""

# 1. Fix Password Hash Leakage
echo "🔐 1. PASSWORD HASH LEAKAGE FIX"
echo "============================="
echo ""

echo "📋 Checking if password hash is still exposed..."
echo ""

# Check current auth verification endpoint
echo "Command: grep -A 15 'return.*password_hash' /Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/routers.py"
echo "Output:"
grep -A 15 'return.*password_hash' "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/routers.py" > "$PROD_DIR/password_hash_check.txt" 2>/dev/null

echo "📋 Current password hash exposure:"
cat "$PROD_DIR/password_hash_check.txt"
echo ""

if grep -q 'password_hash.*decoded.get' "$PROD_DIR/password_hash_check.txt"; then
    echo "❌ CRITICAL: Password hash still exposed"
    echo "🔧 Applying fix..."
    
    # Create fixed version
    echo "📋 Creating fixed auth verification endpoint..."
    
    # Backup original file
    cp "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/routers.py" "$PROD_DIR/auth_routers_backup.py"
    
    # Fix the password hash leakage
    echo "📋 Removing password_hash from auth verification response..."
    
    # Apply the fix
    sed -i.bak 's/.*password_hash.*decoded.get.*password_hash.*,//' "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/routers.py"
    
    # Verify fix
    echo "Command: grep -A 15 'return.*password_hash' /Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/routers.py"
    echo "Output:"
    grep -A 15 'return.*password_hash' "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/routers.py" > "$PROD_DIR/password_hash_after_fix.txt" 2>/dev/null
    
    echo "📋 After fix:"
    cat "$PROD_DIR/password_hash_after_fix.txt"
    
    if grep -q 'password_hash.*decoded.get' "$PROD_DIR/password_hash_after_fix.txt"; then
        echo "❌ Fix failed - password hash still exposed"
        password_hash_fixed=false
    else
        echo "✅ Password hash successfully removed"
        password_hash_fixed=true
    fi
else
    echo "✅ Password hash already fixed"
    password_hash_fixed=true
fi

# 2. Fix CORS Configuration
echo ""
echo "🌐 2. CORS CONFIGURATION FIX"
echo "==========================="
echo ""

echo "📋 Checking current CORS configuration..."
echo ""

# Check gateway CORS
echo "Command: grep -A 10 'allow_origins' /Users/devswat/Genesis2026 /genesis_backend_3/gateway/app/main.py"
echo "Output:"
grep -A 10 'allow_origins' "/Users/devswat/Genesis2026 /genesis_backend_3/gateway/app/main.py" > "$PROD_DIR/cors_check.txt" 2>/dev/null

echo "📋 Current CORS configuration:"
cat "$PROD_DIR/cors_check.txt"
echo ""

if grep -q '"*"' "$PROD_DIR/cors_check.txt"; then
    echo "❌ CRITICAL: CORS allows all origins"
    echo "🔧 Applying fix..."
    
    # Backup original file
    cp "/Users/devswat/Genesis2026 /genesis_backend_3/gateway/app/main.py" "$PROD_DIR/gateway_main_backup.py"
    
    # Fix CORS configuration
    echo "📋 Restricting CORS to specific domains..."
    
    # Apply the fix
    sed -i.bak 's/allow_origins=\["\*"\]/allow_origins=["https:\/\/resonantgenesis.ai", "https:\/\/www.resonantgenesis.ai", "https:\/\/app.resonantgenesis.ai", "https:\/\/api.resonantgenesis.ai"]/' "/Users/devswat/Genesis2026 /genesis_backend_3/gateway/app/main.py"
    
    # Verify fix
    echo "Command: grep -A 10 'allow_origins' /Users/devswat/Genesis2026 /genesis_backend_3/gateway/app/main.py"
    echo "Output:"
    grep -A 10 'allow_origins' "/Users/devswat/Genesis2026 /genesis_backend_3/gateway/app/main.py" > "$PROD_DIR/cors_after_fix.txt" 2>/dev/null
    
    echo "📋 After fix:"
    cat "$PROD_DIR/cors_after_fix.txt"
    
    if grep -q '"*"' "$PROD_DIR/cors_after_fix.txt"; then
        echo "❌ Fix failed - CORS still allows all origins"
        cors_restricted=false
    else
        echo "✅ CORS successfully restricted"
        cors_restricted=true
    fi
else
    echo "✅ CORS already restricted"
    cors_restricted=true
fi

# 3. Fix JWT Lifetime
echo ""
echo "⏰ 3. JWT LIFETIME FIX"
echo "==================="
echo ""

echo "📋 Checking current JWT lifetime configuration..."
echo ""

# Check auth service config
echo "Command: grep 'ACCESS_TOKEN_EXPIRE_MINUTES.*=' /Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/config.py"
echo "Output:"
grep 'ACCESS_TOKEN_EXPIRE_MINUTES.*=' "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/config.py" > "$PROD_DIR/jwt_lifetime_check.txt" 2>/dev/null

echo "📋 Current JWT lifetime:"
cat "$PROD_DIR/jwt_lifetime_check.txt"
echo ""

current_minutes=$(grep 'ACCESS_TOKEN_EXPIRE_MINUTES.*=' "$PROD_DIR/jwt_lifetime_check.txt" | cut -d'=' -f2 | tr -d ' ')

if [ "$current_minutes" -gt 15 ]; then
    echo "❌ CRITICAL: JWT lifetime too long ($current_minutes minutes)"
    echo "🔧 Applying fix..."
    
    # Backup original file
    cp "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/config.py" "$PROD_DIR/auth_config_backup.py"
    
    # Fix JWT lifetime
    echo "📋 Reducing JWT lifetime to 5 minutes..."
    
    # Apply the fix
    sed -i.bak 's/ACCESS_TOKEN_EXPIRE_MINUTES.*=.*$/ACCESS_TOKEN_EXPIRE_MINUTES: int = 5/' "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/config.py"
    
    # Verify fix
    echo "Command: grep 'ACCESS_TOKEN_EXPIRE_MINUTES.*=' /Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/config.py"
    echo "Output:"
    grep 'ACCESS_TOKEN_EXPIRE_MINUTES.*=' "/Users/devswat/Genesis2026 /genesis_backend_3/auth_service/app/config.py" > "$PROD_DIR/jwt_lifetime_after_fix.txt" 2>/dev/null
    
    echo "📋 After fix:"
    cat "$PROD_DIR/jwt_lifetime_after_fix.txt"
    
    new_minutes=$(grep 'ACCESS_TOKEN_EXPIRE_MINUTES.*=' "$PROD_DIR/jwt_lifetime_after_fix.txt" | cut -d'=' -f2 | tr -d ' ')
    
    if [ "$new_minutes" -le 15 ]; then
        echo "✅ JWT lifetime successfully reduced to $new_minutes minutes"
        jwt_lifetime_fixed=true
    else
        echo "❌ Fix failed - JWT lifetime still too long"
        jwt_lifetime_fixed=false
    fi
else
    echo "✅ JWT lifetime already acceptable ($current_minutes minutes)"
    jwt_lifetime_fixed=true
fi

# 4. Verify Gateway Boundary
echo ""
echo "🔒 4. GATEWAY BOUNDARY VERIFICATION"
echo "==============================="
echo ""

echo "📋 Running system boundary verification..."
echo ""

# Run boundary verification
if [ -f "./scripts/verify-system-boundary.sh" ]; then
    echo "📋 Executing system boundary verification..."
    ./scripts/verify-system-boundary.sh > "$PROD_DIR/boundary_verification.txt" 2>&1
    
    # Check results
    if grep -q "SYSTEM BOUNDARY SECURE" "$PROD_DIR/boundary_verification.txt"; then
        echo "✅ Gateway boundary verified"
        gateway_boundary_verified=true
    else
        echo "❌ Gateway boundary compromised"
        gateway_boundary_verified=false
    fi
    
    echo "📋 Boundary verification results:"
    tail -20 "$PROD_DIR/boundary_verification.txt"
else
    echo "❌ System boundary verification script not found"
    gateway_boundary_verified=false
fi

# 5. Verify Public Endpoints
echo ""
echo "🌐 5. PUBLIC ENDPOINTS VERIFICATION"
echo "================================="
echo ""

echo "📋 Running public endpoint verification..."
echo ""

# Run public endpoint verification
if [ -f "./scripts/verify-public-endpoints.sh" ]; then
    echo "📋 Executing public endpoint verification..."
    ./scripts/verify-public-endpoints.sh > "$PROD_DIR/public_endpoint_verification.txt" 2>&1
    
    # Check results
    if grep -q "PUBLIC ENDPOINTS SECURE" "$PROD_DIR/public_endpoint_verification.txt"; then
        echo "✅ Public endpoints verified"
        public_endpoints_safe=true
    else
        echo "❌ Public endpoints compromised"
        public_endpoints_safe=false
    fi
    
    echo "📋 Public endpoint verification results:"
    tail -20 "$PROD_DIR/public_endpoint_verification.txt"
else
    echo "❌ Public endpoint verification script not found"
    public_endpoints_safe=false
fi

# 6. Generate Final Evidence Report
echo ""
echo "📋 6. FINAL EVIDENCE REPORT"
echo "========================="
echo ""

# Update evidence report
jq --arg ".production_security.password_hash_fixed = $password_hash_fixed" \
   "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"

jq --arg ".production_security.cors_restricted = $cors_restricted" \
   "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"

jq --arg ".production_security.jwt_lifetime_fixed = $jwt_lifetime_fixed" \
   "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"

jq --arg ".production_security.gateway_boundary_verified = $gateway_boundary_verified" \
   "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"

jq --arg ".production_security.public_endpoints_safe = $public_endpoints_safe" \
   "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"

# Add critical issues
critical_issues=0

if [ "$password_hash_fixed" = false ]; then
    jq --arg ".production_security.critical_issues += [{\"issue\": \"Password hash leakage not fixed\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

if [ "$cors_restricted" = false ]; then
    jq --arg ".production_security.critical_issues += [{\"issue\": \"CORS not restricted\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

if [ "$jwt_lifetime_fixed" = false ]; then
    jq --arg ".production_security.critical_issues += [{\"issue\": \"JWT lifetime not fixed\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

if [ "$gateway_boundary_verified" = false ]; then
    jq --arg ".production_security.critical_issues += [{\"issue\": \"Gateway boundary not verified\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

if [ "$public_endpoints_safe" = false ]; then
    jq --arg ".production_security.critical_issues += [{\"issue\": \"Public endpoints not safe\", \"severity\": \"critical\"}]" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
    ((critical_issues++))
fi

# Determine overall status
if [ $critical_issues -eq 0 ]; then
    jq --arg ".production_security.overall_status = \"PRODUCTION_READY\"" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
else
    jq --arg ".production_security.overall_status = \"NOT_PRODUCTION_READY\"" \
       "$EVIDENCE_FILE" > "$EVIDENCE_FILE.tmp" && mv "$EVIDENCE_FILE.tmp" "$EVIDENCE_FILE"
fi

# 7. Final Assessment
echo ""
echo "📊 PRODUCTION SECURITY ASSESSMENT"
echo "==============================="
echo ""
echo "📁 Evidence directory: $PROD_DIR"
echo "📋 Evidence report: $EVIDENCE_FILE"
echo ""
echo "📊 PRODUCTION SECURITY VERIFICATION RESULTS:"
echo "  - Password hash fixed: $password_hash_fixed"
echo "  - CORS restricted: $cors_restricted"
echo "  - JWT lifetime fixed: $jwt_lifetime_fixed"
echo "  - Gateway boundary verified: $gateway_boundary_verified"
echo "  - Public endpoints safe: $public_endpoints_safe"
echo "  - Critical issues: $critical_issues"
echo ""

if [ $critical_issues -eq 0 ]; then
    echo -e "${GREEN}✅ PRODUCTION SECURITY VERIFIED${NC}"
    echo "🎉 All critical security issues have been addressed"
    echo ""
    echo "✅ Security status: PRODUCTION READY"
    echo "✅ Password hash: FIXED"
    echo "✅ CORS: RESTRICTED"
    echo "✅ JWT lifetime: SECURE"
    echo "✅ Gateway boundary: VERIFIED"
    echo "✅ Public endpoints: SAFE"
    echo ""
    echo "🚀 System is ready for production deployment"
else
    echo -e "${RED}❌ PRODUCTION SECURITY COMPROMISED${NC}"
    echo "🚨 Critical security issues remain unaddressed"
    echo ""
    echo "❌ Security status: NOT PRODUCTION READY"
    echo "❌ Critical issues: $critical_issues"
    echo "❌ System is NOT ready for production deployment"
fi

echo ""
echo "📋 This verification provides concrete evidence of:"
echo "  - Password hash leakage fix"
echo "  - CORS restriction implementation"
echo "  - JWT lifetime security fix"
echo "  - Gateway boundary verification"
echo "  - Public endpoint safety verification"
echo "  - Overall production readiness assessment"
echo ""
echo "🔍 Evidence files:"
ls -la "$PROD_DIR"

echo ""
echo "📋 Next steps:"
if [ $critical_issues -eq 0 ]; then
    echo "  ✅ Deploy to production"
    echo "  ✅ Monitor security metrics"
    echo "  ✅ Run regular security audits"
else
    echo "  ❌ Address remaining critical issues"
    echo "  ❌ Re-run verification after fixes"
    echo "  ❌ Do not deploy until all issues resolved"
fi
