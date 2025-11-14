"""
Simple script to run the Flask server
"""
from app import app

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Starting Universal Email Validator Server")
    print("="*60)
    print("Server running at: http://localhost:5000")
    print("API Documentation: http://localhost:5000/apidocs")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False)

