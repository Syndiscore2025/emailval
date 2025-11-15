"""Admin actions for email records: re-verify and soft-delete.

These endpoints are used by the admin UI to re-run validation on invalid
emails and to move obviously bad ones into a disposable/deleted state
without losing history.
"""

from typing import List, Dict, Any

from flask import Blueprint, request, jsonify

from modules.email_tracker import get_tracker
from modules.obvious_invalid import is_obviously_invalid
from app import validate_email_complete  # circular import is acceptable here in this small app


admin_email_actions_bp = Blueprint("admin_email_actions", __name__)


@admin_email_actions_bp.route("/admin/api/emails/reverify", methods=["POST"])
def reverify_emails():
    """Re-validate one or more invalid emails.

    Request JSON: {"emails": ["foo@example.com", ...]}
    """
    try:
        data = request.get_json() or {}
        emails = data.get("emails") or []

        if not isinstance(emails, list) or not emails:
            return jsonify({"success": False, "error": "No emails provided"}), 400

        tracker = get_tracker()
        results: List[Dict[str, Any]] = []

        for raw_email in emails:
            if not raw_email or not isinstance(raw_email, str):
                continue

            email = raw_email.strip().lower()

            # First, check if this is obviously invalid junk
            is_obvious, reason = is_obviously_invalid(email)
            if is_obvious:
                record = tracker.data.get("emails", {}).get(email, {})
                record.setdefault("status", "disposable")
                record["status"] = "disposable"
                record["delete_reason"] = reason or "obvious_invalid"
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
    except Exception as exc:  # pragma: no cover - safety net
        return jsonify({"success": False, "error": str(exc)}), 500


@admin_email_actions_bp.route("/admin/api/emails/delete", methods=["POST"])
def delete_emails():
    """Soft-delete disposable emails from the active pool but keep history.

    Request JSON: {"emails": ["foo@example.com", ...]}
    """
    try:
        data = request.get_json() or {}
        emails = data.get("emails") or []

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
    except Exception as exc:  # pragma: no cover - safety net
        return jsonify({"success": False, "error": str(exc)}), 500

