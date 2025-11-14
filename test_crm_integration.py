"""
Test CRM Integration Features (Phase 3.3)
"""
import sys
import json
from app import app


def test_crm_integration():
    """Test CRM integration mode with crm_context"""
    print("\n" + "="*60)
    print("Testing CRM Integration Features")
    print("="*60)
    
    client = app.test_client()
    
    # Test 1: CRM mode with custom vendor
    print("\n1. Testing CRM mode with custom vendor and crm_context")
    payload = {
        "integration_mode": "crm",
        "crm_vendor": "custom",
        "crm_context": [
            {
                "record_id": "LEAD-12345",
                "email": "john.doe@example.com",
                "list_id": "prospects-2025-q1",
                "campaign": "cold-outreach"
            },
            {
                "record_id": "LEAD-67890",
                "email": "jane.smith@gmail.com",
                "list_id": "prospects-2025-q1"
            }
        ],
        "include_smtp": False
    }
    
    response = client.post(
        '/api/webhook/validate',
        data=json.dumps(payload),
        content_type='application/json'
    )
    
    print(f"   Status: {response.status_code}")
    data = response.get_json()
    print(f"   Event: {data.get('event')}")
    print(f"   Integration Mode: {data.get('integration_mode')}")
    print(f"   CRM Vendor: {data.get('crm_vendor')}")
    print(f"   Summary: {data.get('summary')}")
    
    # Check that records have CRM metadata
    if 'records' in data:
        print(f"   Records count: {len(data['records'])}")
        for i, record in enumerate(data['records'][:2]):
            print(f"   Record {i+1}:")
            print(f"     - Email: {record.get('email')}")
            print(f"     - Status: {record.get('status')}")
            print(f"     - CRM Record ID: {record.get('crm_record_id')}")
            if 'crm_metadata' in record:
                print(f"     - CRM Metadata: {record.get('crm_metadata')}")
    
    assert response.status_code == 200
    assert data['integration_mode'] == 'crm'
    assert data['crm_vendor'] == 'custom'
    assert data['event'] == 'validation.completed'
    assert len(data['records']) == 2
    assert data['records'][0]['crm_record_id'] == 'LEAD-12345'
    assert data['records'][1]['crm_record_id'] == 'LEAD-67890'
    print("   ✓ CRM integration test passed")
    
    # Test 2: Salesforce vendor
    print("\n2. Testing Salesforce vendor")
    payload = {
        "integration_mode": "crm",
        "crm_vendor": "salesforce",
        "crm_context": [
            {
                "record_id": "003xx000004TmiQAAS",
                "email": "contact@salesforce-test.com"
            }
        ]
    }
    
    response = client.post(
        '/api/webhook/validate',
        data=json.dumps(payload),
        content_type='application/json'
    )
    
    data = response.get_json()
    print(f"   Status: {response.status_code}")
    print(f"   CRM Vendor: {data.get('crm_vendor')}")
    assert data['crm_vendor'] == 'salesforce'
    print("   ✓ Salesforce vendor test passed")
    
    # Test 3: HubSpot vendor
    print("\n3. Testing HubSpot vendor")
    payload = {
        "integration_mode": "crm",
        "crm_vendor": "hubspot",
        "crm_context": [
            {
                "record_id": "12345",
                "email": "contact@hubspot-test.com"
            }
        ]
    }
    
    response = client.post(
        '/api/webhook/validate',
        data=json.dumps(payload),
        content_type='application/json'
    )
    
    data = response.get_json()
    print(f"   Status: {response.status_code}")
    print(f"   CRM Vendor: {data.get('crm_vendor')}")
    assert data['crm_vendor'] == 'hubspot'
    print("   ✓ HubSpot vendor test passed")
    
    # Test 4: Async callback with CRM mode
    print("\n4. Testing async callback with CRM mode")
    payload = {
        "integration_mode": "crm",
        "crm_vendor": "custom",
        "crm_context": [
            {
                "record_id": "CONTACT-999",
                "email": "async@example.com"
            }
        ],
        "callback_url": "https://my-crm.example.com/webhooks/validation"
    }
    
    response = client.post(
        '/api/webhook/validate',
        data=json.dumps(payload),
        content_type='application/json'
    )
    
    data = response.get_json()
    print(f"   Status: {response.status_code}")
    print(f"   Response: {data}")
    assert response.status_code == 202
    assert data['status'] == 'accepted'
    assert 'job_id' in data
    assert data['integration_mode'] == 'crm'
    assert data['crm_vendor'] == 'custom'
    print("   ✓ Async callback test passed")
    
    print("\n" + "="*60)
    print("All CRM integration tests passed! ✓")
    print("="*60)


if __name__ == '__main__':
    test_crm_integration()

