#!/usr/bin/env python3
"""
Sandbox Security Test Suite
Tests Docker isolation for code execution services
"""

import requests
import json
import time

# Test configuration
CODE_EXECUTION_URL = "http://localhost:8002"  # Adjust if needed
ED_SERVICE_URL = "http://localhost:8000"  # Adjust if needed

def test_code_execution(url, code, language="python"):
    """Test code execution and return result."""
    try:
        response = requests.post(
            f"{url}/code/execute",
            json={"code": code, "language": language},
            timeout=35
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def print_test(name, passed, details=""):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {name}")
    if details:
        print(f"  Details: {details}")
    print()

# Security Tests
print("=" * 60)
print("SANDBOX SECURITY TEST SUITE")
print("=" * 60)
print()

# Test 1: Basic execution works
print("Test 1: Basic Python execution")
result = test_code_execution(CODE_EXECUTION_URL, "print('Hello, World!')")
passed = result.get("success") and "Hello, World!" in result.get("output", "")
print_test("Basic execution", passed, result.get("output", ""))

# Test 2: Network isolation (should fail)
print("Test 2: Network isolation (should be blocked)")
code = """
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('8.8.8.8', 53))
    print('SECURITY BREACH: Network access allowed!')
except Exception as e:
    print(f'Network blocked: {type(e).__name__}')
"""
result = test_code_execution(CODE_EXECUTION_URL, code)
passed = "Network blocked" in result.get("output", "") or "error" in result.get("output", "").lower()
print_test("Network isolation", passed, result.get("output", ""))

# Test 3: Filesystem isolation (should fail to read host files)
print("Test 3: Filesystem isolation")
code = """
import os
try:
    with open('/etc/passwd', 'r') as f:
        print('SECURITY BREACH: Can read /etc/passwd!')
except Exception as e:
    print(f'Filesystem isolated: {type(e).__name__}')
"""
result = test_code_execution(CODE_EXECUTION_URL, code)
passed = "Filesystem isolated" in result.get("output", "") or "Permission denied" in result.get("output", "")
print_test("Filesystem isolation", passed, result.get("output", ""))

# Test 4: Environment variable isolation (shouldn't see host env vars)
print("Test 4: Environment variable isolation")
code = """
import os
env_vars = list(os.environ.keys())
sensitive = [k for k in env_vars if 'PASSWORD' in k or 'SECRET' in k or 'KEY' in k]
if sensitive:
    print(f'SECURITY BREACH: Found sensitive vars: {sensitive}')
else:
    print('Environment isolated: No sensitive variables')
print(f'Total env vars: {len(env_vars)}')
"""
result = test_code_execution(CODE_EXECUTION_URL, code)
passed = "Environment isolated" in result.get("output", "")
print_test("Environment isolation", passed, result.get("output", ""))

# Test 5: Process limits (should be restricted)
print("Test 5: Process limits")
code = """
import subprocess
try:
    # Try to spawn many processes
    for i in range(100):
        subprocess.Popen(['sleep', '1'])
    print('SECURITY BREACH: No process limits!')
except Exception as e:
    print(f'Process limits enforced: {type(e).__name__}')
"""
result = test_code_execution(CODE_EXECUTION_URL, code)
passed = "limits enforced" in result.get("output", "") or "error" in result.get("output", "").lower()
print_test("Process limits", passed, result.get("output", ""))

# Test 6: Timeout enforcement
print("Test 6: Timeout enforcement (30s test)")
code = """
import time
time.sleep(100)
print('SECURITY BREACH: Timeout not enforced!')
"""
start = time.time()
result = test_code_execution(CODE_EXECUTION_URL, code)
duration = time.time() - start
passed = "timed out" in result.get("error", "").lower() and duration < 35
print_test("Timeout enforcement", passed, f"Duration: {duration:.1f}s, Error: {result.get('error', '')}")

# Test 7: Memory limits (should fail on excessive allocation)
print("Test 7: Memory limits")
code = """
try:
    # Try to allocate 1GB
    data = bytearray(1024 * 1024 * 1024)
    print('SECURITY BREACH: No memory limits!')
except MemoryError:
    print('Memory limits enforced: MemoryError')
except Exception as e:
    print(f'Memory limits enforced: {type(e).__name__}')
"""
result = test_code_execution(CODE_EXECUTION_URL, code)
passed = "limits enforced" in result.get("output", "")
print_test("Memory limits", passed, result.get("output", ""))

# Test 8: Cannot execute system commands
print("Test 8: System command isolation")
code = """
import subprocess
try:
    result = subprocess.run(['whoami'], capture_output=True, text=True)
    user = result.stdout.strip()
    if user == 'root':
        print('SECURITY BREACH: Running as root!')
    elif user == 'nobody':
        print('Security OK: Running as nobody')
    else:
        print(f'Running as: {user}')
except Exception as e:
    print(f'Command execution restricted: {type(e).__name__}')
"""
result = test_code_execution(CODE_EXECUTION_URL, code)
passed = "nobody" in result.get("output", "") or "restricted" in result.get("output", "")
print_test("Non-root execution", passed, result.get("output", ""))

# Summary
print("=" * 60)
print("TEST SUITE COMPLETE")
print("=" * 60)
print()
print("If all tests passed, the sandbox is properly isolated.")
print("If any tests failed, there are security vulnerabilities.")
