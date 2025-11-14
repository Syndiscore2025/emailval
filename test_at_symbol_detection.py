"""
Test @ symbol detection fallback in file parser
"""
from modules.file_parser import parse_csv, extract_emails_by_at_symbol


def test_at_symbol_extraction():
    """Test extracting emails by @ symbol from text"""
    print("\n" + "="*60)
    print("Test 1: @ Symbol Extraction from Text")
    print("="*60)
    
    test_cases = [
        ("Contact us at support@example.com", ["support@example.com"]),
        ("Email: john.doe@company.org", ["john.doe@company.org"]),
        ("Multiple: a@test.com and b@test.org", ["a@test.com", "b@test.org"]),
        ("No email here", []),
        ("Just @ symbol", []),
    ]
    
    for text, expected in test_cases:
        result = extract_emails_by_at_symbol(text)
        status = "✓" if result == expected else "✗"
        print(f"{status} Input: '{text}'")
        print(f"  Expected: {expected}")
        print(f"  Got: {result}")
        print()


def test_csv_no_header_with_at():
    """Test CSV with no clear header but cells containing @ symbols"""
    print("\n" + "="*60)
    print("Test 2: CSV with No Email Column Header")
    print("="*60)
    
    # CSV with no "email" keyword in header
    csv_content = """ID,ContactInfo,Status
1,reach us at admin@company.com,active
2,contact: sales@business.org,pending
3,support available at help@service.net,active"""
    
    result = parse_csv(csv_content)
    
    print(f"CSV Content:\n{csv_content}\n")
    print(f"Emails found: {result['count']}")
    print(f"Emails: {result['emails']}")
    print(f"Expected: 3 emails")
    
    expected_emails = ["admin@company.com", "sales@business.org", "help@service.net"]
    
    if result['count'] == 3 and all(email in result['emails'] for email in expected_emails):
        print("✓ Test PASSED - All emails extracted via @ symbol detection")
    else:
        print("✗ Test FAILED")
        print(f"  Expected: {expected_emails}")
        print(f"  Got: {result['emails']}")


def test_csv_mixed_content():
    """Test CSV with emails embedded in mixed content"""
    print("\n" + "="*60)
    print("Test 3: CSV with Emails in Mixed Content")
    print("="*60)
    
    csv_content = """Name,Notes
John,Call john@example.com before 5pm
Jane,Email sent to jane.smith@company.org
Bob,Meeting scheduled - bob.jones@test.com will attend"""
    
    result = parse_csv(csv_content)
    
    print(f"CSV Content:\n{csv_content}\n")
    print(f"Emails found: {result['count']}")
    print(f"Emails: {result['emails']}")
    
    expected_emails = ["john@example.com", "jane.smith@company.org", "bob.jones@test.com"]
    
    if result['count'] == 3 and all(email in result['emails'] for email in expected_emails):
        print("✓ Test PASSED - Emails extracted from mixed content")
    else:
        print("✗ Test FAILED")
        print(f"  Expected: {expected_emails}")
        print(f"  Got: {result['emails']}")


def test_csv_unstructured():
    """Test completely unstructured CSV with @ symbols"""
    print("\n" + "="*60)
    print("Test 4: Unstructured CSV Data")
    print("="*60)
    
    csv_content = """Data1,Data2,Data3
random text,user1@domain.com,more text
12345,another@email.org,67890
text with @ but no email,valid@test.com,end"""
    
    result = parse_csv(csv_content)
    
    print(f"CSV Content:\n{csv_content}\n")
    print(f"Emails found: {result['count']}")
    print(f"Emails: {result['emails']}")
    
    expected_emails = ["user1@domain.com", "another@email.org", "valid@test.com"]
    
    if result['count'] == 3 and all(email in result['emails'] for email in expected_emails):
        print("✓ Test PASSED - Emails found in unstructured data")
    else:
        print("✗ Test FAILED")
        print(f"  Expected: {expected_emails}")
        print(f"  Got: {result['emails']}")


if __name__ == "__main__":
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*10 + "@ SYMBOL DETECTION TESTS" + " "*24 + "║")
    print("╚" + "="*58 + "╝")
    
    test_at_symbol_extraction()
    test_csv_no_header_with_at()
    test_csv_mixed_content()
    test_csv_unstructured()
    
    print("\n" + "="*60)
    print("All @ symbol detection tests completed!")
    print("="*60 + "\n")

