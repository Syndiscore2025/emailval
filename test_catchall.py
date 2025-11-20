"""Test catch-all detection module"""
from modules.catchall_check import check_catchall_domain, check_catchall_from_email, generate_random_email
from modules.domain_check import validate_domain

print("=" * 80)
print("CATCH-ALL DETECTION TEST")
print("=" * 80)

# Test 1: Generate random emails
print("\nTest 1: Generate random emails")
print("-" * 80)
for i in range(3):
    random_email = generate_random_email("example.com")
    print(f"Random email {i+1}: {random_email}")

# Test 2: Test with a known catch-all domain (if you have one)
# Note: Most major providers (Gmail, Yahoo, etc.) are NOT catch-all
print("\nTest 2: Test catch-all detection on sample domains")
print("-" * 80)

test_domains = [
    "gmail.com",  # Not catch-all
    "yahoo.com",  # Not catch-all
    # Add your own test domains here
]

for domain in test_domains:
    print(f"\nTesting domain: {domain}")
    
    # First validate domain
    domain_check = validate_domain(f"test@{domain}")
    if not domain_check.get("valid"):
        print(f"  ❌ Domain not valid: {domain_check.get('errors')}")
        continue
    
    mx_records = domain_check.get("mx_records", [])
    if not mx_records:
        print(f"  ❌ No MX records found")
        continue
    
    mx_host = mx_records[0].rstrip(".")
    print(f"  MX Host: {mx_host}")
    
    # Check catch-all
    try:
        result = check_catchall_domain(domain, mx_host, timeout=5, num_tests=2)
        
        if result.get("is_catchall"):
            print(f"  ⚠️  CATCH-ALL DETECTED!")
            print(f"     Confidence: {result.get('confidence')}")
            print(f"     Tests run: {result.get('tests_run')}")
            print(f"     Accepts: {result.get('accepts_count')}")
            print(f"     Rejects: {result.get('rejects_count')}")
        else:
            print(f"  ✓ NOT catch-all")
            print(f"     Confidence: {result.get('confidence')}")
            print(f"     Tests run: {result.get('tests_run')}")
            print(f"     Accepts: {result.get('accepts_count')}")
            print(f"     Rejects: {result.get('rejects_count')}")
        
        if result.get("errors"):
            print(f"  Errors: {result.get('errors')}")
            
        # Show test results
        print(f"  Test results:")
        for i, test in enumerate(result.get("test_results", [])):
            print(f"    {i+1}. {test.get('email')}: code={test.get('code')}")
            
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")

# Test 3: Test with email address (convenience wrapper)
print("\n\nTest 3: Test catch-all from email address")
print("-" * 80)

test_emails = [
    "test@gmail.com",
    "test@yahoo.com",
]

for email in test_emails:
    print(f"\nTesting email: {email}")
    
    # First validate domain to get MX records
    domain_check = validate_domain(email)
    if not domain_check.get("valid"):
        print(f"  ❌ Domain not valid")
        continue
    
    mx_records = domain_check.get("mx_records", [])
    
    # Check catch-all
    try:
        result = check_catchall_from_email(email, timeout=5, mx_records=mx_records)
        
        if result.get("is_catchall"):
            print(f"  ⚠️  CATCH-ALL DETECTED (confidence: {result.get('confidence')})")
        else:
            print(f"  ✓ NOT catch-all (confidence: {result.get('confidence')})")
            
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print("\nNOTE: Catch-all detection requires SMTP connections to mail servers.")
print("Some servers may block or rate-limit these checks.")
print("For production use, results are cached per domain to minimize checks.")

