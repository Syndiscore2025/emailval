# 📐 Technical Specification: Phases 4, 6, 7

## Table of Contents
1. [Phase 4: Dynamic Column Handling](#phase-4)
2. [Phase 6: Analytics & Advanced Features](#phase-6)
3. [Phase 7: Admin Dashboard & QA](#phase-7)
4. [Data Schemas](#data-schemas)
5. [API Endpoints](#api-endpoints)
6. [Testing Requirements](#testing-requirements)

---

## Phase 4: Dynamic Column Handling

### 4.1 @ Symbol Detection Enhancement

**File**: `modules/file_parser.py`

**Current Implementation**:
```python
# Existing 3-tier extraction in parse_file():
# 1. Scan email-related columns
# 2. Scan all columns if no email columns found
# 3. Regex fallback (basic)
```

**Required Enhancement**:
```python
def extract_emails_with_at_symbol(data, file_type):
    """
    Enhanced @ symbol detection as primary fallback.
    
    Args:
        data: Parsed file data (list of rows or text)
        file_type: 'csv', 'excel', or 'pdf'
    
    Returns:
        {
            "emails": [
                {
                    "email": "john@example.com",
                    "source": {"row": 5, "column": "B", "method": "at_symbol_scan"},
                    "confidence": 85,
                    "context": "Contact: john@example.com for info"
                }
            ],
            "extraction_stats": {
                "cells_scanned": 1000,
                "patterns_found": 50,
                "validated": 45,
                "rejected": 5
            }
        }
    """
    from modules.syntax_check import validate_syntax
    
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    results = []
    stats = {"cells_scanned": 0, "patterns_found": 0, "validated": 0, "rejected": 0}
    
    # Scan all cells
    for row_idx, row in enumerate(data):
        for col_idx, cell in enumerate(row):
            stats["cells_scanned"] += 1
            cell_str = str(cell)
            
            # Find all email patterns in cell
            matches = re.findall(email_pattern, cell_str, re.IGNORECASE)
            
            for match in matches:
                stats["patterns_found"] += 1
                
                # Validate using syntax_check module
                validation = validate_syntax(match)
                
                if validation["valid"]:
                    stats["validated"] += 1
                    results.append({
                        "email": match.lower(),
                        "source": {
                            "row": row_idx + 1,
                            "column": col_idx,
                            "method": "at_symbol_scan"
                        },
                        "confidence": calculate_confidence(match, cell_str),
                        "context": cell_str[:100]  # First 100 chars for context
                    })
                else:
                    stats["rejected"] += 1
    
    return {"emails": results, "extraction_stats": stats}

def calculate_confidence(email, context):
    """
    Calculate confidence score (0-100) for extracted email.
    
    Factors:
    - Email is standalone in cell: +30
    - Email has valid TLD: +20
    - Email domain is common (gmail, yahoo, etc.): +20
    - Email has proper format: +20
    - Context suggests it's an email field: +10
    """
    score = 50  # Base score
    
    # Standalone check
    if context.strip() == email:
        score += 30
    
    # Valid TLD check
    common_tlds = ['.com', '.org', '.net', '.edu', '.gov', '.co.uk']
    if any(email.endswith(tld) for tld in common_tlds):
        score += 20
    
    # Common domain check
    common_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']
    if any(domain in email for domain in common_domains):
        score += 20
    
    # Context check
    email_keywords = ['email', 'contact', 'mail', '@']
    if any(keyword in context.lower() for keyword in email_keywords):
        score += 10
    
    return min(score, 100)
```

### 4.2 Advanced Column Mapping

**Implementation**:
```python
def standardize_column_headers(headers):
    """
    Standardize column header variations.
    
    Returns:
        {
            "email": {"source": "E-mail Address", "confidence": 95, "index": 2},
            "name": {"source": "Full Name", "confidence": 100, "index": 0},
            "phone": {"source": "Phone Number", "confidence": 90, "index": 1}
        }
    """
    from difflib import SequenceMatcher
    
    # Standard mappings
    email_variations = [
        'email', 'e-mail', 'e_mail', 'email_address', 'emailaddress',
        'contact', 'contact_email', 'contact_info', 'mail', 'mail_address'
    ]
    
    name_variations = [
        'name', 'full_name', 'fullname', 'contact_name', 'customer_name'
    ]
    
    phone_variations = [
        'phone', 'phone_number', 'phonenumber', 'telephone', 'mobile', 'cell'
    ]
    
    mapping = {}
    
    for idx, header in enumerate(headers):
        header_lower = str(header).lower().strip()
        
        # Exact match for email
        if header_lower in email_variations:
            mapping['email'] = {"source": header, "confidence": 100, "index": idx}
        # Fuzzy match for email
        else:
            for variation in email_variations:
                similarity = SequenceMatcher(None, header_lower, variation).ratio()
                if similarity > 0.8:  # 80% similarity threshold
                    mapping['email'] = {"source": header, "confidence": int(similarity * 100), "index": idx}
                    break
        
        # Similar logic for name and phone
        # ... (implement for other fields)
    
    return mapping
```

### 4.3 Intelligent Row Reconstruction

**Implementation**:
```python
def reconstruct_row_with_metadata(row, column_mapping, row_number, filename):
    """
    Rebuild row object with all available metadata.
    
    Returns:
        {
            "email": "john@example.com",
            "metadata": {
                "name": "John Doe",
                "phone": "555-1234",
                "company": "Acme Corp",
                "row_number": 5,
                "source_file": "contacts.xlsx",
                "extraction_method": "column_mapping",
                "confidence": 95
            }
        }
    """
    result = {}
    metadata = {
        "row_number": row_number,
        "source_file": filename,
        "extraction_method": "column_mapping"
    }
    
    # Extract email
    if 'email' in column_mapping:
        email_idx = column_mapping['email']['index']
        result['email'] = str(row[email_idx]).strip().lower()
        metadata['confidence'] = column_mapping['email']['confidence']
    
    # Extract other fields
    for field in ['name', 'phone', 'company', 'address']:
        if field in column_mapping:
            field_idx = column_mapping[field]['index']
            metadata[field] = str(row[field_idx]).strip()
    
    result['metadata'] = metadata
    return result
```

### 4.4 Normalized Output Format

**Standard Schema**:
```python
{
    "emails": [
        {
            "email": "john@example.com",
            "source": {
                "file": "contacts.csv",
                "row": 5,
                "column": "Email Address",
                "extraction_method": "column_mapping"
            },
            "confidence": 95,
            "metadata": {
                "name": "John Doe",
                "phone": "555-1234",
                "company": "Acme Corp"
            }
        }
    ],
    "summary": {
        "file_info": {
            "filename": "contacts.csv",
            "file_type": "csv",
            "total_rows": 1000,
            "processed_rows": 1000
        },
        "extraction_stats": {
            "emails_extracted": 987,
            "extraction_methods": {
                "column_mapping": 950,
                "full_scan": 30,
                "at_symbol_scan": 7
            },
            "average_confidence": 92.5
        },
        "quality_metrics": {
            "completeness": 98.7,  # % of rows with emails
            "confidence_distribution": {
                "high (90-100)": 950,
                "medium (70-89)": 30,
                "low (0-69)": 7
            }
        }
    }
}
```

---

## Phase 6: Analytics & Advanced Features

### 6.1 Analytics Dashboard

**Endpoint**: `GET /admin/analytics/data`

**Response Schema**:
```python
{
    "kpis": {
        "total_emails": 125847,
        "valid_emails": 98234,
        "invalid_emails": 27613,
        "valid_percentage": 78.05,
        "total_validations": 156234,
        "duplicates_prevented": 30387
    },
    "email_type_distribution": {
        "personal": {"count": 65432, "percentage": 52.0},
        "role_based": {"count": 28901, "percentage": 23.0},
        "disposable": {"count": 15234, "percentage": 12.1},
        "invalid": {"count": 16280, "percentage": 12.9}
    },
    "validation_trends": {
        "daily": [
            {"date": "2025-11-08", "total": 8234, "valid": 6543, "invalid": 1691},
            {"date": "2025-11-09", "total": 9123, "valid": 7234, "invalid": 1889},
            // ... last 30 days
        ]
    },
    "top_domains": [
        {"domain": "gmail.com", "count": 45678, "valid_percentage": 95.2},
        {"domain": "yahoo.com", "count": 23456, "valid_percentage": 87.3},
        {"domain": "outlook.com", "count": 18234, "valid_percentage": 91.5}
    ],
    "domain_reputation": {
        "gmail.com": {"score": 95, "total_validated": 45678, "success_rate": 95.2},
        "yahoo.com": {"score": 87, "total_validated": 23456, "success_rate": 87.3}
    }
}
```

**Implementation**:
```python
@app.route('/admin/analytics/data')
@require_admin_auth
def get_analytics_data():
    """Generate analytics data from email_history.json"""
    tracker = EmailTracker()
    stats = tracker.get_stats()
    
    # Calculate KPIs from real data
    kpis = {
        "total_emails": stats.get('total_emails', 0),
        "valid_emails": stats.get('valid_count', 0),
        "invalid_emails": stats.get('invalid_count', 0),
        "valid_percentage": calculate_percentage(stats.get('valid_count', 0), stats.get('total_emails', 0)),
        "total_validations": stats.get('total_validations', 0),
        "duplicates_prevented": stats.get('duplicate_count', 0)
    }
    
    # Calculate email type distribution from real data
    email_type_dist = calculate_email_type_distribution(tracker)
    
    # Calculate validation trends from sessions
    validation_trends = calculate_validation_trends(tracker)
    
    # Calculate top domains
    top_domains = calculate_top_domains(tracker)
    
    # Calculate domain reputation
    domain_reputation = calculate_domain_reputation(tracker)
    
    return jsonify({
        "kpis": kpis,
        "email_type_distribution": email_type_dist,
        "validation_trends": validation_trends,
        "top_domains": top_domains,
        "domain_reputation": domain_reputation
    })
```

### 6.2 Export & Reporting

**PDF Report Generation**:
```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def generate_pdf_report(validation_results, filename="report.pdf"):
    """
    Generate professional PDF report.
    
    Includes:
    - Summary statistics
    - Validation results table
    - Charts (as images)
    - Branding
    """
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph("Email Validation Report", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    
    # Summary stats
    summary_text = f"""
    Total Emails: {validation_results['total']}
    Valid: {validation_results['valid']} ({validation_results['valid_percent']}%)
    Invalid: {validation_results['invalid']} ({validation_results['invalid_percent']}%)
    """
    summary = Paragraph(summary_text, styles['Normal'])
    story.append(summary)
    story.append(Spacer(1, 12))
    
    # Results table
    table_data = [['Email', 'Status', 'Type', 'Error']]
    for result in validation_results['results']:
        table_data.append([
            result['email'],
            'Valid' if result['valid'] else 'Invalid',
            result.get('email_type', 'N/A'),
            ', '.join(result.get('errors', []))
        ])
    
    table = Table(table_data)
    story.append(table)
    
    doc.build(story)
    return filename
```

### 6.3 Advanced Features

**Email Deliverability Scoring**:
```python
def calculate_deliverability_score(validation_result):
    """
    Calculate deliverability score (0-100).
    
    Weighting:
    - Syntax valid: 20 points
    - Domain valid + MX records: 30 points
    - Not disposable + not role-based: 20 points
    - SMTP valid: 30 points
    """
    score = 0
    
    # Syntax check (20 points)
    if validation_result.get('checks', {}).get('syntax', {}).get('valid'):
        score += 20
    
    # Domain check (30 points)
    domain_check = validation_result.get('checks', {}).get('domain', {})
    if domain_check.get('valid') and domain_check.get('has_mx'):
        score += 30
    
    # Type check (20 points)
    type_check = validation_result.get('checks', {}).get('type', {})
    if not type_check.get('is_disposable') and not type_check.get('is_role_based'):
        score += 20
    
    # SMTP check (30 points)
    if validation_result.get('checks', {}).get('smtp', {}).get('valid'):
        score += 30
    
    return score
```

---

## Phase 7: Admin Dashboard & QA

### 7.1 Admin Dashboard Pages

**Main Dashboard** (`/admin`):
```html
<!-- templates/admin/dashboard.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <link rel="stylesheet" href="/static/css/admin.css">
</head>
<body>
    <nav class="admin-nav">
        <a href="/admin">Dashboard</a>
        <a href="/admin/api-keys">API Keys</a>
        <a href="/admin/emails">Emails</a>
        <a href="/admin/analytics">Analytics</a>
        <a href="/admin/settings">Settings</a>
        <a href="/admin/logout">Logout</a>
    </nav>
    
    <div class="dashboard-container">
        <h1>Admin Dashboard</h1>
        
        <!-- KPIs -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <h3>Total Emails</h3>
                <p id="kpi-total-emails">Loading...</p>
            </div>
            <div class="kpi-card">
                <h3>Valid %</h3>
                <p id="kpi-valid-percent">Loading...</p>
            </div>
            <div class="kpi-card">
                <h3>API Requests</h3>
                <p id="kpi-api-requests">Loading...</p>
            </div>
            <div class="kpi-card">
                <h3>Active Keys</h3>
                <p id="kpi-active-keys">Loading...</p>
            </div>
        </div>
        
        <!-- Charts -->
        <div class="chart-container">
            <canvas id="validation-trends-chart"></canvas>
        </div>
        
        <!-- Activity Feed -->
        <div class="activity-feed">
            <h2>Recent Activity</h2>
            <div id="activity-list">Loading...</div>
        </div>
    </div>
    
    <script src="/static/js/admin.js"></script>
</body>
</html>
```

**Admin JavaScript** (`static/js/admin.js`):
```javascript
// Load KPIs from real data
async function loadKPIs() {
    const response = await fetch('/admin/analytics/data');
    const data = await response.json();
    
    // Update KPIs with REAL data (no hardcoding)
    document.getElementById('kpi-total-emails').textContent = data.kpis.total_emails.toLocaleString();
    document.getElementById('kpi-valid-percent').textContent = data.kpis.valid_percentage.toFixed(1) + '%';
    document.getElementById('kpi-api-requests').textContent = data.kpis.total_validations.toLocaleString();
    document.getElementById('kpi-active-keys').textContent = data.active_keys;
}

// Load charts
async function loadCharts() {
    const response = await fetch('/admin/analytics/data');
    const data = await response.json();
    
    // Validation trends chart
    const ctx = document.getElementById('validation-trends-chart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.validation_trends.daily.map(d => d.date),
            datasets: [{
                label: 'Valid',
                data: data.validation_trends.daily.map(d => d.valid),
                borderColor: 'rgb(75, 192, 192)'
            }, {
                label: 'Invalid',
                data: data.validation_trends.daily.map(d => d.invalid),
                borderColor: 'rgb(255, 99, 132)'
            }]
        }
    });
}

// Auto-refresh every 30 seconds
setInterval(loadKPIs, 30000);

// Initial load
loadKPIs();
loadCharts();
```

---

## Data Schemas

### Email History (`data/email_history.json`)
```json
{
  "emails": {
    "john@example.com": {
      "first_seen": "2025-11-14T10:30:00Z",
      "last_validated": "2025-11-14T15:45:00Z",
      "validation_count": 3,
      "status": "valid",
      "checks": {
        "syntax": {"valid": true},
        "domain": {"valid": true, "has_mx": true},
        "type": {"email_type": "personal", "is_disposable": false}
      },
      "deliverability_score": 90
    }
  },
  "sessions": [
    {
      "session_id": "sess_abc123",
      "timestamp": "2025-11-14T10:30:00Z",
      "file": "contacts.csv",
      "total_emails": 1000,
      "new_emails": 987,
      "duplicates": 13
    }
  ],
  "stats": {
    "total_emails": 125847,
    "valid_count": 98234,
    "invalid_count": 27613,
    "total_validations": 156234,
    "duplicate_count": 30387
  }
}
```

### API Keys (`data/api_keys.json`)
```json
{
  "keys": {
    "ak_abc123": {
      "key_hash": "sha256_hash_here",
      "name": "Marketing Team",
      "created_at": "2025-11-01T00:00:00Z",
      "active": true,
      "rate_limit_per_minute": 500,
      "usage_total": 45123,
      "window_start": "2025-11-14T15:45:00Z",
      "window_count": 23
    }
  }
}
```

---

## API Endpoints (New)

### Analytics
- `GET /admin/analytics/data` - Get analytics data (KPIs, charts, trends)
- `GET /admin/analytics/domains` - Get domain reputation data
- `GET /admin/analytics/trends` - Get validation trends

### Reporting
- `POST /export/csv` - Export results as CSV
- `POST /export/excel` - Export results as Excel
- `POST /export/pdf` - Export results as PDF
- `POST /reports/schedule` - Schedule recurring report
- `GET /reports/templates` - List report templates

### Admin Dashboard
- `GET /admin` - Main dashboard
- `GET /admin/api-keys` - API key management
- `GET /admin/emails` - Email database explorer
- `GET /admin/analytics` - Analytics page
- `GET /admin/settings` - Settings page
- `POST /admin/login` - Admin login
- `POST /admin/logout` - Admin logout

---

## Testing Requirements

### Phase 4 Tests (`test_phase4.py`)
```python
def test_at_symbol_detection():
    """Test @ symbol detection in various scenarios"""
    # Test with email in sentence
    # Test with multiple emails per cell
    # Test with malformed text
    # Test confidence scoring

def test_column_mapping():
    """Test column header standardization"""
    # Test exact matches
    # Test fuzzy matches
    # Test confidence scoring

def test_row_reconstruction():
    """Test row metadata preservation"""
    # Test with all fields present
    # Test with missing fields
    # Test with merged cells

def test_normalized_output():
    """Test output format consistency"""
    # Test CSV output
    # Test Excel output
    # Test PDF output
```

### Phase 6 Tests (`test_analytics.py`)
```python
def test_analytics_data_real():
    """Test analytics uses real data (no mocks)"""
    # Verify KPIs calculated from email_history.json
    # Verify charts use real data
    # Verify no hardcoded values

def test_pdf_report_generation():
    """Test PDF report generation"""
    # Test with real validation results
    # Verify PDF structure
    # Verify charts included

def test_deliverability_scoring():
    """Test deliverability score calculation"""
    # Test with all checks passing (score = 100)
    # Test with some checks failing
    # Test edge cases
```

### Phase 7 Tests (`test_e2e.py`)
```python
def test_complete_user_flow():
    """Test complete user journey"""
    # 1. Upload file
    # 2. Validate emails
    # 3. View results
    # 4. Export results
    # 5. View in admin dashboard

def test_admin_dashboard_kpis():
    """Test admin dashboard KPIs are real"""
    # Load dashboard
    # Verify KPIs match email_history.json
    # Verify no hardcoded values

def test_all_links_functional():
    """Test all navigation links work"""
    # Test main nav
    # Test admin nav
    # Test breadcrumbs
    # Verify no 404s
```

---

**End of Technical Specification**

