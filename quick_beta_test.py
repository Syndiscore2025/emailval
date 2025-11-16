"""Quick beta test - simplified version"""
import requests
import json
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:5000"

print("\n" + "="*70)
print("QUICK BETA TEST")
print("="*70 + "\n")

# Test 1: Health Check
print("1. Testing Health Check...")
try:
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    if r.status_code == 200:
        print("   [PASS] Server is healthy")
    else:
        print(f"   [FAIL] Status: {r.status_code}")
except Exception as e:
    print(f"   [FAIL] {e}")

# Test 2: Single Email Validation
print("\n2. Testing Single Email Validation...")
try:
    r = requests.post(
        f"{BASE_URL}/validate",
        json={"email": "test@example.com", "include_smtp": False},
        timeout=10
    )
    if r.status_code == 200:
        data = r.json()
        print(f"   [PASS] Valid: {data.get('valid')}, Checks: {len(data.get('checks', {}))}")
    else:
        print(f"   [FAIL] Status: {r.status_code}")
except Exception as e:
    print(f"   [FAIL] {e}")

# Test 3: Admin Login
print("\n3. Testing Admin Login...")
session = requests.Session()
try:
    r = session.post(
        f"{BASE_URL}/admin/login",
        json={"username": "admin", "password": "admin123"},
        timeout=5
    )
    if r.status_code == 200 and r.json().get("success"):
        print("   [PASS] Admin login successful")

        # Test 4: API Key Creation
        print("\n4. Testing API Key Creation...")
        r = session.post(
            f"{BASE_URL}/admin/api/keys",
            json={"name": "Test Key", "rate_limit": 100},
            timeout=5
        )
        if r.status_code == 200 and r.json().get("success"):
            api_key = r.json().get("api_key")
            print(f"   [PASS] API Key created: {api_key[:20]}...")

            # Test 5: CRM Webhook with API Key
            print("\n5. Testing CRM Webhook Validation...")
            r = requests.post(
                f"{BASE_URL}/api/webhook/validate",
                json={
                    "integration_mode": "crm",
                    "crm_vendor": "hubspot",
                    "crm_context": [
                        {"email": "test1@example.com", "record_id": "001"},
                        {"email": "test2@example.com", "record_id": "002"}
                    ],
                    "include_smtp": False
                },
                headers={"X-API-Key": api_key},
                timeout=15
            )
            if r.status_code == 200:
                data = r.json()
                print(f"   [PASS] Records validated: {len(data.get('records', []))}")
            else:
                print(f"   [FAIL] Status: {r.status_code}, Response: {r.text[:100]}")
        else:
            print(f"   [FAIL] Status: {r.status_code}")

        # Test 6: Email Explorer
        print("\n6. Testing Admin Email Explorer...")
        r = session.get(f"{BASE_URL}/admin/api/emails", timeout=10)
        if r.status_code == 200:
            data = r.json()
            print(f"   [PASS] Total emails: {len(data.get('emails', []))}")
        else:
            print(f"   [FAIL] Status: {r.status_code}")

        # Test 7: Database Stats
        print("\n7. Testing Database Stats...")
        r = session.get(f"{BASE_URL}/admin/api/database-stats", timeout=10)
        if r.status_code == 200:
            data = r.json()
            print(f"   [PASS] Total: {data.get('total_emails')}, Sessions: {data.get('total_sessions')}, Size: {data.get('database_size')}")
        else:
            print(f"   [FAIL] Status: {r.status_code}")

    else:
        print(f"   [FAIL] Status: {r.status_code}")
except Exception as e:
    print(f"   [FAIL] {e}")

# Test 8: Data Persistence
print("\n8. Testing Data Persistence...")
try:
    import os
    data_files = ["data/email_history.json", "data/validation_jobs.json"]
    all_exist = all(os.path.exists(f) for f in data_files)
    if all_exist:
        with open("data/email_history.json", 'r') as f:
            email_data = json.load(f)
            print(f"   [PASS] {len(email_data.get('emails', {}))} emails persisted")
    else:
        print("   [FAIL] Missing data files")
except Exception as e:
    print(f"   [FAIL] {e}")

print("\n" + "="*70)
print("Beta test complete!")
print("="*70 + "\n")

