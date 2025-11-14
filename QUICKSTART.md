# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python app.py
```

The application will start at `http://localhost:5000`

### 3. Test the Web Interface

Open your browser and go to:
```
http://localhost:5000
```

You'll see a dark-themed interface where you can:
- Validate single email addresses
- Upload CSV/Excel/PDF files
- View validation results in real-time

### 4. Test the API

#### Validate a Single Email

```bash
curl -X POST http://localhost:5000/validate \
  -H "Content-Type: application/json" \
  -d '{"email": "test@gmail.com"}'
```

**Response:**
```json
{
  "email": "test@gmail.com",
  "valid": true,
  "checks": {
    "syntax": {"valid": true, "errors": []},
    "domain": {"valid": true, "has_mx": true},
    "type": {"email_type": "personal", "is_disposable": false}
  },
  "errors": []
}
```

#### Upload a File

```bash
curl -X POST http://localhost:5000/upload \
  -F "file=@contacts.csv" \
  -F "validate=true"
```

#### CRM Webhook Integration

```bash
curl -X POST http://localhost:5000/api/webhook/validate \
  -H "Content-Type: application/json" \
  -d '{"emails": ["test1@example.com", "test2@example.com"]}'
```

### 5. Run Tests

```bash
# Run all tests
python run_tests.py

# Or run individual tests
python test_syntax.py
python test_domain.py
python test_type.py
python test_file_parser.py
python test_complete.py
```

## 📝 Example Use Cases

### Use Case 1: Validate User Registration Email

```python
import requests

response = requests.post('http://localhost:5000/validate', 
    json={'email': 'newuser@example.com'})

data = response.json()
if data['valid']:
    print("Email is valid!")
else:
    print(f"Email is invalid: {', '.join(data['errors'])}")
```

### Use Case 2: Clean Email List from CSV

1. Prepare your CSV file with emails
2. Go to `http://localhost:5000`
3. Click "Choose File" and select your CSV
4. Check "Validate extracted emails"
5. Click "Upload & Process"
6. Download the results

### Use Case 3: CRM Integration

```python
import requests

# Your CRM webhook endpoint
webhook_url = 'http://localhost:5000/api/webhook/validate'

# Send contact data
contact_data = {
    'contact': {
        'email': 'customer@example.com'
    }
}

response = requests.post(webhook_url, json=contact_data)
result = response.json()

if result['results'][0]['valid']:
    # Add to CRM
    pass
else:
    # Flag for review
    pass
```

## 🎯 Key Features

### Validation Checks

1. **Syntax Check** - RFC 5322 compliant
2. **Domain Check** - MX/A record verification
3. **Type Detection** - Identifies disposable/role-based emails
4. **SMTP Check** - Optional mailbox verification

### File Support

- CSV (any delimiter)
- Excel (.xls, .xlsx)
- PDF (extracts emails from text)

### Smart Parsing

- Auto-detects email columns
- Handles unstructured data
- Deduplicates emails
- Skips invalid entries

## 🔧 Configuration

### Environment Variables

Create a `.env` file:

```env
FLASK_ENV=development
FLASK_DEBUG=True
PORT=5000
MAX_CONTENT_LENGTH=16777216
SMTP_TIMEOUT=10
```

### Customize Validation

Edit `app.py` to adjust:
- File size limits
- Allowed file types
- SMTP timeout
- Worker count

## 📊 Understanding Results

### Valid Email
```json
{
  "email": "user@example.com",
  "valid": true,
  "checks": {
    "syntax": {"valid": true},
    "domain": {"valid": true, "has_mx": true},
    "type": {"email_type": "personal"}
  }
}
```

### Invalid Email
```json
{
  "email": "invalid@fake-domain-xyz.com",
  "valid": false,
  "checks": {
    "syntax": {"valid": true},
    "domain": {"valid": false},
    "type": {"email_type": "personal"}
  },
  "errors": ["Domain does not exist"]
}
```

### Disposable Email
```json
{
  "email": "temp@mailinator.com",
  "valid": true,
  "checks": {
    "type": {
      "email_type": "disposable",
      "is_disposable": true
    }
  },
  "errors": ["Email uses disposable domain"]
}
```

## 🐛 Troubleshooting

**Problem**: Module not found errors
```bash
pip install -r requirements.txt
```

**Problem**: Port already in use
```bash
# Change port in app.py or use environment variable
PORT=8000 python app.py
```

**Problem**: DNS lookups fail
- Check internet connection
- Some networks block DNS queries
- Try with different email domains

**Problem**: File upload fails
- Check file size (max 16MB by default)
- Verify file format (CSV/XLS/XLSX/PDF)
- Ensure file contains valid emails

## 📚 Next Steps

- Read the full [README.md](README.md)
- Check [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment
- Explore the API documentation in the web interface
- Customize validation rules in `modules/`

## 💡 Tips

- Use `include_smtp: false` for faster validation
- SMTP checks can be slow and may be blocked
- Disposable emails are technically valid but flagged
- Role-based emails (info@, support@) are flagged as warnings
- Large files may take time to process

