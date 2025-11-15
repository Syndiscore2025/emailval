"""
Test SMTP validation on sample emails to see real results
"""
from modules.smtp_check_async import validate_smtp_single
from modules.syntax_check import validate_syntax
from modules.domain_check import validate_domain
import json

# ALL emails from the user's screenshots - comprehensive test
test_emails = [
    # From first screenshot
    "allerconstruction@verizon.com.net",
    "garciagson2@gmail.com",
    "tha@dncarlisleschool4705@gmail.com",
    "mike@craftprmasonry.com",
    "franciscaaquino@gmail6990.com",
    "bratton@silverlefftrans.com",
    "jcogay@channelgrowth.com",
    "dayala@hcpr.com",
    "linettedozing@tsci.net",
    "dougbarton@bartonhardwoodfloor.com",
    "casey@capitaldoorlamsing.com",
    "walterwhite@truebluemeth.com",
    "john@kennelupa.com",
    "rmullens@smithmaterials.com",
    "eyalcarmel@clcbuilders.com",
    "randy@natureescapeinc.us",
]

print("=" * 80)
print("SMTP VALIDATION TEST - Sample Emails")
print("=" * 80)
print()

results = []

for i, email in enumerate(test_emails, 1):
    print(f"\n[{i}/{len(test_emails)}] Testing: {email}")
    print("-" * 80)

    # First check syntax
    syntax_result = validate_syntax(email)
    print(f"  Syntax Valid: {syntax_result['valid']}")
    if not syntax_result['valid']:
        print(f"  Syntax Errors: {', '.join(syntax_result['errors'])}")

    # Then check domain
    domain_result = validate_domain(email)
    print(f"  Domain Valid: {domain_result['valid']}")
    if not domain_result['valid']:
        print(f"  Domain Errors: {', '.join(domain_result.get('errors', []))}")

    # Finally SMTP check
    result = validate_smtp_single(email, timeout=5)

    print(f"  SMTP Valid: {result['valid']}")
    print(f"  SMTP Status: {result.get('smtp_status', 'N/A')}")
    print(f"  Confidence: {result.get('confidence', 'N/A')}")
    print(f"  Mailbox Exists: {result['mailbox_exists']}")

    if result['errors']:
        print(f"  SMTP Errors: {result['errors'][0][:100]}")

    if result['smtp_response']:
        print(f"  SMTP Response: {result['smtp_response'][:100]}")

    # Overall validity
    overall_valid = syntax_result['valid'] and domain_result['valid'] and result['valid']
    print(f"  OVERALL VALID: {overall_valid}")

    results.append({
        "email": email,
        "syntax_valid": syntax_result['valid'],
        "domain_valid": domain_result['valid'],
        "smtp_valid": result['valid'],
        "overall_valid": overall_valid,
        "status": result.get('smtp_status', 'N/A'),
        "confidence": result.get('confidence', 'N/A'),
        "errors": {
            "syntax": syntax_result.get('errors', []),
            "domain": domain_result.get('errors', []),
            "smtp": result['errors']
        }
    })

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

valid_count = sum(1 for r in results if r['overall_valid'])
invalid_count = len(results) - valid_count

syntax_fail = sum(1 for r in results if not r['syntax_valid'])
domain_fail = sum(1 for r in results if not r['domain_valid'])
smtp_fail = sum(1 for r in results if not r['smtp_valid'])

print(f"\nTotal Tested: {len(results)}")
print(f"Overall Valid: {valid_count} ({valid_count/len(results)*100:.1f}%)")
print(f"Overall Invalid: {invalid_count} ({invalid_count/len(results)*100:.1f}%)")
print(f"\nFailure Breakdown:")
print(f"  Syntax Failures: {syntax_fail}")
print(f"  Domain Failures: {domain_fail}")
print(f"  SMTP Failures: {smtp_fail}")

print("\n--- VALID EMAILS (Passed All Checks) ---")
for r in results:
    if r['overall_valid']:
        print(f"  ✅ {r['email']} - {r['status']} ({r['confidence']} confidence)")

print("\n--- INVALID EMAILS (Failed At Least One Check) ---")
for r in results:
    if not r['overall_valid']:
        print(f"  ❌ {r['email']}")
        if r['errors']['syntax']:
            print(f"      Syntax: {', '.join(r['errors']['syntax'][:2])}")
        if r['errors']['domain']:
            print(f"      Domain: {', '.join(r['errors']['domain'][:2])}")
        if r['errors']['smtp']:
            print(f"      SMTP: {r['errors']['smtp'][0][:80]}")

print("\n" + "=" * 80)

