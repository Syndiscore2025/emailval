"""Create Production API Key on Render"""
import requests
import getpass

PRODUCTION_URL = "https://emailval-gpru.onrender.com"

print("\n" + "="*80)
print("CREATE PRODUCTION API KEY")
print("="*80 + "\n")

# Get admin credentials
print("Enter your admin credentials:")
username = input("Username (default: admin): ").strip() or "admin"
password = getpass.getpass("Password: ")

# Login to admin
print("\nLogging in to admin dashboard...")
session = requests.Session()
r = session.post(
    f"{PRODUCTION_URL}/admin/login",
    json={"username": username, "password": password},
    timeout=30
)

if r.status_code != 200:
    print(f"❌ Login failed: {r.status_code}")
    print(f"Response: {r.text}")
    exit(1)

print("✅ Login successful!")

# Create API key
print("\nCreating API key...")
api_key_name = input("API Key Name (default: Production Key): ").strip() or "Production Key"
rate_limit = input("Rate Limit per minute (default: 100): ").strip() or "100"

r = session.post(
    f"{PRODUCTION_URL}/admin/api/keys",
    json={"name": api_key_name, "rate_limit": int(rate_limit)},
    timeout=30
)

if r.status_code != 200:
    print(f"❌ API key creation failed: {r.status_code}")
    print(f"Response: {r.text}")
    exit(1)

result = r.json()
api_key = result.get("api_key")
key_id = result.get("metadata", {}).get("key_id")

print("\n" + "="*80)
print("✅ API KEY CREATED SUCCESSFULLY!")
print("="*80)
print(f"\nAPI Key: {api_key}")
print(f"Key ID: {key_id}")
print(f"Name: {api_key_name}")
print(f"Rate Limit: {rate_limit} requests/minute")
print("\n⚠️  SAVE THIS API KEY SECURELY - IT WILL NOT BE SHOWN AGAIN!")
print("="*80 + "\n")

# Test the API key
print("Testing API key...")
r = requests.post(
    f"{PRODUCTION_URL}/api/webhook/validate",
    json={
        "integration_mode": "standalone",
        "emails": ["test@example.com"],
        "include_smtp": False
    },
    headers={"X-API-Key": api_key},
    timeout=30
)

if r.status_code == 200:
    print("✅ API key is working!")
    print(f"Test validation result: {r.json()['summary']}")
else:
    print(f"⚠️  API key test failed: {r.status_code}")
    print(f"Response: {r.text}")

print("\n" + "="*80)
print("NEXT STEPS:")
print("="*80)
print("1. Save your API key in a secure location")
print("2. Use this key in your CRM webhook configuration")
print("3. Test your CRM integration")
print("4. Monitor usage in the admin dashboard")
print("="*80 + "\n")

