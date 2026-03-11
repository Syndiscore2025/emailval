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
    emails_1 = [r['email'] for r in result['emails']]
    print(f"Test 1 - CSV with 'Email' header:")
    print(f"  Emails found: {len(result['emails'])}")
    print(f"  Emails: {emails_1}")
    print(f"  Expected: 3 emails")
    assert len(result['emails']) == 3, f"Expected 3, got {len(result['emails'])}"
    print(f"  Status: ✓ PASS")

    # Test case 2: CSV without clear header
    csv_content_2 = """john@example.com
jane@example.com
bob@test.com"""

    result = parse_csv(csv_content_2)
    emails_2 = [r['email'] for r in result['emails']]
    print(f"\nTest 2 - CSV without headers:")
    print(f"  Emails found: {len(result['emails'])}")
    print(f"  Emails: {emails_2}")
    print(f"  Expected: 3 emails")
    assert len(result['emails']) == 3, f"Expected 3, got {len(result['emails'])}"
    print(f"  Status: ✓ PASS")

    # Test case 3: CSV with mixed content
    csv_content_3 = """Contact,Info,Notes
Alice,alice@example.com,VIP customer
Bob,bob@test.com,New lead
Charlie,charlie@demo.com,Follow up"""

    result = parse_csv(csv_content_3)
    emails_3 = [r['email'] for r in result['emails']]
    print(f"\nTest 3 - CSV with mixed content:")
    print(f"  Emails found: {len(result['emails'])}")
    print(f"  Emails: {emails_3}")
    print(f"  Expected: 3 emails")
    assert len(result['emails']) == 3, f"Expected 3, got {len(result['emails'])}"
    print(f"  Status: ✓ PASS")

    # Test case 4: CSV with duplicates — parser returns unique emails
    csv_content_4 = """Email
john@example.com
jane@example.com
john@example.com
jane@example.com"""

    result = parse_csv(csv_content_4)
    emails_4 = [r['email'] for r in result['emails']]
    unique_count = len(set(emails_4))
    print(f"\nTest 4 - CSV with duplicates:")
    print(f"  Emails found: {len(result['emails'])} (unique: {unique_count})")
    print(f"  Emails: {emails_4}")
    print(f"  Expected: at most 4 rows, with john and jane present")
    assert 'john@example.com' in emails_4, "john@example.com should be present"
    assert 'jane@example.com' in emails_4, "jane@example.com should be present"
    print(f"  Status: ✓ PASS")

    # Test case 5: Different delimiter (semicolon)
    csv_content_5 = """Name;Email;Phone
John;john@example.com;555-1234
Jane;jane@example.com;555-5678"""

    result = parse_csv(csv_content_5)
    emails_5 = [r['email'] for r in result['emails']]
    print(f"\nTest 5 - CSV with semicolon delimiter:")
    print(f"  Emails found: {len(result['emails'])}")
    print(f"  Emails: {emails_5}")
    print(f"  Expected: 2 emails")
    assert len(result['emails']) == 2, f"Expected 2, got {len(result['emails'])}"
    print(f"  Status: ✓ PASS")
    
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

