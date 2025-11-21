# 🛠️ Implementation Guide - Priority Fixes

**Quick-start guide for implementing critical production improvements**

---

## 1. STRUCTURED LOGGING (P0 - 1 Day)

### Step 1: Install Dependencies
```bash
pip install python-json-logger sentry-sdk
```

### Step 2: Create logging configuration
**File:** `modules/logger.py`
```python
import logging
import os
from pythonjsonlogger import jsonlogger

def setup_logging():
    """Configure structured logging"""
    logger = logging.getLogger()
    
    # Set level from environment
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logger.setLevel(getattr(logging, log_level))
    
    # JSON formatter
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s',
        timestamp=True
    )
    
    # Console handler
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

# Initialize
logger = setup_logging()
```

### Step 3: Replace print() statements
**Before:**
```python
print(f"[BACKGROUND] Job {job_id} started")
```

**After:**
```python
from modules.logger import logger

logger.info("Background job started", extra={
    "job_id": job_id,
    "email_count": total_emails,
    "include_smtp": include_smtp
})
```

### Step 4: Add Sentry for error tracking
**File:** `app.py` (top of file)
```python
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

# Initialize Sentry
sentry_dsn = os.getenv('SENTRY_DSN')
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.1,  # 10% of transactions
        environment=os.getenv('ENVIRONMENT', 'production')
    )
```

### Step 5: Add to requirements.txt
```
python-json-logger==2.0.7
sentry-sdk==1.40.0
```

### Step 6: Set environment variable in Render
```
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
LOG_LEVEL=INFO
ENVIRONMENT=production
```

---

## 2. DNS CACHING (P1 - 4 Hours)

### Implementation
**File:** `modules/domain_check.py`

**Add at top:**
```python
import time
from threading import Lock

# Domain cache: {domain: (timestamp, mx_records, has_mx)}
_domain_cache = {}
_cache_lock = Lock()
CACHE_TTL = 3600  # 1 hour

def get_mx_records_cached(domain: str):
    """Get MX records with caching"""
    with _cache_lock:
        if domain in _domain_cache:
            cached_time, mx_records, has_mx = _domain_cache[domain]
            if time.time() - cached_time < CACHE_TTL:
                logger.debug(f"DNS cache hit for {domain}")
                return mx_records, has_mx
    
    # Cache miss - do actual DNS lookup
    logger.debug(f"DNS cache miss for {domain}")
    mx_records = []
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        mx_records = sorted(mx_records, key=lambda x: x.preference)
        mx_records = [str(r.exchange).rstrip('.') for r in mx_records]
        has_mx = len(mx_records) > 0
    except Exception as e:
        has_mx = False
    
    # Cache result
    with _cache_lock:
        _domain_cache[domain] = (time.time(), mx_records, has_mx)
    
    return mx_records, has_mx
```

**Update validate_domain():**
```python
def validate_domain(email: str) -> Dict[str, Any]:
    """Validate email domain with DNS caching"""
    domain = extract_domain(email)
    
    # Use cached DNS lookup
    mx_records, has_mx = get_mx_records_cached(domain)
    
    # Rest of validation logic...
```

**Expected Impact:**
- 1000 gmail.com emails: 1000 DNS queries → 1 DNS query
- 50-70% faster bulk validation

---

## 3. AUTOMATED BACKUPS (P0 - 4 Hours)

### Option A: PostgreSQL (Recommended)
**Render automatically backs up PostgreSQL databases**
- Daily backups
- 7-day retention (free tier)
- Point-in-time recovery

**Setup:**
1. Add PostgreSQL addon in Render dashboard
2. Migrate data (see PostgreSQL migration guide below)
3. Done! Backups are automatic

### Option B: JSON Files (Temporary)
**Create backup script:** `scripts/backup_data.sh`
```bash
#!/bin/bash
# Backup JSON databases to S3

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/tmp/backup_$DATE"
S3_BUCKET="your-backup-bucket"

# Create backup directory
mkdir -p $BACKUP_DIR

# Copy data files
cp -r data/*.json $BACKUP_DIR/

# Create tarball
tar -czf backup_$DATE.tar.gz -C /tmp backup_$DATE

# Upload to S3
aws s3 cp backup_$DATE.tar.gz s3://$S3_BUCKET/backups/

# Cleanup
rm -rf $BACKUP_DIR backup_$DATE.tar.gz

echo "Backup completed: backup_$DATE.tar.gz"
```

**Schedule with cron:**
```bash
# Run daily at 2 AM
0 2 * * * /app/scripts/backup_data.sh >> /var/log/backup.log 2>&1
```

**For Render (no cron):**
Use GitHub Actions:
```yaml
# .github/workflows/backup.yml
name: Daily Backup
on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM daily
jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger backup endpoint
        run: |
          curl -X POST https://your-app.onrender.com/admin/api/backup \
            -H "X-Admin-Key: ${{ secrets.ADMIN_API_KEY }}"
```

**Add backup endpoint:** `app.py`
```python
@app.route('/admin/api/backup', methods=['POST'])
@require_admin_api
def trigger_backup():
    """Trigger database backup to S3"""
    try:
        import boto3
        from datetime import datetime
        
        s3 = boto3.client('s3')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Backup each JSON file
        for filename in ['email_history.json', 'validation_jobs.json', 
                        'api_keys.json', 'crm_configs.json', 'crm_uploads.json']:
            filepath = f'data/{filename}'
            if os.path.exists(filepath):
                s3_key = f'backups/{timestamp}/{filename}'
                s3.upload_file(
                    filepath,
                    os.getenv('BACKUP_S3_BUCKET'),
                    s3_key
                )
        
        return jsonify({"success": True, "timestamp": timestamp})
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return jsonify({"error": str(e)}), 500
```

---

## 4. RATE LIMITING & QUOTAS (P1 - 2 Days)

### Step 1: Add quota fields to API keys
**File:** `modules/api_auth.py`

**Update generate_key():**
```python
def generate_key(self, name: str, tier: str = 'free', 
                rate_limit_per_minute: int = 60) -> Dict[str, Any]:
    """Generate API key with tier-based quotas"""
    
    # Define tier quotas
    quotas = {
        'free': {
            'emails_per_month': 1000,
            'requests_per_day': 100,
            'concurrent_jobs': 1
        },
        'starter': {
            'emails_per_month': 10000,
            'requests_per_day': 1000,
            'concurrent_jobs': 3
        },
        'pro': {
            'emails_per_month': 100000,
            'requests_per_day': 10000,
            'concurrent_jobs': 10
        },
        'enterprise': {
            'emails_per_month': -1,  # Unlimited
            'requests_per_day': -1,
            'concurrent_jobs': 50
        }
    }
    
    api_key = "ev_" + secrets.token_urlsafe(32)
    key_id = "ak_" + secrets.token_hex(8)
    key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    
    self.keys[key_id] = {
        "key_hash": key_hash,
        "name": name,
        "tier": tier,
        "quotas": quotas.get(tier, quotas['free']),
        "usage": {
            "emails_this_month": 0,
            "requests_today": 0,
            "month_start": datetime.utcnow().replace(day=1).isoformat(),
            "day_start": datetime.utcnow().replace(hour=0, minute=0).isoformat()
        },
        "created_at": datetime.utcnow().isoformat(),
        "active": True,
        "rate_limit_per_minute": rate_limit_per_minute
    }
    self._save()
    
    return {"api_key": api_key, "metadata": self.keys[key_id]}
```

### Step 2: Add quota checking
```python
def check_quota(self, key_id: str, emails_count: int = 0) -> Tuple[bool, Optional[str]]:
    """Check if request is within quota limits"""
    data = self.keys.get(key_id)
    if not data:
        return False, "Invalid API key"
    
    quotas = data.get('quotas', {})
    usage = data.get('usage', {})
    
    # Check monthly email quota
    monthly_limit = quotas.get('emails_per_month', 0)
    if monthly_limit > 0:  # -1 = unlimited
        current_usage = usage.get('emails_this_month', 0)
        if current_usage + emails_count > monthly_limit:
            remaining = monthly_limit - current_usage
            return False, f"Monthly quota exceeded. Limit: {monthly_limit}, Used: {current_usage}, Remaining: {remaining}"
    
    # Check daily request quota
    daily_limit = quotas.get('requests_per_day', 0)
    if daily_limit > 0:
        requests_today = usage.get('requests_today', 0)
        if requests_today >= daily_limit:
            return False, f"Daily request quota exceeded. Limit: {daily_limit}"
    
    return True, None

def increment_usage(self, key_id: str, emails_count: int = 0):
    """Increment usage counters"""
    data = self.keys.get(key_id)
    if not data:
        return
    
    usage = data.get('usage', {})
    now = datetime.utcnow()
    
    # Reset monthly counter if new month
    month_start = datetime.fromisoformat(usage.get('month_start', now.isoformat()))
    if now.month != month_start.month or now.year != month_start.year:
        usage['emails_this_month'] = 0
        usage['month_start'] = now.replace(day=1).isoformat()
    
    # Reset daily counter if new day
    day_start = datetime.fromisoformat(usage.get('day_start', now.isoformat()))
    if now.date() != day_start.date():
        usage['requests_today'] = 0
        usage['day_start'] = now.replace(hour=0, minute=0).isoformat()
    
    # Increment counters
    usage['emails_this_month'] = usage.get('emails_this_month', 0) + emails_count
    usage['requests_today'] = usage.get('requests_today', 0) + 1
    
    data['usage'] = usage
    self._save()
```

### Step 3: Enforce quotas in endpoints
**File:** `app.py`

**Update @require_api_key decorator:**
```python
def require_api_key(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not API_AUTH_ENABLED:
            return func(*args, **kwargs)
        
        api_key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if not api_key:
            return jsonify({"error": "Missing API key"}), 401
        
        manager = get_key_manager()
        resolved = manager.get_key_by_secret(api_key)
        if not resolved:
            return jsonify({"error": "Invalid API key"}), 401
        
        key_id, _ = resolved
        
        # Check rate limit
        allowed, retry_after = manager.register_usage(key_id)
        if not allowed:
            response = jsonify({
                "error": "Rate limit exceeded",
                "retry_after_seconds": retry_after
            })
            if retry_after:
                response.headers["Retry-After"] = str(retry_after)
            return response, 429
        
        # Check quota (estimate email count from request)
        email_count = estimate_email_count(request)
        quota_ok, quota_error = manager.check_quota(key_id, email_count)
        if not quota_ok:
            return jsonify({
                "error": "Quota exceeded",
                "message": quota_error,
                "upgrade_url": "/pricing"
            }), 429
        
        # Store key_id in request context for later usage tracking
        request.api_key_id = key_id
        request.email_count = email_count
        
        return func(*args, **kwargs)
    
    return wrapper

def estimate_email_count(request):
    """Estimate number of emails in request"""
    data = request.get_json() or {}
    
    # Direct email count
    if 'emails' in data:
        return len(data['emails'])
    
    # File upload
    if 'files' in request.files:
        # Estimate based on file size (rough: 50 bytes per email)
        file = request.files['files']
        file_size = len(file.read())
        file.seek(0)  # Reset file pointer
        return max(1, file_size // 50)
    
    # Single email
    if 'email' in data:
        return 1
    
    return 0
```

**After successful validation, increment usage:**
```python
# At end of /upload endpoint
if hasattr(request, 'api_key_id'):
    manager = get_key_manager()
    manager.increment_usage(request.api_key_id, actual_email_count)
```

---

## 5. WEBHOOK DEAD LETTER QUEUE (P1 - 2 Days)

### Step 1: Create webhook tracking table
**File:** `modules/webhook_tracker.py`
```python
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import uuid4

WEBHOOKS_FILE = 'data/webhook_deliveries.json'

class WebhookTracker:
    """Track webhook delivery attempts"""
    
    def __init__(self):
        self.webhooks = self._load()
    
    def _load(self) -> Dict[str, Any]:
        if os.path.exists(WEBHOOKS_FILE):
            with open(WEBHOOKS_FILE, 'r') as f:
                return json.load(f)
        return {"deliveries": {}}
    
    def _save(self):
        os.makedirs(os.path.dirname(WEBHOOKS_FILE), exist_ok=True)
        with open(WEBHOOKS_FILE, 'w') as f:
            json.dump(self.webhooks, f, indent=2)
    
    def create_delivery(self, url: str, payload: Dict[str, Any], 
                       upload_id: str = None) -> str:
        """Create new webhook delivery record"""
        webhook_id = f"wh_{uuid4().hex[:12]}"
        
        self.webhooks["deliveries"][webhook_id] = {
            "webhook_id": webhook_id,
            "url": url,
            "payload": payload,
            "upload_id": upload_id,
            "status": "pending",  # pending, delivered, failed
            "attempts": 0,
            "max_attempts": 3,
            "last_attempt_at": None,
            "last_error": None,
            "created_at": datetime.now().isoformat(),
            "delivered_at": None
        }
        self._save()
        return webhook_id
    
    def record_attempt(self, webhook_id: str, success: bool, 
                      error: str = None, response_code: int = None):
        """Record webhook delivery attempt"""
        if webhook_id not in self.webhooks["deliveries"]:
            return
        
        delivery = self.webhooks["deliveries"][webhook_id]
        delivery["attempts"] += 1
        delivery["last_attempt_at"] = datetime.now().isoformat()
        
        if success:
            delivery["status"] = "delivered"
            delivery["delivered_at"] = datetime.now().isoformat()
        else:
            delivery["last_error"] = error
            delivery["last_response_code"] = response_code
            
            if delivery["attempts"] >= delivery["max_attempts"]:
                delivery["status"] = "failed"
        
        self._save()
    
    def get_failed_deliveries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all failed webhook deliveries"""
        failed = [
            d for d in self.webhooks["deliveries"].values()
            if d["status"] == "failed"
        ]
        failed.sort(key=lambda x: x["created_at"], reverse=True)
        return failed[:limit]
    
    def retry_delivery(self, webhook_id: str) -> bool:
        """Reset delivery for retry"""
        if webhook_id not in self.webhooks["deliveries"]:
            return False
        
        delivery = self.webhooks["deliveries"][webhook_id]
        delivery["status"] = "pending"
        delivery["attempts"] = 0
        delivery["last_error"] = None
        self._save()
        return True

# Singleton
_webhook_tracker = None

def get_webhook_tracker() -> WebhookTracker:
    global _webhook_tracker
    if _webhook_tracker is None:
        _webhook_tracker = WebhookTracker()
    return _webhook_tracker
```

### Step 2: Update webhook delivery function
**File:** `app.py`

```python
from modules.webhook_tracker import get_webhook_tracker

def send_crm_callback_tracked(callback_url: str, response_data: Dict[str, Any], 
                              settings: Dict[str, Any], upload_id: str = None):
    """Send callback with tracking"""
    tracker = get_webhook_tracker()
    
    # Create delivery record
    webhook_id = tracker.create_delivery(callback_url, response_data, upload_id)
    
    try:
        # Build payload
        payload = json.dumps(response_data).encode('utf-8')
        
        # Create signature if configured
        signature_secret = settings.get('callback_signature_secret')
        headers = {'Content-Type': 'application/json'}
        
        if signature_secret:
            signature = hmac.new(
                signature_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            headers['X-Webhook-Signature'] = signature
        
        # Send request
        req = urllib.request.Request(
            callback_url,
            data=payload,
            headers=headers,
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.status
            
            if 200 <= status_code < 300:
                tracker.record_attempt(webhook_id, success=True)
                logger.info(f"Webhook delivered successfully", extra={
                    "webhook_id": webhook_id,
                    "url": callback_url,
                    "status_code": status_code
                })
            else:
                tracker.record_attempt(webhook_id, success=False, 
                                     error=f"HTTP {status_code}",
                                     response_code=status_code)
                logger.warning(f"Webhook delivery failed", extra={
                    "webhook_id": webhook_id,
                    "status_code": status_code
                })
    
    except Exception as e:
        tracker.record_attempt(webhook_id, success=False, error=str(e))
        logger.error(f"Webhook delivery error", extra={
            "webhook_id": webhook_id,
            "error": str(e)
        })
        
        # Retry logic
        delivery = tracker.webhooks["deliveries"][webhook_id]
        if delivery["attempts"] < delivery["max_attempts"]:
            # Schedule retry (exponential backoff)
            retry_delay = 2 ** delivery["attempts"]  # 2, 4, 8 seconds
            threading.Timer(retry_delay, lambda: send_crm_callback_tracked(
                callback_url, response_data, settings, upload_id
            )).start()
```

### Step 3: Add admin dashboard for failed webhooks
**File:** `app.py`

```python
@app.route('/admin/webhooks/failed', methods=['GET'])
@require_admin_login
def admin_failed_webhooks():
    """View failed webhook deliveries"""
    tracker = get_webhook_tracker()
    failed = tracker.get_failed_deliveries(limit=100)
    return render_template('admin/failed_webhooks.html', webhooks=failed)

@app.route('/admin/api/webhooks/<webhook_id>/retry', methods=['POST'])
@require_admin_api
def retry_webhook(webhook_id):
    """Manually retry failed webhook"""
    tracker = get_webhook_tracker()
    
    if not tracker.retry_delivery(webhook_id):
        return jsonify({"error": "Webhook not found"}), 404
    
    # Get delivery details and retry
    delivery = tracker.webhooks["deliveries"][webhook_id]
    send_crm_callback_tracked(
        delivery["url"],
        delivery["payload"],
        {},  # settings
        delivery.get("upload_id")
    )
    
    return jsonify({"success": True, "webhook_id": webhook_id})
```

---

## 6. ENHANCED HEALTH CHECKS (P1 - 4 Hours)

**File:** `app.py`

```python
@app.route('/health', methods=['GET'])
def health():
    """Comprehensive health check"""
    checks = {}
    overall_status = "healthy"
    
    # Check database
    try:
        tracker = get_tracker()
        tracker.get_stats()
        checks["database"] = {"status": "ok", "type": "json_files"}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}
        overall_status = "unhealthy"
    
    # Check S3 (if configured)
    try:
        if os.getenv('AWS_ACCESS_KEY_ID'):
            import boto3
            s3 = boto3.client('s3')
            s3.list_buckets()
            checks["s3"] = {"status": "ok"}
        else:
            checks["s3"] = {"status": "not_configured"}
    except Exception as e:
        checks["s3"] = {"status": "error", "error": str(e)}
        # Don't mark overall as unhealthy if S3 is optional
    
    # Check SMTP (sample test)
    try:
        import socket
        socket.create_connection(("smtp.gmail.com", 25), timeout=2)
        checks["smtp"] = {"status": "ok"}
    except Exception as e:
        checks["smtp"] = {"status": "degraded", "error": str(e)}
        # SMTP issues shouldn't mark service as unhealthy
    
    # Check disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        free_percent = (free / total) * 100
        checks["disk"] = {
            "status": "ok" if free_percent > 10 else "warning",
            "free_percent": round(free_percent, 2)
        }
        if free_percent < 10:
            overall_status = "degraded"
    except Exception as e:
        checks["disk"] = {"status": "error", "error": str(e)}
    
    # Calculate uptime
    import time
    uptime_seconds = int(time.time() - app.start_time)
    
    response = {
        "status": overall_status,
        "service": "email-validator",
        "version": "1.0.0",
        "uptime_seconds": uptime_seconds,
        "checks": checks,
        "timestamp": datetime.now().isoformat()
    }
    
    status_code = 200 if overall_status == "healthy" else 503
    return jsonify(response), status_code

# Add start time tracking
app.start_time = time.time()

@app.route('/ready', methods=['GET'])
def readiness():
    """Readiness probe for load balancers"""
    # Only return 200 if service is ready to accept traffic
    try:
        tracker = get_tracker()
        tracker.get_stats()
        return jsonify({"status": "ready"}), 200
    except Exception as e:
        return jsonify({"status": "not_ready", "error": str(e)}), 503
```

---

---

## 7. POSTGRESQL MIGRATION (P0 - 2-3 Days)

### Why PostgreSQL?
- **Scalability**: Handles millions of records
- **ACID compliance**: No data corruption
- **Concurrent access**: Multiple workers can read/write safely
- **Indexing**: Fast queries on any field
- **Free on Render**: Starter tier included

### Step 1: Add PostgreSQL to Render
1. Go to Render dashboard
2. Click "New" → "PostgreSQL"
3. Choose "Free" tier (or Starter for $7/month)
4. Copy connection string (format: `postgresql://user:pass@host/db`)

### Step 2: Install dependencies
```bash
pip install psycopg2-binary sqlalchemy alembic
```

**Add to requirements.txt:**
```
psycopg2-binary==2.9.9
SQLAlchemy==2.0.25
alembic==1.13.1
```

### Step 3: Create database models
**File:** `models/database.py`
```python
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class EmailHistory(Base):
    __tablename__ = 'email_history'

    id = Column(Integer, primary_key=True)
    email = Column(String(254), index=True, nullable=False)
    valid = Column(Boolean, index=True)
    domain = Column(String(255), index=True)

    # Validation results
    syntax_valid = Column(Boolean)
    domain_valid = Column(Boolean)
    mx_records = Column(JSON)

    # Type classification
    is_disposable = Column(Boolean, index=True)
    is_role_based = Column(Boolean, index=True)
    is_catchall = Column(Boolean, index=True)
    catchall_confidence = Column(String(20))

    # SMTP results
    smtp_valid = Column(Boolean)
    mailbox_exists = Column(Boolean)
    smtp_response = Column(Text)

    # Metadata
    deliverability_score = Column(Integer)
    deliverability_rating = Column(String(20))
    validation_time_ms = Column(Integer)

    # Tracking
    session_id = Column(String(50), index=True)
    job_id = Column(String(50), index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Full validation result (JSON)
    full_result = Column(JSON)

class ValidationJob(Base):
    __tablename__ = 'validation_jobs'

    id = Column(Integer, primary_key=True)
    job_id = Column(String(50), unique=True, index=True, nullable=False)

    # Job details
    total_emails = Column(Integer)
    processed_emails = Column(Integer, default=0)
    valid_count = Column(Integer, default=0)
    invalid_count = Column(Integer, default=0)

    # Status
    status = Column(String(20), index=True)  # pending, processing, completed, failed
    progress_percent = Column(Float, default=0.0)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    estimated_completion = Column(DateTime)

    # Results
    result_file = Column(String(255))
    error_message = Column(Text)

    # Settings
    include_smtp = Column(Boolean, default=True)

    # Full job data (JSON)
    job_data = Column(JSON)

class APIKey(Base):
    __tablename__ = 'api_keys'

    id = Column(Integer, primary_key=True)
    key_id = Column(String(50), unique=True, index=True, nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False)

    # Metadata
    name = Column(String(255))
    tier = Column(String(50), default='free')
    active = Column(Boolean, default=True, index=True)

    # Rate limiting
    rate_limit_per_minute = Column(Integer, default=60)

    # Quotas (JSON)
    quotas = Column(JSON)

    # Usage tracking (JSON)
    usage = Column(JSON)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime)
    expires_at = Column(DateTime)

class CRMConfig(Base):
    __tablename__ = 'crm_configs'

    id = Column(Integer, primary_key=True)
    crm_id = Column(String(50), unique=True, index=True, nullable=False)

    # CRM details
    crm_name = Column(String(255))

    # AWS S3 credentials (encrypted)
    aws_access_key_id_encrypted = Column(Text)
    aws_secret_access_key_encrypted = Column(Text)
    s3_bucket_name = Column(String(255))
    s3_region = Column(String(50))

    # Settings (JSON)
    settings = Column(JSON)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CRMUpload(Base):
    __tablename__ = 'crm_uploads'

    id = Column(Integer, primary_key=True)
    upload_id = Column(String(50), unique=True, index=True, nullable=False)
    crm_id = Column(String(50), index=True, nullable=False)

    # Upload details
    total_emails = Column(Integer)
    validation_mode = Column(String(20))  # manual, auto

    # Status
    status = Column(String(20), index=True)  # pending, validating, completed, failed
    progress_percent = Column(Float, default=0.0)

    # Results
    clean_count = Column(Integer, default=0)
    catchall_count = Column(Integer, default=0)
    invalid_count = Column(Integer, default=0)
    disposable_count = Column(Integer, default=0)
    role_based_count = Column(Integer, default=0)

    # S3 delivery
    s3_keys = Column(JSON)  # {clean: s3_key, catchall: s3_key, ...}

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)

    # Full upload data (JSON)
    upload_data = Column(JSON)

class WebhookDelivery(Base):
    __tablename__ = 'webhook_deliveries'

    id = Column(Integer, primary_key=True)
    webhook_id = Column(String(50), unique=True, index=True, nullable=False)

    # Webhook details
    url = Column(String(500))
    payload = Column(JSON)
    upload_id = Column(String(50), index=True)

    # Delivery status
    status = Column(String(20), index=True)  # pending, delivered, failed
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)

    # Response tracking
    last_response_code = Column(Integer)
    last_error = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_attempt_at = Column(DateTime)
    delivered_at = Column(DateTime)

# Database connection
def get_db_engine():
    """Get database engine"""
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        # Fallback to SQLite for local development
        database_url = 'sqlite:///data/email_validator.db'

    # Fix for Render's postgres:// URL (should be postgresql://)
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    engine = create_engine(database_url, pool_pre_ping=True)
    return engine

def get_db_session():
    """Get database session"""
    engine = get_db_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def init_db():
    """Initialize database (create tables)"""
    engine = get_db_engine()
    Base.metadata.create_all(engine)
    print("Database initialized successfully")

if __name__ == '__main__':
    init_db()
```

### Step 4: Create migration script
**File:** `scripts/migrate_to_postgres.py`
```python
#!/usr/bin/env python3
"""Migrate JSON data to PostgreSQL"""

import json
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import (
    init_db, get_db_session,
    EmailHistory, ValidationJob, APIKey, CRMConfig, CRMUpload
)

def migrate_email_history():
    """Migrate email_history.json to PostgreSQL"""
    print("Migrating email history...")

    json_file = 'data/email_history.json'
    if not os.path.exists(json_file):
        print(f"  {json_file} not found, skipping")
        return

    with open(json_file, 'r') as f:
        data = json.load(f)

    session = get_db_session()
    count = 0

    for email, record in data.get('emails', {}).items():
        checks = record.get('checks', {})

        email_record = EmailHistory(
            email=email,
            valid=record.get('valid', False),
            domain=record.get('domain', ''),

            syntax_valid=checks.get('syntax', {}).get('valid', False),
            domain_valid=checks.get('domain', {}).get('valid', False),
            mx_records=checks.get('domain', {}).get('mx_records', []),

            is_disposable=checks.get('type', {}).get('is_disposable', False),
            is_role_based=checks.get('type', {}).get('is_role_based', False),
            is_catchall=checks.get('catchall', {}).get('is_catchall', False),
            catchall_confidence=checks.get('catchall', {}).get('confidence'),

            smtp_valid=checks.get('smtp', {}).get('valid', False),
            mailbox_exists=checks.get('smtp', {}).get('mailbox_exists', False),
            smtp_response=checks.get('smtp', {}).get('smtp_response', ''),

            deliverability_score=record.get('deliverability_score', 0),
            deliverability_rating=record.get('deliverability_rating', 'unknown'),
            validation_time_ms=record.get('validation_time_ms', 0),

            session_id=record.get('session_id', ''),
            job_id=record.get('job_id', ''),
            created_at=datetime.fromisoformat(record['validated_at']) if 'validated_at' in record else datetime.utcnow(),

            full_result=record
        )

        session.add(email_record)
        count += 1

        if count % 100 == 0:
            session.commit()
            print(f"  Migrated {count} emails...")

    session.commit()
    print(f"✓ Migrated {count} email records")

def migrate_validation_jobs():
    """Migrate validation_jobs.json to PostgreSQL"""
    print("Migrating validation jobs...")

    json_file = 'data/validation_jobs.json'
    if not os.path.exists(json_file):
        print(f"  {json_file} not found, skipping")
        return

    with open(json_file, 'r') as f:
        data = json.load(f)

    session = get_db_session()
    count = 0

    for job_id, job_data in data.get('jobs', {}).items():
        job = ValidationJob(
            job_id=job_id,
            total_emails=job_data.get('total', 0),
            processed_emails=job_data.get('processed', 0),
            valid_count=job_data.get('valid', 0),
            invalid_count=job_data.get('invalid', 0),

            status=job_data.get('status', 'unknown'),
            progress_percent=job_data.get('progress', 0.0),

            created_at=datetime.fromisoformat(job_data['created_at']) if 'created_at' in job_data else datetime.utcnow(),
            started_at=datetime.fromisoformat(job_data['started_at']) if 'started_at' in job_data else None,
            completed_at=datetime.fromisoformat(job_data['completed_at']) if 'completed_at' in job_data else None,

            result_file=job_data.get('result_file'),
            error_message=job_data.get('error'),
            include_smtp=job_data.get('include_smtp', True),

            job_data=job_data
        )

        session.add(job)
        count += 1

    session.commit()
    print(f"✓ Migrated {count} validation jobs")

def migrate_api_keys():
    """Migrate api_keys.json to PostgreSQL"""
    print("Migrating API keys...")

    json_file = 'data/api_keys.json'
    if not os.path.exists(json_file):
        print(f"  {json_file} not found, skipping")
        return

    with open(json_file, 'r') as f:
        data = json.load(f)

    session = get_db_session()
    count = 0

    for key_id, key_data in data.get('keys', {}).items():
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_data.get('key_hash', ''),
            name=key_data.get('name', ''),
            tier=key_data.get('tier', 'free'),
            active=key_data.get('active', True),
            rate_limit_per_minute=key_data.get('rate_limit_per_minute', 60),
            quotas=key_data.get('quotas', {}),
            usage=key_data.get('usage', {}),
            created_at=datetime.fromisoformat(key_data['created_at']) if 'created_at' in key_data else datetime.utcnow()
        )

        session.add(api_key)
        count += 1

    session.commit()
    print(f"✓ Migrated {count} API keys")

def migrate_crm_configs():
    """Migrate crm_configs.json to PostgreSQL"""
    print("Migrating CRM configs...")

    json_file = 'data/crm_configs.json'
    if not os.path.exists(json_file):
        print(f"  {json_file} not found, skipping")
        return

    with open(json_file, 'r') as f:
        data = json.load(f)

    session = get_db_session()
    count = 0

    for crm_id, config_data in data.get('configs', {}).items():
        config = CRMConfig(
            crm_id=crm_id,
            crm_name=config_data.get('crm_name', ''),
            aws_access_key_id_encrypted=config_data.get('aws_access_key_id', ''),
            aws_secret_access_key_encrypted=config_data.get('aws_secret_access_key', ''),
            s3_bucket_name=config_data.get('s3_bucket_name', ''),
            s3_region=config_data.get('s3_region', 'us-east-1'),
            settings=config_data.get('settings', {}),
            created_at=datetime.fromisoformat(config_data['created_at']) if 'created_at' in config_data else datetime.utcnow()
        )

        session.add(config)
        count += 1

    session.commit()
    print(f"✓ Migrated {count} CRM configs")

def migrate_crm_uploads():
    """Migrate crm_uploads.json to PostgreSQL"""
    print("Migrating CRM uploads...")

    json_file = 'data/crm_uploads.json'
    if not os.path.exists(json_file):
        print(f"  {json_file} not found, skipping")
        return

    with open(json_file, 'r') as f:
        data = json.load(f)

    session = get_db_session()
    count = 0

    for upload_id, upload_data in data.get('uploads', {}).items():
        results = upload_data.get('results', {})

        upload = CRMUpload(
            upload_id=upload_id,
            crm_id=upload_data.get('crm_id', ''),
            total_emails=upload_data.get('total_emails', 0),
            validation_mode=upload_data.get('validation_mode', 'manual'),
            status=upload_data.get('status', 'pending'),
            progress_percent=upload_data.get('progress', 0.0),

            clean_count=len(results.get('clean', [])),
            catchall_count=len(results.get('catchall', [])),
            invalid_count=len(results.get('invalid', [])),
            disposable_count=len(results.get('disposable', [])),
            role_based_count=len(results.get('role_based', [])),

            s3_keys=upload_data.get('s3_keys', {}),
            created_at=datetime.fromisoformat(upload_data['created_at']) if 'created_at' in upload_data else datetime.utcnow(),
            completed_at=datetime.fromisoformat(upload_data['completed_at']) if 'completed_at' in upload_data else None,

            upload_data=upload_data
        )

        session.add(upload)
        count += 1

    session.commit()
    print(f"✓ Migrated {count} CRM uploads")

if __name__ == '__main__':
    print("=" * 60)
    print("PostgreSQL Migration Script")
    print("=" * 60)
    print()

    # Initialize database
    print("Initializing database schema...")
    init_db()
    print("✓ Database schema created")
    print()

    # Run migrations
    migrate_email_history()
    migrate_validation_jobs()
    migrate_api_keys()
    migrate_crm_configs()
    migrate_crm_uploads()

    print()
    print("=" * 60)
    print("✓ Migration completed successfully!")
    print("=" * 60)
```

### Step 5: Run migration
```bash
# Set DATABASE_URL environment variable
export DATABASE_URL="postgresql://user:pass@host/db"

# Run migration
python scripts/migrate_to_postgres.py
```

### Step 6: Update application code
Replace JSON file operations with SQLAlchemy queries. Example:

**Before (JSON):**
```python
def add_email(self, email: str, result: Dict[str, Any]):
    self.data['emails'][email] = result
    self._save_database()
```

**After (PostgreSQL):**
```python
def add_email(self, email: str, result: Dict[str, Any]):
    from models.database import get_db_session, EmailHistory

    session = get_db_session()
    email_record = EmailHistory(
        email=email,
        valid=result.get('valid'),
        # ... map all fields
        full_result=result
    )
    session.add(email_record)
    session.commit()
```

### Step 7: Deploy to Render
1. Add `DATABASE_URL` environment variable (auto-populated by Render)
2. Push code to GitHub
3. Render will auto-deploy
4. Database tables created automatically on first run

---

## Next Steps

1. **Implement P0 items first** (logging, backups, PostgreSQL)
2. **Test thoroughly** in staging environment
3. **Monitor metrics** after deployment
4. **Iterate** based on real usage patterns

**Estimated Timeline:**
- Week 1: P0 items (logging, PostgreSQL, backups)
- Week 2: P1 items (rate limiting, webhooks, DNS caching)
- Week 3: P2 items (job queue, monitoring, security)
- Week 4: Business features (billing, multi-tenancy)


