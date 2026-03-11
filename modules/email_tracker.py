"""
Email Tracker - Persistent deduplication for marketing campaigns
Tracks all validated emails across sessions to prevent duplicate sends
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Set, Any, Optional
from pathlib import Path
from threading import RLock

from modules.json_store import json_file_lock, load_json_data, save_json_data_atomic
from modules.runtime_state_backend import (
    get_runtime_state_table_name,
    postgres_transaction,
    use_postgres_runtime_state,
)

# Database file location
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'email_history.json')


class EmailTracker:
    """
    Persistent email tracking system for marketing campaigns
    Prevents sending to the same email multiple times across different uploads
    """
    
    def __init__(self, db_file: str = DB_FILE):
        """Initialize the email tracker"""
        self.db_file = db_file
        self.lock = RLock()
        self.backend = 'postgres' if use_postgres_runtime_state() else 'json'
        self.postgres_table = get_runtime_state_table_name('email_history')
        self.postgres_state_key = 'default'
        self._postgres_table_ready = False
        self.data = self._load_database()

    def _use_postgres(self) -> bool:
        return self.backend == 'postgres'
    
    def _ensure_data_directory(self):
        """Ensure the data directory exists"""
        if self._use_postgres():
            return
        data_dir = os.path.dirname(self.db_file)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def _ensure_postgres_table(self) -> None:
        if not self._use_postgres() or self._postgres_table_ready:
            return

        with postgres_transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.postgres_table} (
                        state_key TEXT PRIMARY KEY,
                        state_data TEXT NOT NULL
                    )
                    """
                )

        self._postgres_table_ready = True

    def _normalize_database(self, data: Any) -> Dict[str, Any]:
        normalized = self._create_empty_database()
        if not isinstance(data, dict):
            return normalized

        emails = data.get('emails')
        if isinstance(emails, dict):
            normalized['emails'] = emails

        sessions = data.get('sessions')
        if isinstance(sessions, list):
            normalized['sessions'] = sessions

        stats = data.get('stats')
        if isinstance(stats, dict):
            for key in ('total_emails_tracked', 'total_uploads', 'total_duplicates_prevented'):
                value = stats.get(key, normalized['stats'][key])
                try:
                    normalized['stats'][key] = int(value)
                except (TypeError, ValueError):
                    pass

        return normalized

    def _deserialize_state_data(self, raw_value: Any) -> Dict[str, Any]:
        if isinstance(raw_value, dict):
            return self._normalize_database(raw_value)
        if isinstance(raw_value, (bytes, bytearray)):
            raw_value = raw_value.decode('utf-8')
        if not raw_value:
            return self._create_empty_database()
        return self._normalize_database(json.loads(raw_value))

    def _postgres_fetch_database(self, cursor) -> Dict[str, Any]:
        cursor.execute(
            f"SELECT state_data FROM {self.postgres_table} WHERE state_key = %s",
            (self.postgres_state_key,),
        )
        row = cursor.fetchone()
        if not row:
            return self._create_empty_database()
        return self._deserialize_state_data(row[0])

    def _postgres_save_database(self, cursor, state: Dict[str, Any]) -> None:
        cursor.execute(
            f"""
            INSERT INTO {self.postgres_table} (state_key, state_data)
            VALUES (%s, %s)
            ON CONFLICT (state_key) DO UPDATE
            SET state_data = EXCLUDED.state_data
            """,
            (self.postgres_state_key, json.dumps(state)),
        )
    
    def _load_database(self) -> Dict[str, Any]:
        """Load the email history database"""
        with self.lock:
            if self._use_postgres():
                self._ensure_postgres_table()
                with postgres_transaction() as connection:
                    with connection.cursor() as cursor:
                        return self._postgres_fetch_database(cursor)

            self._ensure_data_directory()
            data = load_json_data(self.db_file, self._create_empty_database())
            return self._normalize_database(data)
    
    def _create_empty_database(self) -> Dict[str, Any]:
        """Create an empty database structure"""
        return {
            "emails": {},  # email -> {first_seen, last_seen, send_count, validation_status}
            "sessions": [],  # List of upload sessions
            "stats": {
                "total_emails_tracked": 0,
                "total_uploads": 0,
                "total_duplicates_prevented": 0
            }
        }
    
    def _save_database(self):
        """Save the database to disk"""
        with self.lock:
            state = self._normalize_database(self.data)
            self.data = state
            if self._use_postgres():
                self._ensure_postgres_table()
                with postgres_transaction() as connection:
                    with connection.cursor() as cursor:
                        self._postgres_save_database(cursor, state)
                return

            self._ensure_data_directory()
            with json_file_lock(self.db_file):
                save_json_data_atomic(self.db_file, state)

    def _refresh_from_storage(self) -> None:
        self.data = self._load_database()

    def check_duplicates(self, emails: List[str]) -> Dict[str, Any]:
        """
        Check which emails are duplicates (already seen before)
        
        Args:
            emails: List of email addresses to check
            
        Returns:
            Dictionary with new_emails, duplicate_emails, and stats
        """
        with self.lock:
            self._refresh_from_storage()
            new_emails = []
            duplicate_emails = []

            for email in emails:
                email_lower = email.lower().strip()

                if email_lower in self.data["emails"]:
                    duplicate_emails.append({
                        "email": email_lower,
                        "first_seen": self.data["emails"][email_lower]["first_seen"],
                        "send_count": self.data["emails"][email_lower]["send_count"]
                    })
                else:
                    new_emails.append(email_lower)

            return {
                "new_emails": new_emails,
                "duplicate_emails": duplicate_emails,
                "new_count": len(new_emails),
                "duplicate_count": len(duplicate_emails),
                "total_checked": len(emails)
            }
    
    def track_emails(self, emails: List[str], validation_results: List[Dict] = None, 
                    session_info: Dict = None) -> Dict[str, Any]:
        """
        Track emails in the database
        
        Args:
            emails: List of email addresses to track
            validation_results: Optional validation results for each email
            session_info: Optional session metadata (filename, upload_time, etc.)
            
        Returns:
            Tracking statistics
        """
        with self.lock:
            self._refresh_from_storage()
            timestamp = datetime.now().isoformat()
            new_count = 0
            updated_count = 0

            # Create validation lookup with full data
            validation_lookup = {}
            if validation_results:
                for result in validation_results:
                    email_key = result.get('email', '').lower()
                    # Flatten the nested structure for easier storage
                    checks = result.get('checks', {})
                    type_checks = checks.get('type', {})

                    # Extract SMTP verification status
                    smtp_checks = checks.get('smtp', {})
                    smtp_verified = smtp_checks.get('mailbox_exists', False) and not smtp_checks.get('skipped', True)

                    # Extract catch-all status
                    catchall_checks = checks.get('catchall', {})
                    is_catchall = catchall_checks.get('is_catchall', False)
                    catchall_confidence = catchall_checks.get('confidence', 'low')

                    flattened_result = {
                        'email': result.get('email', ''),
                        'valid': result.get('valid', False),
                        'type': type_checks.get('email_type', 'unknown'),
                        'is_disposable': type_checks.get('is_disposable', False),
                        'is_role_based': type_checks.get('is_role_based', False),
                        'smtp_verified': smtp_verified,
                        'is_catchall': is_catchall,
                        'catchall_confidence': catchall_confidence,
                        'checks': checks
                    }
                    validation_lookup[email_key] = flattened_result

            for email in emails:
                email_lower = email.lower().strip()
                validation_data = validation_lookup.get(email_lower, {})

                if email_lower in self.data["emails"]:
                    # Update existing email
                    record = self.data["emails"][email_lower]
                    record["last_seen"] = timestamp
                    record["send_count"] += 1

                    # Update validation data if provided
                    if validation_data:
                        record["valid"] = validation_data.get('valid', False)
                        record["type"] = validation_data.get('type', 'unknown')
                        record["is_disposable"] = validation_data.get('is_disposable', False)
                        record["is_role_based"] = validation_data.get('is_role_based', False)
                        record["smtp_verified"] = validation_data.get('smtp_verified', False)
                        record["is_catchall"] = validation_data.get('is_catchall', False)
                        record["catchall_confidence"] = validation_data.get('catchall_confidence', 'low')
                        record["last_validated"] = timestamp
                        record["validation_count"] = record.get("validation_count", 0) + 1
                        record["checks"] = validation_data.get('checks', {})

                        # Update high-level status for admin filtering
                        if record["valid"] is True:
                            record["status"] = "valid"
                        elif record.get("is_disposable"):
                            record["status"] = "disposable"
                        else:
                            record["status"] = "invalid"

                    updated_count += 1
                else:
                    # Add new email with full validation data
                    email_record = {
                        "first_seen": timestamp,
                        "last_seen": timestamp,
                        "send_count": 1,
                        "validation_count": 1 if validation_data else 0,
                    }

                    # Add validation fields if available
                    if validation_data:
                        email_record["valid"] = validation_data.get('valid', False)
                        email_record["type"] = validation_data.get('type', 'unknown')
                        email_record["smtp_verified"] = validation_data.get('smtp_verified', False)
                        email_record["is_disposable"] = validation_data.get('is_disposable', False)
                        email_record["is_role_based"] = validation_data.get('is_role_based', False)
                        email_record["is_catchall"] = validation_data.get('is_catchall', False)
                        email_record["catchall_confidence"] = validation_data.get('catchall_confidence', 'low')
                        email_record["last_validated"] = timestamp
                        email_record["checks"] = validation_data.get('checks', {})

                        if email_record["valid"] is True:
                            email_record["status"] = "valid"
                        elif email_record.get("is_disposable"):
                            email_record["status"] = "disposable"
                        else:
                            email_record["status"] = "invalid"
                    else:
                        email_record["valid"] = None
                        email_record["type"] = "unknown"
                        email_record["smtp_verified"] = False
                        email_record["is_disposable"] = False
                        email_record["is_role_based"] = False
                        email_record["is_catchall"] = False
                        email_record["catchall_confidence"] = "low"
                        email_record["last_validated"] = None
                        email_record["status"] = "unknown"
                        email_record["checks"] = {}

                    self.data["emails"][email_lower] = email_record
                    new_count += 1

            # Track session
            if session_info:
                session_data = {
                    "timestamp": timestamp,
                    "emails_count": len(emails),
                    "new_emails": new_count,
                    "duplicates": updated_count,
                    **session_info
                }
                self.data["sessions"].append(session_data)

            # Update stats
            self.data["stats"]["total_emails_tracked"] = len(self.data["emails"])
            self.data["stats"]["total_uploads"] += 1
            self.data["stats"]["total_duplicates_prevented"] += updated_count

            # Save to configured backend
            self._save_database()

            return {
                "new_emails_tracked": new_count,
                "duplicate_emails_found": updated_count,
                "total_emails_in_database": len(self.data["emails"]),
                "total_duplicates_prevented_all_time": self.data["stats"]["total_duplicates_prevented"]
            }
    
    def get_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Return a validation-result-compatible dict for a tracked email.

        The shape mirrors what ``run_smtp_validation_background`` produces so
        that CRM auto/manual validation flows can pass the result directly to
        ``build_segregated_crm_response``.

        Returns ``None`` if the email has not been tracked yet.
        """
        with self.lock:
            self._refresh_from_storage()
            email_lower = email.lower().strip()
            record = self.data["emails"].get(email_lower)
            if record is None:
                return None

            checks = record.get("checks", {})
            return {
                "email": email_lower,
                "valid": record.get("valid", False),
                "errors": [],
                "checks": checks if checks else {
                    "type": {
                        "email_type": record.get("type", "unknown"),
                        "is_disposable": record.get("is_disposable", False),
                        "is_role_based": record.get("is_role_based", False),
                    },
                    "smtp": {
                        "mailbox_exists": record.get("smtp_verified", False),
                        "skipped": not record.get("smtp_verified", False),
                    },
                    "catchall": {
                        "is_catchall": record.get("is_catchall", False),
                        "confidence": record.get("catchall_confidence", "low"),
                    },
                },
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get overall tracking statistics"""
        with self.lock:
            self._refresh_from_storage()
            return {
                "total_unique_emails": len(self.data["emails"]),
                "total_upload_sessions": len(self.data["sessions"]),
                "total_duplicates_prevented": self.data["stats"]["total_duplicates_prevented"],
                "database_file": self.db_file
            }
    
    def clear_database(self):
        """Clear all tracked emails (use with caution!)"""
        with self.lock:
            self.data = self._create_empty_database()
            self._save_database()
    
    def export_emails(self, valid_only: bool = False) -> List[str]:
        """
        Export all tracked emails
        
        Args:
            valid_only: If True, only export emails that passed validation
            
        Returns:
            List of email addresses
        """
        with self.lock:
            self._refresh_from_storage()
            emails = []
            for email, info in self.data["emails"].items():
                if valid_only:
                    if info.get("valid") is True or info.get("validation_status") is True:
                        emails.append(email)
                else:
                    emails.append(email)
            return sorted(emails)


# Global tracker instance
_tracker = None

def get_tracker() -> EmailTracker:
    """Get the global email tracker instance"""
    global _tracker
    if _tracker is None:
        _tracker = EmailTracker()
    return _tracker

