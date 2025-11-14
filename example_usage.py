"""
Example usage of the Email Validator modules
Demonstrates how to use the validation modules programmatically
"""

from modules.syntax_check import validate_syntax
from modules.domain_check import validate_domain
from modules.type_check import validate_type
from modules.smtp_check import validate_smtp
from modules.file_parser import parse_csv, parse_file
from modules.utils import normalize_email


def example_single_validation():
    """Example: Validate a single email address"""
    print("=" * 60)
    print("Example 1: Single Email Validation")
    print("=" * 60)
    
    email = "test@gmail.com"
    
    # Syntax check
    syntax_result = validate_syntax(email)
    print(f"\nEmail: {email}")
    print(f"Syntax Valid: {syntax_result['valid']}")
    
    # Domain check
    domain_result = validate_domain(email)
    print(f"Domain Valid: {domain_result['valid']}")
    print(f"Has MX Records: {domain_result['has_mx']}")
    
    # Type check
    type_result = validate_type(email)
    print(f"Email Type: {type_result['email_type']}")
    print(f"Is Disposable: {type_result['is_disposable']}")
    print(f"Is Role-Based: {type_result['is_role_based']}")


def example_batch_validation():
    """Example: Validate multiple emails"""
    print("\n" + "=" * 60)
    print("Example 2: Batch Email Validation")
    print("=" * 60)
    
    emails = [
        "valid@gmail.com",
        "invalid@fake-domain-xyz.com",
        "temp@mailinator.com",
        "info@company.com",
        "notanemail"
    ]
    
    for email in emails:
        email = normalize_email(email)
        syntax = validate_syntax(email)
        domain = validate_domain(email)
        
        status = "✓" if (syntax['valid'] and domain['valid']) else "✗"
        print(f"{status} {email:40} - Syntax: {syntax['valid']}, Domain: {domain['valid']}")


def example_csv_parsing():
    """Example: Parse CSV and extract emails"""
    print("\n" + "=" * 60)
    print("Example 3: CSV Parsing")
    print("=" * 60)
    
    csv_content = """Name,Email,Phone
John Doe,john@example.com,555-1234
Jane Smith,jane@example.com,555-5678
Bob Johnson,bob@test.com,555-9012"""
    
    result = parse_csv(csv_content)
    
    print(f"\nEmails found: {result['count']}")
    print(f"Emails: {', '.join(result['emails'])}")


def example_disposable_detection():
    """Example: Detect disposable emails"""
    print("\n" + "=" * 60)
    print("Example 4: Disposable Email Detection")
    print("=" * 60)
    
    test_emails = [
        "user@gmail.com",
        "temp@mailinator.com",
        "test@guerrillamail.com",
        "real@yahoo.com"
    ]
    
    for email in test_emails:
        type_result = validate_type(email)
        if type_result['is_disposable']:
            print(f"⚠ {email:35} - DISPOSABLE")
        else:
            print(f"✓ {email:35} - OK")


def example_role_based_detection():
    """Example: Detect role-based emails"""
    print("\n" + "=" * 60)
    print("Example 5: Role-Based Email Detection")
    print("=" * 60)
    
    test_emails = [
        "john.doe@company.com",
        "info@company.com",
        "support@company.com",
        "admin@company.com",
        "sales@company.com"
    ]
    
    for email in test_emails:
        type_result = validate_type(email)
        if type_result['is_role_based']:
            print(f"⚠ {email:35} - ROLE-BASED")
        else:
            print(f"✓ {email:35} - PERSONAL")


def example_complete_validation():
    """Example: Complete validation with all checks"""
    print("\n" + "=" * 60)
    print("Example 6: Complete Validation")
    print("=" * 60)
    
    email = "test@example.com"
    
    print(f"\nValidating: {email}")
    print("-" * 60)
    
    # Run all checks
    syntax = validate_syntax(email)
    domain = validate_domain(email)
    email_type = validate_type(email)
    
    # Display results
    print(f"Syntax Check:  {'✓ PASS' if syntax['valid'] else '✗ FAIL'}")
    if syntax['errors']:
        for error in syntax['errors']:
            print(f"  - {error}")
    
    print(f"Domain Check:  {'✓ PASS' if domain['valid'] else '✗ FAIL'}")
    if domain['has_mx']:
        print(f"  - MX Records: {', '.join(domain['mx_records'][:2])}")
    if domain['errors']:
        for error in domain['errors']:
            print(f"  - {error}")
    
    print(f"Type Check:    {email_type['email_type'].upper()}")
    if email_type['warnings']:
        for warning in email_type['warnings']:
            print(f"  - {warning}")
    
    # Overall result
    is_valid = syntax['valid'] and domain['valid']
    print(f"\nOverall Result: {'✓ VALID' if is_valid else '✗ INVALID'}")


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "EMAIL VALIDATOR - USAGE EXAMPLES" + " " * 16 + "║")
    print("╚" + "=" * 58 + "╝")
    
    example_single_validation()
    example_batch_validation()
    example_csv_parsing()
    example_disposable_detection()
    example_role_based_detection()
    example_complete_validation()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60 + "\n")

