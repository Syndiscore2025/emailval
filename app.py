"""
Universal Email Validator Flask Application
Production-grade email validation API with file upload support
"""
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
from typing import Dict, Any, List

from modules.syntax_check import validate_syntax
from modules.domain_check import validate_domain
from modules.type_check import validate_type
from modules.smtp_check import validate_smtp
from modules.file_parser import parse_file
from modules.utils import normalize_email, create_validation_result
from modules.email_tracker import get_tracker

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'xls', 'xlsx', 'pdf'}

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


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
def validate_single():
    """
    Validate a single email address
    
    Request JSON:
    {
        "email": "test@example.com",
        "include_smtp": false  // optional
    }
    
    Response JSON:
    {
        "email": "test@example.com",
        "valid": true,
        "checks": {...},
        "errors": []
    }
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


@app.route('/upload', methods=['POST'])
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
def webhook_validate():
    """
    CRM webhook endpoint for email validation

    Accepts various payload formats from different CRMs

    Request JSON (flexible format):
    {
        "email": "test@example.com",
        // OR
        "emails": ["test1@example.com", "test2@example.com"],
        // OR
        "contact": {
            "email": "test@example.com"
        },
        // Additional fields
        "include_smtp": false,
        "callback_url": "https://crm.example.com/webhook"  // optional
    }

    Response JSON:
    {
        "results": [...],
        "summary": {
            "total": 1,
            "valid": 1,
            "invalid": 0
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "error": "No JSON data provided"
            }), 400

        # Extract emails from various possible formats
        emails = []

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

        if not emails:
            return jsonify({
                "error": "No email addresses found in request"
            }), 400

        # Get options
        include_smtp = data.get('include_smtp', False)

        # Validate all emails
        results = []
        for email in emails:
            if email and isinstance(email, str):
                result = validate_email_complete(email, include_smtp=include_smtp)
                results.append(result)

        # Create summary
        summary = {
            "total": len(results),
            "valid": sum(1 for r in results if r["valid"]),
            "invalid": sum(1 for r in results if not r["valid"])
        }

        response = {
            "results": results,
            "summary": summary
        }

        # TODO: If callback_url is provided, send results there
        # This would be implemented based on specific CRM requirements

        return jsonify(response), 200

    except Exception as e:
        return jsonify({
            "error": f"Webhook processing error: {str(e)}"
        }), 500


@app.route('/tracker/stats', methods=['GET'])
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
def export_results():
    """
    Export validation results as CSV

    Request JSON:
    {
        "results": [...],  // Array of validation results
        "format": "csv"    // Export format (currently only CSV)
    }

    Returns CSV file download
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


if __name__ == '__main__':
    # Development server
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)

