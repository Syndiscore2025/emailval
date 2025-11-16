"""Test Production Performance on Render"""
import requests
import time

PRODUCTION_URL = "https://emailval-gpru.onrender.com"
API_KEY = "ev_23llvw5vc6yjOCE-U71AuZsbiJcUE3NGuatzucvaYNg"

print("\n" + "="*80)
print("PRODUCTION PERFORMANCE TEST")
print("="*80 + "\n")

# Test 1: Single email (no SMTP)
print("TEST 1: Single Email Validation (No SMTP)")
print("-"*80)
start = time.time()
r = requests.post(
    f"{PRODUCTION_URL}/api/webhook/validate",
    json={
        "integration_mode": "standalone",
        "emails": ["test@example.com"],
        "include_smtp": False
    },
    headers={"X-API-Key": API_KEY},
    timeout=30
)
elapsed = (time.time() - start) * 1000
print(f"Status: {r.status_code}")
print(f"Time: {elapsed:.0f}ms")
print(f"Result: {r.json()['summary']}\n")

# Test 2: Single email (WITH SMTP)
print("TEST 2: Single Email Validation (WITH SMTP)")
print("-"*80)
start = time.time()
r = requests.post(
    f"{PRODUCTION_URL}/api/webhook/validate",
    json={
        "integration_mode": "standalone",
        "emails": ["test@gmail.com"],
        "include_smtp": True
    },
    headers={"X-API-Key": API_KEY},
    timeout=60
)
elapsed = (time.time() - start) * 1000
print(f"Status: {r.status_code}")
print(f"Time: {elapsed:.0f}ms")
print(f"Result: {r.json()['summary']}\n")

# Test 3: 10 emails (WITH SMTP)
print("TEST 3: 10 Emails Validation (WITH SMTP)")
print("-"*80)
test_emails = [
    "test1@gmail.com",
    "test2@yahoo.com",
    "test3@outlook.com",
    "test4@hotmail.com",
    "test5@icloud.com",
    "invalid@",
    "test6@aol.com",
    "test7@protonmail.com",
    "test8@zoho.com",
    "test9@mail.com"
]
start = time.time()
r = requests.post(
    f"{PRODUCTION_URL}/api/webhook/validate",
    json={
        "integration_mode": "standalone",
        "emails": test_emails,
        "include_smtp": True
    },
    headers={"X-API-Key": API_KEY},
    timeout=120
)
elapsed = (time.time() - start) * 1000
print(f"Status: {r.status_code}")
print(f"Time: {elapsed:.0f}ms ({elapsed/1000:.1f}s)")
print(f"Result: {r.json()['summary']}")
print(f"Per email: {elapsed/len(test_emails):.0f}ms\n")

# Test 4: CRM webhook (WITH SMTP)
print("TEST 4: CRM Webhook (WITH SMTP)")
print("-"*80)
start = time.time()
r = requests.post(
    f"{PRODUCTION_URL}/api/webhook/validate",
    json={
        "integration_mode": "crm",
        "crm_vendor": "hubspot",
        "crm_context": [
            {
                "email": "contact@company.com",
                "record_id": "hs_12345",
                "name": "Test Contact",
                "company": "Test Company"
            }
        ],
        "include_smtp": True
    },
    headers={"X-API-Key": API_KEY},
    timeout=60
)
elapsed = (time.time() - start) * 1000
print(f"Status: {r.status_code}")
print(f"Time: {elapsed:.0f}ms")
print(f"Result: {r.json()['summary']}\n")

print("="*80)
print("PERFORMANCE SUMMARY")
print("="*80)
print("\nRender Starter Instance (0.5 CPU, 512 MB RAM)")
print("\nExpected Performance:")
print("- Single email (no SMTP): ~200-300ms")
print("- Single email (with SMTP): ~1-3 seconds")
print("- 10 emails (with SMTP): ~5-15 seconds")
print("- CRM webhook (with SMTP): ~1-3 seconds")
print("\nNote: SMTP validation depends on external mail servers")
print("      Response times may vary based on server availability")
print("="*80 + "\n")

