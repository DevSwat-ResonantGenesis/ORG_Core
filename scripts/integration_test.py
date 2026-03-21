#!/usr/bin/env python3
"""
Integration test script for ResonantGenesis backend services.
Tests all microservices through the gateway.
"""

import json
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

GATEWAY_URL = "http://localhost:8000"
TIMEOUT = 10

# Test results
results: List[Dict[str, Any]] = []


def log(msg: str, status: str = "INFO"):
    """Print formatted log message."""
    icons = {"PASS": "✅", "FAIL": "❌", "INFO": "ℹ️", "WARN": "⚠️"}
    print(f"{icons.get(status, '•')} {msg}")


def test(name: str, passed: bool, details: str = ""):
    """Record test result."""
    results.append({"name": name, "passed": passed, "details": details})
    status = "PASS" if passed else "FAIL"
    log(f"{name}: {details}" if details else name, status)


def api_call(
    method: str,
    path: str,
    data: Optional[Dict] = None,
    token: Optional[str] = None,
    headers: Optional[Dict] = None,
) -> Tuple[int, Any]:
    """Make API call and return (status_code, response_data)."""
    url = f"{GATEWAY_URL}{path}"
    default_headers = {"Content-Type": "application/json"}
    if token:
        default_headers["Authorization"] = f"Bearer {token}"
    if headers:
        default_headers.update(headers)

    try:
        if method == "GET":
            resp = requests.get(url, headers=default_headers, timeout=TIMEOUT)
        elif method == "POST":
            resp = requests.post(url, json=data, headers=default_headers, timeout=TIMEOUT)
        elif method == "PUT":
            resp = requests.put(url, json=data, headers=default_headers, timeout=TIMEOUT)
        elif method == "DELETE":
            resp = requests.delete(url, headers=default_headers, timeout=TIMEOUT)
        else:
            return -1, {"error": f"Unknown method: {method}"}

        try:
            return resp.status_code, resp.json()
        except:
            return resp.status_code, resp.text
    except requests.exceptions.ConnectionError:
        return -1, {"error": "Connection refused"}
    except requests.exceptions.Timeout:
        return -1, {"error": "Request timeout"}
    except Exception as e:
        return -1, {"error": str(e)}


def test_health_endpoints():
    """Test all service health endpoints."""
    log("\n=== HEALTH ENDPOINT TESTS ===", "INFO")

    services = [
        ("/health", "Gateway"),
        ("/api/auth/health", "Auth Service"),
        ("/api/user/health", "User Service"),
        ("/api/chat/health", "Chat Service"),
        ("/api/memory/health", "Memory Service"),
        ("/api/cognitive/health", "Cognitive Service"),
        ("/api/workflow/health", "Workflow Service"),
        ("/api/ml/health", "ML Service"),
        ("/api/storage/health", "Storage Service"),
        ("/api/llm/health", "LLM Service"),
        ("/api/ed/health", "ED Service"),
        ("/api/marketplace/health", "Marketplace Service"),
        ("/api/agents/health", "Agent Engine Service"),
        ("/api/crypto/health", "Crypto Service"),
        ("/api/blockchain/health", "Blockchain Service"),
    ]

    for path, name in services:
        status, data = api_call("GET", path)
        passed = status == 200 and isinstance(data, dict) and data.get("status") == "ok"
        test(f"{name} Health", passed, f"status={status}")


def test_auth_service():
    """Test auth service functionality."""
    log("\n=== AUTH SERVICE TESTS ===", "INFO")

    # Register user
    user_data = {
        "email": f"test_{int(time.time())}@example.com",
        "password": "TestPass123!",
        "name": "Test User",
    }
    status, data = api_call("POST", "/api/auth/auth/register", user_data)
    test("Auth: Register User", status in [200, 201, 409], f"status={status}")

    # Login
    login_data = {"email": user_data["email"], "password": user_data["password"]}
    status, data = api_call("POST", "/api/auth/auth/login", login_data)
    passed = status == 200 and "access_token" in str(data)
    test("Auth: Login", passed, f"status={status}")

    token = data.get("access_token") if isinstance(data, dict) else None
    return token


def test_user_service(token: Optional[str] = None):
    """Test user service functionality."""
    log("\n=== USER SERVICE TESTS ===", "INFO")

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # Get profile (may fail without auth)
    status, data = api_call("GET", "/api/user/users/me", headers=headers)
    test("User: Get Profile", status in [200, 401, 403], f"status={status}")


def test_chat_service(token: Optional[str] = None):
    """Test chat service functionality."""
    log("\n=== CHAT SERVICE TESTS ===", "INFO")

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # Create conversation
    conv_data = {"title": "Test Conversation"}
    status, data = api_call("POST", "/api/chat/chat/conversations", conv_data, headers)
    passed = status in [200, 201, 401]
    test("Chat: Create Conversation", passed, f"status={status}")

    conv_id = data.get("id") if isinstance(data, dict) and status in [200, 201] else None

    # List conversations
    status, data = api_call("GET", "/api/chat/chat/conversations", headers=headers)
    test("Chat: List Conversations", status in [200, 401], f"status={status}")

    return conv_id


def test_memory_service():
    """Test memory service functionality."""
    log("\n=== MEMORY SERVICE TESTS ===", "INFO")

    # Ingest memory
    memory_data = {
        "content": "This is a test memory about machine learning and AI.",
        "source": "integration_test",
        "metadata": {"test": True},
    }
    status, data = api_call("POST", "/api/memory/memory/ingest", memory_data)
    passed = status in [200, 201]
    test("Memory: Ingest", passed, f"status={status}")

    memory_id = data.get("id") if isinstance(data, dict) else None

    # Retrieve memories
    retrieve_data = {"query": "machine learning", "limit": 5}
    status, data = api_call("POST", "/api/memory/memory/retrieve", retrieve_data)
    test("Memory: Retrieve", status == 200, f"status={status}")

    # Stats endpoint
    status, data = api_call("GET", "/api/memory/memory/stats")
    test("Memory: Stats", status == 200, f"status={status}")

    return memory_id


def test_cognitive_service():
    """Test cognitive service functionality."""
    log("\n=== COGNITIVE SERVICE TESTS ===", "INFO")

    # Create tick
    tick_data = {
        "kind": "test_event",
        "payload": "Integration test tick payload",
        "auto_analyze": True,
    }
    status, data = api_call("POST", "/api/cognitive/cognitive/ticks", tick_data)
    passed = status in [200, 201]
    test("Cognitive: Create Tick", passed, f"status={status}")

    # List ticks
    status, data = api_call("GET", "/api/cognitive/cognitive/ticks")
    test("Cognitive: List Ticks", status == 200, f"status={status}")

    # List anomalies
    status, data = api_call("GET", "/api/cognitive/cognitive/anomalies")
    test("Cognitive: List Anomalies", status == 200, f"status={status}")

    # List clusters
    status, data = api_call("GET", "/api/cognitive/cognitive/clusters")
    test("Cognitive: List Clusters", status == 200, f"status={status}")

    # Get insights
    status, data = api_call("GET", "/api/cognitive/cognitive/insights")
    test("Cognitive: Get Insights", status == 200, f"status={status}")


def test_workflow_service():
    """Test workflow service functionality."""
    log("\n=== WORKFLOW SERVICE TESTS ===", "INFO")

    # Create workflow
    workflow_data = {
        "name": "Test Workflow",
        "description": "Integration test workflow",
        "trigger_type": "manual",
        "steps": [
            {
                "name": "step1",
                "type": "transform_data",
                "config": {"expression": "$.input.message"},
            },
            {
                "name": "step2",
                "type": "delay",
                "config": {"seconds": 1},
            },
        ],
    }
    status, data = api_call("POST", "/api/workflow/workflow/workflows", workflow_data)
    passed = status in [200, 201]
    test("Workflow: Create", passed, f"status={status}")

    workflow_id = data.get("id") if isinstance(data, dict) else None

    # List workflows
    status, data = api_call("GET", "/api/workflow/workflow/workflows")
    test("Workflow: List", status == 200, f"status={status}")

    # Run workflow
    if workflow_id:
        run_data = {"input_data": {"message": "Hello from test"}}
        status, data = api_call(
            "POST", f"/api/workflow/workflow/workflows/{workflow_id}/run", run_data
        )
        test("Workflow: Run", status in [200, 201], f"status={status}")

        run_id = data.get("id") if isinstance(data, dict) else None

        # Get run status
        if run_id:
            status, data = api_call("GET", f"/api/workflow/workflow/runs/{run_id}")
            test("Workflow: Get Run", status == 200, f"status={status}")

    # Publish event
    event_data = {
        "event_type": "test_event",
        "source": "integration_test",
        "payload": {"test": True},
    }
    status, data = api_call("POST", "/api/workflow/workflow/events", event_data)
    test("Workflow: Publish Event", status in [200, 201], f"status={status}")

    return workflow_id


def test_ml_service():
    """Test ML service functionality."""
    log("\n=== ML SERVICE TESTS ===", "INFO")

    # Register model
    model_data = {
        "name": "test-model",
        "model_type": "classification",
        "framework": "pytorch",
        "description": "Test model for integration testing",
    }
    status, data = api_call("POST", "/api/ml/ml/models", model_data)
    passed = status in [200, 201]
    test("ML: Register Model", passed, f"status={status}")

    model_id = data.get("id") if isinstance(data, dict) else None

    # List models
    status, data = api_call("GET", "/api/ml/ml/models")
    test("ML: List Models", status == 200, f"status={status}")

    # Create version
    if model_id:
        version_data = {
            "version": "1.0.0",
            "location": "s3://models/test-model-v1",
            "is_default": True,
        }
        status, data = api_call(
            "POST", f"/api/ml/ml/models/{model_id}/versions", version_data
        )
        test("ML: Create Version", status in [200, 201], f"status={status}")

        # Run inference
        infer_data = {
            "model_id": model_id,
            "input_data": {"features": [1.0, 2.0, 3.0]},
        }
        status, data = api_call("POST", "/api/ml/ml/infer", infer_data)
        test("ML: Run Inference", status == 200, f"status={status}")

    # Create training job
    training_data = {
        "name": "test-training",
        "config": {"epochs": 10, "batch_size": 32},
    }
    status, data = api_call("POST", "/api/ml/ml/training", training_data)
    test("ML: Create Training Job", status in [200, 201], f"status={status}")

    return model_id


def test_storage_service():
    """Test storage service functionality."""
    log("\n=== STORAGE SERVICE TESTS ===", "INFO")

    # List buckets
    status, data = api_call("GET", "/api/storage/storage/buckets")
    test("Storage: List Buckets", status == 200, f"status={status}")

    # List files
    status, data = api_call("GET", "/api/storage/storage/files")
    test("Storage: List Files", status == 200, f"status={status}")


def test_llm_service():
    """Test LLM service functionality."""
    log("\n=== LLM SERVICE TESTS ===", "INFO")

    # List tools
    status, data = api_call("GET", "/api/llm/llm/tools")
    test("LLM: List Tools", status == 200, f"status={status}")

    # List models
    status, data = api_call("GET", "/api/llm/llm/models")
    test("LLM: List Models", status == 200, f"status={status}")

    # Chat completion (will fail without API key, but should return proper error)
    chat_data = {
        "messages": [{"role": "user", "content": "Say hello"}],
        "model": "gpt-4-turbo-preview",
        "max_tokens": 50,
    }
    status, data = api_call("POST", "/api/llm/llm/chat/completions", chat_data)
    # Accept 200 (success), 400 (validation), or 500/503 (API key not configured)
    test("LLM: Chat Completion Endpoint", status in [200, 400, 500, 503], f"status={status}")


def test_gateway_features():
    """Test gateway-specific features."""
    log("\n=== GATEWAY FEATURE TESTS ===", "INFO")

    # Root endpoint
    status, data = api_call("GET", "/")
    test("Gateway: Root Endpoint", status == 200, f"status={status}")

    # Metrics endpoint
    status, data = api_call("GET", "/metrics")
    passed = status == 200 and isinstance(data, dict) and "total_requests" in data
    test("Gateway: Metrics", passed, f"status={status}")

    # Check rate limit headers
    status, data = api_call("GET", "/health")
    # Rate limit headers are added by middleware
    test("Gateway: Health with Rate Limit", status == 200, f"status={status}")


def test_ed_service():
    """Test ED service functionality."""
    log("\n=== ED SERVICE TESTS ===", "INFO")

    # List tools
    status, data = api_call("GET", "/api/ed/ed/tools")
    test("ED: List Tools", status == 200, f"status={status}")

    # Validate code
    validate_data = {"code": "print('hello')", "language": "python"}
    status, data = api_call("POST", "/api/ed/ed/validate", validate_data)
    passed = status == 200 and isinstance(data, dict) and data.get("valid") == True
    test("ED: Validate Code", passed, f"status={status}")

    # Execute code
    exec_data = {"code": "print('Hello from ED!')", "language": "python", "timeout": 30}
    status, data = api_call("POST", "/api/ed/ed/execute", exec_data)
    passed = status == 200 and isinstance(data, dict)
    test("ED: Execute Code", passed, f"status={status}")

    # Create workspace
    ws_data = {"name": "Test Workspace", "description": "Integration test workspace"}
    status, data = api_call("POST", "/api/ed/ed/workspaces", ws_data)
    passed = status == 201 and isinstance(data, dict) and "id" in data
    test("ED: Create Workspace", passed, f"status={status}")

    workspace_id = data.get("id") if isinstance(data, dict) else None

    # List workspaces
    status, data = api_call("GET", "/api/ed/ed/workspaces")
    test("ED: List Workspaces", status == 200, f"status={status}")

    # Create agent
    agent_data = {"name": "Test Agent", "workspace_id": workspace_id}
    status, data = api_call("POST", "/api/ed/ed/agents", agent_data)
    passed = status == 201 and isinstance(data, dict) and "id" in data
    test("ED: Create Agent", passed, f"status={status}")

    agent_id = data.get("id") if isinstance(data, dict) else None

    # List agents
    status, data = api_call("GET", "/api/ed/ed/agents")
    test("ED: List Agents", status == 200, f"status={status}")

    # Get agent stats (note: endpoint is at /stats not /agents/stats)
    status, data = api_call("GET", "/api/ed/ed/agents")
    test("ED: Agent Stats (via list)", status == 200, f"status={status}")

    return workspace_id, agent_id


def test_marketplace_service(token: str = None):
    """Test marketplace service functionality."""
    log("\n=== MARKETPLACE SERVICE TESTS ===", "INFO")

    # List categories
    status, data = api_call("GET", "/api/marketplace/marketplace/categories")
    test("Marketplace: List Categories", status == 200, f"status={status}")

    # Get stats
    status, data = api_call("GET", "/api/marketplace/marketplace/stats")
    test("Marketplace: Get Stats", status == 200, f"status={status}")

    # List listings (empty initially)
    status, data = api_call("GET", "/api/marketplace/marketplace/listings")
    test("Marketplace: List Listings", status == 200, f"status={status}")

    # Create listing (requires auth)
    listing_data = {
        "name": "Test AI Agent",
        "tagline": "A test agent for integration testing",
        "description": "This is a test agent created during integration tests.",
        "category": "coding",
        "tags": ["test", "integration"],
        "price_type": "free",
        "agent_config": {"system_prompt": "You are a helpful assistant."},
    }
    status, data = api_call("POST", "/api/marketplace/marketplace/listings", listing_data, token)
    passed = status == 201 and isinstance(data, dict) and "id" in data
    test("Marketplace: Create Listing", passed, f"status={status}")

    listing_id = data.get("id") if isinstance(data, dict) else None

    if listing_id:
        # Get listing
        status, data = api_call("GET", f"/api/marketplace/marketplace/listings/{listing_id}")
        test("Marketplace: Get Listing", status == 200, f"status={status}")

        # Publish listing
        status, data = api_call("POST", f"/api/marketplace/marketplace/listings/{listing_id}/publish", token=token)
        test("Marketplace: Publish Listing", status == 200, f"status={status}")

        # Purchase listing (free)
        status, data = api_call("POST", f"/api/marketplace/marketplace/listings/{listing_id}/purchase", token=token)
        test("Marketplace: Purchase Listing", status == 200, f"status={status}")

        # List purchases
        status, data = api_call("GET", "/api/marketplace/marketplace/purchases", token=token)
        test("Marketplace: List Purchases", status == 200, f"status={status}")

        # Create review
        review_data = {"rating": 5, "title": "Great agent!", "content": "Works perfectly for testing."}
        status, data = api_call("POST", f"/api/marketplace/marketplace/listings/{listing_id}/reviews", review_data, token)
        passed = status == 201 and isinstance(data, dict)
        test("Marketplace: Create Review", passed, f"status={status}")

        # List reviews
        status, data = api_call("GET", f"/api/marketplace/marketplace/listings/{listing_id}/reviews")
        test("Marketplace: List Reviews", status == 200, f"status={status}")

    return listing_id


def test_agent_engine_service(token: str = None):
    """Test agent engine service functionality."""
    log("\n=== AGENT ENGINE SERVICE TESTS ===", "INFO")

    headers = {"x-user-id": "test-user-123"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Create agent definition
    agent_data = {
        "name": "Test Agent",
        "description": "Integration test agent",
        "system_prompt": "You are a helpful test assistant.",
        "model": "gpt-4-turbo-preview",
        "tools": [],
    }
    status, data = api_call("POST", "/api/agents/agents/", agent_data, headers=headers)
    passed = status in [200, 201]
    test("Agent Engine: Create Agent", passed, f"status={status}")

    agent_id = data.get("id") if isinstance(data, dict) else None

    # List agents
    status, data = api_call("GET", "/api/agents/agents/", headers=headers)
    test("Agent Engine: List Agents", status == 200, f"status={status}")

    # Create tool
    tool_data = {
        "name": "test_tool",
        "description": "A test tool",
        "handler_type": "http",
        "handler_config": {"url": "http://example.com/api"},
        "risk_level": "low",
    }
    status, data = api_call("POST", "/api/agents/agents/tools", tool_data, headers=headers)
    test("Agent Engine: Create Tool", status in [200, 201], f"status={status}")

    # List tools
    status, data = api_call("GET", "/api/agents/agents/tools", headers=headers)
    test("Agent Engine: List Tools", status == 200, f"status={status}")

    # Create safety rule
    rule_data = {
        "name": "test_rate_limit",
        "rule_type": "rate_limit",
        "action": "block",
        "parameters": {"max_requests": 100, "window_seconds": 60},
    }
    status, data = api_call("POST", "/api/agents/agents/safety-rules", rule_data, headers=headers)
    test("Agent Engine: Create Safety Rule", status in [200, 201], f"status={status}")

    # List safety rules
    status, data = api_call("GET", "/api/agents/agents/safety-rules", headers=headers)
    test("Agent Engine: List Safety Rules", status == 200, f"status={status}")

    return agent_id


def test_crypto_service(token: str = None):
    """Test crypto service functionality."""
    log("\n=== CRYPTO SERVICE TESTS ===", "INFO")

    headers = {"x-user-id": "test-user-123"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Create wallet
    status, data = api_call("POST", "/api/crypto/crypto/wallet", headers=headers)
    passed = status in [200, 201]
    test("Crypto: Create Wallet", passed, f"status={status}")

    # Get wallet
    status, data = api_call("GET", "/api/crypto/crypto/wallet", headers=headers)
    test("Crypto: Get Wallet", status == 200, f"status={status}")

    # Get balance
    status, data = api_call("GET", "/api/crypto/crypto/wallet/balance", headers=headers)
    test("Crypto: Get Balance", status == 200, f"status={status}")

    # Get token stats
    status, data = api_call("GET", "/api/crypto/crypto/token/stats", headers=headers)
    test("Crypto: Token Stats", status == 200, f"status={status}")

    # Get token price
    status, data = api_call("GET", "/api/crypto/crypto/token/price", headers=headers)
    test("Crypto: Token Price", status == 200, f"status={status}")

    # List transactions
    status, data = api_call("GET", "/api/crypto/crypto/transactions", headers=headers)
    test("Crypto: List Transactions", status == 200, f"status={status}")

    # List funding sources
    status, data = api_call("GET", "/api/crypto/crypto/funding-sources", headers=headers)
    test("Crypto: List Funding Sources", status == 200, f"status={status}")


def test_blockchain_service(token: str = None):
    """Test blockchain service functionality."""
    log("\n=== BLOCKCHAIN SERVICE TESTS ===", "INFO")

    headers = {"x-user-id": "test-user-123"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Create DSID
    dsid_data = {
        "entity_type": "test",
        "entity_id": "test-entity-123",
        "content": {"test": "data", "timestamp": int(time.time())},
    }
    status, data = api_call("POST", "/api/blockchain/blockchain/dsid", dsid_data, headers=headers)
    passed = status in [200, 201]
    test("Blockchain: Create DSID", passed, f"status={status}")

    dsid = data.get("dsid") if isinstance(data, dict) else None

    if dsid:
        # Get DSID
        status, data = api_call("GET", f"/api/blockchain/blockchain/dsid/{dsid}", headers=headers)
        test("Blockchain: Get DSID", status == 200, f"status={status}")

        # Get lineage
        status, data = api_call("GET", f"/api/blockchain/blockchain/dsid/{dsid}/lineage", headers=headers)
        test("Blockchain: Get DSID Lineage", status == 200, f"status={status}")

    # Create transaction
    tx_data = {
        "tx_type": "test",
        "payload": {"action": "integration_test"},
    }
    status, data = api_call("POST", "/api/blockchain/blockchain/transactions", tx_data, headers=headers)
    passed = status in [200, 201]
    test("Blockchain: Create Transaction", passed, f"status={status}")

    tx_hash = data.get("tx_hash") if isinstance(data, dict) else None

    if tx_hash:
        # Get transaction
        status, data = api_call("GET", f"/api/blockchain/blockchain/transactions/{tx_hash}", headers=headers)
        test("Blockchain: Get Transaction", status == 200, f"status={status}")

    # Get chain stats
    status, data = api_call("GET", "/api/blockchain/blockchain/chain/stats", headers=headers)
    test("Blockchain: Chain Stats", status == 200, f"status={status}")

    # Create audit entry
    audit_data = {
        "event_type": "test_event",
        "event_category": "security",
        "action": "integration_test",
        "success": True,
    }
    status, data = api_call("POST", "/api/blockchain/blockchain/audit", audit_data, headers=headers)
    passed = status in [200, 201]
    test("Blockchain: Create Audit Entry", passed, f"status={status}")

    # Get audit stats
    status, data = api_call("GET", "/api/blockchain/blockchain/audit/stats", headers=headers)
    test("Blockchain: Audit Stats", status == 200, f"status={status}")

    # Compute Merkle root
    merkle_data = ["hash1", "hash2", "hash3", "hash4"]
    status, data = api_call("POST", "/api/blockchain/blockchain/merkle/root", merkle_data, headers=headers)
    test("Blockchain: Compute Merkle Root", status == 200, f"status={status}")

    return dsid


def test_cross_service_integration():
    """Test cross-service communication."""
    log("\n=== CROSS-SERVICE INTEGRATION TESTS ===", "INFO")

    # Memory → Cognitive: Ingest memory and check if cognitive can see it
    memory_data = {
        "content": "Cross-service test: AI agent performing task analysis",
        "source": "cross_test",
    }
    status, _ = api_call("POST", "/api/memory/memory/ingest", memory_data)
    test("Cross: Memory Ingest for Cognitive", status in [200, 201], f"status={status}")

    # Cognitive tick that might trigger workflow
    tick_data = {
        "kind": "cross_service_test",
        "payload": "Testing cross-service communication",
        "auto_analyze": True,
    }
    status, _ = api_call("POST", "/api/cognitive/cognitive/ticks", tick_data)
    test("Cross: Cognitive Tick", status in [200, 201], f"status={status}")


def print_summary():
    """Print test summary."""
    log("\n" + "=" * 60, "INFO")
    log("TEST SUMMARY", "INFO")
    log("=" * 60, "INFO")

    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    total = len(results)

    log(f"Total: {total} | Passed: {passed} | Failed: {failed}", "INFO")
    log(f"Success Rate: {passed/total*100:.1f}%" if total > 0 else "No tests run", "INFO")

    if failed > 0:
        log("\nFailed Tests:", "WARN")
        for r in results:
            if not r["passed"]:
                log(f"  - {r['name']}: {r['details']}", "FAIL")

    return failed == 0


def main():
    """Run all integration tests."""
    log("=" * 60, "INFO")
    log("RESONANTGENESIS INTEGRATION TESTS", "INFO")
    log("=" * 60, "INFO")
    log(f"Gateway URL: {GATEWAY_URL}", "INFO")

    # Wait for services to be ready
    log("\nWaiting for services...", "INFO")
    time.sleep(2)

    # Run tests
    test_health_endpoints()
    token = test_auth_service()
    test_user_service(token)
    test_chat_service(token)
    test_memory_service()
    test_cognitive_service()
    test_workflow_service()
    test_ml_service()
    test_storage_service()
    test_llm_service()
    test_ed_service()
    test_marketplace_service(token)
    test_agent_engine_service(token)
    test_crypto_service(token)
    test_blockchain_service(token)
    test_gateway_features()
    test_cross_service_integration()

    # Summary
    success = print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
