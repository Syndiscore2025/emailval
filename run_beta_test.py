"""
Simple script to run beta tests with server wait
"""
import time
import requests
import subprocess
import sys

print("Waiting for server to be ready...")
max_attempts = 30
for i in range(max_attempts):
    try:
        response = requests.get("http://localhost:5000/health", timeout=2)
        if response.status_code == 200:
            print(f"✅ Server is ready after {i+1} attempts")
            break
    except:
        pass
    time.sleep(1)
    if i % 5 == 0:
        print(f"  Still waiting... ({i+1}/{max_attempts})")
else:
    print("❌ Server did not start in time")
    sys.exit(1)

print("\nRunning comprehensive beta tests...\n")
result = subprocess.run([sys.executable, "test_comprehensive_beta.py"], 
                       capture_output=False, text=True)
sys.exit(result.returncode)

