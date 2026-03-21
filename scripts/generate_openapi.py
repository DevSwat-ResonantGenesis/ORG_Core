#!/usr/bin/env python3
"""
Generate OpenAPI documentation for all ResonantGenesis backend services.

This script fetches OpenAPI specs from running services via HTTP.
Requires services to be running (docker-compose up).
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

# Service configurations with their ports
SERVICES = {
    "gateway": {
        "port": 8000,
        "title": "ResonantGenesis API Gateway",
        "description": "Central API Gateway for all ResonantGenesis services",
    },
    "auth_service": {
        "port": 8001,
        "title": "Auth Service",
        "description": "Authentication and authorization service",
    },
    "chat_service": {
        "port": 8002,
        "title": "Chat Service",
        "description": "Resonant Chat and conversation management",
    },
    "memory_service": {
        "port": 8004,
        "title": "Memory Service",
        "description": "Hash Sphere and RAG memory management",
    },
    "agent_engine_service": {
        "port": 8005,
        "title": "Agent Engine Service",
        "description": "Autonomous AI agent orchestration",
    },
    "blockchain_service": {
        "port": 8007,
        "title": "Blockchain Service",
        "description": "DSID-P identity and audit trail",
    },
    "billing_service": {
        "port": 8006,
        "title": "Billing Service",
        "description": "Subscriptions, credits, and payment processing",
    },
    "llm_service": {
        "port": 8003,
        "title": "LLM Service",
        "description": "Multi-provider LLM completions",
    },
    "marketplace_service": {
        "port": 8008,
        "title": "Marketplace Service",
        "description": "Agent marketplace and listings",
    },
    "crypto_service": {
        "port": 8010,
        "title": "Crypto Service",
        "description": "Cryptographic operations and wallets",
    },
    "notification_service": {
        "port": 8011,
        "title": "Notification Service",
        "description": "Email and push notifications",
    },
    "storage_service": {
        "port": 8012,
        "title": "Storage Service",
        "description": "File storage (MinIO S3)",
    },
    "workflow_service": {
        "port": 8017,
        "title": "Workflow Service",
        "description": "Workflow automation",
    },
    "ide_platform_service": {
        "port": 8009,
        "title": "IDE Service",
        "description": "Code editing and project management",
    },
    "code_execution_service": {
        "port": 8014,
        "title": "Code Execution Service",
        "description": "Sandboxed code execution",
    },
}

OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "openapi"


def fetch_openapi_spec(service_name: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fetch OpenAPI spec from a running service."""
    port = config["port"]
    url = f"http://localhost:{port}/openapi.json"
    
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            response.raise_for_status()
            spec = response.json()
            
            # Enhance with metadata
            spec["info"]["title"] = config["title"]
            spec["info"]["description"] = config["description"]
            spec["info"]["version"] = spec["info"].get("version", "1.0.0")
            
            # Add server info
            spec["servers"] = [
                {"url": f"http://localhost:{port}", "description": "Local development"},
                {"url": "https://api.resonantgenesis.ai", "description": "Production"},
            ]
            
            return spec
    except httpx.ConnectError:
        print(f"  ⚠ Service not running on port {port}")
        return None
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None


def main():
    """Fetch and save OpenAPI specs from all running services."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Fetching OpenAPI documentation from running services...")
    print("=" * 60)
    
    generated = []
    failed = []
    
    for service_name, config in SERVICES.items():
        print(f"\nProcessing {service_name} (port {config['port']})...")
        
        spec = fetch_openapi_spec(service_name, config)
        
        if spec:
            output_file = OUTPUT_DIR / f"{service_name}.json"
            with open(output_file, "w") as f:
                json.dump(spec, f, indent=2)
            
            # Count endpoints
            paths = spec.get("paths", {})
            endpoint_count = sum(len(methods) for methods in paths.values())
            print(f"  ✓ Generated: {output_file} ({endpoint_count} endpoints)")
            generated.append(service_name)
        else:
            failed.append(service_name)
    
    # Generate index file
    index = {
        "title": "ResonantGenesis Backend API Documentation",
        "version": "1.0.0",
        "generated_at": datetime.now().isoformat(),
        "services": {
            name: {
                "file": f"{name}.json",
                "port": SERVICES[name]["port"],
                "description": SERVICES[name]["description"],
            }
            for name in generated
        },
        "failed_services": failed,
    }
    
    index_file = OUTPUT_DIR / "index.json"
    with open(index_file, "w") as f:
        json.dump(index, f, indent=2)
    
    print("\n" + "=" * 60)
    print(f"Generated: {len(generated)} | Failed: {len(failed)}")
    if failed:
        print(f"Failed services (not running): {', '.join(failed)}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Index file: {index_file}")


if __name__ == "__main__":
    main()
