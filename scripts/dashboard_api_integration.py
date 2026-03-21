#!/usr/bin/env python3
"""
Dashboard API Integration for Creator Dashboard
===============================================

This script provides API endpoints for the creator dashboard to manage
search API keys and monitor web search functionality.

Features:
- View current API keys (masked)
- Update API keys
- Test API key validity
- Monitor search usage statistics
- Rotate backup keys
"""

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List, Optional
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from scripts.manage_api_keys import APIKeyManager

app = FastAPI(title="Creator Dashboard API", version="1.0.0")

class APIKeyUpdate(BaseModel):
    service: str
    new_key: str

class APIKeyResponse(BaseModel):
    service: str
    masked_key: str
    status: str  # "active", "backup", "not_configured"

class SearchStats(BaseModel):
    total_searches: int
    successful_searches: int
    failed_searches: int
    last_search_time: Optional[str]
    active_provider: str

# Initialize API manager
api_manager = APIKeyManager()

@app.get("/api/keys", response_model=List[APIKeyResponse])
async def list_api_keys():
    """List all configured API keys (masked for security)."""
    keys = []
    
    services = [
        ("tavily", "TAVILY_API_KEY"),
        ("tavily_backup", "TAVILY_API_KEY_BACKUP"),
        ("tavily_dev", "TAVILY_API_KEY_DEV"),
        ("serpapi", "SERPAPI_KEY"),
    ]
    
    for service_name, env_var in services:
        value = api_manager.keys.get(env_var, "Not configured")
        masked = api_manager._mask_key(value) if value != "Not configured" else "Not configured"
        
        # Determine status
        if value == "Not configured":
            status = "not_configured"
        elif service_name == "tavily":
            status = "active"
        elif "backup" in service_name:
            status = "backup"
        else:
            status = "configured"
        
        keys.append(APIKeyResponse(
            service=service_name,
            masked_key=masked,
            status=status
        ))
    
    return keys

@app.post("/api/keys/update")
async def update_api_key(update: APIKeyUpdate):
    """Update an API key."""
    success = api_manager.update_key(update.service, update.new_key)
    if success:
        return {"message": f"✅ {update.service} API key updated successfully"}
    else:
        raise HTTPException(status_code=400, detail="Failed to update API key")

@app.post("/api/keys/validate/{service}")
async def validate_api_key(service: str):
    """Validate an API key."""
    success = api_manager.validate_key(service)
    if success:
        return {"message": f"✅ {service} API key is valid", "status": "valid"}
    else:
        return {"message": f"❌ {service} API key is invalid", "status": "invalid"}

@app.post("/api/keys/rotate/{service}")
async def rotate_api_key(service: str):
    """Rotate to backup API key."""
    success = api_manager.rotate_key(service)
    if success:
        return {"message": f"🔄 {service} API key rotated successfully", "status": "rotated"}
    else:
        raise HTTPException(status_code=400, detail="Failed to rotate API key")

@app.get("/api/search/stats", response_model=SearchStats)
async def get_search_stats():
    """Get web search statistics."""
    # This would connect to your actual search metrics
    # For now, return mock data
    return SearchStats(
        total_searches=0,
        successful_searches=0,
        failed_searches=0,
        last_search_time=None,
        active_provider="duckduckgo"  # or "tavily", "serpapi"
    )

@app.get("/api/search/test/{query}")
async def test_search(query: str):
    """Test web search with current configuration."""
    try:
        # Import and test web search
        sys.path.append(str(project_root / "chat_service" / "app" / "services"))
        from web_search import WebSearchService
        import asyncio
        
        async def run_test():
            service = WebSearchService()
            results = await service.search(query, 3)
            return {
                "query": query,
                "results_count": len(results),
                "provider_used": "tavily" if service.tavily_api_key else "duckduckgo",
                "results": [{"title": r.title, "source": r.source} for r in results[:2]]
            }
        
        return asyncio.run(run_test())
        
    except Exception as e:
        return {
            "query": query,
            "error": str(e),
            "results_count": 0,
            "provider_used": "none"
        }

@app.get("/api/health")
async def health_check():
    """Health check for dashboard API."""
    return {
        "status": "healthy",
        "services": {
            "api_manager": "✅",
            "web_search": "🔍",
            "dashboard": "📊"
        }
    }

# Dashboard UI Integration Info
DASHBOARD_INTEGRATION = {
    "api_base_url": "http://localhost:8001",
    "endpoints": {
        "list_keys": "/api/keys",
        "update_key": "/api/keys/update",
        "validate_key": "/api/keys/validate/{service}",
        "rotate_key": "/api/keys/rotate/{service}",
        "search_stats": "/api/search/stats",
        "test_search": "/api/search/test/{query}",
        "health": "/api/health"
    },
    "supported_services": ["tavily", "tavily_backup", "tavily_dev", "serpapi"],
    "current_keys": {
        "tavily": "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",
        "tavily_backup": "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", 
        "tavily_dev": "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"
    }
}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Creator Dashboard API...")
    print("📊 Available at: http://localhost:8001")
    print("📖 Docs at: http://localhost:8001/docs")
    uvicorn.run(app, host="0.0.0.0", port=8001)
