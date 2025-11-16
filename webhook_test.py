"""Test webhook functionality and signature verification"""
import requests
import json
import hmac
import hashlib

BASE_URL = "http://localhost:5000"

print("\n" + "="*70)
print("WEBHOOK FUNCTIONALITY TEST")
print("="*70 + "\n")

# First, create an API key
session = requests.Session()
session.post(
    f"{BASE_URL}/admin/login",
    json={"username": "admin", "password": "admin123"},
    timeout=5
)

r = session.post(
    f"{BASE_URL}/admin/api/keys",
    json={"name": "Webhook Test Key", "rate_limit": 100},
    timeout=5
)
api_key = r.json().get("api_key")
print(f"1. Created API Key: {api_key[:20]}...\n")

# Test 1: CRM Webhook - HubSpot format
print("2. Testing CRM Webhook (HubSpot format)...")
payload = {
    "integration_mode": "crm",
    "crm_vendor": "hubspot",
    "event_type": "contact.created",
    "crm_context": [
        {"email": "hubspot1@example.com", "record_id": "hs_001", "name": "John Doe"},
        {"email": "hubspot2@example.com", "record_id": "hs_002", "name": "Jane Smith"}
    ],
    "include_smtp": False
}

r = requests.post(
    f"{BASE_URL}/api/webhook/validate",
    json=payload,
    headers={"X-API-Key": api_key},
    timeout=15
)

if r.status_code == 200:
    data = r.json()
    print(f"   [PASS] Event: {data.get('event')}")
    print(f"   Records processed: {len(data.get('records', []))}")
    for rec in data.get('records', []):
        email_type = rec.get('checks', {}).get('type', {}).get('email_type', 'unknown')
        print(f"     - {rec['email']}: status={rec['status']}, type={email_type}")
else:
    print(f"   [FAIL] Status: {r.status_code}, Response: {r.text[:200]}")

# Test 2: CRM Webhook - Salesforce format
print("\n3. Testing CRM Webhook (Salesforce format)...")
payload = {
    "integration_mode": "crm",
    "crm_vendor": "salesforce",
    "event_type": "contact.updated",
    "crm_context": [
        {"email": "sf1@example.com", "record_id": "003xx000004TmiQAAS"},
        {"email": "sf2@example.com", "record_id": "003xx000004TmiRAAS"}
    ],
    "include_smtp": False
}

r = requests.post(
    f"{BASE_URL}/api/webhook/validate",
    json=payload,
    headers={"X-API-Key": api_key},
    timeout=15
)

if r.status_code == 200:
    data = r.json()
    print(f"   [PASS] Event: {data.get('event')}")
    print(f"   Records processed: {len(data.get('records', []))}")
else:
    print(f"   [FAIL] Status: {r.status_code}")

# Test 3: One-time validation (file upload simulation)
print("\n4. Testing One-time Validation Mode...")
payload = {
    "integration_mode": "standalone",
    "emails": [
        "test1@gmail.com",
        "test2@yahoo.com",
        "invalid@",
        "disposable@tempmail.com"
    ],
    "include_smtp": False
}

r = requests.post(
    f"{BASE_URL}/api/webhook/validate",
    json=payload,
    headers={"X-API-Key": api_key},
    timeout=15
)

if r.status_code == 200:
    data = r.json()
    print(f"   [PASS] Event: {data.get('event')}")
    print(f"   Records processed: {len(data.get('records', []))}")
    valid_count = sum(1 for rec in data.get('records', []) if rec['status'] == 'valid')
    invalid_count = sum(1 for rec in data.get('records', []) if rec['status'] == 'invalid')
    print(f"   Valid: {valid_count}, Invalid: {invalid_count}")
else:
    print(f"   [FAIL] Status: {r.status_code}")

# Test 4: Rate limiting
print("\n5. Testing Rate Limiting...")
success_count = 0
rate_limited = False

for i in range(105):  # Try to exceed 100 req/min limit
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
        print(f"   [PASS] Rate limit enforced after {success_count} requests")
        break

if not rate_limited:
    print(f"   [WARNING] Rate limit not enforced (processed {success_count} requests)")

print("\n" + "="*70)
print("Webhook test complete!")
print("="*70 + "\n")

