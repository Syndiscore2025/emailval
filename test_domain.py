"""
Test script for domain validation module
"""
from modules.domain_check import validate_domain, is_valid_domain


def test_domain_validation():
    """Test domain DNS validation"""
    
    test_cases = [
        # Valid domains (should have MX or A records)
        ("test@gmail.com", True),
        ("test@google.com", True),
        ("test@yahoo.com", True),
        ("test@outlook.com", True),
        
        # Invalid domains
        ("test@thisisnotarealdomainthatexists12345.com", False),
        ("test@invalid-domain-xyz-999.com", False),
    ]
    
    print("Testing Domain Validation Module")
    print("=" * 50)
    print("Note: This test requires internet connection")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for email, expected_valid in test_cases:
        result = validate_domain(email)
        is_valid = result["valid"]
        
        if is_valid == expected_valid:
            status = "✓ PASS"
            passed += 1
        else:
            status = "✗ FAIL"
            failed += 1
        
        print(f"{status}: '{email}' -> {is_valid} (expected {expected_valid})")
        print(f"  Has MX: {result['has_mx']}, Has A: {result['has_a']}")
        if result["mx_records"]:
            print(f"  MX Records: {', '.join(result['mx_records'][:3])}")
        if result["errors"]:
            print(f"  Errors: {', '.join(result['errors'])}")
    
    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = test_domain_validation()
    exit(0 if success else 1)

