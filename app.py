"""
Universal Email Validator Flask Application
Production-grade email validation API with file upload support
"""
from flask import Flask, request, jsonify, render_template, redirect
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
from modules.file_parser import parse_file
from modules.utils import normalize_email, create_validation_result
from modules.email_tracker import get_tracker
from modules.api_auth import require_api_key, get_key_manager
from modules.crm_adapter import parse_crm_request, build_crm_response, get_crm_event_type, validate_crm_vendor

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'xls', 'xlsx', 'pdf'}

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

    # Optional SMTP check
    if include_smtp and is_valid:
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

    return create_validation_result(email, is_valid, checks, all_errors)


@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for Render"""
    return jsonify({
        "status": "healthy",
        "service": "email-validator",
        "version": "1.0.0"
    }), 200


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
        # Get all uploaded files
        files = request.files.getlist('files[]')

        # Fallback to single file upload for backward compatibility
        if not files:
            if 'file' in request.files:
                files = [request.files['file']]
            else:
                return jsonify({
                    "error": "No files provided"
                }), 400

        if not files or all(f.filename == '' for f in files):
            return jsonify({
                "error": "No files selected"
            }), 400

        # Configuration
        should_validate = request.form.get('validate', 'false').lower() == 'true'
        include_smtp = request.form.get('include_smtp', 'false').lower() == 'true'
        batch_size = int(request.form.get('batch_size', 1000))

        # Process all files
        all_emails = []
        file_results = []
        all_errors = []

        for file in files:
            if file.filename == '':
                continue

            if not allowed_file(file.filename):
                all_errors.append(f"File '{file.filename}' type not allowed")
                continue

            try:
                # Read and parse file
                filename = secure_filename(file.filename)
                file_content = file.read()
                parse_result = parse_file(file_content, filename)

                file_info = {
                    "filename": filename,
                    "file_type": parse_result.get("file_type", "unknown"),
                    "emails_found": len(parse_result["emails"]),
                    "errors": parse_result.get("errors", [])
                }

                file_results.append(file_info)
                all_emails.extend(parse_result["emails"])

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
            validation_results = []

            # Process in batches to avoid memory issues
            for i in range(0, len(new_emails), batch_size):
                batch = new_emails[i:i + batch_size]
                for email in batch:
                    result = validate_email_complete(email, include_smtp=include_smtp)
                    validation_results.append(result)

            # Calculate statistics
            valid_count = sum(1 for r in validation_results if r["valid"])
            invalid_count = len(validation_results) - valid_count

            # Count by type
            disposable_count = sum(1 for r in validation_results
                                 if r.get("checks", {}).get("type", {}).get("is_disposable", False))
            role_based_count = sum(1 for r in validation_results
                                  if r.get("checks", {}).get("type", {}).get("is_role_based", False))

            response["validation_results"] = validation_results[:100]  # Return first 100 for preview
            response["validation_summary"] = {
                "total": len(validation_results),
                "valid": valid_count,
                "invalid": invalid_count,
                "disposable": disposable_count,
                "role_based": role_based_count,
                "personal": valid_count - disposable_count - role_based_count
            }
            response["full_results_count"] = len(validation_results)

            # Track the new emails in the database
            session_info = {
                "files_processed": len(file_results),
                "filenames": [f["filename"] for f in file_results]
            }
            tracking_stats = tracker.track_emails(new_emails, validation_results, session_info)
            response["tracking_stats"] = tracking_stats
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
                    "validation_skipped": True
                }
                tracking_stats = tracker.track_emails(new_emails, None, session_info)
                response["tracking_stats"] = tracking_stats

        return jsonify(response), 200

    except Exception as e:
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

                file_results.append({
                    "source_url": url,
                    "filename": filename,
                    "file_type": parse_result.get("file_type", "unknown"),
                    "emails_found": len(parse_result.get("emails", [])),
                    "errors": parse_result.get("errors", []),
                })

                emails.extend(parse_result.get("emails", []))
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
        for email in emails:
            if email and isinstance(email, str):
                result = validate_email_complete(email, include_smtp=include_smtp)
                results.append(result)

        # Build CRM-compatible response
        job_id = str(uuid4()) if callback_url else None
        event_type = get_crm_event_type(success=True, has_errors=False)

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
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = 'attachment; filename=tracked_emails.csv'
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
def create_api_key():
    """Create a new API key (admin-only).

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
def list_api_keys():
    """List existing API keys (admin-only, secret not included)."""
    admin_token = os.getenv('ADMIN_API_TOKEN')
    if not admin_token or request.headers.get('X-Admin-Token') != admin_token:
        return jsonify({"error": "Unauthorized"}), 401

    manager = get_key_manager()
    return jsonify({"keys": manager.list_keys()}), 200


@app.route('/api/keys/<key_id>', methods=['DELETE'])
def revoke_api_key(key_id):
    """Revoke (deactivate) an API key (admin-only)."""
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


if __name__ == '__main__':
    # Development server
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)

