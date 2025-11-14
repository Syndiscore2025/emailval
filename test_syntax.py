"""
Test script for syntax validation module
"""
from modules.syntax_check import validate_syntax, is_valid_syntax


def test_syntax_validation():
    """Test various email syntax scenarios"""
    
    test_cases = [
        # Valid emails
        ("test@example.com", True),
        ("user.name@example.com", True),
        ("user+tag@example.co.uk", True),
        ("first.last@subdomain.example.com", True),
        ("123@example.com", True),
        
        # Invalid emails
        ("", False),
        ("notanemail", False),
        ("@example.com", False),
        ("user@", False),
        ("user @example.com", False),
        ("user@.com", False),
        ("user@example", False),
        ("user..name@example.com", False),
        ("user@example..com", False),
        ("a" * 65 + "@example.com", False),  # Local part too long
    ]
    
    print("Testing Syntax Validation Module")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for email, expected_valid in test_cases:
        result = validate_syntax(email)
        is_valid = result["valid"]
        
        if is_valid == expected_valid:
            status = "✓ PASS"
            passed += 1
        else:
            status = "✗ FAIL"
            failed += 1
        
        print(f"{status}: '{email}' -> {is_valid} (expected {expected_valid})")
        if not is_valid and result["errors"]:
            print(f"  Errors: {', '.join(result['errors'])}")
    
    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = test_syntax_validation()
    exit(0 if success else 1)

