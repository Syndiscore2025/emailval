"""
Integration Test - Email Deduplication for Marketing Campaigns
Tests the complete flow of preventing duplicate email sends across multiple uploads
"""

import os
import json
import tempfile
from app import app
from modules.email_tracker import EmailTracker

# Use test database
TEST_DB = 'data/test_integration_history.json'

def cleanup():
    """Clean up test files"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def create_test_csv(filename, emails):
    """Create a test CSV file"""
    with open(filename, 'w') as f:
        f.write('Email,Name\n')
        for i, email in enumerate(emails):
            f.write(f'{email},User{i}\n')

def test_first_upload_no_duplicates():
    """Test first upload - should have no duplicates"""
    print("\n" + "="*70)
    print("TEST 1: First Upload - No Duplicates Expected")
    print("="*70)
    
    cleanup()
    
    # Override tracker to use test database
    from modules import email_tracker
    email_tracker._tracker = EmailTracker(db_file=TEST_DB)
    
    client = app.test_client()
    
    # Create test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write('Email\n')
        f.write('john@example.com\n')
        f.write('jane@example.com\n')
        f.write('bob@test.com\n')
        temp_file = f.name
    
    try:
        # Upload file
        with open(temp_file, 'rb') as f:
            response = client.post('/upload', data={
                'files[]': (f, 'contacts.csv'),
                'validate': 'false'
            }, content_type='multipart/form-data')
        
        data = json.loads(response.data)
        
        print(f"Total emails found: {data['total_emails_found']}")
        print(f"New emails: {data['new_emails_count']}")
        print(f"Duplicates: {data['duplicate_emails_count']}")
        
        assert data['new_emails_count'] == 3
        assert data['duplicate_emails_count'] == 0
        print("✓ PASS: First upload has no duplicates")
        
    finally:
        os.unlink(temp_file)

def test_second_upload_with_duplicates():
    """Test second upload - should detect duplicates from first upload"""
    print("\n" + "="*70)
    print("TEST 2: Second Upload - Duplicates Should Be Detected")
    print("="*70)
    
    # Don't cleanup - use data from previous test
    from modules import email_tracker
    email_tracker._tracker = EmailTracker(db_file=TEST_DB)
    
    client = app.test_client()
    
    # Create test file with some duplicates
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write('Email\n')
        f.write('john@example.com\n')  # DUPLICATE
        f.write('alice@example.com\n')  # NEW
        f.write('charlie@test.com\n')  # NEW
        temp_file = f.name
    
    try:
        # Upload file
        with open(temp_file, 'rb') as f:
            response = client.post('/upload', data={
                'files[]': (f, 'contacts2.csv'),
                'validate': 'false'
            }, content_type='multipart/form-data')
        
        data = json.loads(response.data)
        
        print(f"Total emails found: {data['total_emails_found']}")
        print(f"New emails: {data['new_emails_count']}")
        print(f"Duplicates: {data['duplicate_emails_count']}")
        print(f"Duplicate list: {data.get('duplicate_emails', [])}")
        
        assert data['new_emails_count'] == 2  # alice and charlie
        assert data['duplicate_emails_count'] == 1  # john
        assert 'john@example.com' in data.get('duplicate_emails', [])
        print("✓ PASS: Duplicates detected correctly")
        
    finally:
        os.unlink(temp_file)

def test_multi_file_upload_with_duplicates():
    """Test uploading multiple files at once with cross-file duplicates"""
    print("\n" + "="*70)
    print("TEST 3: Multi-File Upload with Cross-File Duplicates")
    print("="*70)
    
    from modules import email_tracker
    email_tracker._tracker = EmailTracker(db_file=TEST_DB)
    
    client = app.test_client()
    
    # Create multiple test files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f1:
        f1.write('Email\n')
        f1.write('new1@example.com\n')
        f1.write('new2@example.com\n')
        temp_file1 = f1.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f2:
        f2.write('Email\n')
        f2.write('new3@example.com\n')
        f2.write('john@example.com\n')  # DUPLICATE from first test
        temp_file2 = f2.name
    
    try:
        # Upload both files
        with open(temp_file1, 'rb') as f1, open(temp_file2, 'rb') as f2:
            response = client.post('/upload', data={
                'files[]': [(f1, 'file1.csv'), (f2, 'file2.csv')],
                'validate': 'false'
            }, content_type='multipart/form-data')
        
        data = json.loads(response.data)
        
        print(f"Files processed: {data['files_processed']}")
        print(f"Total emails found: {data['total_emails_found']}")
        print(f"New emails: {data['new_emails_count']}")
        print(f"Duplicates: {data['duplicate_emails_count']}")
        
        assert data['files_processed'] == 2
        assert data['new_emails_count'] == 3  # new1, new2, new3
        assert data['duplicate_emails_count'] == 1  # john
        print("✓ PASS: Multi-file duplicates detected correctly")
        
    finally:
        os.unlink(temp_file1)
        os.unlink(temp_file2)

def test_tracker_stats_endpoint():
    """Test the tracker stats endpoint"""
    print("\n" + "="*70)
    print("TEST 4: Tracker Stats Endpoint")
    print("="*70)
    
    from modules import email_tracker
    email_tracker._tracker = EmailTracker(db_file=TEST_DB)
    
    client = app.test_client()
    
    response = client.get('/tracker/stats')
    data = json.loads(response.data)
    
    print(f"Success: {data['success']}")
    print(f"Stats: {data['stats']}")
    
    assert data['success'] == True
    assert data['stats']['total_unique_emails'] > 0
    print("✓ PASS: Tracker stats endpoint works")

def test_tracker_export_endpoint():
    """Test the tracker export endpoint"""
    print("\n" + "="*70)
    print("TEST 5: Tracker Export Endpoint")
    print("="*70)
    
    from modules import email_tracker
    email_tracker._tracker = EmailTracker(db_file=TEST_DB)
    
    client = app.test_client()
    
    # Export as CSV
    response = client.get('/tracker/export?format=csv')
    
    print(f"Response status: {response.status_code}")
    print(f"Content type: {response.content_type}")
    
    assert response.status_code == 200
    assert 'text/csv' in response.content_type
    
    # Check CSV content
    csv_content = response.data.decode('utf-8')
    lines = csv_content.strip().split('\n')
    print(f"CSV lines: {len(lines)}")
    print(f"First few lines:\n{chr(10).join(lines[:5])}")
    
    assert 'Email' in lines[0]  # Header
    assert len(lines) > 1  # Has data
    print("✓ PASS: Tracker export works")

if __name__ == '__main__':
    print("\n" + "="*70)
    print("INTEGRATION TEST - EMAIL DEDUPLICATION FOR MARKETING")
    print("="*70)
    
    test_first_upload_no_duplicates()
    test_second_upload_with_duplicates()
    test_multi_file_upload_with_duplicates()
    test_tracker_stats_endpoint()
    test_tracker_export_endpoint()
    
    # Cleanup
    cleanup()
    
    print("\n" + "="*70)
    print("ALL INTEGRATION TESTS PASSED! ✓")
    print("="*70)
    print("\nThe email deduplication system is working correctly!")
    print("Marketing campaigns can now safely upload multiple files without")
    print("worrying about sending duplicate emails to the same contacts.")
    print("="*70)

