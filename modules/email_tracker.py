"""
Email Tracker - Persistent deduplication for marketing campaigns
Tracks all validated emails across sessions to prevent duplicate sends
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Set, Any
from pathlib import Path

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
        self.data = self._load_database()
    
    def _ensure_data_directory(self):
        """Ensure the data directory exists"""
        data_dir = os.path.dirname(self.db_file)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
    def _load_database(self) -> Dict[str, Any]:
        """Load the email history database"""
        self._ensure_data_directory()
        
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load email history: {e}")
                return self._create_empty_database()
        else:
            return self._create_empty_database()
    
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
        self._ensure_data_directory()
        try:
            with open(self.db_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving email history: {e}")
    
    def check_duplicates(self, emails: List[str]) -> Dict[str, Any]:
        """
        Check which emails are duplicates (already seen before)
        
        Args:
            emails: List of email addresses to check
            
        Returns:
            Dictionary with new_emails, duplicate_emails, and stats
        """
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
        timestamp = datetime.now().isoformat()
        new_count = 0
        updated_count = 0
        
        # Create validation lookup
        validation_lookup = {}
        if validation_results:
            for result in validation_results:
                validation_lookup[result.get('email', '').lower()] = result.get('valid', False)
        
        for email in emails:
            email_lower = email.lower().strip()
            
            if email_lower in self.data["emails"]:
                # Update existing email
                self.data["emails"][email_lower]["last_seen"] = timestamp
                self.data["emails"][email_lower]["send_count"] += 1
                updated_count += 1
            else:
                # Add new email
                self.data["emails"][email_lower] = {
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "send_count": 1,
                    "validation_status": validation_lookup.get(email_lower, None)
                }
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
        
        # Save to disk
        self._save_database()
        
        return {
            "new_emails_tracked": new_count,
            "duplicate_emails_found": updated_count,
            "total_emails_in_database": len(self.data["emails"]),
            "total_duplicates_prevented_all_time": self.data["stats"]["total_duplicates_prevented"]
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall tracking statistics"""
        return {
            "total_unique_emails": len(self.data["emails"]),
            "total_upload_sessions": len(self.data["sessions"]),
            "total_duplicates_prevented": self.data["stats"]["total_duplicates_prevented"],
            "database_file": self.db_file
        }
    
    def clear_database(self):
        """Clear all tracked emails (use with caution!)"""
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
        emails = []
        for email, info in self.data["emails"].items():
            if valid_only:
                if info.get("validation_status") == True:
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

