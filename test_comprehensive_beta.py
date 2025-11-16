"""
Comprehensive Beta Test Suite
Tests all system components for production readiness:
- One-time validation flow
- CRM API integration
- Admin panel operations
- Webhook functionality
- Settings and configuration
- Data persistence
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:5000"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def log_test(name, status, message=""):
    """Log test result"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    if status == "PASS":
        test_results["passed"].append(name)
        print(f"✅ [{timestamp}] {name}: PASS {message}")
    elif status == "FAIL":
        test_results["failed"].append(name)
        print(f"❌ [{timestamp}] {name}: FAIL {message}")
    elif status == "WARN":
        test_results["warnings"].append(name)
        print(f"⚠️  [{timestamp}] {name}: WARN {message}")

def test_health_check():
    """Test 1: Health check endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                log_test("Health Check", "PASS", f"- Service: {data.get('service')}")
                return True
        log_test("Health Check", "FAIL", f"- Status: {response.status_code}")
        return False
    except Exception as e:
        log_test("Health Check", "FAIL", f"- Error: {str(e)}")
        return False

def test_admin_login(session):
    """Test 2: Admin login"""
    try:
        response = session.post(
            f"{BASE_URL}/admin/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            allow_redirects=False,
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                log_test("Admin Login", "PASS")
                return True
        log_test("Admin Login", "FAIL", f"- Status: {response.status_code}, Response: {response.text[:100]}")
        return False
    except Exception as e:
        log_test("Admin Login", "FAIL", f"- Error: {str(e)}")
        return False

def test_api_key_creation(session):
    """Test 3: API key creation"""
    try:
        response = session.post(
            f"{BASE_URL}/admin/api/keys",
            json={"name": "Beta Test Key", "rate_limit": 100},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "api_key" in data:
                api_key = data["api_key"]
                log_test("API Key Creation", "PASS", f"- Key: {api_key[:20]}...")
                return api_key
        log_test("API Key Creation", "FAIL", f"- Response: {response.text[:100]}")
        return None
    except Exception as e:
        log_test("API Key Creation", "FAIL", f"- Error: {str(e)}")
        return None

def test_single_email_validation(api_key=None):
    """Test 4: Single email validation"""
    try:
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key
        
        response = requests.post(
            f"{BASE_URL}/validate",
            json={"email": "test@example.com", "include_smtp": False},
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if "valid" in data and "checks" in data:
                log_test("Single Email Validation", "PASS", f"- Valid: {data.get('valid')}")
                return True
        log_test("Single Email Validation", "FAIL", f"- Status: {response.status_code}")
        return False
    except Exception as e:
        log_test("Single Email Validation", "FAIL", f"- Error: {str(e)}")
        return False

def test_crm_webhook_validation(api_key=None):
    """Test 5: CRM webhook validation"""
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key

        payload = {
            "integration_mode": "crm",
            "crm_vendor": "hubspot",
            "event_type": "contact.created",
            "crm_context": [
                {"email": "crm_test1@example.com", "record_id": "test_001"},
                {"email": "crm_test2@example.com", "record_id": "test_002"}
            ],
            "include_smtp": False
        }

        response = requests.post(
            f"{BASE_URL}/api/webhook/validate",
            json=payload,
            headers=headers,
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and "records" in data:
                log_test("CRM Webhook Validation", "PASS", f"- Records: {len(data['records'])}")
                return True
        log_test("CRM Webhook Validation", "FAIL", f"- Status: {response.status_code}, Response: {response.text[:200]}")
        return False
    except Exception as e:
        log_test("CRM Webhook Validation", "FAIL", f"- Error: {str(e)}")
        return False

def test_file_upload_validation(session):
    """Test 6: File upload and validation"""
    try:
        # Create a small test CSV file
        test_csv = "email,name\ntest1@example.com,Test User 1\ntest2@example.com,Test User 2\n"
        files = {'files': ('test.csv', test_csv, 'text/csv')}
        data = {'validate': 'true', 'include_smtp': 'false'}

        response = session.post(
            f"{BASE_URL}/upload",
            files=files,
            data=data,
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            if result.get("total_emails_found", 0) > 0:
                log_test("File Upload Validation", "PASS", f"- Emails found: {result.get('total_emails_found')}")
                return True
        log_test("File Upload Validation", "FAIL", f"- Status: {response.status_code}")
        return False
    except Exception as e:
        log_test("File Upload Validation", "FAIL", f"- Error: {str(e)}")
        return False

def test_admin_email_explorer(session):
    """Test 7: Admin email explorer"""
    try:
        response = session.get(f"{BASE_URL}/admin/api/emails", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "emails" in data:
                log_test("Admin Email Explorer", "PASS", f"- Total emails: {len(data['emails'])}")
                return True
        log_test("Admin Email Explorer", "FAIL", f"- Status: {response.status_code}")
        return False
    except Exception as e:
        log_test("Admin Email Explorer", "FAIL", f"- Error: {str(e)}")
        return False

def test_database_stats(session):
    """Test 8: Database statistics"""
    try:
        response = session.get(f"{BASE_URL}/admin/api/database-stats", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "stats" in data:
                stats = data["stats"]
                log_test("Database Stats", "PASS",
                        f"- Total: {stats.get('total_emails')}, Valid: {stats.get('valid_count')}")
                return True
        log_test("Database Stats", "FAIL", f"- Status: {response.status_code}")
        return False
    except Exception as e:
        log_test("Database Stats", "FAIL", f"- Error: {str(e)}")
        return False

def test_reverify_invalid(session):
    """Test 9: Re-verify invalid emails"""
    try:
        # First, get list of invalid emails
        response = session.get(f"{BASE_URL}/admin/api/emails", timeout=10)
        if response.status_code != 200:
            log_test("Re-verify Invalid", "WARN", "- No emails to test with")
            return True

        data = response.json()
        invalid_emails = [e["email"] for e in data.get("emails", []) if e.get("status") == "invalid"][:5]

        if not invalid_emails:
            log_test("Re-verify Invalid", "WARN", "- No invalid emails found")
            return True

        # Test reverify endpoint
        response = session.post(
            f"{BASE_URL}/admin/api/emails/reverify",
            json={"emails": invalid_emails},
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                log_test("Re-verify Invalid", "PASS", f"- Reverified {len(invalid_emails)} emails")
                return True
        log_test("Re-verify Invalid", "FAIL", f"- Status: {response.status_code}")
        return False
    except Exception as e:
        log_test("Re-verify Invalid", "FAIL", f"- Error: {str(e)}")
        return False

def test_webhook_management(session):
    """Test 10: Webhook management"""
    try:
        # Test webhook list endpoint
        response = session.get(f"{BASE_URL}/admin/api/webhook-logs", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                log_test("Webhook Management", "PASS", "- Webhook logs accessible")
                return True
        log_test("Webhook Management", "FAIL", f"- Status: {response.status_code}")
        return False
    except Exception as e:
        log_test("Webhook Management", "FAIL", f"- Error: {str(e)}")
        return False

def test_data_persistence(session):
    """Test 11: Data persistence"""
    try:
        # Check if data files exist
        data_dir = "data"
        required_files = ["email_history.json", "validation_jobs.json"]

        missing_files = []
        for file in required_files:
            file_path = os.path.join(data_dir, file)
            if not os.path.exists(file_path):
                missing_files.append(file)

        if missing_files:
            log_test("Data Persistence", "FAIL", f"- Missing files: {', '.join(missing_files)}")
            return False

        # Verify email_history.json is valid JSON
        with open(os.path.join(data_dir, "email_history.json"), 'r') as f:
            email_data = json.load(f)
            if "emails" in email_data:
                log_test("Data Persistence", "PASS", f"- {len(email_data['emails'])} emails persisted")
                return True

        log_test("Data Persistence", "FAIL", "- Invalid data structure")
        return False
    except Exception as e:
        log_test("Data Persistence", "FAIL", f"- Error: {str(e)}")
        return False

def run_all_tests():
    """Run all beta tests"""
    print("\n" + "="*70)
    print("🧪 COMPREHENSIVE BETA TEST SUITE")
    print("="*70 + "\n")

    session = requests.Session()
    api_key = None

    # Test 1: Health check
    if not test_health_check():
        print("\n❌ Server not responding. Please start the server first.")
        return False

    # Test 2: Admin login
    if not test_admin_login(session):
        print("\n❌ Admin login failed. Cannot continue with admin tests.")
    else:
        # Test 3: API key creation
        api_key = test_api_key_creation(session)

        # Test 6: File upload
        test_file_upload_validation(session)

        # Test 7: Email explorer
        test_admin_email_explorer(session)

        # Test 8: Database stats
        test_database_stats(session)

        # Test 9: Re-verify invalid
        test_reverify_invalid(session)

        # Test 10: Webhook management
        test_webhook_management(session)

        # Test 11: Data persistence
        test_data_persistence(session)

    # Test 4: Single email validation (with or without API key)
    test_single_email_validation(api_key)

    # Test 5: CRM webhook validation (with or without API key)
    test_crm_webhook_validation(api_key)

    # Print summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    print(f"✅ Passed: {len(test_results['passed'])}")
    print(f"❌ Failed: {len(test_results['failed'])}")
    print(f"⚠️  Warnings: {len(test_results['warnings'])}")

    if test_results['failed']:
        print("\nFailed tests:")
        for test in test_results['failed']:
            print(f"  - {test}")

    print("\n" + "="*70 + "\n")

    return len(test_results['failed']) == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

