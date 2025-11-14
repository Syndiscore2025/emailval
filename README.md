# Universal Email Validator

A production-grade, modular SaaS web application for validating email addresses with support for single validation, bulk file uploads, and CRM webhook integration.

## Features

- ✅ **Single Email Validation** - Validate individual email addresses via web UI or API
- 📁 **Bulk File Upload** - Support for CSV, XLS, XLSX, and PDF files
- 🔌 **CRM Integration** - Webhook endpoint for seamless CRM integration
- 🎯 **Multi-Layer Validation**:
  - Syntax validation (RFC 5322 compliant)
  - Domain validation (MX/A record lookup)
  - Type detection (disposable/role-based emails)
  - Optional SMTP verification
- 🎨 **Modern UI** - VSCode-inspired dark theme with Tailwind CSS
- 🚀 **Production Ready** - Render-deployable with health checks

## Project Structure

```
email_validator/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── Procfile               # Render deployment config
├── runtime.txt            # Python version
├── modules/
│   ├── syntax_check.py    # RFC 5322 syntax validation
│   ├── domain_check.py    # DNS MX/A record validation
│   ├── type_check.py      # Disposable/role-based detection
│   ├── smtp_check.py      # SMTP mailbox verification
│   ├── file_parser.py     # CSV/XLS/PDF parsing
│   └── utils.py           # Utility functions
├── templates/
│   └── index.html         # Web interface
├── static/                # Static assets
└── tests/
    ├── test_syntax.py
    ├── test_domain.py
    ├── test_type.py
    ├── test_file_parser.py
    └── test_complete.py
```

## Installation

### Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd emailval
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python app.py
```

5. Open your browser to `http://localhost:5000`

## API Documentation

### 1. Health Check
```
GET /health
```
Returns service health status.

**Response:**
```json
{
  "status": "healthy",
  "service": "email-validator",
  "version": "1.0.0"
}
```

### 2. Single Email Validation
```
POST /validate
Content-Type: application/json
```

**Request:**
```json
{
  "email": "test@example.com",
  "include_smtp": false
}
```

**Response:**
```json
{
  "email": "test@example.com",
  "valid": true,
  "checks": {
    "syntax": {"valid": true, "errors": []},
    "domain": {"valid": true, "has_mx": true, "mx_records": [...]},
    "type": {"is_disposable": false, "is_role_based": false, "email_type": "personal"}
  },
  "errors": []
}
```

### 3. File Upload
```
POST /upload
Content-Type: multipart/form-data
```

**Form Data:**
- `file`: CSV, XLS, XLSX, or PDF file
- `validate`: "true" to validate extracted emails (optional)
- `include_smtp`: "true" for SMTP checks (optional)

**Response:**
```json
{
  "file_info": {
    "filename": "contacts.csv",
    "file_type": "csv",
    "emails_found": 150
  },
  "emails": ["email1@example.com", "email2@example.com"],
  "validation_results": [...],
  "validation_summary": {
    "total": 150,
    "valid": 145,
    "invalid": 5
  }
}
```

### 4. CRM Webhook
```
POST /api/webhook/validate
Content-Type: application/json
```

**Request (flexible formats):**
```json
{
  "email": "test@example.com"
}
```
or
```json
{
  "emails": ["test1@example.com", "test2@example.com"]
}
```
or
```json
{
  "contact": {
    "email": "test@example.com"
  }
}
```

**Response:**
```json
{
  "results": [...],
  "summary": {
    "total": 2,
    "valid": 2,
    "invalid": 0
  }
}
```

## Testing

Run individual module tests:
```bash
python test_syntax.py
python test_domain.py
python test_type.py
python test_file_parser.py
```

Run complete integration tests:
```bash
python test_complete.py
```

## Deployment to Render

1. Push code to GitHub
2. Create new Web Service on Render
3. Connect your repository
4. Render will auto-detect the Procfile
5. Set environment variables if needed
6. Deploy!

The `/health` endpoint is automatically used by Render for health checks.

## Configuration

Environment variables (optional):
- `FLASK_ENV`: production/development
- `PORT`: Server port (default: 5000)
- `MAX_CONTENT_LENGTH`: Max file upload size in bytes
- `SMTP_TIMEOUT`: SMTP verification timeout in seconds

## License

MIT License

