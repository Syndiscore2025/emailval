# Universal Email Validator

A production-grade, modular SaaS web application for validating email addresses with support for single validation, bulk file uploads, and CRM webhook integration.

## Features

### Core Validation
- ✅ **Single Email Validation** - Validate individual email addresses via web UI or API
- 📁 **Bulk File Upload** - Streaming CSV/XLS/XLSX/PDF processing (memory-efficient, no disk writes)
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
- 🔑 **Self-Service Rate Limit Management**:
  - `GET /api/keys/self` — inspect your own key metadata and usage
  - `PATCH /api/keys/self/rate-limit` — update your own rate limit with no admin involvement
- 🔄 **Reliable Callback Delivery**:
  - Retry-with-exponential-backoff (3 attempts, factor 1.5×) for CRM callbacks
  - Dead-letter log marker (`dead_letter: true`) on permanent failure — searchable in log drain
- 🔌 **RESTful API**:
  - Lead upload endpoint
  - Manual validation trigger
  - Real-time status polling
  - Results retrieval with segregated lists
  - Backward-compatible webhook endpoint

## Project Structure

```
emailval/
├── app.py                  # Main Flask application (21+ API endpoints)
├── requirements.txt        # Python dependencies
├── Procfile               # Render deployment config
├── runtime.txt            # Python version
├── modules/
│   ├── syntax_check.py          # RFC 5322 syntax validation
│   ├── domain_check.py          # DNS MX/A record validation
│   ├── type_check.py            # Disposable/role-based detection
│   ├── smtp_check.py            # SMTP mailbox verification (sync)
│   ├── smtp_check_async.py      # SMTP mailbox verification (async)
│   ├── catchall_check.py        # Catch-all domain detection
│   ├── obvious_invalid.py       # Fast pre-filter for obviously invalid emails
│   ├── file_parser.py           # Streaming CSV/XLS/PDF parsing (pypdf)
│   ├── reporting.py             # CSV/Excel/PDF report generation
│   ├── email_tracker.py         # Persistent email deduplication
│   ├── api_auth.py              # API key auth + sliding-window rate limiting
│   ├── admin_auth.py            # Admin session authentication
│   ├── admin_email_actions.py   # Admin email management actions
│   ├── crm_adapter.py           # CRM integration adapter with email segregation
│   ├── crm_config.py            # CRM configuration management with encryption
│   ├── lead_manager.py          # Lead upload tracking system
│   ├── s3_delivery.py           # AWS S3 delivery for validated lists
│   ├── job_tracker.py           # Background job tracking
│   ├── validation_worker.py     # Background validation job queue
│   ├── outbound_delivery_worker.py # Async callback delivery with retry/backoff
│   ├── webhook_log_manager.py   # Webhook request/response logging
│   ├── runtime_state_backend.py # Postgres / JSON state backend selector
│   ├── json_store.py            # Thread-safe JSON file I/O
│   ├── external_kpi.py          # External KPI event delivery (Switchbox)
│   ├── n8n_integration.py       # n8n automation integration
│   ├── backup_manager.py        # Data backup utilities
│   ├── logger.py                # Structured JSON/text logger setup
│   └── utils.py                 # Utility functions + deliverability scoring
├── templates/
│   ├── index.html         # Main web interface
│   ├── developer.html     # Developer/API docs view
│   └── admin/
│       └── dashboard.html # Admin dashboard
├── static/
│   ├── css/
│   │   └── admin.css      # Admin dashboard styles
│   └── js/
│       └── admin.js       # Admin dashboard JavaScript
├── data/
│   ├── api_keys.json        # API key storage (or Postgres table)
│   ├── email_history.json   # Persistent email tracking (or Postgres table)
│   ├── validation_jobs.json # Background job tracking (or Postgres table)
│   ├── crm_configs.json     # CRM configurations (encrypted credentials)
│   └── webhook_logs.json    # Webhook request/response log
└── tests/
    ├── test_complete.py                    # Core validation flow
    ├── test_file_parser.py                 # CSV/XLS/PDF parser tests
    ├── test_api_auth.py                    # API key auth & rate limiting
    ├── test_crm_modules_direct.py          # CRM module unit tests
    ├── test_crm_endpoints.py               # CRM API endpoint tests
    ├── test_email_tracker.py               # Email tracker tests
    ├── test_enterprise_integration_contract.py # Integration contract tests
    ├── test_bulk_upload_monitoring.py      # Bulk upload monitoring tests
    └── test_upload_non_smtp.py             # Upload without SMTP tests
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

Run the full test suite:
```bash
python -m pytest -q
```

Run specific suites:
```bash
python -m pytest test_complete.py           # Core validation flow
python -m pytest test_file_parser.py        # CSV/XLS/PDF parser
python -m pytest test_api_auth.py           # API key auth & rate limiting
python -m pytest test_crm_endpoints.py      # CRM API endpoints
python -m pytest test_crm_modules_direct.py # CRM module unit tests
```

## Deployment

### Render (current)

1. Push code to GitHub
2. Create a new Web Service on Render and connect your repository
3. Render auto-detects the `Procfile`
4. Set the required environment variables (see below)
5. Deploy — `/health` is used automatically for health checks

### DigitalOcean

See `DIGITAL_OCEAN_SETUP_GUIDE.md` for a full step-by-step guide covering App Platform and Droplet deployments with Postgres-backed state.

## Configuration

### Required in production

| Variable | Notes |
|---|---|
| `SECRET_KEY` | 64-char random string — Flask session secret |
| `ADMIN_USERNAME` | Admin UI login |
| `ADMIN_PASSWORD` | Admin UI password |
| `API_AUTH_ENABLED` | Set to `true` to enforce API key auth on all endpoints |
| `API_KEY_ALLOW_QUERY_PARAM` | Set to `false` in production (header-only key delivery) |

### Postgres runtime state (recommended for multi-worker / production)

| Variable | Notes |
|---|---|
| `RUNTIME_STATE_BACKEND` | Set to `postgres` — defaults to `json` (single-worker only) |
| `RUNTIME_STATE_DATABASE_URL` | Full Postgres connection URL |

When `postgres` backend is active, all tables are auto-created on first start.

### Optional features

| Variable | Notes |
|---|---|
| `SMTP_ENABLED` | `true` to enable live SMTP MX checks (default: `false`) |
| `WEBHOOK_SIGNING_SECRET` | HMAC key for signing outbound callbacks |
| `REQUIRE_WEBHOOK_SIGNATURES` | Reject unsigned inbound webhooks |
| `CRM_CONFIG_ENCRYPTION_KEY` | Fernet key for encrypting stored AWS credentials |
| `EXTERNAL_KPI_ENABLED` | Send KPI events to Switchbox command center |
| `SENTRY_DSN` | Sentry error tracking DSN |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`) |
| `LOG_FORMAT` | `json` or `text` (default: `json`) |

## License

MIT License

