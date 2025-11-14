"""
Test script for email type classification module
"""
from modules.type_check import validate_type, is_disposable, is_role_based


def test_type_classification():
    """Test email type classification"""
    
    test_cases = [
        # Personal emails
        ("john.doe@gmail.com", "personal", False, False),
        ("user123@yahoo.com", "personal", False, False),
        
        # Disposable emails
        ("temp@mailinator.com", "disposable", True, False),
        ("test@guerrillamail.com", "disposable", True, False),
        ("user@tempmail.com", "disposable", True, False),
        
        # Role-based emails
        ("info@company.com", "role", False, True),
        ("support@example.com", "role", False, True),
        ("admin@website.com", "role", False, True),
        ("noreply@service.com", "role", False, True),
    ]
    
    print("Testing Email Type Classification Module")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for email, expected_type, expected_disposable, expected_role in test_cases:
        result = validate_type(email)
        
        type_match = result["email_type"] == expected_type
        disposable_match = result["is_disposable"] == expected_disposable
        role_match = result["is_role_based"] == expected_role
        
        all_match = type_match and disposable_match and role_match
        
        if all_match:
            status = "✓ PASS"
            passed += 1
        else:
            status = "✗ FAIL"
            failed += 1
        
        print(f"{status}: '{email}'")
        print(f"  Type: {result['email_type']} (expected {expected_type})")
        print(f"  Disposable: {result['is_disposable']} (expected {expected_disposable})")
        print(f"  Role-based: {result['is_role_based']} (expected {expected_role})")
        if result["warnings"]:
            print(f"  Warnings: {', '.join(result['warnings'])}")
    
    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = test_type_classification()
    exit(0 if success else 1)

