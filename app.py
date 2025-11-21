"""
Universal Email Validator Flask Application
Production-grade email validation API with file upload support
"""
from flask import Flask, request, jsonify, render_template, redirect, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
from typing import Dict, Any, List
import hmac
import hashlib
import json
import threading
import time
from urllib.parse import urlparse
import urllib.request
import urllib.error
from uuid import uuid4
from datetime import timedelta

# Optional: Flasgger for interactive API documentation
try:
    from flasgger import Swagger
    FLASGGER_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    Swagger = None  # type: ignore
    FLASGGER_AVAILABLE = False

from modules.syntax_check import validate_syntax
from modules.domain_check import validate_domain
from modules.type_check import validate_type
from modules.smtp_check import validate_smtp
from modules.smtp_check_async import validate_smtp_batch, validate_smtp_batch_with_progress, check_catchall_for_domains
from modules.file_parser import parse_file
from modules.utils import normalize_email, create_validation_result, calculate_deliverability_score, get_deliverability_rating
from modules.email_tracker import get_tracker
from modules.job_tracker import get_job_tracker
from modules.api_auth import require_api_key, get_key_manager
from modules.crm_adapter import (
    parse_crm_request,
    build_crm_response,
    build_segregated_crm_response,
    segregate_validation_results,
    get_crm_event_type,
    validate_crm_vendor
)
from modules.crm_config import get_crm_config_manager
from modules.lead_manager import get_lead_manager
from modules.s3_delivery import S3Delivery, S3DeliveryError
from modules.reporting import generate_csv_report, generate_excel_report, generate_pdf_report
from modules.admin_auth import (
    authenticate_admin,
    create_admin_session,
    destroy_admin_session,
    is_admin_logged_in,
    require_admin_login,
    require_admin_api,
    change_admin_password,
)
from modules.obvious_invalid import is_obviously_invalid
from modules.logger import init_logger, get_logger, PerformanceTimer
from modules.backup_manager import get_backup_manager

app = Flask(__name__)

# Initialize structured logging
logger = init_logger(app)
logger.info("Email Validator application starting", extra={
    'smtp_enabled': os.getenv("SMTP_ENABLED", "false").lower() == "true",
    'environment': os.getenv("ENVIRONMENT", "production")
})

# Global feature flag: controls whether SMTP verification is available anywhere in the app
SMTP_ENABLED = os.getenv("SMTP_ENABLED", "false").lower() == "true"



def run_smtp_validation_background(job_id, emails_to_validate, tracker, include_smtp: bool = True):
    """Run validation in background thread with real-time progress.

    When SMTP is disabled or include_smtp is False, only fast pre-checks
    (syntax/domain/type) are run and the progress bar maps directly 0–100%
    to those checks.
    """
    job_tracker = get_job_tracker()
    validation_results = []

    # Honor global SMTP feature flag: if disabled, force pre-check-only mode.
    effective_include_smtp = include_smtp and SMTP_ENABLED

    # Treat validation as one or two phases depending on effective_include_smtp:
    #  - Phase 1: syntax / domain / type checks (always)
    #  - Phase 2: SMTP checks in parallel (optional)
    total_emails = len(emails_to_validate)
    if total_emails == 0:
        job_tracker.complete_job(job_id, success=True)
        return

    if effective_include_smtp:
        PRECHECK_WEIGHT = 0.4
        SMTP_WEIGHT = 0.6
    else:
        PRECHECK_WEIGHT = 1.0
        SMTP_WEIGHT = 0.0

    start_time = time.time()

    try:
        logger.info("Background validation started", extra={
            'job_id': job_id,
            'email_count': total_emails,
            'include_smtp': effective_include_smtp
        })

        job = job_tracker.get_job(job_id) or {}
        job_session_info = job.get("session_info", {}) if isinstance(job, dict) else {}

        # --------------------
        # Phase 1: Fast checks
        # --------------------
        logger.info("Phase 1: Running syntax/domain/type checks", extra={'job_id': job_id})


        # For smoother real-time updates on large files, update progress more frequently
        # but avoid writing to disk on every single email.
        UPDATE_BATCH_SIZE = 10 if total_emails > 200 else 1
        last_update_time = time.time()

        for i, email in enumerate(emails_to_validate):
            result = validate_email_complete(email, include_smtp=False)
            validation_results.append(result)

            completed_precheck = i + 1


            # Decide whether to push a progress update
            should_update = False
            if completed_precheck % UPDATE_BATCH_SIZE == 0:
                should_update = True

            # Also update at least once per second so ETA doesn't drift upwards
            now = time.time()
            if now - last_update_time >= 1.0:
                should_update = True

            if completed_precheck == total_emails:
                should_update = True

            if should_update:
                valid = sum(1 for r in validation_results if r.get('valid', False))
                invalid = completed_precheck - valid

                disposable = sum(
                    1 for r in validation_results
                    if r.get("checks", {}).get("type", {}).get("is_disposable", False)
                )
                role_based = sum(
                    1 for r in validation_results
                    if r.get("checks", {}).get("type", {}).get("is_role_based", False)
                )
                personal = valid - disposable - role_based

                # Map phase 1 progress into the appropriate portion of the bar.
                # If include_smtp is False, PRECHECK_WEIGHT will be 1.0 so this covers 0-100%.
                if effective_include_smtp:
                    progress_fraction = PRECHECK_WEIGHT * (completed_precheck / total_emails)
                else:
                    progress_fraction = completed_precheck / total_emails

                # Update job tracker with actual count of emails processed so far
                job_tracker.update_progress(
                    job_id,
                    completed_precheck,  # Actual count, not weighted fraction
                    valid,
                    invalid,
                    disposable,
                    role_based,
                    personal,
                )

                logger.debug("Pre-check progress", extra={
                    'job_id': job_id,
                    'completed': completed_precheck,
                    'total': total_emails,
                    'progress_percent': round(progress_fraction * 100, 1)
                })

                last_update_time = now

        logger.info("Phase 1 complete: Pre-checks finished", extra={
            'job_id': job_id,
            'emails_validated': len(validation_results)
        })

        # If SMTP is disabled for this job (or globally), we can finish after pre-checks.
        if not effective_include_smtp:
            final_valid = sum(1 for r in validation_results if r.get("valid", False))
            final_invalid = total_emails - final_valid

            final_disposable = sum(
                1
                for r in validation_results
                if r.get("checks", {}).get("type", {}).get("is_disposable", False)
            )
            final_role_based = sum(
                1
                for r in validation_results
                if r.get("checks", {}).get("type", {}).get("is_role_based", False)
            )
            final_personal = final_valid - final_disposable - final_role_based

            # Catch-all is 0 for pre-check only (no SMTP = no catch-all detection)
            final_catchall = 0

            job_tracker.update_progress(
                job_id,
                total_emails,
                final_valid,
                final_invalid,
                final_disposable,
                final_role_based,
                final_personal,
                final_catchall,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            session_info = {
                "job_id": job_id,
                "session_type": job_session_info.get("session_type", "bulk"),
                "files_processed": job_session_info.get("files_processed"),
                "filenames": job_session_info.get("filenames"),
                "include_smtp": effective_include_smtp,
                "duration_ms": duration_ms,
            }
            tracker.track_emails(emails_to_validate, validation_results, session_info)

            job_tracker.complete_job(job_id, success=True)
            logger.info("Pre-check-only validation complete", extra={
                'job_id': job_id,
                'duration_ms': duration_ms,
                'total_emails': total_emails
            })
            return

        # Build a mapping of email -> domain info from phase 1 so the SMTP
        # phase can reuse DNS/MX results instead of repeating DNS lookups in
        # every worker thread. This reduces external DNS load and makes the
        # SMTP phase more predictable on Render.
        email_domain_map: Dict[str, Dict[str, Any]] = {}
        for result in validation_results:
            email = result.get("email")
            if not email:
                continue
            domain_checks = result.get("checks", {}).get("domain", {})
            email_domain_map[email] = {
                "valid": domain_checks.get("valid", False),
                "has_mx": domain_checks.get("has_mx", False),
                "has_a": domain_checks.get("has_a", False),
                "mx_records": domain_checks.get("mx_records", []),
                "errors": domain_checks.get("errors", []),
            }

        # ---------------------------------
        # Phase 2: SMTP checks with progress
        # ---------------------------------
        def progress_callback(completed_smtp, total_smtp):
            """Update job progress during SMTP phase.

            We treat phase 1 as 40% of the work and phase 2 as 60%.
            This keeps the progress bar moving smoothly for large files.
            """

            # Phase 1 is fully done at this point
            precheck_progress = PRECHECK_WEIGHT
            smtp_progress = SMTP_WEIGHT * (completed_smtp / max(total_smtp, 1))
            total_progress_fraction = min(1.0, precheck_progress + smtp_progress)

            effective_validated = int(total_emails * total_progress_fraction)

            # Only update the overall progress counter here; keep detailed
            # stats (valid/invalid/etc.) from the pre-check phase until we
            # have final SMTP results.
            job_tracker.update_progress(
                job_id,
                effective_validated,
            )

            # For logging, still show current pre-check counts so we can see
            # how many emails look good so far.
            valid_precheck = sum(1 for r in validation_results if r.get("valid", False))
            invalid_precheck = total_emails - valid_precheck

            logger.debug("SMTP validation progress", extra={
                'job_id': job_id,
                'completed_smtp': completed_smtp,
                'total_smtp': total_smtp,
                'progress_percent': round(total_progress_fraction * 100, 1),
                'precheck_valid': valid_precheck,
                'precheck_invalid': invalid_precheck
            })

        max_smtp_workers_env = os.getenv("SMTP_MAX_WORKERS")
        try:
            # Default to a conservative number of workers; we already do DNS in
            # phase 1, so extremely high SMTP concurrency mainly increases the
            # chance of remote throttling/timeouts on providers like Gmail.
            max_smtp_workers = int(max_smtp_workers_env) if max_smtp_workers_env else 20
        except (TypeError, ValueError):
            max_smtp_workers = 20

        if max_smtp_workers < 1:
            max_smtp_workers = 1

        logger.info("Phase 2: Starting SMTP validation", extra={
            'job_id': job_id,
            'max_workers': max_smtp_workers,
            'email_count': len(emails_to_validate)
        })
        smtp_results = validate_smtp_batch_with_progress(
            emails_to_validate,
            max_workers=max_smtp_workers,
            timeout=3,
            sender=None,
            progress_callback=progress_callback,
            email_domain_map=email_domain_map,
        )
        logger.info("SMTP validation complete", extra={
            'job_id': job_id,
            'results_count': len(smtp_results)
        })

        # Check for catch-all domains (done once per domain, not per email)
        logger.info("Checking for catch-all domains", extra={'job_id': job_id})
        catchall_results = check_catchall_for_domains(
            email_domain_map,
            timeout=3,
            sender=None
        )
        logger.info("Catch-all check complete", extra={
            'job_id': job_id,
            'domains_checked': len(catchall_results)
        })

        # Merge SMTP results into validation results
        for i, result in enumerate(validation_results):
            email = result["email"]
            if email in smtp_results:
                smtp_data = smtp_results[email]
                result["checks"]["smtp"] = {
                    "valid": smtp_data.get("valid", False),
                    "mailbox_exists": smtp_data.get("mailbox_exists", False),
                    "smtp_response": smtp_data.get("smtp_response", ""),
                    "errors": smtp_data.get("errors", []),
                    "skipped": smtp_data.get("skipped", False),
                }
                # Update overall validity based on SMTP
                if not smtp_data.get("skipped", False):
                    result["valid"] = result["valid"] and smtp_data.get("valid", False)

            # Add catch-all information (domain-level, not email-level)
            from modules.utils import extract_domain
            domain = extract_domain(email)
            if domain and domain in catchall_results:
                catchall_data = catchall_results[domain]
                result["checks"]["catchall"] = {
                    "is_catchall": catchall_data.get("is_catchall", False),
                    "confidence": catchall_data.get("confidence", "low"),
                    "errors": catchall_data.get("errors", [])
                }

                # If domain is catch-all with high confidence, mark email validity as uncertain
                if catchall_data.get("is_catchall") and catchall_data.get("confidence") == "high":
                    # Don't mark as invalid, but add a warning
                    result.setdefault("warnings", []).append(
                        "Domain is catch-all - mailbox existence cannot be verified"
                    )

        # After merging SMTP results, compute final stats and push one last update
        final_valid = sum(1 for r in validation_results if r.get("valid", False))
        final_invalid = total_emails - final_valid

        final_disposable = sum(
            1
            for r in validation_results
            if r.get("checks", {}).get("type", {}).get("is_disposable", False)
        )
        final_role_based = sum(
            1
            for r in validation_results
            if r.get("checks", {}).get("type", {}).get("is_role_based", False)
        )
        final_personal = final_valid - final_disposable - final_role_based

        # Count catch-all emails
        final_catchall = sum(
            1
            for r in validation_results
            if r.get("checks", {}).get("catchall", {}).get("is_catchall", False)
        )

        job_tracker.update_progress(
            job_id,
            total_emails,
            final_valid,
            final_invalid,
            final_disposable,
            final_role_based,
            final_personal,
            final_catchall,
        )

        # Save results to database
        duration_ms = int((time.time() - start_time) * 1000)
        session_info = {
            "job_id": job_id,
            "session_type": job_session_info.get("session_type", "bulk"),
            "files_processed": job_session_info.get("files_processed"),
            "filenames": job_session_info.get("filenames"),
            "include_smtp": effective_include_smtp,
            "duration_ms": duration_ms,
        }
        tracker.track_emails(emails_to_validate, validation_results, session_info)

        # Mark job as complete
        job_tracker.complete_job(job_id, success=True)
        logger.info("Background validation completed successfully", extra={
            'job_id': job_id,
            'duration_ms': duration_ms,
            'total_emails': total_emails,
            'valid_count': final_valid,
            'invalid_count': final_invalid
        })

    except Exception as smtp_error:
        logger.error("Background validation failed", extra={
            'job_id': job_id,
            'error': str(smtp_error)
        }, exc_info=True)
        job_tracker.complete_job(job_id, success=False, error=str(smtp_error))


# Flask app configuration
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size (increased for large datasets)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['START_TIME'] = time.time()
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'xls', 'xlsx', 'pdf'}
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching for development

# Enable CORS for all routes (allows testing from file:// and other origins)
# In production, restrict origins to specific domains
CORS(app,
     supports_credentials=True,
     origins=["*"],  # Allow all origins for testing
     allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Admin-Token"],
     expose_headers=["Content-Type"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Swagger (if available)
if 'FLASGGER_AVAILABLE' in globals() and FLASGGER_AVAILABLE and Swagger is not None:
    swagger_template = {
        "info": {
            "title": "Universal Email Validator API",
            "description": (
                "Production-grade email validation API with file uploads and CRM "
                "webhook integration.\n\n"
                "Authentication: API key via X-API-Key header. Enable with "
                "API_AUTH_ENABLED=true. Admins manage keys via /api/keys endpoints.\n"
                "Rate limiting: simple per-API-key per-minute limits enforced by "
                "the key manager layer."
            ),
            "version": "1.0.0",
        },
        "basePath": "/",
        "schemes": ["https", "http"],
    }
    swagger = Swagger(app, template=swagger_template)
else:
    swagger = None

# Webhook / remote file configuration
WEBHOOK_SIGNATURE_HEADER = "X-Webhook-Signature"
MAX_REMOTE_FILE_SIZE = 16 * 1024 * 1024  # 16MB safety limit for remote files


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def verify_webhook_signature() -> (bool, str):
    """Verify HMAC signature for incoming webhook requests.

    If WEBHOOK_SIGNING_SECRET is not set, signature verification is skipped
    (useful for local development).

    Returns:
        Tuple of (is_valid, error_message). If is_valid is True, error_message
        will be None.
    """
    secret = os.getenv('WEBHOOK_SIGNING_SECRET')
    if not secret:
        # Signing not configured; treat as valid for now
        return True, None

    signature = request.headers.get(WEBHOOK_SIGNATURE_HEADER)
    if not signature:
        return False, "Missing webhook signature header"

    # Use raw request body for deterministic signing
    body = request.get_data(cache=True) or b""
    expected = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
        return False, "Invalid webhook signature"

    return True, None


def download_remote_file(url: str, max_size: int = MAX_REMOTE_FILE_SIZE, timeout: int = 10):
    """Download a remote file and return its content and a safe filename.

    Args:
        url: HTTP(S) URL of the file to download
        max_size: Maximum number of bytes to read
        timeout: Network timeout in seconds

    Returns:
        Tuple (content_bytes, filename)
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are supported for file_url")

    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            chunks = []
            total = 0
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_size:
                    raise ValueError("Remote file is too large")
                chunks.append(chunk)
    except urllib.error.URLError as e:
        raise ValueError(f"Failed to download remote file: {e}")

    content = b"".join(chunks)
    filename = os.path.basename(parsed.path) or "remote_file"
    filename = secure_filename(filename)
    return content, filename


def start_callback_delivery(callback_url: str, payload: Dict[str, Any], max_retries: int = 3, timeout: int = 10,
                            backoff_factor: float = 1.5) -> None:
    """Kick off background delivery of webhook callback with retries."""

    def _deliver():
        data_bytes = json.dumps(payload).encode('utf-8')
        for attempt in range(1, max_retries + 1):
            try:
                req = urllib.request.Request(
                    callback_url,
                    data=data_bytes,
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    # Consider any 2xx code a success
                    status = getattr(resp, 'status', getattr(resp, 'code', 200))
                    if 200 <= status < 300:
                        return
            except Exception as e:
                if attempt == max_retries:
                    # For now, just log to stdout; in production, route to proper logging
                    print(f"[callback] Failed to deliver to {callback_url} after {max_retries} attempts: {e}")
                else:
                    sleep_time = backoff_factor ** (attempt - 1)
                    time.sleep(sleep_time)

    thread = threading.Thread(target=_deliver, daemon=True)
    thread.start()


def validate_email_complete(email: str, include_smtp: bool = False) -> Dict[str, Any]:
    """
    Perform complete email validation with all checks

    Args:
        email: Email address to validate
        include_smtp: Whether to include SMTP verification (slower)

    Returns:
        Complete validation result dictionary
    """
    email = normalize_email(email)

    # Run all validation checks
    syntax_result = validate_syntax(email)
    domain_result = validate_domain(email)
    type_result = validate_type(email)

    # Collect all errors
    all_errors = []
    all_errors.extend(syntax_result.get("errors", []))
    all_errors.extend(domain_result.get("errors", []))
    all_errors.extend(type_result.get("warnings", []))

    # Determine overall validity
    # Email is valid if syntax and domain are valid
    is_valid = syntax_result["valid"] and domain_result["valid"]

    # Build checks dictionary
    checks = {
        "syntax": {
            "valid": syntax_result["valid"],
            "errors": syntax_result.get("errors", [])
        },
        "domain": {
            "valid": domain_result["valid"],
            "has_mx": domain_result.get("has_mx", False),
            "has_a": domain_result.get("has_a", False),
            "mx_records": domain_result.get("mx_records", []),
            "errors": domain_result.get("errors", [])
        },
        "type": {
            "is_disposable": type_result.get("is_disposable", False),
            "is_role_based": type_result.get("is_role_based", False),
            "email_type": type_result.get("email_type", "unknown"),
            "warnings": type_result.get("warnings", [])
        }
    }

    # Optional SMTP check (only if globally enabled)
    if SMTP_ENABLED and include_smtp and is_valid:
        smtp_result = validate_smtp(email, timeout=10)
        checks["smtp"] = {
            "valid": smtp_result["valid"],
            "mailbox_exists": smtp_result.get("mailbox_exists", False),
            "smtp_response": smtp_result.get("smtp_response", ""),
            "errors": smtp_result.get("errors", []),
            "skipped": smtp_result.get("skipped", False)
        }
        all_errors.extend(smtp_result.get("errors", []))

        # Update overall validity based on SMTP
        if not smtp_result.get("skipped", False):
            is_valid = is_valid and smtp_result["valid"]

    # Create validation result
    result = create_validation_result(email, is_valid, checks, all_errors)

    # Add deliverability scoring (Phase 6)
    deliverability_score = calculate_deliverability_score(result)
    result['deliverability'] = {
        'score': deliverability_score,
        'rating': get_deliverability_rating(deliverability_score)
    }

    return result


@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')


@app.route('/admin')
@require_admin_login
def admin_dashboard():
    """Render admin dashboard"""
    return render_template('admin/dashboard.html')


@app.route('/developer', methods=['GET'])
@require_api_key
def developer_options():
    """Developer & API options view"""
    # Use request.url_root so the endpoint shown in the UI matches the current host
    api_base_url = request.url_root
    return render_template('developer.html', api_base_url=api_base_url)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page and handler"""
    if request.method == 'GET':
        # If already logged in, redirect to dashboard
        if is_admin_logged_in():
            return redirect('/admin')
        return render_template('admin/login.html')

    # POST - handle login
    try:
        data = request.get_json()
        username = data.get('username', '')
        password = data.get('password', '')

        if authenticate_admin(username, password):
            create_admin_session(username)
            next_url = request.args.get('next', '/admin')
            return jsonify({"success": True, "redirect": next_url})
        else:
            return jsonify({"success": False, "error": "Invalid username or password"}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    destroy_admin_session()
    return redirect('/admin/login')


@app.route('/admin/api-keys')
@require_admin_login
def admin_api_keys():
    """Render API keys management page"""
    return render_template('admin/api_keys.html')


@app.route('/admin/api/keys', methods=['GET'])
@require_admin_api
def get_api_keys():
    """Get all API keys"""
    try:
        key_manager = get_key_manager()
        keys = key_manager.list_keys()
        return jsonify({"success": True, "keys": keys})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/keys', methods=['POST'])
@require_admin_api
def create_api_key():
    """Create new API key"""
    try:
        data = request.get_json()
        name = data.get('name', '')
        rate_limit = data.get('rate_limit', 60)

        if not name:
            return jsonify({"success": False, "error": "Key name is required"}), 400

        key_manager = get_key_manager()
        result = key_manager.generate_key(name, rate_limit_per_minute=rate_limit)

        return jsonify({"success": True, "api_key": result["api_key"], "metadata": result["metadata"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/keys/<api_key>', methods=['DELETE'])
@require_admin_api
def revoke_api_key(api_key):
    """Revoke an API key"""
    try:
        key_manager = get_key_manager()
        success = key_manager.revoke_key(api_key)

        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Key not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/emails')
@require_admin_login
def admin_emails():
    """Render email database explorer page"""
    return render_template('admin/emails.html')


@app.route('/admin/api/emails', methods=['GET'])
@require_admin_api
def get_emails():
    """Get all emails from database"""
    try:
        tracker = get_tracker()
        # Force reload from disk to get fresh data (fixes singleton caching issue)
        tracker.data = tracker._load_database()

        emails_data = []

        for email, data in tracker.data.get('emails', {}).items():
            status = data.get('status')
            if not status:
                # Backwards compatible: infer from "valid" flag if no explicit status
                if data.get('valid') is True:
                    status = 'valid'
                elif data.get('valid') is False:
                    status = 'invalid'
                else:
                    status = 'unknown'

            # Do not return hard-deleted entries in the main explorer.
            # We still keep minimal history in the tracker file, but rows
            # with statuses like "deleted_manual" / "deleted_crm" should
            # disappear from this table once removed.
            if status and status.startswith('deleted_'):
                continue

            emails_data.append({
                'email': email,
                'status': status,
                'type': data.get('type', 'unknown'),
                'domain': email.split('@')[1] if '@' in email else '',
                'smtp_verified': data.get('smtp_verified', False),
                'is_catchall': data.get('is_catchall', False),
                'catchall_confidence': data.get('catchall_confidence', 'low'),
                'first_seen': data.get('first_seen', ''),
                'last_validated': data.get('last_validated', ''),
                'validation_count': data.get('validation_count', 0)
            })

        return jsonify({"success": True, "emails": emails_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/emails/reverify', methods=['POST'])
@require_admin_api
def admin_reverify_emails():
    """Re-validate one or more invalid emails.

    Request JSON: {"emails": ["foo@example.com", ...]}
    """
    try:
        data = request.get_json() or {}
        emails = data.get('emails') or []

        if not isinstance(emails, list) or not emails:
            return jsonify({"success": False, "error": "No emails provided"}), 400

        tracker = get_tracker()
        results = []

        for raw_email in emails:
            if not raw_email or not isinstance(raw_email, str):
                continue

            email = raw_email.strip().lower()

            # First, check if this is obviously invalid junk
            is_obvious, reason = is_obviously_invalid(email)
            if is_obvious:
                record = tracker.data.get("emails", {}).get(email, {})
                record["status"] = "disposable"
                record["delete_reason"] = reason or "obvious_invalid"
                record["valid"] = False
                record["is_disposable"] = True
                tracker.data.setdefault("emails", {})[email] = record
                results.append({"email": email, "status": "disposable", "reason": record["delete_reason"]})
                continue

            # Run validation twice max
            first = validate_email_complete(email, include_smtp=True)
            final = first
            if not first.get("valid"):
                second = validate_email_complete(email, include_smtp=True)
                if second.get("valid"):
                    meta = second.setdefault("meta", {})
                    meta["rescued_on_second_pass"] = True
                    final = second
                else:
                    checks = final.setdefault("checks", {})
                    type_checks = checks.setdefault("type", {})
                    type_checks["is_disposable"] = True
                    if not type_checks.get("email_type"):
                        type_checks["email_type"] = "disposable"
                    errors = final.setdefault("errors", [])
                    errors.append({
                        "code": "failed_twice",
                        "message": "Still invalid after re-verify; marked disposable.",
                    })

            # Update tracker with this single-email session
            tracker.track_emails([email], [final], {"session_type": "admin_reverify"})
            results.append({
                "email": email,
                "valid": final.get("valid", False),
                "checks": final.get("checks", {}),
            })

        return jsonify({"success": True, "results": results})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route('/admin/api/emails/delete', methods=['POST'])
@require_admin_api
def admin_delete_emails():
    """Soft-delete disposable emails from the active pool but keep history.

    Request JSON: {"emails": ["foo@example.com", ...]}
    """
    try:
        data = request.get_json() or {}
        emails = data.get('emails') or []

        if not isinstance(emails, list) or not emails:
            return jsonify({"success": False, "error": "No emails provided"}), 400

        tracker = get_tracker()
        deleted = []

        for raw_email in emails:
            if not raw_email or not isinstance(raw_email, str):
                continue

            email = raw_email.strip().lower()
            record = tracker.data.get("emails", {}).get(email)
            if not record:
                continue

            record["status"] = "deleted_manual"
            record["delete_reason"] = "user_deleted"
            tracker.data["emails"][email] = record
            deleted.append(email)

        tracker._save_database()

        return jsonify({"success": True, "deleted": deleted})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500

@app.route('/admin/settings')
@require_admin_login
def admin_settings():
    """Render settings page"""
    return render_template('admin/settings.html')


@app.route('/admin/api/change-password', methods=['POST'])
@require_admin_api
def change_password():
    """Change admin password"""
    try:
        data = request.get_json()
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')

        if change_admin_password(old_password, new_password):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Invalid current password"}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/system-info', methods=['GET'])
@require_admin_api
def get_system_info():
    """Get system information"""
    import sys
    import flask
    try:
        uptime_seconds = time.time() - app.config.get('START_TIME', time.time())
        uptime_str = f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m"

        return jsonify({
            "success": True,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "flask_version": flask.__version__,
            "uptime": uptime_str
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/database-stats', methods=['GET'])
@require_admin_api
def get_database_stats():
    """Get database statistics"""
    try:
        tracker = get_tracker()
        # Force reload from disk to get fresh data
        tracker.data = tracker._load_database()
        stats = tracker.get_stats()

        # Calculate database size
        import os
        db_file = os.path.join(os.path.dirname(__file__), 'data', 'email_history.json')
        db_size = os.path.getsize(db_file) if os.path.exists(db_file) else 0
        db_size_str = f"{db_size / 1024:.2f} KB" if db_size < 1024*1024 else f"{db_size / (1024*1024):.2f} MB"

        return jsonify({
            "success": True,
            "total_emails": stats.get('total_unique_emails', 0),
            "total_sessions": stats.get('total_upload_sessions', 0),
            "database_size": db_size_str
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/config', methods=['POST'])
@require_admin_api
def save_config():
    """Save application configuration"""
    try:
        data = request.get_json()
        # In a real app, save to config file
        # For now, just return success
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/export-database', methods=['GET'])
@require_admin_api
def export_database():
    """Export database as JSON"""
    try:
        tracker = get_tracker()
        return jsonify(tracker.data)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/clear-database', methods=['POST'])
@require_admin_api
def clear_database():
    """Clear all database data"""
    try:
        tracker = get_tracker()
        # Use the tracker's own method to ensure correct structure
        tracker.clear_database()

        # Force reload from disk to clear in-memory cache
        tracker.data = tracker._load_database()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/backup/create', methods=['POST'])
@require_admin_api
def create_backup():
    """Create a manual backup of all database files"""
    try:
        data = request.get_json() or {}
        upload_to_s3 = data.get('upload_to_s3', None)

        backup_manager = get_backup_manager()
        result = backup_manager.create_backup(upload_to_s3=upload_to_s3)

        logger.info("Manual backup created", extra={
            'success': result.get('success'),
            'backup_name': result.get('backup_name'),
            'files_backed_up': result.get('files_backed_up')
        })

        return jsonify(result)
    except Exception as e:
        logger.error("Backup creation failed", extra={'error': str(e)}, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/backup/list', methods=['GET'])
@require_admin_api
def list_backups():
    """List all available backups"""
    try:
        limit = int(request.args.get('limit', 50))
        backup_manager = get_backup_manager()
        backups = backup_manager.list_backups(limit=limit)

        return jsonify({"success": True, "backups": backups, "count": len(backups)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/backup/config', methods=['GET'])
@require_admin_api
def get_backup_config():
    """Get backup configuration"""
    try:
        backup_manager = get_backup_manager()
        config = backup_manager.get_config()

        return jsonify({"success": True, "config": config})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/backup/config', methods=['POST'])
@require_admin_api
def update_backup_config():
    """Update backup configuration"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request body is required"}), 400

        backup_manager = get_backup_manager()
        backup_manager.update_config(data)

        logger.info("Backup configuration updated", extra={'updates': list(data.keys())})

        return jsonify({"success": True, "config": backup_manager.get_config()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/analytics')
@require_admin_login
def admin_analytics():
    """Render analytics page"""
    return render_template('admin/analytics.html')


@app.route('/admin/logs')
@require_admin_login
def admin_logs():
    """Render logs page"""
    return render_template('admin/logs.html')


@app.route('/admin/webhooks')
@require_admin_login
def admin_webhooks():
    """Render webhooks page"""
    return render_template('admin/webhooks.html')


@app.route('/admin/api/logs', methods=['GET'])
@require_admin_api
def get_logs():
    """Get validation logs"""
    try:
        # In a real app, load from log file or database
        # For now, return sample data from tracker sessions
        tracker = get_tracker()
        logs = []

        # Get sessions in reverse order (newest first)
        sessions = tracker.data.get('sessions', [])
        sessions_reversed = list(reversed(sessions))[:100]  # Last 100 sessions

        for session in sessions_reversed:
            # Get filenames from session
            filenames = session.get('filenames', [])
            filename_str = ', '.join(filenames) if filenames else 'N/A'

            emails_count = session.get('emails_count', 0)
            new_emails = session.get('new_emails', 0)
            duplicates = session.get('duplicates', 0)

            # Determine session type (bulk upload vs webhook/CRM)
            session_type = session.get('session_type', 'bulk')

            # Format duration if available
            duration_ms = session.get('duration_ms')
            if isinstance(duration_ms, (int, float)) and duration_ms >= 0:
                if duration_ms < 1000:
                    duration_str = f"{int(duration_ms)}ms"
                elif duration_ms < 60000:
                    duration_str = f"{duration_ms / 1000:.1f}s"
                else:
                    minutes = int(duration_ms // 60000)
                    seconds = int((duration_ms % 60000) // 1000)
                    duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = "-"

            logs.append({
                'timestamp': session.get('timestamp', ''),
                'type': session_type,
                'email': filename_str,
                'filename': filename_str,
                'status': 'success',
                'result': f"{emails_count} emails found ({new_emails} new, {duplicates} duplicates)",
                'duration': duration_str,
                'ip': 'N/A'
            })

        return jsonify({"success": True, "logs": logs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/webhook-logs', methods=['GET'])
@require_admin_api
def get_webhook_logs():
    """Get webhook logs"""
    try:
        # In a real app, load from webhook log file
        # For now, return sample data
        logs = []
        return jsonify({"success": True, "logs": logs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for Render"""
    return jsonify({
        "status": "healthy",
        "service": "email-validator",
        "version": "1.0.0"
    }), 200


@app.route('/api/jobs/<job_id>', methods=['GET'])
@require_api_key
def get_job_status(job_id):
    """Get validation job status and progress"""
    job_tracker = get_job_tracker()
    job = job_tracker.get_job(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Add calculated fields
    job["progress_percent"] = job_tracker.get_progress_percent(job_id)
    job["time_remaining_seconds"] = job_tracker.estimate_time_remaining(job_id)

    return jsonify(job), 200


@app.route('/api/jobs/<job_id>/stream', methods=['GET'])
@require_api_key
def stream_job_progress(job_id):
    """Server-Sent Events stream for real-time job progress"""
    from flask import Response, stream_with_context
    import time

    job_tracker = get_job_tracker()
    job = job_tracker.get_job(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    def generate():
        """Generate SSE events"""
        while True:
            job = job_tracker.get_job(job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            # Send progress update
            progress_data = {
                "job_id": job_id,
                "status": job["status"],
                "validated_count": job["validated_count"],
                "total_emails": job["total_emails"],
                "valid_count": job["valid_count"],
                "invalid_count": job["invalid_count"],
                "disposable_count": job.get("disposable_count", 0),
                "role_based_count": job.get("role_based_count", 0),
                "personal_count": job.get("personal_count", 0),
                "catchall_count": job.get("catchall_count", 0),
                "progress_percent": job_tracker.get_progress_percent(job_id),
                "time_remaining_seconds": job_tracker.estimate_time_remaining(job_id)
            }

            yield f"data: {json.dumps(progress_data)}\n\n"

            # If job is complete, send final update and close
            if job["status"] in ["completed", "failed"]:
                # Send final status with complete counts
                final_data = {
                    **progress_data,
                    "status": "done"
                }
                yield f"data: {json.dumps(final_data)}\n\n"
                break

            # Wait before next update
            time.sleep(1)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/validate', methods=['POST'])
@require_api_key
def validate_single():
    """Validate a single email address
    ---
    tags:
      - Email Validation
    security:
      - ApiKeyAuth: []
    parameters:
      - in: header
        name: X-API-Key
        schema:
          type: string
        required: false
        description: API key for authentication (required when API_AUTH_ENABLED=true)
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - email
            properties:
              email:
                type: string
                example: "user@example.com"
                description: Email address to validate
              include_smtp:
                type: boolean
                default: false
                description: Whether to include SMTP verification (slower)
    responses:
      200:
        description: Validation result
        content:
          application/json:
            schema:
              type: object
              properties:
                email:
                  type: string
                  example: "user@example.com"
                valid:
                  type: boolean
                  example: true
                checks:
                  type: object
                  properties:
                    syntax:
                      type: object
                    domain:
                      type: object
                    type:
                      type: object
                    smtp:
                      type: object
                errors:
                  type: array
                  items:
                    type: string
      400:
        description: Bad request
      401:
        description: Unauthorized (missing or invalid API key)
      429:
        description: Rate limit exceeded
      500:
        description: Server error
    """
    try:
        data = request.get_json()

        if not data or 'email' not in data:
            return jsonify({
                "error": "Missing 'email' field in request body"
            }), 400

        email = data['email']
        include_smtp = data.get('include_smtp', False)

        if not email or not isinstance(email, str):
            return jsonify({
                "error": "Invalid email format"
            }), 400

        result = validate_email_complete(email, include_smtp=include_smtp)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({
            "error": f"Validation error: {str(e)}"
        }), 500


@app.route('/docs', methods=['GET'])
def api_docs():
    """API documentation entrypoint.

    - If Flasgger is installed, redirects to the interactive Swagger UI.
    - Otherwise, returns a JSON summary and setup instructions.
    """
    if swagger is not None:
        # Flasgger's default Swagger UI lives at /apidocs
        return redirect('/apidocs')

    return jsonify({
        "interactive_docs": False,
        "message": "Install 'flasgger' to enable interactive Swagger UI at /docs.",
        "install_command": "pip install flasgger",
        "endpoints": [
            {"path": "/health", "method": "GET", "description": "Service health check"},
            {"path": "/validate", "method": "POST", "description": "Validate a single email"},
            {"path": "/upload", "method": "POST", "description": "Bulk file upload and validation"},
            {"path": "/api/webhook/validate", "method": "POST", "description": "CRM/webhook validation"},
            {"path": "/tracker/stats", "method": "GET", "description": "Email tracker statistics"},
            {"path": "/tracker/export", "method": "GET", "description": "Export tracked emails"},
            {"path": "/export", "method": "POST", "description": "Export validation results as CSV"},
            {"path": "/api/keys", "method": "GET/POST", "description": "Admin API key management"},
        ],
        "authentication": {
            "status": "configurable",
            "header": "X-API-Key",
            "enabled_when": "API_AUTH_ENABLED=true",
            "note": "When enabled, all core validation and tracker endpoints require a valid API key. Admins must set ADMIN_API_TOKEN to manage keys via /api/keys."
        },
    }), 200


@app.route('/upload', methods=['POST'])
@require_api_key
def upload_file():
    """
    Upload and parse single or multiple files to extract and validate emails

    Form data:
    - files[]: One or more CSV, XLS, XLSX, or PDF files
    - validate: "true" to validate extracted emails (optional)
    - include_smtp: "true" to include SMTP checks (optional)
    - batch_size: Number of emails to process per batch (default: 1000)

    Response JSON:
    {
        "files_processed": 2,
        "total_emails_found": 5000,
        "file_results": [...],
        "all_emails": [...],
        "validation_results": [...],  // if validate=true
        "validation_summary": {...},
        "errors": []
    }
    """
    try:
        logger.info("File upload request received", extra={
            'endpoint': '/upload',
            'method': 'POST'
        })

        # Get all uploaded files
        files = request.files.getlist('files[]')

        # Fallback to single file upload for backward compatibility
        if not files:
            if 'file' in request.files:
                files = [request.files['file']]
            else:
                print("[UPLOAD] Error: No files provided")
                return jsonify({
                    "error": "No files provided"
                }), 400

        if not files or all(f.filename == '' for f in files):
            print("[UPLOAD] Error: No files selected")
            return jsonify({
                "error": "No files selected"
            }), 400

        print(f"[UPLOAD] Processing {len(files)} file(s)")

        # Configuration
        should_validate = request.form.get('validate', 'false').lower() == 'true'
        include_smtp = request.form.get('include_smtp', 'false').lower() == 'true'
        batch_size = int(request.form.get('batch_size', 1000))

        print(f"[UPLOAD] Config: validate={should_validate}, smtp={include_smtp}, batch_size={batch_size}")

        # Process all files
        all_emails = []
        file_results = []
        all_errors = []

        for idx, file in enumerate(files):
            if file.filename == '':
                continue

            if not allowed_file(file.filename):
                error_msg = f"File '{file.filename}' type not allowed"
                print(f"[UPLOAD] {error_msg}")
                all_errors.append(error_msg)
                continue

            try:
                # Read and parse file
                filename = secure_filename(file.filename)
                print(f"[UPLOAD] Processing file {idx+1}/{len(files)}: {filename}")

                file_content = file.read()
                file_size_mb = len(file_content) / (1024 * 1024)
                print(f"[UPLOAD] File size: {file_size_mb:.2f} MB")

                parse_result = parse_file(file_content, filename)
                print(f"[UPLOAD] Parsed {filename}, found {len(parse_result.get('emails', []))} emails")

                # Extract file type from summary (new format) or fallback to old format
                summary = parse_result.get("summary", {})
                file_info_data = summary.get("file_info", {})
                extraction_stats = summary.get("extraction_stats", {})

                file_info = {
                    "filename": filename,
                    "file_type": file_info_data.get("file_type", parse_result.get("file_type", "unknown")),
                    "emails_found": extraction_stats.get("emails_extracted", len(parse_result.get("emails", []))),
                    "errors": parse_result.get("errors", []),
                    "summary": summary  # Include full summary for detailed info
                }

                file_results.append(file_info)

                # Extract email strings from new format (emails are now objects with metadata)
                emails_data = parse_result.get("emails", [])
                if emails_data and isinstance(emails_data[0], dict):
                    # New format: extract email strings
                    all_emails.extend([e["email"] for e in emails_data])
                else:
                    # Old format: emails are already strings
                    all_emails.extend(emails_data)

                if parse_result.get("errors"):
                    all_errors.extend([f"{filename}: {err}" for err in parse_result["errors"]])

            except Exception as e:
                all_errors.append(f"Error processing {file.filename}: {str(e)}")

        # Deduplicate emails across all files
        from modules.utils import deduplicate_emails
        all_emails = deduplicate_emails(all_emails)

        # Check for duplicates against historical database
        tracker = get_tracker()
        duplicate_check = tracker.check_duplicates(all_emails)

        # Separate new vs duplicate emails
        new_emails = duplicate_check["new_emails"]
        duplicate_emails = duplicate_check["duplicate_emails"]

        response = {
            "files_processed": len(file_results),
            "total_emails_found": len(all_emails),
            "new_emails_count": len(new_emails),
            "duplicate_emails_count": len(duplicate_emails),
            "file_results": file_results,
            "all_emails": all_emails[:100],  # Return first 100 for preview
            "new_emails": new_emails[:100],  # Preview of new emails
            "duplicate_emails": [d["email"] for d in duplicate_emails[:100]],  # Preview of duplicates
            "total_unique_emails": len(all_emails),
            "deduplication_info": {
                "emails_in_this_upload": len(all_emails),
                "new_emails_never_seen_before": len(new_emails),
                "duplicate_emails_already_in_database": len(duplicate_emails),
                "duplicate_details": duplicate_emails[:20]  # Show first 20 with details
            },
            "errors": all_errors
        }

        # Validate emails if requested (with batching for large datasets)
        # ONLY validate NEW emails to save time and resources
        if should_validate and new_emails:
            print(f"[UPLOAD] Starting validation of {len(new_emails)} new emails...")
            print(f"[UPLOAD] SMTP validation: {include_smtp}")

            # Validate ALL emails (no limits!)
            emails_to_validate = new_emails

            # Create job for progress tracking
            job_tracker = get_job_tracker()
            job_id = job_tracker.create_job(
                total_emails=len(emails_to_validate),
                session_info={
                    "files_processed": len(file_results),
                    "filenames": [f["filename"] for f in file_results],
                    "include_smtp": include_smtp,
                    "session_type": "bulk",
                },
            )
            response["job_id"] = job_id

            print(f"[UPLOAD] Created job {job_id} for {len(emails_to_validate)} emails (SMTP: {include_smtp})")

            # Initialize progress to 0 to show job has started
            job_tracker.update_progress(job_id, 0, 0, 0, 0, 0, 0)

            # Run validation in a background thread (with or without SMTP).
            print(
                f"[UPLOAD] Starting background validation for {len(emails_to_validate)} "
                f"emails (include_smtp={include_smtp})..."
            )
            print(f"[UPLOAD] Sample emails to validate: {emails_to_validate[:3]}")

            def thread_wrapper():
                try:
                    run_smtp_validation_background(
                        job_id,
                        emails_to_validate,
                        tracker,
                        include_smtp=include_smtp,
                    )
                except Exception as e:
                    print(f"[UPLOAD] CRITICAL ERROR in background thread: {e}")
                    import traceback
                    traceback.print_exc()
                    job_tracker.complete_job(job_id, success=False, error=str(e))

            thread = threading.Thread(
                target=thread_wrapper,
                daemon=True,
            )
            thread.start()
            print(f"[UPLOAD] Background validation thread started for job {job_id}")
            print(f"[UPLOAD] Thread is alive: {thread.is_alive()}")

            # Return immediately with job_id - client will stream progress via SSE
            if include_smtp:
                response["message"] = "SMTP validation started in background"
            else:
                response["message"] = "Validation started in background (SMTP disabled)"

            response["validation_status"] = "in_progress"
            # total_emails_found already set in response dict above

            # Return early - validation happening in background
            return jsonify(response), 200
        elif should_validate and not new_emails:
            # All emails are duplicates
            response["validation_summary"] = {
                "message": "All emails are duplicates - no validation performed",
                "duplicates_skipped": len(duplicate_emails)
            }
        else:
            # Not validating, but still track the new emails
            if new_emails:
                session_info = {
                    "files_processed": len(file_results),
                    "filenames": [f["filename"] for f in file_results],
                    "validation_skipped": True,
                    "session_type": "bulk",
                }
                tracking_stats = tracker.track_emails(new_emails, None, session_info)
                response["tracking_stats"] = tracking_stats

        return jsonify(response), 200

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[UPLOAD] ERROR: {error_details}")
        return jsonify({
            "error": f"Upload processing error: {str(e)}"
        }), 500


@app.route('/api/webhook/validate', methods=['POST'])
@require_api_key
def webhook_validate():
    """CRM webhook endpoint for email validation with CRM integration support
    ---
    tags:
      - CRM Integration
    security:
      - ApiKeyAuth: []
    parameters:
      - in: header
        name: X-API-Key
        schema:
          type: string
        required: false
        description: API key for authentication
      - in: header
        name: X-Webhook-Signature
        schema:
          type: string
        required: false
        description: HMAC-SHA256 signature of request body (if WEBHOOK_SIGNING_SECRET is configured)
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              integration_mode:
                type: string
                enum: [single_use, crm]
                default: single_use
                description: Integration mode - use 'crm' for CRM integrations
              crm_vendor:
                type: string
                enum: [salesforce, hubspot, custom, other]
                default: other
                description: CRM vendor identifier
              crm_context:
                type: array
                description: CRM record metadata for mapping results back to CRM
                items:
                  type: object
                  properties:
                    record_id:
                      type: string
                      description: CRM record identifier
                    email:
                      type: string
                      description: Email address to validate
                    list_id:
                      type: string
                      description: Optional list/campaign identifier
              email:
                type: string
                description: Single email to validate
              emails:
                type: array
                items:
                  type: string
                description: Array of emails to validate
              file_url:
                type: string
                description: URL to remote file (CSV/XLS/XLSX/PDF) to download and process
              file_urls:
                type: array
                items:
                  type: string
                description: Array of remote file URLs
              include_smtp:
                type: boolean
                default: false
                description: Include SMTP verification
              response_format:
                type: string
                enum: [standard, segregated]
                default: standard
                description: Response format - 'segregated' returns separate lists (clean, catchall, invalid, etc.)
              include_catchall_in_clean:
                type: boolean
                default: false
                description: Include catch-all emails in clean list (only for segregated format)
              include_role_based_in_clean:
                type: boolean
                default: false
                description: Include role-based emails in clean list (only for segregated format)
              callback_url:
                type: string
                description: URL to receive async validation results
          examples:
            crm_integration:
              summary: CRM Integration Example
              value:
                integration_mode: crm
                crm_vendor: custom
                crm_context:
                  - record_id: "12345"
                    email: "user@example.com"
                    list_id: "prospects-2025-q1"
                callback_url: "https://your-crm.com/webhooks/email-validation"
                include_smtp: false
            simple_validation:
              summary: Simple Email Validation
              value:
                emails: ["user1@example.com", "user2@example.com"]
                include_smtp: false
    responses:
      200:
        description: Synchronous validation results (when no callback_url)
        content:
          application/json:
            schema:
              type: object
              properties:
                event:
                  type: string
                  example: "validation.completed"
                integration_mode:
                  type: string
                crm_vendor:
                  type: string
                summary:
                  type: object
                  properties:
                    total:
                      type: integer
                    valid:
                      type: integer
                    invalid:
                      type: integer
                records:
                  type: array
                  items:
                    type: object
                    properties:
                      email:
                        type: string
                      status:
                        type: string
                        enum: [valid, invalid]
                      crm_record_id:
                        type: string
                      checks:
                        type: object
                      errors:
                        type: array
      202:
        description: Accepted for async processing (when callback_url provided)
      400:
        description: Bad request
      401:
        description: Unauthorized
      429:
        description: Rate limit exceeded
    """
    try:
        # Optional webhook signature verification
        is_valid_sig, sig_error = verify_webhook_signature()
        if not is_valid_sig:
            return jsonify({
                "error": sig_error
            }), 401

        data = request.get_json()

        if not data:
            return jsonify({
                "error": "No JSON data provided"
            }), 400

        # Parse CRM request metadata
        crm_data = parse_crm_request(data)
        integration_mode = crm_data['integration_mode']
        crm_vendor = validate_crm_vendor(crm_data['crm_vendor'])
        crm_context = crm_data['crm_context']

        # Extract options
        include_smtp = data.get('include_smtp', False)
        callback_url = data.get('callback_url')

        # Extract emails from various possible formats
        emails = list(crm_data['emails'])  # Start with emails from crm_context
        file_results = []

        # Remote file URLs
        file_urls = []
        if data.get('file_url'):
            file_urls.append(data['file_url'])
        if isinstance(data.get('file_urls'), list):
            file_urls.extend([u for u in data['file_urls'] if u])

        for url in file_urls:
            try:
                file_content, filename = download_remote_file(url)
                parse_result = parse_file(file_content, filename)

                # Extract file type from summary (new format) or fallback to old format
                summary = parse_result.get("summary", {})
                file_info_data = summary.get("file_info", {})
                extraction_stats = summary.get("extraction_stats", {})

                file_results.append({
                    "source_url": url,
                    "filename": filename,
                    "file_type": file_info_data.get("file_type", parse_result.get("file_type", "unknown")),
                    "emails_found": extraction_stats.get("emails_extracted", len(parse_result.get("emails", []))),
                    "errors": parse_result.get("errors", []),
                })

                # Extract email strings from new format
                emails_data = parse_result.get("emails", [])
                if emails_data and isinstance(emails_data[0], dict):
                    # New format: extract email strings
                    emails.extend([e["email"] for e in emails_data])
                else:
                    # Old format: emails are already strings
                    emails.extend(emails_data)
            except Exception as e:
                file_results.append({
                    "source_url": url,
                    "error": f"Failed to download or parse remote file: {e}",
                    "emails_found": 0,
                })

        # Direct email field
        if 'email' in data:
            emails.append(data['email'])

        # Emails array
        if 'emails' in data and isinstance(data['emails'], list):
            emails.extend(data['emails'])

        # Nested contact object
        if 'contact' in data and isinstance(data['contact'], dict):
            if 'email' in data['contact']:
                emails.append(data['contact']['email'])

        # Data array (for bulk operations)
        if 'data' in data and isinstance(data['data'], list):
            for item in data['data']:
                if isinstance(item, dict) and 'email' in item:
                    emails.append(item['email'])
                elif isinstance(item, str):
                    emails.append(item)

        # Normalize and deduplicate emails
        from modules.utils import deduplicate_emails
        emails = deduplicate_emails(emails)

        if not emails:
            return jsonify({
                "error": "No email addresses found in request"
            }), 400

        # Validate all emails
        results = []
        from datetime import datetime
        tracker = get_tracker()

        results = []
        crm_session_start = datetime.now()

        for email in emails:
            if not email or not isinstance(email, str):
                continue

            # Fast path: obviously garbage -> disposable immediately
            is_obvious, reason = is_obviously_invalid(email)
            if is_obvious:
                checks = {
                    "syntax": {"valid": False, "errors": []},
                    "domain": {
                        "valid": False,
                        "has_mx": False,
                        "has_a": False,
                        "mx_records": [],
                        "errors": [],
                    },
                    "type": {
                        "is_disposable": True,
                        "is_role_based": False,
                        "email_type": "disposable",
                        "warnings": [],
                    },
                }
                errors = [
                    {
                        "code": reason or "obvious_invalid",
                        "message": "Obvious invalid pattern detected in CRM flow; marked disposable.",
                    }
                ]
                result = {
                    "email": email,
                    "valid": False,
                    "checks": checks,
                    "errors": errors,
                }
                results.append(result)
                continue

            # Normal validation with a second-pass retry if first pass is invalid
            result = validate_email_complete(email, include_smtp=include_smtp)
            if not result.get("valid"):
                second_result = validate_email_complete(email, include_smtp=include_smtp)
                if second_result.get("valid"):
                    # Rescued on second pass
                    meta = second_result.setdefault("meta", {})
                    meta["rescued_on_second_pass"] = True
                    result = second_result
                else:
                    # Still invalid after second attempt: treat as disposable
                    checks = result.setdefault("checks", {})
                    type_checks = checks.setdefault("type", {})
                    type_checks["is_disposable"] = True
                    if not type_checks.get("email_type"):
                        type_checks["email_type"] = "disposable"
                    errors = result.setdefault("errors", [])
                    errors.append(
                        {
                            "code": "failed_twice",
                            "message": "Invalid in CRM flow even after second validation; marked disposable.",
                        }
                    )

            results.append(result)

        # Run catch-all detection if SMTP was enabled
        if include_smtp:
            print(f"[CRM] Running catch-all detection for {len(emails)} emails...")

            # Build email-to-domain map for catch-all detection
            from modules.utils import extract_domain
            email_domain_map = {}
            for result in results:
                email = result.get("email")
                if not email:
                    continue
                domain = extract_domain(email)
                if domain and result.get("checks", {}).get("domain", {}).get("valid"):
                    mx_records = result.get("checks", {}).get("domain", {}).get("mx_records", [])
                    if mx_records:
                        email_domain_map[email] = {
                            "domain": domain,
                            "mx_records": mx_records
                        }

            # Check catch-all status for unique domains
            catchall_results = check_catchall_for_domains(
                email_domain_map,
                timeout=3,
                sender=None
            )
            print(f"[CRM] Catch-all check complete for {len(catchall_results)} domains")

            # Merge catch-all results into validation results
            for result in results:
                email = result.get("email")
                if not email:
                    continue
                domain = extract_domain(email)
                if domain and domain in catchall_results:
                    catchall_data = catchall_results[domain]
                    result.setdefault("checks", {})["catchall"] = {
                        "is_catchall": catchall_data.get("is_catchall", False),
                        "confidence": catchall_data.get("confidence", "low"),
                        "errors": catchall_data.get("errors", [])
                    }

                    if catchall_data.get("is_catchall") and catchall_data.get("confidence") == "high":
                        result.setdefault("warnings", []).append(
                            "Domain is catch-all - mailbox existence cannot be verified"
                        )

        # Track these emails so admin explorer stays in sync with CRM validations
        duration_ms = int((datetime.now() - crm_session_start).total_seconds() * 1000)
        tracker.track_emails(
            emails,
            results,
            {
                "session_type": "webhook",
                "integration_mode": integration_mode,
                "crm_vendor": crm_vendor,
                "duration_ms": duration_ms,
            },
        )

        # Build CRM-compatible response
        job_id = str(uuid4()) if callback_url else None
        event_type = get_crm_event_type(success=True, has_errors=False)

        # Check response format preference
        response_format = data.get('response_format', 'standard')

        if response_format == 'segregated':
            # Use new segregated response format
            include_catchall_in_clean = data.get('include_catchall_in_clean', False)
            include_role_based_in_clean = data.get('include_role_based_in_clean', False)

            response = build_segregated_crm_response(
                validation_results=results,
                crm_context=crm_context,
                integration_mode=integration_mode,
                crm_vendor=crm_vendor,
                job_id=job_id,
                include_catchall_in_clean=include_catchall_in_clean,
                include_role_based_in_clean=include_role_based_in_clean,
                event=event_type
            )
        else:
            # Use standard response format (backward compatible)
            response = build_crm_response(
                validation_results=results,
                crm_context=crm_context,
                integration_mode=integration_mode,
                crm_vendor=crm_vendor,
                job_id=job_id,
                event=event_type
            )

        if file_results:
            response["files"] = file_results

        # If a callback_url is provided, send results asynchronously and
        # return an acknowledgment response with a job_id
        if callback_url:
            start_callback_delivery(callback_url, response)

            ack = {
                "status": "accepted",
                "job_id": job_id,
                "callback_url": callback_url,
                "summary": response["summary"],
                "integration_mode": integration_mode,
                "crm_vendor": crm_vendor,
            }
            return jsonify(ack), 202

        # Default: return results synchronously
        return jsonify(response), 200

    except Exception as e:
        # Build error response in CRM format
        error_event = get_crm_event_type(success=False, has_errors=True)
        error_response = {
            "event": error_event,
            "error": f"Webhook processing error: {str(e)}",
            "integration_mode": data.get('integration_mode', 'single_use') if data else 'single_use',
            "crm_vendor": data.get('crm_vendor', 'other') if data else 'other',
        }

        # If callback_url was provided, try to notify about the failure
        if data and data.get('callback_url'):
            try:
                start_callback_delivery(data['callback_url'], error_response)
            except:
                pass  # Best effort

        return jsonify(error_response), 500


# ============================================================================
# HELPER FUNCTIONS FOR CRM S3 DELIVERY
# ============================================================================

def upload_to_s3(upload_id: str, segregated_lists: Dict[str, List], s3_config: Dict[str, Any]) -> Dict[str, Any]:
    """Upload segregated lists to S3"""
    try:
        s3_delivery = S3Delivery(s3_config)
        upload_lists = s3_config.get('upload_lists', {})

        s3_results = {}

        # Upload each list type if enabled
        for list_type, records in segregated_lists.items():
            should_upload = upload_lists.get(list_type, False)

            # Clean list is always uploaded by default
            if list_type == 'clean':
                should_upload = True

            if should_upload and records:
                result = s3_delivery.upload_list(
                    upload_id=upload_id,
                    list_type=list_type,
                    records=records
                )
                s3_results[list_type] = result

        return s3_results

    except S3DeliveryError as e:
        raise Exception(f"S3 delivery error: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected S3 error: {str(e)}")


def send_crm_callback(callback_url: str, response_data: Dict[str, Any], settings: Dict[str, Any]):
    """Send callback to CRM webhook"""
    try:
        # Build callback payload
        payload = json.dumps(response_data).encode('utf-8')

        # Create signature if secret is configured
        signature_secret = settings.get('callback_signature_secret')
        headers = {'Content-Type': 'application/json'}

        if signature_secret:
            signature = hmac.new(
                signature_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            headers['X-Webhook-Signature'] = signature

        # Send POST request
        req = urllib.request.Request(
            callback_url,
            data=payload,
            headers=headers,
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            print(f"[CALLBACK] Sent to {callback_url}, status: {response.status}")

    except Exception as e:
        print(f"[ERROR] Callback delivery failed: {e}")


# ============================================================================
# NEW CRM INTEGRATION ENDPOINTS (Manual & Auto Validation with S3 Delivery)
# ============================================================================

@app.route('/api/crm/leads/upload', methods=['POST'])
@require_api_key
def crm_upload_leads():
    """
    Upload leads for validation (Manual or Auto mode)

    Request body:
    {
        "crm_id": "salesforce_acme_corp",
        "crm_vendor": "salesforce",
        "validation_mode": "manual" or "auto",
        "emails": ["email1@example.com", "email2@example.com"],
        "crm_context": [
            {"record_id": "001", "email": "email1@example.com", "name": "John Doe"},
            {"record_id": "002", "email": "email2@example.com", "name": "Jane Smith"}
        ]
    }

    Returns:
        Upload record with upload_id and status
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request body is required"}), 400

        # Extract required fields
        crm_id = data.get('crm_id')
        crm_vendor = data.get('crm_vendor', 'other')
        validation_mode = data.get('validation_mode', 'manual')
        emails = data.get('emails', [])
        crm_context = data.get('crm_context', [])

        # Validate inputs
        if not crm_id:
            return jsonify({"error": "crm_id is required"}), 400

        if not emails:
            return jsonify({"error": "emails array is required"}), 400

        if validation_mode not in ['manual', 'auto']:
            return jsonify({"error": "validation_mode must be 'manual' or 'auto'"}), 400

        # Get CRM configuration
        config_manager = get_crm_config_manager()
        crm_config = config_manager.get_config(crm_id)

        if not crm_config:
            return jsonify({
                "error": f"CRM configuration not found for crm_id: {crm_id}",
                "hint": "Create CRM configuration first using /api/crm/config endpoint"
            }), 404

        # Check if auto-validation is allowed
        if validation_mode == 'auto':
            premium_features = crm_config.get('premium_features', {})
            if not premium_features.get('auto_validate', False):
                return jsonify({
                    "error": "Auto-validation is not enabled for this CRM",
                    "hint": "Enable auto_validate premium feature in CRM configuration"
                }), 403

        # Create upload record
        lead_manager = get_lead_manager()
        settings = crm_config.get('settings', {})

        upload = lead_manager.create_upload(
            crm_id=crm_id,
            crm_vendor=crm_vendor,
            emails=emails,
            crm_context=crm_context,
            validation_mode=validation_mode,
            settings=settings
        )

        # If auto-validation mode, trigger validation immediately
        if validation_mode == 'auto':
            # Create validation job
            job_tracker = get_job_tracker()
            job_id = f"job_{uuid4().hex[:12]}"

            job_tracker.create_job(
                job_id=job_id,
                total_emails=len(emails),
                session_info={
                    'upload_id': upload['upload_id'],
                    'crm_id': crm_id,
                    'validation_mode': 'auto'
                }
            )

            # Update upload with job_id
            lead_manager.start_validation(upload['upload_id'], job_id)

            # Start background validation
            include_smtp = settings.get('enable_smtp', True) and SMTP_ENABLED

            def run_auto_validation():
                """Run validation and S3 delivery in background"""
                try:
                    # Run validation
                    run_smtp_validation_background(
                        job_id=job_id,
                        emails_to_validate=emails,
                        tracker=get_tracker(),
                        include_smtp=include_smtp
                    )

                    # Get validation results
                    job = job_tracker.get_job(job_id)
                    if not job or not job.get('success'):
                        lead_manager.fail_validation(
                            upload['upload_id'],
                            error="Validation job failed"
                        )
                        return

                    # Get tracked results
                    tracker = get_tracker()
                    validation_results = []
                    for email in emails:
                        result = tracker.get_email(email)
                        if result:
                            validation_results.append(result)

                    # Segregate results
                    include_catchall_in_clean = settings.get('include_catchall_in_clean', False)
                    include_role_based_in_clean = settings.get('include_role_based_in_clean', False)

                    # Build segregated response
                    response = build_segregated_crm_response(
                        validation_results=validation_results,
                        crm_context=crm_context,
                        integration_mode='crm',
                        crm_vendor=crm_vendor,
                        upload_id=upload['upload_id'],
                        job_id=job_id,
                        include_catchall_in_clean=include_catchall_in_clean,
                        include_role_based_in_clean=include_role_based_in_clean
                    )

                    # S3 delivery if enabled
                    s3_delivery_info = None
                    s3_config = settings.get('s3_delivery', {})
                    if s3_config.get('enabled', False):
                        try:
                            s3_delivery_info = upload_to_s3(
                                upload_id=upload['upload_id'],
                                segregated_lists=response['lists'],
                                s3_config=s3_config
                            )
                        except Exception as e:
                            print(f"[ERROR] S3 delivery failed: {e}")

                    # Complete upload
                    lead_manager.complete_validation(
                        upload['upload_id'],
                        results=response,
                        s3_delivery=s3_delivery_info
                    )

                    # Send callback if configured
                    callback_url = settings.get('callback_url')
                    if callback_url:
                        send_crm_callback(callback_url, response, settings)

                except Exception as e:
                    print(f"[ERROR] Auto-validation failed: {e}")
                    lead_manager.fail_validation(upload['upload_id'], error=str(e))

            # Start background thread
            thread = threading.Thread(target=run_auto_validation, daemon=True)
            thread.start()

            return jsonify({
                "success": True,
                "upload_id": upload['upload_id'],
                "job_id": job_id,
                "status": "validating",
                "validation_mode": "auto",
                "email_count": len(emails),
                "message": "Auto-validation started. Check status at /api/crm/leads/{upload_id}/status"
            }), 202

        # Manual mode - return upload record
        return jsonify({
            "success": True,
            "upload_id": upload['upload_id'],
            "status": "pending_validation",
            "validation_mode": "manual",
            "email_count": len(emails),
            "message": "Upload created. Trigger validation with POST /api/crm/leads/{upload_id}/validate"
        }), 201

    except Exception as e:
        print(f"[ERROR] Upload leads failed: {e}")
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


@app.route('/api/crm/leads/<upload_id>/validate', methods=['POST'])
@require_api_key
def crm_validate_leads(upload_id):
    """
    Trigger validation for uploaded leads (Manual mode only)

    Returns:
        Job information and status
    """
    try:
        lead_manager = get_lead_manager()
        upload = lead_manager.get_upload(upload_id)

        if not upload:
            return jsonify({"error": f"Upload not found: {upload_id}"}), 404

        # Check if already validating or completed
        status = upload.get('status')
        if status == 'validating':
            return jsonify({
                "error": "Validation already in progress",
                "upload_id": upload_id,
                "job_id": upload.get('job_id'),
                "status": status
            }), 409

        if status == 'completed':
            return jsonify({
                "error": "Validation already completed",
                "upload_id": upload_id,
                "status": status,
                "hint": "Get results at /api/crm/leads/{upload_id}/results"
            }), 409

        # Check if manual mode
        if upload.get('validation_mode') != 'manual':
            return jsonify({
                "error": "This upload is in auto-validation mode",
                "upload_id": upload_id,
                "validation_mode": upload.get('validation_mode')
            }), 400

        # Create validation job
        job_tracker = get_job_tracker()
        job_id = f"job_{uuid4().hex[:12]}"
        emails = upload.get('emails', [])

        job_tracker.create_job(
            job_id=job_id,
            total_emails=len(emails),
            session_info={
                'upload_id': upload_id,
                'crm_id': upload.get('crm_id'),
                'validation_mode': 'manual'
            }
        )

        # Update upload status
        lead_manager.start_validation(upload_id, job_id)

        # Get settings
        settings = upload.get('settings', {})
        include_smtp = settings.get('enable_smtp', True) and SMTP_ENABLED

        # Start background validation
        def run_manual_validation():
            """Run validation and S3 delivery in background"""
            try:
                # Run validation
                run_smtp_validation_background(
                    job_id=job_id,
                    emails_to_validate=emails,
                    tracker=get_tracker(),
                    include_smtp=include_smtp
                )

                # Get validation results
                job = job_tracker.get_job(job_id)
                if not job or not job.get('success'):
                    lead_manager.fail_validation(
                        upload_id,
                        error="Validation job failed"
                    )
                    return

                # Get tracked results
                tracker = get_tracker()
                validation_results = []
                for email in emails:
                    result = tracker.get_email(email)
                    if result:
                        validation_results.append(result)

                # Build segregated response
                include_catchall_in_clean = settings.get('include_catchall_in_clean', False)
                include_role_based_in_clean = settings.get('include_role_based_in_clean', False)

                response = build_segregated_crm_response(
                    validation_results=validation_results,
                    crm_context=upload.get('crm_context', []),
                    integration_mode='crm',
                    crm_vendor=upload.get('crm_vendor', 'other'),
                    upload_id=upload_id,
                    job_id=job_id,
                    include_catchall_in_clean=include_catchall_in_clean,
                    include_role_based_in_clean=include_role_based_in_clean
                )

                # S3 delivery if enabled
                s3_delivery_info = None
                s3_config = settings.get('s3_delivery', {})
                if s3_config.get('enabled', False):
                    try:
                        s3_delivery_info = upload_to_s3(
                            upload_id=upload_id,
                            segregated_lists=response['lists'],
                            s3_config=s3_config
                        )
                    except Exception as e:
                        print(f"[ERROR] S3 delivery failed: {e}")

                # Complete upload
                lead_manager.complete_validation(
                    upload_id,
                    results=response,
                    s3_delivery=s3_delivery_info
                )

                # Send callback if configured
                callback_url = settings.get('callback_url')
                if callback_url:
                    send_crm_callback(callback_url, response, settings)

            except Exception as e:
                print(f"[ERROR] Manual validation failed: {e}")
                lead_manager.fail_validation(upload_id, error=str(e))

        # Start background thread
        thread = threading.Thread(target=run_manual_validation, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "upload_id": upload_id,
            "job_id": job_id,
            "status": "validating",
            "email_count": len(emails),
            "message": "Validation started. Check status at /api/crm/leads/{upload_id}/status"
        }), 202

    except Exception as e:
        print(f"[ERROR] Validate leads failed: {e}")
        return jsonify({"error": f"Validation failed: {str(e)}"}), 500


@app.route('/api/crm/leads/<upload_id>/status', methods=['GET'])
@require_api_key
def crm_get_upload_status(upload_id):
    """Get upload and validation status"""
    try:
        lead_manager = get_lead_manager()
        upload = lead_manager.get_upload(upload_id)

        if not upload:
            return jsonify({"error": f"Upload not found: {upload_id}"}), 404

        # Build status response
        response = {
            "upload_id": upload_id,
            "status": upload.get('status'),
            "validation_mode": upload.get('validation_mode'),
            "email_count": upload.get('email_count'),
            "created_at": upload.get('created_at'),
            "updated_at": upload.get('updated_at')
        }

        # Add job progress if validating
        if upload.get('status') == 'validating' and upload.get('job_id'):
            job_tracker = get_job_tracker()
            job = job_tracker.get_job(upload['job_id'])
            if job:
                response['job'] = {
                    'job_id': upload['job_id'],
                    'progress': job.get('progress', 0),
                    'status': job.get('status'),
                    'completed': job.get('completed', 0),
                    'total': job.get('total', 0)
                }

        # Add summary if completed
        if upload.get('status') == 'completed' and upload.get('results'):
            results = upload['results']
            response['summary'] = results.get('summary', {})
            response['validated_at'] = upload.get('validated_at')

            # Add S3 delivery info if available
            if upload.get('s3_delivery'):
                response['s3_delivery'] = upload['s3_delivery']

        # Add error if failed
        if upload.get('status') == 'failed':
            response['error'] = upload.get('error')

        return jsonify(response), 200

    except Exception as e:
        print(f"[ERROR] Get upload status failed: {e}")
        return jsonify({"error": f"Status check failed: {str(e)}"}), 500


@app.route('/api/crm/leads/<upload_id>/results', methods=['GET'])
@require_api_key
def crm_get_upload_results(upload_id):
    """Get validation results for upload"""
    try:
        lead_manager = get_lead_manager()
        upload = lead_manager.get_upload(upload_id)

        if not upload:
            return jsonify({"error": f"Upload not found: {upload_id}"}), 404

        if upload.get('status') != 'completed':
            return jsonify({
                "error": "Validation not completed yet",
                "upload_id": upload_id,
                "status": upload.get('status'),
                "hint": "Check status at /api/crm/leads/{upload_id}/status"
            }), 409

        # Return full results
        results = upload.get('results', {})

        # Add S3 delivery info
        if upload.get('s3_delivery'):
            results['s3_delivery'] = upload['s3_delivery']

        return jsonify(results), 200

    except Exception as e:
        print(f"[ERROR] Get upload results failed: {e}")
        return jsonify({"error": f"Results retrieval failed: {str(e)}"}), 500


@app.route('/api/crm/config', methods=['POST'])
@require_api_key
def crm_create_config():
    """
    Create CRM configuration

    Request body:
    {
        "crm_id": "salesforce_acme_corp",
        "crm_vendor": "salesforce",
        "api_key": "sk_live_...",
        "settings": {
            "auto_validate": false,
            "enable_smtp": true,
            "enable_catchall": true,
            "include_catchall_in_clean": false,
            "include_role_based_in_clean": false,
            "callback_url": "https://crm.example.com/webhook",
            "s3_delivery": {
                "enabled": true,
                "bucket_name": "acme-validated-leads",
                "region": "us-east-1",
                "access_key_id": "AKIA...",
                "secret_access_key": "...",
                "upload_lists": {
                    "clean": true,
                    "catchall": false,
                    "invalid": false
                }
            }
        },
        "premium_features": {
            "auto_validate": false,
            "s3_delivery": true
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request body is required"}), 400

        crm_id = data.get('crm_id')
        if not crm_id:
            return jsonify({"error": "crm_id is required"}), 400

        # Create configuration
        config_manager = get_crm_config_manager()

        # Check if config already exists
        existing = config_manager.get_config(crm_id)
        if existing:
            return jsonify({
                "error": f"Configuration already exists for crm_id: {crm_id}",
                "hint": "Use PUT /api/crm/config/{crm_id} to update"
            }), 409

        # Test S3 connection if S3 delivery is enabled
        s3_config = data.get('settings', {}).get('s3_delivery', {})
        if s3_config.get('enabled', False):
            try:
                s3_delivery = S3Delivery(s3_config)
                test_result = s3_delivery.test_connection()
                if not test_result.get('success'):
                    return jsonify({
                        "error": "S3 connection test failed",
                        "details": test_result.get('error')
                    }), 400
            except S3DeliveryError as e:
                return jsonify({
                    "error": "Invalid S3 configuration",
                    "details": str(e)
                }), 400

        # Create config
        config = config_manager.create_config(crm_id, data)

        # Remove sensitive data from response
        if 's3_delivery' in config.get('settings', {}):
            s3_settings = config['settings']['s3_delivery']
            if 'secret_access_key' in s3_settings:
                del s3_settings['secret_access_key']
            if 'secret_access_key_encrypted' in s3_settings:
                s3_settings['secret_access_key_encrypted'] = '***ENCRYPTED***'

        return jsonify({
            "success": True,
            "config": config,
            "message": "CRM configuration created successfully"
        }), 201

    except Exception as e:
        print(f"[ERROR] Create CRM config failed: {e}")
        return jsonify({"error": f"Configuration creation failed: {str(e)}"}), 500


@app.route('/api/crm/config/<crm_id>', methods=['GET'])
@require_api_key
def crm_get_config(crm_id):
    """Get CRM configuration"""
    try:
        config_manager = get_crm_config_manager()
        config = config_manager.get_config(crm_id)

        if not config:
            return jsonify({"error": f"Configuration not found for crm_id: {crm_id}"}), 404

        # Remove sensitive data from response
        if 's3_delivery' in config.get('settings', {}):
            s3_settings = config['settings']['s3_delivery']
            if 'secret_access_key' in s3_settings:
                del s3_settings['secret_access_key']
            if 'secret_access_key_encrypted' in s3_settings:
                s3_settings['secret_access_key_encrypted'] = '***ENCRYPTED***'

        return jsonify(config), 200

    except Exception as e:
        print(f"[ERROR] Get CRM config failed: {e}")
        return jsonify({"error": f"Configuration retrieval failed: {str(e)}"}), 500


@app.route('/api/crm/config/<crm_id>', methods=['PUT'])
@require_api_key
def crm_update_config(crm_id):
    """Update CRM configuration"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request body is required"}), 400

        config_manager = get_crm_config_manager()

        # Check if config exists
        existing = config_manager.get_config(crm_id)
        if not existing:
            return jsonify({
                "error": f"Configuration not found for crm_id: {crm_id}",
                "hint": "Use POST /api/crm/config to create"
            }), 404

        # Test S3 connection if S3 settings are being updated
        if 'settings' in data and 's3_delivery' in data['settings']:
            s3_config = data['settings']['s3_delivery']
            if s3_config.get('enabled', False):
                try:
                    s3_delivery = S3Delivery(s3_config)
                    test_result = s3_delivery.test_connection()
                    if not test_result.get('success'):
                        return jsonify({
                            "error": "S3 connection test failed",
                            "details": test_result.get('error')
                        }), 400
                except S3DeliveryError as e:
                    return jsonify({
                        "error": "Invalid S3 configuration",
                        "details": str(e)
                    }), 400

        # Update config
        config = config_manager.update_config(crm_id, data)

        # Remove sensitive data from response
        if 's3_delivery' in config.get('settings', {}):
            s3_settings = config['settings']['s3_delivery']
            if 'secret_access_key' in s3_settings:
                del s3_settings['secret_access_key']
            if 'secret_access_key_encrypted' in s3_settings:
                s3_settings['secret_access_key_encrypted'] = '***ENCRYPTED***'

        return jsonify({
            "success": True,
            "config": config,
            "message": "CRM configuration updated successfully"
        }), 200

    except Exception as e:
        print(f"[ERROR] Update CRM config failed: {e}")
        return jsonify({"error": f"Configuration update failed: {str(e)}"}), 500


@app.route('/tracker/stats', methods=['GET'])
@require_api_key
def get_tracker_stats():
    """
    Get email tracker statistics

    Returns:
        JSON with tracking statistics
    """
    try:
        tracker = get_tracker()
        stats = tracker.get_stats()

        return jsonify({
            "success": True,
            "stats": stats
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"Error getting tracker stats: {str(e)}"
        }), 500


@app.route('/tracker/export', methods=['GET'])
@require_api_key
def export_tracked_emails():
    """
    Export all tracked emails

    Query params:
    - valid_only: "true" to export only validated emails
    - format: "json" or "csv" (default: json)

    Returns:
        List of tracked emails
    """
    try:
        tracker = get_tracker()
        valid_only = request.args.get('valid_only', 'false').lower() == 'true'
        export_format = request.args.get('format', 'json').lower()

        emails = tracker.export_emails(valid_only=valid_only)

        if export_format == 'csv':
            import io
            import csv
            from flask import make_response

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Email'])
            for email in emails:
                writer.writerow([email])

            output.seek(0)
            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/csv; charset=utf-8'
            response.headers['Content-Disposition'] = 'attachment; filename=tracked_emails.csv'
            response.headers['Cache-Control'] = 'no-cache'
            return response
        else:
            return jsonify({
                "success": True,
                "total_emails": len(emails),
                "emails": emails
            }), 200

    except Exception as e:
        return jsonify({
            "error": f"Error exporting emails: {str(e)}"
        }), 500


@app.route('/tracker/clear', methods=['POST'])
@require_api_key
def clear_tracker():
    """
    Clear all tracked emails (use with caution!)

    Requires confirmation in request body:
    {
        "confirm": "CLEAR_ALL_DATA"
    }
    """
    try:
        data = request.get_json()

        if not data or data.get('confirm') != 'CLEAR_ALL_DATA':
            return jsonify({
                "error": "Confirmation required. Send {\"confirm\": \"CLEAR_ALL_DATA\"} to proceed."
            }), 400

        tracker = get_tracker()
        tracker.clear_database()

        return jsonify({
            "success": True,
            "message": "All tracked emails have been cleared"
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"Error clearing tracker: {str(e)}"
        }), 500


@app.route('/export', methods=['POST'])
@require_api_key
def export_results():
    """Export validation results as CSV.

    Request JSON:
        {
            "results": [...],  // Array of validation results
            "format": "csv"    // Export format (currently only CSV)
        }

    Returns CSV file download.
    """
    try:
        data = request.get_json()

        if not data or 'results' not in data:
            return jsonify({
                "error": "Missing 'results' in request body"
            }), 400

        results = data['results']
        export_format = data.get('format', 'csv').lower()

        if export_format != 'csv':
            return jsonify({
                "error": "Only CSV format is currently supported"
            }), 400

        # Generate CSV
        import io
        import csv

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Email', 'Valid', 'Syntax Valid', 'Domain Valid',
            'Email Type', 'Is Disposable', 'Is Role-Based', 'Errors'
        ])

        # Write data
        for result in results:
            email = result.get('email', '')
            valid = result.get('valid', False)
            checks = result.get('checks', {})

            syntax_valid = checks.get('syntax', {}).get('valid', False)
            domain_valid = checks.get('domain', {}).get('valid', False)

            type_info = checks.get('type', {})
            email_type = type_info.get('email_type', 'unknown')
            is_disposable = type_info.get('is_disposable', False)
            is_role_based = type_info.get('is_role_based', False)

            errors = '; '.join(result.get('errors', []))

            writer.writerow([
                email, valid, syntax_valid, domain_valid,
                email_type, is_disposable, is_role_based, errors
            ])

        # Prepare response
        output.seek(0)
        from flask import make_response

        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=validation_results.csv'

        return response

    except Exception as e:
        return jsonify({
            "error": f"Export error: {str(e)}"
        }), 500


@app.route('/api/keys', methods=['POST'])
def create_api_key_legacy():
    """Create a new API key (admin-only) - Legacy endpoint.

    Requires the X-Admin-Token header to match ADMIN_API_TOKEN env var.
    """
    admin_token = os.getenv('ADMIN_API_TOKEN')
    if not admin_token or request.headers.get('X-Admin-Token') != admin_token:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or {}
    name = data.get('name', 'default')
    rate_raw = data.get('rate_limit_per_minute', 60)
    try:
        rate_limit = int(rate_raw)
    except (TypeError, ValueError):
        rate_limit = 60

    manager = get_key_manager()
    result = manager.generate_key(name=name, rate_limit_per_minute=rate_limit)
    return jsonify(result), 201


@app.route('/api/keys', methods=['GET'])
def list_api_keys_legacy():
    """List existing API keys (admin-only, secret not included) - Legacy endpoint."""
    admin_token = os.getenv('ADMIN_API_TOKEN')
    if not admin_token or request.headers.get('X-Admin-Token') != admin_token:
        return jsonify({"error": "Unauthorized"}), 401

    manager = get_key_manager()
    return jsonify({"keys": manager.list_keys()}), 200


@app.route('/api/keys/<key_id>', methods=['DELETE'])
def revoke_api_key_legacy(key_id):
    """Revoke (deactivate) an API key (admin-only) - Legacy endpoint."""
    admin_token = os.getenv('ADMIN_API_TOKEN')
    if not admin_token or request.headers.get('X-Admin-Token') != admin_token:
        return jsonify({"error": "Unauthorized"}), 401

    manager = get_key_manager()
    if not manager.revoke_key(key_id):
        return jsonify({"error": "API key not found"}), 404

    return jsonify({"success": True, "key_id": key_id}), 200


@app.route('/api/keys/<key_id>/usage', methods=['GET'])
def get_api_key_usage(key_id):
    """Get usage statistics for a specific API key (admin-only)."""
    admin_token = os.getenv('ADMIN_API_TOKEN')
    if not admin_token or request.headers.get('X-Admin-Token') != admin_token:
        return jsonify({"error": "Unauthorized"}), 401

    manager = get_key_manager()
    usage = manager.get_usage(key_id)
    if not usage:
        return jsonify({"error": "API key not found"}), 404

    return jsonify({"usage": usage}), 200


# ============================================================================
# ANALYTICS ENDPOINTS (Phase 6)
# ============================================================================

def calculate_email_type_distribution(tracker):
    """Calculate email type distribution from tracker data"""
    # This would require storing type info in tracker - for now return placeholder
    # In production, we'd enhance the tracker to store validation results
    return {
        "personal": {"count": 0, "percentage": 0},
        "role_based": {"count": 0, "percentage": 0},
        "disposable": {"count": 0, "percentage": 0},
        "invalid": {"count": 0, "percentage": 0}
    }


def calculate_validation_trends(tracker):
    """Calculate validation trends from session data"""
    from datetime import datetime, timedelta
    from collections import defaultdict

    sessions = tracker.data.get("sessions", [])

    # Group by date
    daily_stats = defaultdict(lambda: {"total": 0, "valid": 0, "invalid": 0})

    for session in sessions:
        timestamp = session.get("timestamp", "")
        if timestamp:
            try:
                date = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d")
                emails_count = session.get("emails_count", 0)
                daily_stats[date]["total"] += emails_count
                # For now, assume all are valid - in production we'd track this
                daily_stats[date]["valid"] += emails_count
            except:
                pass

    # Convert to list and sort by date
    trends = []
    for date in sorted(daily_stats.keys(), reverse=True)[:30]:  # Last 30 days
        trends.append({
            "date": date,
            "total": daily_stats[date]["total"],
            "valid": daily_stats[date]["valid"],
            "invalid": daily_stats[date]["invalid"]
        })

    return {"daily": list(reversed(trends))}  # Oldest first


def calculate_top_domains(tracker):
    """Calculate top domains from tracked emails"""
    from collections import Counter

    emails = tracker.data.get("emails", {})
    domains = []

    for email in emails.keys():
        if '@' in email:
            domain = email.split('@')[1]
            domains.append(domain)

    # Count domains
    domain_counts = Counter(domains)

    # Get top 10
    top_domains = []
    for domain, count in domain_counts.most_common(10):
        top_domains.append({
            "domain": domain,
            "count": count,
            "valid_percentage": 100.0  # Placeholder - would need validation data
        })

    return top_domains


def calculate_domain_reputation(tracker):
    """Calculate domain reputation scores"""
    top_domains = calculate_top_domains(tracker)

    reputation = {}
    for domain_info in top_domains:
        domain = domain_info["domain"]
        reputation[domain] = {
            "score": int(domain_info["valid_percentage"]),
            "total_validated": domain_info["count"],
            "success_rate": domain_info["valid_percentage"]
        }

    return reputation


@app.route('/admin/analytics/data', methods=['GET'])
def get_analytics_data():
    """
    Get analytics data for admin dashboard.
    Returns KPIs, trends, and domain statistics from real data.
    """
    tracker = get_tracker()
    # Force reload from disk to get fresh data
    tracker.data = tracker._load_database()
    stats = tracker.get_stats()

    # Get email data
    emails_data = tracker.data.get("emails", {})
    total_emails = len(emails_data)

    # Calculate KPIs from real data
    kpis = {
        "total_emails": total_emails,
        "valid_emails": total_emails,  # Placeholder - would need validation status
        "invalid_emails": 0,  # Placeholder
        "valid_percentage": 100.0 if total_emails > 0 else 0,
        "total_validations": stats.get("total_upload_sessions", 0),
        "duplicates_prevented": stats.get("total_duplicates_prevented", 0)
    }

    # Calculate email type distribution
    email_type_dist = calculate_email_type_distribution(tracker)

    # Calculate validation trends
    validation_trends = calculate_validation_trends(tracker)

    # Calculate top domains
    top_domains = calculate_top_domains(tracker)

    # Calculate domain reputation
    domain_reputation = calculate_domain_reputation(tracker)

    # Get API key stats
    try:
        manager = get_key_manager()
        all_keys = manager.list_keys()
        active_keys = sum(1 for k in all_keys if k.get("active", False))
    except:
        active_keys = 0

    # Add email types for analytics page
    email_types = {
        "personal": sum(1 for e in emails_data.values() if e.get('type') == 'personal'),
        "business": sum(1 for e in emails_data.values() if e.get('type') == 'business'),
        "role": sum(1 for e in emails_data.values() if e.get('type') == 'role'),
        "disposable": sum(1 for e in emails_data.values() if e.get('type') == 'disposable')
    }

    # Add additional KPIs for analytics page
    kpis["total_validations"] = stats.get("total_upload_sessions", 0)
    kpis["api_requests"] = stats.get("total_upload_sessions", 0)
    kpis["avg_response_time"] = 150  # Placeholder

    return jsonify({
        "kpis": kpis,
        "email_type_distribution": email_type_dist,
        "email_types": email_types,
        "validation_trends": validation_trends,
        "top_domains": top_domains,
        "domain_reputation": domain_reputation,
        "active_keys": active_keys
    })


# ============================================================================
# EXPORT/REPORTING ENDPOINTS (Phase 6)
# ============================================================================

# Store validation results temporarily for export (in production, use Redis or database)
_validation_cache = {}


@app.route('/api/export/csv', methods=['POST'])
@require_api_key
def export_csv():
    """
    Export validation results as CSV.
    Expects JSON body with 'validation_results' array.
    """
    data = request.get_json()
    if not data or 'validation_results' not in data:
        return jsonify({"error": "Missing validation_results in request body"}), 400

    validation_results = data['validation_results']

    try:
        csv_content = generate_csv_report(validation_results)

        from flask import Response
        return Response(
            csv_content,
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename=validation_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                'Cache-Control': 'no-cache'
            }
        )
    except Exception as e:
        return jsonify({"error": f"Failed to generate CSV: {str(e)}"}), 500


@app.route('/api/export/excel', methods=['POST'])
@require_api_key
def export_excel():
    """
    Export validation results as Excel.
    Expects JSON body with 'validation_results' array.
    """
    data = request.get_json()
    if not data or 'validation_results' not in data:
        return jsonify({"error": "Missing validation_results in request body"}), 400

    validation_results = data['validation_results']

    try:
        excel_content = generate_excel_report(validation_results)

        from flask import Response
        return Response(
            excel_content,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename=validation_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'}
        )
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to generate Excel: {str(e)}"}), 500


@app.route('/api/export/pdf', methods=['POST'])
@require_api_key
def export_pdf():
    """
    Export validation results as PDF.
    Expects JSON body with 'validation_results' array and optional 'summary_stats'.
    """
    data = request.get_json()
    if not data or 'validation_results' not in data:
        return jsonify({"error": "Missing validation_results in request body"}), 400

    validation_results = data['validation_results']
    summary_stats = data.get('summary_stats')

    try:
        pdf_content = generate_pdf_report(validation_results, summary_stats)

        from flask import Response
        return Response(
            pdf_content,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=validation_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'}
        )
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to generate PDF: {str(e)}"}), 500


if __name__ == '__main__':
    # Development server
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)

