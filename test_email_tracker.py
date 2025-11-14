"""
Test Email Tracker - Persistent Deduplication System
"""

import os
import json
from modules.email_tracker import EmailTracker

# Use a test database file
TEST_DB = 'data/test_email_history.json'

def cleanup_test_db():
    """Remove test database file"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def test_tracker_initialization():
    """Test tracker initialization"""
    print("\n" + "="*60)
    print("TEST 1: Tracker Initialization")
    print("="*60)
    
    cleanup_test_db()
    tracker = EmailTracker(db_file=TEST_DB)
    
    stats = tracker.get_stats()
    print(f"Initial Stats: {stats}")
    
    assert stats["total_unique_emails"] == 0
    assert stats["total_upload_sessions"] == 0
    print("✓ PASS: Tracker initialized correctly")

def test_check_duplicates_first_time():
    """Test checking duplicates on first upload"""
    print("\n" + "="*60)
    print("TEST 2: First Upload - No Duplicates")
    print("="*60)
    
    cleanup_test_db()
    tracker = EmailTracker(db_file=TEST_DB)
    
    emails = ['john@example.com', 'jane@example.com', 'bob@test.com']
    result = tracker.check_duplicates(emails)
    
    print(f"New emails: {result['new_count']}")
    print(f"Duplicates: {result['duplicate_count']}")
    print(f"New email list: {result['new_emails']}")
    
    assert result['new_count'] == 3
    assert result['duplicate_count'] == 0
    print("✓ PASS: First upload has no duplicates")

def test_track_emails():
    """Test tracking emails"""
    print("\n" + "="*60)
    print("TEST 3: Track Emails")
    print("="*60)
    
    cleanup_test_db()
    tracker = EmailTracker(db_file=TEST_DB)
    
    emails = ['john@example.com', 'jane@example.com', 'bob@test.com']
    session_info = {"filename": "contacts.csv"}
    
    result = tracker.track_emails(emails, session_info=session_info)
    
    print(f"New emails tracked: {result['new_emails_tracked']}")
    print(f"Total in database: {result['total_emails_in_database']}")
    
    assert result['new_emails_tracked'] == 3
    assert result['total_emails_in_database'] == 3
    print("✓ PASS: Emails tracked successfully")

def test_detect_duplicates_second_upload():
    """Test detecting duplicates on second upload"""
    print("\n" + "="*60)
    print("TEST 4: Second Upload - Detect Duplicates")
    print("="*60)
    
    cleanup_test_db()
    tracker = EmailTracker(db_file=TEST_DB)
    
    # First upload
    first_batch = ['john@example.com', 'jane@example.com', 'bob@test.com']
    tracker.track_emails(first_batch, session_info={"filename": "file1.csv"})
    
    # Second upload with some duplicates
    second_batch = ['john@example.com', 'alice@example.com', 'charlie@test.com']
    result = tracker.check_duplicates(second_batch)
    
    print(f"New emails: {result['new_count']}")
    print(f"Duplicates: {result['duplicate_count']}")
    print(f"New: {result['new_emails']}")
    print(f"Duplicates: {[d['email'] for d in result['duplicate_emails']]}")
    
    assert result['new_count'] == 2  # alice and charlie
    assert result['duplicate_count'] == 1  # john
    assert 'john@example.com' in [d['email'] for d in result['duplicate_emails']]
    print("✓ PASS: Duplicates detected correctly")

def test_track_with_validation_results():
    """Test tracking with validation results"""
    print("\n" + "="*60)
    print("TEST 5: Track with Validation Results")
    print("="*60)
    
    cleanup_test_db()
    tracker = EmailTracker(db_file=TEST_DB)
    
    emails = ['valid@gmail.com', 'invalid@fakefake.com']
    validation_results = [
        {'email': 'valid@gmail.com', 'valid': True},
        {'email': 'invalid@fakefake.com', 'valid': False}
    ]
    
    result = tracker.track_emails(emails, validation_results=validation_results)
    
    print(f"Tracked: {result['new_emails_tracked']}")
    
    # Check that validation status was saved
    assert tracker.data['emails']['valid@gmail.com']['validation_status'] == True
    assert tracker.data['emails']['invalid@fakefake.com']['validation_status'] == False
    print("✓ PASS: Validation results saved correctly")

def test_export_emails():
    """Test exporting tracked emails"""
    print("\n" + "="*60)
    print("TEST 6: Export Tracked Emails")
    print("="*60)
    
    cleanup_test_db()
    tracker = EmailTracker(db_file=TEST_DB)
    
    emails = ['valid@gmail.com', 'invalid@fakefake.com', 'another@test.com']
    validation_results = [
        {'email': 'valid@gmail.com', 'valid': True},
        {'email': 'invalid@fakefake.com', 'valid': False},
        {'email': 'another@test.com', 'valid': True}
    ]
    
    tracker.track_emails(emails, validation_results=validation_results)
    
    # Export all
    all_emails = tracker.export_emails(valid_only=False)
    print(f"All emails: {len(all_emails)}")
    
    # Export valid only
    valid_emails = tracker.export_emails(valid_only=True)
    print(f"Valid emails: {len(valid_emails)}")
    print(f"Valid list: {valid_emails}")
    
    assert len(all_emails) == 3
    assert len(valid_emails) == 2
    assert 'valid@gmail.com' in valid_emails
    assert 'another@test.com' in valid_emails
    assert 'invalid@fakefake.com' not in valid_emails
    print("✓ PASS: Export works correctly")

def test_persistence():
    """Test that data persists across tracker instances"""
    print("\n" + "="*60)
    print("TEST 7: Data Persistence")
    print("="*60)
    
    cleanup_test_db()
    
    # First tracker instance
    tracker1 = EmailTracker(db_file=TEST_DB)
    tracker1.track_emails(['test1@example.com', 'test2@example.com'])
    
    # Second tracker instance (simulates app restart)
    tracker2 = EmailTracker(db_file=TEST_DB)
    stats = tracker2.get_stats()
    
    print(f"Stats after reload: {stats}")
    
    assert stats['total_unique_emails'] == 2
    print("✓ PASS: Data persists correctly")

def test_large_scale():
    """Test with large number of emails"""
    print("\n" + "="*60)
    print("TEST 8: Large Scale (10,000 emails)")
    print("="*60)
    
    cleanup_test_db()
    tracker = EmailTracker(db_file=TEST_DB)
    
    # Generate 10,000 emails
    emails = [f'user{i}@example.com' for i in range(10000)]
    
    result = tracker.track_emails(emails)
    print(f"Tracked: {result['new_emails_tracked']}")
    print(f"Total in DB: {result['total_emails_in_database']}")
    
    # Upload again with 5,000 duplicates and 5,000 new
    second_batch = [f'user{i}@example.com' for i in range(5000, 15000)]
    dup_check = tracker.check_duplicates(second_batch)
    
    print(f"Second batch - New: {dup_check['new_count']}, Duplicates: {dup_check['duplicate_count']}")
    
    assert result['new_emails_tracked'] == 10000
    assert dup_check['new_count'] == 5000
    assert dup_check['duplicate_count'] == 5000
    print("✓ PASS: Large scale tracking works")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("EMAIL TRACKER - PERSISTENT DEDUPLICATION TESTS")
    print("="*60)
    
    test_tracker_initialization()
    test_check_duplicates_first_time()
    test_track_emails()
    test_detect_duplicates_second_upload()
    test_track_with_validation_results()
    test_export_emails()
    test_persistence()
    test_large_scale()
    
    # Cleanup
    cleanup_test_db()
    
    print("\n" + "="*60)
    print("ALL TESTS PASSED! ✓")
    print("="*60)

