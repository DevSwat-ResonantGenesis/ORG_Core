#!/bin/bash
# Commit and push gateway 500 error fixes

cd /Users/devswat/Genesis2026\ /genesis2026_production_backend

git add gateway/app/main.py gateway/app/routers.py GATEWAY_500_ERROR_ANALYSIS.md

git commit -m "CRITICAL FIX: Add missing /api/auth and /api/billing routes + fix proxy args

Root Cause: Frontend calls /api/auth/login and /api/billing/pricing
but router included with prefix /api/v1, causing route mismatch.

Changes:
1. Added missing routes in routers.py:
   - /api/auth/login -> auth_service
   - /api/auth/providers -> auth_service
   - /api/billing/pricing -> billing_service

2. Fixed proxy argument order in main.py (21 endpoints)
   - Was: proxy(request, service, path)
   - Now: proxy(service, path, request)

Impact: Fixes all 500 errors on login, pricing, providers"

git push origin feature/gateway-phase3-replace-stubs

echo "✅ Changes committed and pushed!"
echo "Next: Go to GitHub and merge the PR"
