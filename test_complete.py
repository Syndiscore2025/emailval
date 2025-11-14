"""
Complete integration test for email validation system
"""
import json
from app import app, validate_email_complete


def test_complete_validation():
    """Test complete email validation flow"""
    
    print("Testing Complete Email Validation")
    print("=" * 50)
    
    test_emails = [
        "test@gmail.com",
        "invalid@thisisnotarealdomainthatexists12345.com",
        "info@google.com",
        "temp@mailinator.com",
        "notanemail",
    ]
    
    for email in test_emails:
        print(f"\nValidating: {email}")
        print("-" * 50)
        
        result = validate_email_complete(email, include_smtp=False)
        
        print(f"Valid: {result['valid']}")
        print(f"Syntax: {result['checks']['syntax']['valid']}")
        print(f"Domain: {result['checks']['domain']['valid']}")
        print(f"Type: {result['checks']['type']['email_type']}")
        
        if result['errors']:
            print(f"Errors: {', '.join(result['errors'][:3])}")
    
    print("\n" + "=" * 50)


def test_api_endpoints():
    """Test Flask API endpoints"""
    
    print("\nTesting API Endpoints")
    print("=" * 50)
    
    with app.test_client() as client:
        # Test health endpoint
        print("\n1. Testing /health endpoint")
        response = client.get('/health')
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.get_json()}")
        
        # Test single validation endpoint
        print("\n2. Testing /validate endpoint")
        response = client.post('/validate',
                              json={'email': 'test@gmail.com'},
                              content_type='application/json')
        print(f"   Status: {response.status_code}")
        data = response.get_json()
        print(f"   Valid: {data.get('valid')}")
        print(f"   Email: {data.get('email')}")
        
        # Test validation with invalid email
        print("\n3. Testing /validate with invalid email")
        response = client.post('/validate',
                              json={'email': 'notanemail'},
                              content_type='application/json')
        print(f"   Status: {response.status_code}")
        data = response.get_json()
        print(f"   Valid: {data.get('valid')}")
        
        # Test webhook endpoint
        print("\n4. Testing /api/webhook/validate endpoint")
        response = client.post('/api/webhook/validate',
                              json={'emails': ['test@gmail.com', 'test@yahoo.com']},
                              content_type='application/json')
        print(f"   Status: {response.status_code}")
        data = response.get_json()
        print(f"   Summary: {data.get('summary')}")
        
        # Test webhook with nested contact
        print("\n5. Testing /api/webhook/validate with nested contact")
        response = client.post('/api/webhook/validate',
                              json={'contact': {'email': 'test@example.com'}},
                              content_type='application/json')
        print(f"   Status: {response.status_code}")
        data = response.get_json()
        print(f"   Results count: {len(data.get('results', []))}")
        
        # Test missing email
        print("\n6. Testing /validate with missing email")
        response = client.post('/validate',
                              json={},
                              content_type='application/json')
        print(f"   Status: {response.status_code}")
        print(f"   Error: {response.get_json().get('error')}")
    
    print("\n" + "=" * 50)


def test_file_upload():
    """Test file upload endpoint"""
    
    print("\nTesting File Upload")
    print("=" * 50)
    
    # Create a test CSV file
    csv_content = b"""Email,Name
test@example.com,John Doe
test2@example.com,Jane Smith
test3@example.com,Bob Johnson"""
    
    with app.test_client() as client:
        print("\n1. Testing CSV upload")
        response = client.post('/upload',
                              data={'file': (csv_content, 'test.csv'),
                                    'validate': 'false'},
                              content_type='multipart/form-data')
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.get_json()
            print(f"   Emails found: {data.get('file_info', {}).get('emails_found')}")
            print(f"   File type: {data.get('file_info', {}).get('file_type')}")
        else:
            print(f"   Error: {response.get_json()}")
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    print("=" * 50)
    print("UNIVERSAL EMAIL VALIDATOR - INTEGRATION TESTS")
    print("=" * 50)
    
    test_complete_validation()
    test_api_endpoints()
    test_file_upload()
    
    print("\n" + "=" * 50)
    print("All tests completed!")
    print("=" * 50)

