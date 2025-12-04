"""
n8n Integration Module

Dedicated endpoint for n8n workflows with exact JSON structure needed for:
- Scraper → Validator → Clean List flow
- Batch email validation
- Segregated list output (clean, invalid, catchall, disposable, role_based)

Endpoint: POST /api/n8n/validate
"""

from flask import Blueprint, request, jsonify
from typing import List, Dict, Any
from datetime import datetime

# Create blueprint
n8n_bp = Blueprint('n8n', __name__, url_prefix='/api/n8n')


def validate_emails_for_n8n(emails: List[str], include_smtp: bool = False) -> Dict[str, Any]:
    """
    Validate emails and return n8n-compatible response structure.
    
    Args:
        emails: List of email addresses to validate
        include_smtp: Whether to include SMTP verification
        
    Returns:
        Dict with exact structure n8n expects
    """
    # Import here to avoid circular imports
    from app import validate_email_complete
    from modules.email_tracker import get_tracker
    from modules.obvious_invalid import is_obviously_invalid
    from modules.utils import deduplicate_emails
    
    # Deduplicate emails
    emails = deduplicate_emails(emails)
    
    # Validate each email
    results = []
    tracker = get_tracker()
    
    for email in emails:
        if not email or not isinstance(email, str):
            continue
            
        # Fast path: obviously invalid emails
        is_obvious, reason = is_obviously_invalid(email)
        if is_obvious:
            results.append({
                "email": email,
                "valid": False,
                "status": "invalid",
                "is_catchall": False,
                "is_disposable": True,
                "is_role_based": False,
                "reason": reason or "obvious_invalid"
            })
            continue
        
        # Normal validation
        result = validate_email_complete(email, include_smtp=include_smtp)
        
        # Extract flags from nested checks
        checks = result.get("checks", {})
        is_catchall = checks.get("catchall", {}).get("is_catchall", False)
        is_disposable = checks.get("type", {}).get("is_disposable", False)
        is_role_based = checks.get("type", {}).get("is_role_based", False)
        
        results.append({
            "email": email,
            "valid": result.get("valid", False),
            "status": "valid" if result.get("valid", False) else "invalid",
            "is_catchall": is_catchall,
            "is_disposable": is_disposable,
            "is_role_based": is_role_based,
            "reason": None
        })
    
    # Segregate into lists
    segregated_lists = {
        "clean": [],
        "invalid": [],
        "catchall": [],
        "disposable": [],
        "role_based": []
    }
    
    for record in results:
        email = record["email"]
        
        if not record["valid"]:
            segregated_lists["invalid"].append(email)
        elif record["is_disposable"]:
            segregated_lists["disposable"].append(email)
        elif record["is_catchall"]:
            segregated_lists["catchall"].append(email)
        elif record["is_role_based"]:
            segregated_lists["role_based"].append(email)
        else:
            # Valid, non-catchall, non-disposable, non-role-based = CLEAN
            segregated_lists["clean"].append(email)
    
    # Build summary
    summary = {
        "total": len(results),
        "clean": len(segregated_lists["clean"]),
        "invalid": len(segregated_lists["invalid"]),
        "catchall": len(segregated_lists["catchall"]),
        "disposable": len(segregated_lists["disposable"]),
        "role_based": len(segregated_lists["role_based"])
    }
    
    # Track emails
    tracker.track_emails(
        emails,
        results,
        {"session_type": "n8n", "duration_ms": 0}
    )
    
    return {
        "event": "validation.completed",
        "summary": summary,
        "records": results,
        "segregated_lists": segregated_lists,
        "timestamp": datetime.now().isoformat()
    }


@n8n_bp.route('/validate', methods=['POST'])
def n8n_validate():
    """
    n8n-optimized email validation endpoint.
    
    Request:
        {
            "emails": ["email1@example.com", "email2@example.com"],
            "include_smtp": false  // optional, default false
        }
    
    Response:
        {
            "event": "validation.completed",
            "summary": {
                "total": 2,
                "clean": 1,
                "invalid": 0,
                "catchall": 1,
                "disposable": 0,
                "role_based": 0
            },
            "records": [
                {
                    "email": "email1@example.com",
                    "status": "valid",
                    "is_catchall": false,
                    "is_disposable": false,
                    "is_role_based": false
                }
            ],
            "segregated_lists": {
                "clean": ["email1@example.com"],
                "invalid": [],
                "catchall": ["email2@example.com"],
                "disposable": [],
                "role_based": []
            }
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Extract emails - support multiple input formats
        emails = []
        
        # Format 1: { "emails": ["a@b.com"] }
        if "emails" in data and isinstance(data["emails"], list):
            emails.extend(data["emails"])
        
        # Format 2: { "email": "a@b.com" }
        if "email" in data and isinstance(data["email"], str):
            emails.append(data["email"])
        
        # Format 3: [{"email": "a@b.com"}, {"email": "b@c.com"}] (n8n array format)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "email" in item:
                    emails.append(item["email"])
        
        if not emails:
            return jsonify({"error": "No emails provided. Use 'emails' array or 'email' field."}), 400
        
        include_smtp = data.get("include_smtp", False) if isinstance(data, dict) else False
        
        # Validate and return
        response = validate_emails_for_n8n(emails, include_smtp=include_smtp)
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({
            "event": "validation.failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

