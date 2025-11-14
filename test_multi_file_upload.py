"""
Test Multi-File Upload and Large-Scale Email Processing
"""

import io
import csv
from app import app

def create_csv_file(emails, filename="test.csv"):
    """Create a CSV file in memory with emails"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Email', 'Name', 'Company'])
    
    for i, email in enumerate(emails):
        writer.writerow([email, f'User {i+1}', f'Company {i+1}'])
    
    output.seek(0)
    return (io.BytesIO(output.getvalue().encode('utf-8')), filename)

def test_single_file_upload():
    """Test single file upload (backward compatibility)"""
    print("\n" + "="*60)
    print("TEST 1: Single File Upload (Backward Compatibility)")
    print("="*60)
    
    emails = [
        'john@example.com',
        'jane@example.com',
        'bob@test.com'
    ]
    
    with app.test_client() as client:
        data = {
            'file': create_csv_file(emails, 'contacts.csv'),
            'validate': 'true'
        }
        
        response = client.post('/upload', data=data, content_type='multipart/form-data')
        result = response.get_json()
        
        print(f"Status Code: {response.status_code}")
        print(f"Files Processed: {result.get('files_processed', 0)}")
        print(f"Total Emails Found: {result.get('total_emails_found', 0)}")
        print(f"Validation Summary: {result.get('validation_summary', {})}")
        
        assert response.status_code == 200
        assert result['total_emails_found'] == 3
        print("✓ PASS: Single file upload works")

def test_multi_file_upload():
    """Test multiple file upload"""
    print("\n" + "="*60)
    print("TEST 2: Multi-File Upload")
    print("="*60)
    
    file1_emails = ['user1@example.com', 'user2@example.com']
    file2_emails = ['user3@test.com', 'user4@test.com', 'user5@test.com']
    file3_emails = ['admin@company.com']
    
    with app.test_client() as client:
        data = {
            'files[]': [
                create_csv_file(file1_emails, 'file1.csv'),
                create_csv_file(file2_emails, 'file2.csv'),
                create_csv_file(file3_emails, 'file3.csv')
            ],
            'validate': 'true'
        }
        
        response = client.post('/upload', data=data, content_type='multipart/form-data')
        result = response.get_json()
        
        print(f"Status Code: {response.status_code}")
        print(f"Files Processed: {result.get('files_processed', 0)}")
        print(f"Total Emails Found: {result.get('total_emails_found', 0)}")
        print(f"File Results:")
        for file_info in result.get('file_results', []):
            print(f"  - {file_info['filename']}: {file_info['emails_found']} emails")
        print(f"Validation Summary: {result.get('validation_summary', {})}")
        
        assert response.status_code == 200
        assert result['files_processed'] == 3
        assert result['total_emails_found'] == 6
        print("✓ PASS: Multi-file upload works")

def test_large_dataset():
    """Test handling of large dataset (10,000 emails)"""
    print("\n" + "="*60)
    print("TEST 3: Large Dataset (10,000 emails)")
    print("="*60)
    
    # Generate 10,000 emails
    emails = [f'user{i}@example.com' for i in range(10000)]
    
    with app.test_client() as client:
        data = {
            'files[]': [create_csv_file(emails, 'large_dataset.csv')],
            'validate': 'true',
            'batch_size': '1000'
        }
        
        response = client.post('/upload', data=data, content_type='multipart/form-data')
        result = response.get_json()
        
        print(f"Status Code: {response.status_code}")
        print(f"Total Emails Found: {result.get('total_emails_found', 0)}")
        print(f"Validation Summary: {result.get('validation_summary', {})}")
        print(f"Full Results Count: {result.get('full_results_count', 0)}")
        print(f"Preview Results Returned: {len(result.get('validation_results', []))}")
        
        assert response.status_code == 200
        assert result['total_emails_found'] == 10000
        assert result['full_results_count'] == 10000
        assert len(result['validation_results']) == 100  # Only first 100 returned
        print("✓ PASS: Large dataset handling works")

def test_deduplication():
    """Test email deduplication across multiple files"""
    print("\n" + "="*60)
    print("TEST 4: Email Deduplication Across Files")
    print("="*60)
    
    # Same emails in different files
    file1_emails = ['john@example.com', 'jane@example.com', 'bob@test.com']
    file2_emails = ['john@example.com', 'alice@example.com']  # john is duplicate
    file3_emails = ['bob@test.com', 'charlie@example.com']  # bob is duplicate
    
    with app.test_client() as client:
        data = {
            'files[]': [
                create_csv_file(file1_emails, 'file1.csv'),
                create_csv_file(file2_emails, 'file2.csv'),
                create_csv_file(file3_emails, 'file3.csv')
            ],
            'validate': 'false'
        }
        
        response = client.post('/upload', data=data, content_type='multipart/form-data')
        result = response.get_json()
        
        print(f"Status Code: {response.status_code}")
        print(f"Files Processed: {result.get('files_processed', 0)}")
        print(f"Total Unique Emails: {result.get('total_unique_emails', 0)}")
        print(f"All Emails (preview): {result.get('all_emails', [])}")
        
        assert response.status_code == 200
        assert result['files_processed'] == 3
        # 3 + 2 + 2 = 7 total, but 2 duplicates, so 5 unique
        assert result['total_unique_emails'] == 5
        print("✓ PASS: Deduplication works correctly")

def test_export_endpoint():
    """Test CSV export functionality"""
    print("\n" + "="*60)
    print("TEST 5: CSV Export Endpoint")
    print("="*60)
    
    validation_results = [
        {
            'email': 'test@gmail.com',
            'valid': True,
            'checks': {
                'syntax': {'valid': True},
                'domain': {'valid': True},
                'type': {
                    'email_type': 'personal',
                    'is_disposable': False,
                    'is_role_based': False
                }
            },
            'errors': []
        },
        {
            'email': 'invalid@fakefakefake.com',
            'valid': False,
            'checks': {
                'syntax': {'valid': True},
                'domain': {'valid': False},
                'type': {
                    'email_type': 'unknown',
                    'is_disposable': False,
                    'is_role_based': False
                }
            },
            'errors': ['Domain does not exist']
        }
    ]
    
    with app.test_client() as client:
        response = client.post('/export', 
                              json={'results': validation_results, 'format': 'csv'},
                              content_type='application/json')
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print(f"Content-Disposition: {response.headers.get('Content-Disposition')}")
        
        assert response.status_code == 200
        assert 'text/csv' in response.headers.get('Content-Type', '')
        assert 'attachment' in response.headers.get('Content-Disposition', '')
        
        # Check CSV content
        csv_content = response.data.decode('utf-8')
        print(f"\nCSV Content (first 200 chars):\n{csv_content[:200]}")
        
        assert 'Email' in csv_content
        assert 'test@gmail.com' in csv_content
        print("✓ PASS: CSV export works")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("MULTI-FILE UPLOAD & LARGE-SCALE PROCESSING TESTS")
    print("="*60)
    
    test_single_file_upload()
    test_multi_file_upload()
    test_large_dataset()
    test_deduplication()
    test_export_endpoint()
    
    print("\n" + "="*60)
    print("ALL TESTS PASSED! ✓")
    print("="*60)

