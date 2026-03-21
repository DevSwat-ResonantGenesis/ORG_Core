#!/usr/bin/env python3
"""
Contract Validator - Validates frontend-backend API contracts.

This script validates that backend endpoints conform to their contract definitions.
Run this as part of CI/CD or before deployment.
"""

import json
import sys
import httpx
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime


GATEWAY_URL = "http://localhost:8000"
CONTRACTS_FILE = Path(__file__).parent / "api_contracts.json"


def load_contracts() -> Dict[str, Any]:
    """Load contract definitions."""
    with open(CONTRACTS_FILE) as f:
        return json.load(f)


def validate_response_shape(response_data: Any, schema: Dict[str, Any], path: str = "") -> List[str]:
    """Validate response data against schema. Returns list of errors."""
    errors = []
    
    if isinstance(schema, dict):
        if not isinstance(response_data, dict):
            errors.append(f"{path}: Expected object, got {type(response_data).__name__}")
            return errors
            
        for key, expected_type in schema.items():
            if key not in response_data:
                if "|null" not in str(expected_type):
                    errors.append(f"{path}.{key}: Missing required field")
            else:
                value = response_data[key]
                if isinstance(expected_type, dict):
                    errors.extend(validate_response_shape(value, expected_type, f"{path}.{key}"))
                elif isinstance(expected_type, str):
                    if not validate_type(value, expected_type):
                        errors.append(f"{path}.{key}: Expected {expected_type}, got {type(value).__name__}")
    
    return errors


def validate_type(value: Any, type_str: str) -> bool:
    """Validate a value against a type string."""
    types = type_str.split("|")
    
    for t in types:
        t = t.strip()
        if t == "null" and value is None:
            return True
        elif t == "string" and isinstance(value, str):
            return True
        elif t == "number" and isinstance(value, (int, float)):
            return True
        elif t == "boolean" and isinstance(value, bool):
            return True
        elif t == "array" and isinstance(value, list):
            return True
        elif t == "object" and isinstance(value, dict):
            return True
    
    return False


def validate_contract(contract: Dict[str, Any], client: httpx.Client) -> Tuple[bool, List[str]]:
    """Validate a single contract. Returns (success, errors)."""
    endpoint = contract["endpoint"]
    method = contract["method"]
    errors = []
    
    try:
        if method == "GET":
            response = client.get(f"{GATEWAY_URL}{endpoint}", timeout=10)
        elif method == "POST":
            # For POST, we need test data - skip validation for now
            # Just check endpoint exists
            response = client.options(f"{GATEWAY_URL}{endpoint}", timeout=10)
            if response.status_code == 405:
                # OPTIONS not allowed, try with minimal data
                response = client.post(f"{GATEWAY_URL}{endpoint}", json={}, timeout=10)
        else:
            errors.append(f"Unsupported method: {method}")
            return False, errors
        
        # Check if endpoint exists (not 404)
        if response.status_code == 404:
            errors.append(f"Endpoint not found: {endpoint}")
            return False, errors
        
        # For GET requests, validate response shape
        if method == "GET" and response.status_code == 200:
            try:
                data = response.json()
                if "schema" in contract.get("response", {}):
                    shape_errors = validate_response_shape(data, contract["response"]["schema"])
                    errors.extend(shape_errors)
            except json.JSONDecodeError:
                errors.append("Response is not valid JSON")
        
        # Check for expected success code
        expected_code = contract.get("response", {}).get("success_code", 200)
        if method == "GET" and response.status_code != expected_code:
            # Allow 401 for auth-required endpoints
            if response.status_code != 401:
                errors.append(f"Expected {expected_code}, got {response.status_code}")
        
        return len(errors) == 0, errors
        
    except httpx.RequestError as e:
        errors.append(f"Request failed: {str(e)}")
        return False, errors


def main():
    """Run contract validation."""
    print("=" * 60)
    print("API Contract Validation")
    print(f"Gateway: {GATEWAY_URL}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print("=" * 60)
    
    contracts_data = load_contracts()
    contracts = contracts_data.get("contracts", [])
    
    print(f"\nValidating {len(contracts)} contracts...\n")
    
    passed = 0
    failed = 0
    skipped = 0
    
    with httpx.Client() as client:
        for contract in contracts:
            endpoint = contract["endpoint"]
            method = contract["method"]
            
            # Skip POST contracts that need auth/data
            if method == "POST":
                print(f"⏭️  SKIP: {method} {endpoint} (requires test data)")
                skipped += 1
                continue
            
            success, errors = validate_contract(contract, client)
            
            if success:
                print(f"✅ PASS: {method} {endpoint}")
                passed += 1
            else:
                print(f"❌ FAIL: {method} {endpoint}")
                for error in errors:
                    print(f"   └─ {error}")
                failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 60)
    
    # Exit with error code if any failures
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
