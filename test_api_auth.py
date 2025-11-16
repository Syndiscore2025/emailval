"""Test API Authentication and Rate Limiting"""
import requests
import json
import os

BASE_URL = "http://localhost:5000"

print("\n" + "="*80)
print("API AUTHENTICATION & RATE LIMITING TEST")
print("="*80 + "\n")

# Test 1: Missing API Key (when auth is enabled)
print("TEST 1: Missing API Key")
print("-"*80)
r = requests.post(
    f"{BASE_URL}/api/webhook/validate",
    json={"integration_mode": "standalone", "emails": ["test@example.com"], "include_smtp": False},
    timeout=5
)
print(f"Status: {r.status_code}")
print(f"Response: {r.json()}")

if os.getenv('API_AUTH_ENABLED', 'false').lower() == 'true':
    assert r.status_code == 401, "Should return 401 when API key is missing"
    print("✓ Correctly rejected missing API key\n")
else:
    print("⚠ API_AUTH_ENABLED is false - authentication bypassed (development mode)\n")

# Test 2: Invalid API Key
print("TEST 2: Invalid API Key")
print("-"*80)
r = requests.post(
    f"{BASE_URL}/api/webhook/validate",
    json={"integration_mode": "standalone", "emails": ["test@example.com"], "include_smtp": False},
    headers={"X-API-Key": "invalid_key_12345"},
    timeout=5
)
print(f"Status: {r.status_code}")
print(f"Response: {r.json()}")

if os.getenv('API_AUTH_ENABLED', 'false').lower() == 'true':
    assert r.status_code == 401, "Should return 401 for invalid API key"
    print("✓ Correctly rejected invalid API key\n")
else:
    print("⚠ API_AUTH_ENABLED is false - authentication bypassed (development mode)\n")

# Test 3: Valid API Key
print("TEST 3: Valid API Key")
print("-"*80)

# Create API key
session = requests.Session()
session.post(
    f"{BASE_URL}/admin/login",
    json={"username": "admin", "password": "admin123"},
    timeout=5
)

r = session.post(
    f"{BASE_URL}/admin/api/keys",
    json={"name": "Auth Test Key", "rate_limit": 10},  # Low limit for testing
    timeout=5
)
api_key = r.json().get("api_key")
key_id = r.json().get("metadata", {}).get("key_id")
print(f"Created API Key: {api_key[:20]}...")
print(f"Key ID: {key_id}")
print(f"Rate Limit: 10 requests/minute\n")

# Test with valid key
r = requests.post(
    f"{BASE_URL}/api/webhook/validate",
    json={"integration_mode": "standalone", "emails": ["test@example.com"], "include_smtp": False},
    headers={"X-API-Key": api_key},
    timeout=5
)
print(f"Status: {r.status_code}")
assert r.status_code == 200, "Should return 200 with valid API key"
print("✓ Valid API key accepted\n")

# Test 4: Rate Limiting
print("TEST 4: Rate Limiting (10 requests/minute)")
print("-"*80)

if os.getenv('API_AUTH_ENABLED', 'false').lower() == 'true':
    success_count = 0
    rate_limited = False
    
    for i in range(15):  # Try to exceed 10 req/min limit
        r = requests.post(
            f"{BASE_URL}/api/webhook/validate",
            json={"integration_mode": "standalone", "emails": ["test@example.com"], "include_smtp": False},
            headers={"X-API-Key": api_key},
            timeout=5
        )
        if r.status_code == 200:
            success_count += 1
        elif r.status_code == 429:
            rate_limited = True
            retry_after = r.headers.get('Retry-After')
            print(f"Rate limit enforced after {success_count} requests")
            print(f"Status: {r.status_code}")
            print(f"Retry-After: {retry_after} seconds")
            print(f"Response: {r.json()}")
            break
    
    if rate_limited:
        print("✓ Rate limiting working correctly\n")
    else:
        print(f"⚠ Rate limit not enforced (processed {success_count} requests)\n")
else:
    print("⚠ API_AUTH_ENABLED is false - rate limiting bypassed (development mode)")
    print("  To enable: Set environment variable API_AUTH_ENABLED=true\n")

# Test 5: API Key Management
print("TEST 5: API Key Management")
print("-"*80)

# List all keys
r = session.get(f"{BASE_URL}/admin/api/keys", timeout=5)
keys = r.json().get("keys", [])
print(f"Total API keys: {len(keys)}")

# Find our test key
test_key = next((k for k in keys if k.get("name") == "Auth Test Key"), None)
if test_key:
    print(f"Test key found:")
    print(f"  - Name: {test_key.get('name')}")
    print(f"  - Key ID: {test_key.get('key_id')}")
    print(f"  - Active: {test_key.get('active')}")
    print(f"  - Rate Limit: {test_key.get('rate_limit_per_minute')}/min")
    print(f"  - Usage Total: {test_key.get('usage_total')}")
    print(f"  - Window Count: {test_key.get('window_count')}")
    print("✓ API key management working\n")

# Test 6: Revoke API Key
print("TEST 6: Revoke API Key")
print("-"*80)

r = session.delete(f"{BASE_URL}/admin/api/keys/{key_id}", timeout=5)
print(f"Revoke status: {r.status_code}")
print(f"Response: {r.json()}")

# Try to use revoked key
if os.getenv('API_AUTH_ENABLED', 'false').lower() == 'true':
    r = requests.post(
        f"{BASE_URL}/api/webhook/validate",
        json={"integration_mode": "standalone", "emails": ["test@example.com"], "include_smtp": False},
        headers={"X-API-Key": api_key},
        timeout=5
    )
    print(f"\nUsing revoked key - Status: {r.status_code}")
    if r.status_code == 401:
        print("✓ Revoked key correctly rejected\n")
    else:
        print("⚠ Revoked key still works (unexpected)\n")
else:
    print("⚠ API_AUTH_ENABLED is false - revocation check bypassed\n")

print("="*80)
print("SUMMARY")
print("="*80)
print(f"API_AUTH_ENABLED: {os.getenv('API_AUTH_ENABLED', 'false')}")
print("\nNOTE: To enable full API authentication and rate limiting in production:")
print("  1. Set environment variable: API_AUTH_ENABLED=true")
print("  2. Restart the server")
print("  3. All webhook endpoints will require valid API keys")
print("  4. Rate limiting will be enforced per API key")
print("\nCurrent mode: DEVELOPMENT (authentication optional)")
print("="*80 + "\n")

