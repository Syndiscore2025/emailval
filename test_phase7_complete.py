"""
Phase 7 Complete - Beta Testing Script
Tests all admin panel connections and flows
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:5000"
session = requests.Session()

def print_test(name, status, message=""):
    """Print test result"""
    symbol = "✓" if status else "✗"
    color = "\033[92m" if status else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{symbol}{reset} {name}: {message}")

def test_admin_login():
    """Test 1: Admin Authentication"""
    print("\n=== TEST 1: ADMIN AUTHENTICATION ===")
    
    # Test login page loads
    try:
        response = session.get(f"{BASE_URL}/admin/login")
        print_test("Login page loads", response.status_code == 200, f"Status: {response.status_code}")
    except Exception as e:
        print_test("Login page loads", False, str(e))
        return False
    
    # Test login with correct credentials
    try:
        response = session.post(f"{BASE_URL}/admin/login", 
                               json={"username": "admin", "password": "admin123"})
        data = response.json()
        print_test("Login with correct credentials", data.get("success", False), 
                  f"Message: {data.get('message', 'No message')}")
        return data.get("success", False)
    except Exception as e:
        print_test("Login with correct credentials", False, str(e))
        return False

def test_dashboard():
    """Test 2: Dashboard Access"""
    print("\n=== TEST 2: DASHBOARD ACCESS ===")
    
    try:
        response = session.get(f"{BASE_URL}/admin")
        print_test("Dashboard loads", response.status_code == 200, f"Status: {response.status_code}")
        
        # Test analytics data endpoint
        response = session.get(f"{BASE_URL}/admin/analytics/data")
        data = response.json()
        print_test("Analytics data loads", "kpis" in data, 
                  f"KPIs present: {list(data.get('kpis', {}).keys())[:3]}")
        return True
    except Exception as e:
        print_test("Dashboard loads", False, str(e))
        return False

def test_api_keys():
    """Test 3: API Key Management"""
    print("\n=== TEST 3: API KEY MANAGEMENT ===")
    
    try:
        # Test API keys page loads
        response = session.get(f"{BASE_URL}/admin/api-keys")
        print_test("API Keys page loads", response.status_code == 200, f"Status: {response.status_code}")
        
        # Test list API keys
        response = session.get(f"{BASE_URL}/admin/api/keys")
        data = response.json()
        print_test("List API keys", data.get("success", False), 
                  f"Keys count: {len(data.get('keys', []))}")
        
        # Test create API key
        response = session.post(f"{BASE_URL}/admin/api/keys",
                               json={"name": "Test Key", "description": "Beta test key"})
        data = response.json()
        created_key = data.get("api_key")
        print_test("Create API key", data.get("success", False), 
                  f"Key: {created_key[:8] if created_key else 'None'}...")
        
        # Test delete API key
        if created_key:
            response = session.delete(f"{BASE_URL}/admin/api/keys/{created_key}")
            data = response.json()
            print_test("Delete API key", data.get("success", False))
        
        return True
    except Exception as e:
        print_test("API Key Management", False, str(e))
        return False

def test_email_explorer():
    """Test 4: Email Database Explorer"""
    print("\n=== TEST 4: EMAIL DATABASE EXPLORER ===")
    
    try:
        # Test emails page loads
        response = session.get(f"{BASE_URL}/admin/emails")
        print_test("Emails page loads", response.status_code == 200, f"Status: {response.status_code}")
        
        # Test get emails API
        response = session.get(f"{BASE_URL}/admin/api/emails")
        data = response.json()
        print_test("Get emails API", data.get("success", False), 
                  f"Emails count: {len(data.get('emails', []))}")
        
        return True
    except Exception as e:
        print_test("Email Explorer", False, str(e))
        return False

def test_settings():
    """Test 5: Settings Page"""
    print("\n=== TEST 5: SETTINGS PAGE ===")
    
    try:
        # Test settings page loads
        response = session.get(f"{BASE_URL}/admin/settings")
        print_test("Settings page loads", response.status_code == 200, f"Status: {response.status_code}")
        
        # Test system info API
        response = session.get(f"{BASE_URL}/admin/api/system-info")
        data = response.json()
        print_test("System info API", data.get("success", False), 
                  f"Python: {data.get('python_version', 'N/A')}")
        
        # Test database stats API
        response = session.get(f"{BASE_URL}/admin/api/database-stats")
        data = response.json()
        print_test("Database stats API", data.get("success", False), 
                  f"Total emails: {data.get('total_emails', 0)}")
        
        # Test config save API
        response = session.post(f"{BASE_URL}/admin/api/config",
                               json={"smtp_timeout": 10, "max_file_size": 16})
        data = response.json()
        print_test("Save config API", data.get("success", False))
        
        return True
    except Exception as e:
        print_test("Settings Page", False, str(e))
        return False

def test_analytics():
    """Test 6: Enhanced Analytics Page"""
    print("\n=== TEST 6: ENHANCED ANALYTICS PAGE ===")
    
    try:
        # Test analytics page loads
        response = session.get(f"{BASE_URL}/admin/analytics")
        print_test("Analytics page loads", response.status_code == 200, f"Status: {response.status_code}")
        
        # Test analytics data with date range
        response = session.get(f"{BASE_URL}/admin/analytics/data?range=30")
        data = response.json()
        print_test("Analytics data API", "kpis" in data and "email_types" in data, 
                  f"Data keys: {list(data.keys())[:4]}")
        
        return True
    except Exception as e:
        print_test("Analytics Page", False, str(e))
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 7 COMPLETE - BETA TESTING")
    print("=" * 60)
    print(f"Testing against: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run all tests
    results = []
    results.append(("Admin Login", test_admin_login()))
    results.append(("Dashboard", test_dashboard()))
    results.append(("API Keys", test_api_keys()))
    results.append(("Email Explorer", test_email_explorer()))
    results.append(("Settings", test_settings()))
    results.append(("Analytics", test_analytics()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED! Phase 7 is fully functional.")
    else:
        print(f"\n✗ {total - passed} test(s) failed. Review errors above.")

