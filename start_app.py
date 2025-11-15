"""
Simple startup script for Flask app
"""
import sys
import os

print("=" * 60, flush=True)
print("Starting Email Validator Application...", flush=True)
print("=" * 60, flush=True)

# Import and run the app
print("Importing app module...", flush=True)
from app import app
print("✓ App imported successfully!", flush=True)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"\n✓ Starting Flask server on http://localhost:{port}", flush=True)
    print(f"✓ Admin panel: http://localhost:{port}/admin", flush=True)
    print(f"✓ Login: username=admin, password=admin123\n", flush=True)
    print("Starting server...\n", flush=True)
    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=False)

