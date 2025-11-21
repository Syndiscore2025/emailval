# Universal Email Validator

A production-grade, modular SaaS web application for validating email addresses with support for single validation, bulk file uploads, and CRM webhook integration.

## Features

### Core Validation
- ✅ **Single Email Validation** - Validate individual email addresses via web UI or API
- 📁 **Bulk File Upload** - Support for CSV, XLS, XLSX, and PDF files
- 🔌 **CRM Integration** - Full two-way integration with manual/auto validation modes
- 🎯 **Multi-Layer Validation**:
  - Syntax validation (RFC 5322 compliant)
  - Domain validation (MX/A record lookup)
  - Type detection (disposable/role-based emails)
  - Catch-all domain detection with confidence scoring
  - Optional SMTP verification
  - **Deliverability Scoring** (0-100 with rating)

### Advanced Features
- 🎯 **Dynamic Column Handling**:
  - Intelligent @ symbol detection with confidence scoring
  - Fuzzy column header matching (handles typos and variations)
  - Row metadata preservation (name, phone, company, etc.)
  - Normalized output format with source tracking
- 📊 **Analytics Dashboard**:
  - Real-time KPIs (total emails, valid %, API requests, active keys)
  - Validation trends and charts
  - Top domains analysis
  - Domain reputation scoring
  - Catch-all detection statistics
- 📄 **Export & Reporting**:
  - CSV export with detailed validation results
  - Excel export with formatting and auto-column sizing
  - PDF reports with summary statistics
- 🔐 **API Authentication** - API key management with rate limiting
- 📧 **Email Deduplication** - Persistent tracking across sessions
- 🎨 **Modern UI** - VSCode-inspired dark theme with Tailwind CSS
- 🚀 **Production Ready** - Render-deployable with health checks

### CRM Integration Features
- 🔄 **Two Validation Modes**:
  - **Manual Mode**: Upload → User clicks validate → Get results
  - **Auto Mode**: Upload → Auto-validates → Get results (Premium)
- 📋 **Email Segregation** - 5 separate lists:
  - Clean (valid, ready to use)
  - Catch-all (valid but unverifiable)
  - Invalid (failed validation)
  - Disposable (temporary email services)
  - Role-based (info@, admin@, etc.)
- ☁️ **S3 Delivery**:
  - Upload validated lists to client's AWS S3 bucket
  - SSE-S3 encryption (AES256)
  - Presigned URLs with 24-hour expiry
  - Date-partitioned file structure
- 🔐 **Secure Configuration**:
  - Encrypted AWS credentials storage (Fernet encryption)
  - API key authentication
  - Configurable premium features
- 🔌 **RESTful API**:
  - Lead upload endpoint
  - Manual validation trigger
  - Real-time status polling
  - Results retrieval with segregated lists
  - Backward-compatible webhook endpoint

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
│   ├── catchall_check.py  # Catch-all domain detection
│   ├── file_parser.py     # CSV/XLS/PDF parsing with dynamic column handling
│   ├── reporting.py       # CSV/Excel/PDF report generation
│   ├── email_tracker.py   # Persistent email deduplication
│   ├── api_auth.py        # API key authentication
│   ├── admin_auth.py      # Admin authentication
│   ├── crm_adapter.py     # CRM integration adapter with email segregation
│   ├── crm_config.py      # CRM configuration management with encryption
│   ├── lead_manager.py    # Lead upload tracking system
│   ├── s3_delivery.py     # AWS S3 delivery for validated lists
│   ├── job_tracker.py     # Background job tracking
│   └── utils.py           # Utility functions + deliverability scoring
├── templates/
│   ├── index.html         # Main web interface
│   └── admin/
│       └── dashboard.html # Admin dashboard (Phase 7)
├── static/
│   ├── css/
│   │   └── admin.css      # Admin dashboard styles
│   └── js/
│       └── admin.js       # Admin dashboard JavaScript
├── data/
│   ├── email_history.json # Persistent email tracking database
│   ├── validation_jobs.json # Background job tracking
│   ├── api_keys.json      # API key storage
│   ├── crm_configs.json   # CRM configurations (encrypted credentials)
│   └── crm_uploads.json   # CRM lead upload tracking
└── tests/
    ├── test_crm_modules_direct.py  # CRM module tests
    ├── test_crm_endpoints.py       # CRM API endpoint tests
    └── test_complete.py            # Complete validation tests
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

### 5. Analytics Dashboard (Phase 6)
```
GET /admin/analytics/data
```
Returns real-time analytics data including KPIs, trends, and domain statistics.

**Response:**
```json
{
  "kpis": {
    "total_emails": 1500,
    "valid_emails": 1450,
    "invalid_emails": 50,
    "valid_percentage": 96.7,
    "total_validations": 25,
    "duplicates_prevented": 120
  },
  "validation_trends": {
    "daily": [
      {"date": "2025-01-01", "total": 100, "valid": 95, "invalid": 5}
    ]
  },
  "top_domains": [
    {"domain": "gmail.com", "count": 450, "valid_percentage": 98.5}
  ],
  "domain_reputation": {
    "gmail.com": {"score": 98, "total_validated": 450, "success_rate": 98.5}
  },
  "active_keys": 3
}
```

### 6. Export Reports (Phase 6)
```
POST /api/export/csv
POST /api/export/excel
POST /api/export/pdf
Content-Type: application/json
X-API-Key: your-api-key
```

**Request:**
```json
{
  "validation_results": [...],
  "summary_stats": {
    "total": 100,
    "valid": 95,
    "invalid": 5,
    "valid_percent": 95.0
  }
}
```

**Response:** File download (CSV/Excel/PDF)

## Testing

Run individual module tests:
```bash
python test_syntax.py
python test_domain.py
python test_type.py
python test_file_parser.py
```

Run phase-specific tests:
```bash
python test_phase4.py      # Phase 4: Dynamic column handling
python test_analytics.py   # Phase 6: Analytics & reporting
python test_e2e.py         # Phase 7: End-to-end integration
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

