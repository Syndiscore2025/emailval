"""Detailed CRM Integration Testing"""
import requests
import json

BASE_URL = "http://localhost:5000"

print("\n" + "="*80)
print("DETAILED CRM INTEGRATION TEST")
print("="*80 + "\n")

# Create API key
session = requests.Session()
session.post(
    f"{BASE_URL}/admin/login",
    json={"username": "admin", "password": "admin123"},
    timeout=5
)

r = session.post(
    f"{BASE_URL}/admin/api/keys",
    json={"name": "CRM Test Key", "rate_limit": 100},
    timeout=5
)
api_key = r.json().get("api_key")
print(f"✓ Created API Key: {api_key[:20]}...\n")

# Test 1: HubSpot CRM Integration
print("="*80)
print("TEST 1: HubSpot CRM Integration")
print("="*80)

hubspot_payload = {
    "integration_mode": "crm",
    "crm_vendor": "hubspot",
    "event_type": "contact.created",
    "crm_context": [
        {
            "email": "john.doe@company.com",
            "record_id": "hs_12345",
            "name": "John Doe",
            "company": "Acme Corp",
            "phone": "+1-555-0100"
        },
        {
            "email": "jane.smith@example.com",
            "record_id": "hs_67890",
            "name": "Jane Smith",
            "company": "Example Inc"
        },
        {
            "email": "invalid@",
            "record_id": "hs_11111",
            "name": "Invalid User"
        }
    ],
    "include_smtp": False
}

print("\nRequest Payload:")
print(json.dumps(hubspot_payload, indent=2))

r = requests.post(
    f"{BASE_URL}/api/webhook/validate",
    json=hubspot_payload,
    headers={"X-API-Key": api_key},
    timeout=15
)

print(f"\nResponse Status: {r.status_code}")
print("\nResponse Body:")
response_data = r.json()
print(json.dumps(response_data, indent=2))

# Verify response structure
print("\n" + "-"*80)
print("VERIFICATION:")
print("-"*80)
assert response_data.get('event') == 'validation.completed', "Event should be validation.completed"
print("✓ Event type correct")

assert response_data.get('integration_mode') == 'crm', "Integration mode should be crm"
print("✓ Integration mode correct")

assert response_data.get('crm_vendor') == 'hubspot', "CRM vendor should be hubspot"
print("✓ CRM vendor correct")

records = response_data.get('records', [])
assert len(records) == 3, f"Should have 3 records, got {len(records)}"
print(f"✓ Record count correct: {len(records)}")

# Check first record has CRM metadata
first_record = records[0]
assert 'crm_record_id' in first_record, "Record should have crm_record_id"
print(f"✓ CRM record ID present: {first_record.get('crm_record_id')}")

assert 'crm_metadata' in first_record, "Record should have crm_metadata"
print(f"✓ CRM metadata present: {list(first_record.get('crm_metadata', {}).keys())}")

# Check summary
summary = response_data.get('summary', {})
print(f"✓ Summary: {summary}")

# Test 2: Salesforce CRM Integration
print("\n" + "="*80)
print("TEST 2: Salesforce CRM Integration")
print("="*80)

salesforce_payload = {
    "integration_mode": "crm",
    "crm_vendor": "salesforce",
    "event_type": "contact.updated",
    "crm_context": [
        {
            "email": "contact1@salesforce-test.com",
            "record_id": "003xx000004TmiQAAS",
            "FirstName": "Alice",
            "LastName": "Johnson"
        },
        {
            "email": "contact2@salesforce-test.com",
            "record_id": "003xx000004TmiRAAS",
            "FirstName": "Bob",
            "LastName": "Williams"
        }
    ],
    "include_smtp": False
}

print("\nRequest Payload:")
print(json.dumps(salesforce_payload, indent=2))

r = requests.post(
    f"{BASE_URL}/api/webhook/validate",
    json=salesforce_payload,
    headers={"X-API-Key": api_key},
    timeout=15
)

print(f"\nResponse Status: {r.status_code}")
print("\nResponse Body:")
response_data = r.json()
print(json.dumps(response_data, indent=2))

print("\n" + "-"*80)
print("VERIFICATION:")
print("-"*80)
assert response_data.get('crm_vendor') == 'salesforce', "CRM vendor should be salesforce"
print("✓ CRM vendor correct")

records = response_data.get('records', [])
assert len(records) == 2, f"Should have 2 records, got {len(records)}"
print(f"✓ Record count correct: {len(records)}")

# Test 3: Standalone Mode (No CRM)
print("\n" + "="*80)
print("TEST 3: Standalone Mode (No CRM Context)")
print("="*80)

standalone_payload = {
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
    json=standalone_payload,
    headers={"X-API-Key": api_key},
    timeout=15
)

response_data = r.json()
print(f"\nResponse Status: {r.status_code}")
print(json.dumps(response_data, indent=2))

print("\n" + "="*80)
print("ALL CRM INTEGRATION TESTS PASSED! ✓")
print("="*80 + "\n")

