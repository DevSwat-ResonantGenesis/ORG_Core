#!/bin/bash
# Commit and push analytics fix to repository

echo "========================================="
echo "Analytics Fix - Git Commit & Push"
echo "========================================="
echo ""

# Check if we're in a git repository
if [ ! -d .git ]; then
    echo "Error: Not in a git repository"
    exit 1
fi

# Show what will be committed
echo "Files to be committed:"
git status --short

echo ""
echo "Creating commit..."

# Create commit with detailed message
git commit -m "Fix: Add missing analytics endpoint routes to gateway

## Problem
- Resonant chat metrics not displaying on user dashboard
- Browser console showing 404 errors on /analytics endpoint
- Frontend calling /api/analytics but gateway only had /analytics route

## Root Cause
Gateway was missing critical route variants:
- /api/analytics (frontend standard pattern)
- /api/v1/analytics (versioned API pattern)

## Solution
Added comprehensive analytics route coverage:

1. gateway/app/main.py - Added /api/analytics routes
2. gateway/app/routers.py - Added /api/v1/analytics routes

## Impact
- ✅ All analytics endpoints now accessible
- ✅ Dashboard metrics loading correctly
- ✅ No more 404 errors
- ✅ Backward compatible (existing routes still work)

## Testing
- Created test_analytics_endpoints.sh for endpoint testing
- Created test_db_connection.py for database verification
- All route patterns tested and working

## Files Changed
- gateway/app/main.py
- gateway/app/routers.py
- test_analytics_endpoints.sh (new)
- test_db_connection.py (new)
- ANALYTICS_FIX_DETAILED_REPORT.md (new)
- RESONANT_CHAT_METRICS_FIX_REPORT.md (new)
- PR_SUMMARY_ANALYTICS_FIX.md (new)

Fixes: P0 - Resonant chat metrics 404 error
Type: Bug Fix (Critical)
Component: Gateway API Routing"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Commit created successfully!"
    echo ""
    echo "Pushing to remote repository..."
    
    # Get current branch
    BRANCH=$(git branch --show-current)
    echo "Current branch: $BRANCH"
    
    # Push to remote
    git push origin "$BRANCH"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "========================================="
        echo "✓ Successfully pushed to origin/$BRANCH"
        echo "========================================="
        echo ""
        echo "Next steps:"
        echo "1. Go to GitHub repository"
        echo "2. Create Pull Request from $BRANCH to main"
        echo "3. Use PR_SUMMARY_ANALYTICS_FIX.md as PR description"
        echo "4. Request review and merge"
        echo ""
    else
        echo ""
        echo "✗ Failed to push to remote"
        echo "You may need to push manually:"
        echo "  git push origin $BRANCH"
        exit 1
    fi
else
    echo ""
    echo "✗ Failed to create commit"
    exit 1
fi
