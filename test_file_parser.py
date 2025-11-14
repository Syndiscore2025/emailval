"""
Test script for file parser module
"""
import os
from modules.file_parser import parse_csv, parse_file


def test_csv_parsing():
    """Test CSV file parsing"""
    
    print("Testing CSV File Parser")
    print("=" * 50)
    
    # Test case 1: CSV with email column header
    csv_content_1 = """Name,Email,Phone
John Doe,john@example.com,555-1234
Jane Smith,jane@example.com,555-5678
Bob Johnson,bob@test.com,555-9012"""
    
    result = parse_csv(csv_content_1)
    print(f"Test 1 - CSV with 'Email' header:")
    print(f"  Emails found: {result['count']}")
    print(f"  Emails: {result['emails']}")
    print(f"  Expected: 3 emails")
    print(f"  Status: {'✓ PASS' if result['count'] == 3 else '✗ FAIL'}")
    
    # Test case 2: CSV without clear header
    csv_content_2 = """john@example.com
jane@example.com
bob@test.com"""
    
    result = parse_csv(csv_content_2)
    print(f"\nTest 2 - CSV without headers:")
    print(f"  Emails found: {result['count']}")
    print(f"  Emails: {result['emails']}")
    print(f"  Expected: 3 emails")
    print(f"  Status: {'✓ PASS' if result['count'] == 3 else '✗ FAIL'}")
    
    # Test case 3: CSV with mixed content
    csv_content_3 = """Contact,Info,Notes
Alice,alice@example.com,VIP customer
Bob,bob@test.com,New lead
Charlie,charlie@demo.com,Follow up"""
    
    result = parse_csv(csv_content_3)
    print(f"\nTest 3 - CSV with mixed content:")
    print(f"  Emails found: {result['count']}")
    print(f"  Emails: {result['emails']}")
    print(f"  Expected: 3 emails")
    print(f"  Status: {'✓ PASS' if result['count'] == 3 else '✗ FAIL'}")
    
    # Test case 4: CSV with duplicates
    csv_content_4 = """Email
john@example.com
jane@example.com
john@example.com
jane@example.com"""
    
    result = parse_csv(csv_content_4)
    print(f"\nTest 4 - CSV with duplicates:")
    print(f"  Emails found: {result['count']}")
    print(f"  Emails: {result['emails']}")
    print(f"  Expected: 2 unique emails")
    print(f"  Status: {'✓ PASS' if result['count'] == 2 else '✗ FAIL'}")
    
    # Test case 5: Different delimiter (semicolon)
    csv_content_5 = """Name;Email;Phone
John;john@example.com;555-1234
Jane;jane@example.com;555-5678"""
    
    result = parse_csv(csv_content_5)
    print(f"\nTest 5 - CSV with semicolon delimiter:")
    print(f"  Emails found: {result['count']}")
    print(f"  Emails: {result['emails']}")
    print(f"  Expected: 2 emails")
    print(f"  Status: {'✓ PASS' if result['count'] == 2 else '✗ FAIL'}")
    
    print("\n" + "=" * 50)


def test_email_extraction():
    """Test email extraction from various formats"""
    
    print("\nTesting Email Extraction from Text")
    print("=" * 50)
    
    from modules.file_parser import extract_emails_from_text
    
    text = """
    Contact us at support@example.com or sales@example.com
    For urgent matters: urgent@test.org
    Invalid: notanemail.com
    Another valid: info@company.co.uk
    """
    
    emails = extract_emails_from_text(text)
    print(f"Text content: {text[:100]}...")
    print(f"Emails found: {len(emails)}")
    print(f"Emails: {emails}")
    print(f"Expected: 4 emails")
    print(f"Status: {'✓ PASS' if len(emails) == 4 else '✗ FAIL'}")
    
    print("=" * 50)


if __name__ == "__main__":
    test_csv_parsing()
    test_email_extraction()

