"""
Quick test of async SMTP validation
"""
from modules.smtp_check_async import validate_smtp_batch

# Test with a few emails
test_emails = [
    'test@gmail.com',
    'user@yahoo.com',
    'admin@example.com'
]

print(f"Testing async SMTP validation with {len(test_emails)} emails...")
print(f"Emails: {test_emails}")

try:
    results = validate_smtp_batch(test_emails, max_workers=3, timeout=5)
    print(f"\n✅ Success! Got {len(results)} results")
    
    for email, result in results.items():
        print(f"\n{email}:")
        print(f"  Valid: {result.get('valid')}")
        print(f"  Mailbox exists: {result.get('mailbox_exists')}")
        print(f"  Errors: {result.get('errors')}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

