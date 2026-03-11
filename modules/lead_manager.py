"""
Lead Upload Manager

Tracks CRM lead uploads and validation jobs
Supports:
- Manual validation mode (upload → validate button → results)
- Auto validation mode (upload → auto-validate → results)
- Upload status tracking
- Results retrieval
"""
import json
import os
from threading import Lock
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4

from modules.json_store import json_file_lock, load_json_data, save_json_data_atomic


# Upload tracking file
UPLOADS_FILE = os.path.join('data', 'crm_uploads.json')


class LeadManager:
    """Manages CRM lead uploads and validation tracking"""
    
    def __init__(self, uploads_file: str = UPLOADS_FILE):
        self.uploads_file = uploads_file
        self.lock = Lock()
        self.uploads = self._load_uploads()

    def _empty_uploads(self) -> Dict[str, Any]:
        return {}
    
    def _load_uploads(self) -> Dict[str, Any]:
        """Load uploads from file"""
        data = load_json_data(self.uploads_file, self._empty_uploads())
        return data if isinstance(data, dict) else self._empty_uploads()

    def _refresh_from_disk(self):
        self.uploads = self._load_uploads()
    
    def _save_uploads(self):
        """Save uploads to file"""
        save_json_data_atomic(self.uploads_file, self.uploads)
    
    def create_upload(
        self,
        crm_id: str,
        crm_vendor: str,
        emails: List[str],
        crm_context: List[Dict[str, Any]],
        validation_mode: str = 'manual',
        settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create new lead upload
        
        Args:
            crm_id: CRM client identifier
            crm_vendor: CRM vendor (salesforce, hubspot, custom, other)
            emails: List of email addresses
            crm_context: CRM record metadata
            validation_mode: 'manual' or 'auto'
            settings: Validation settings (SMTP, catch-all, etc.)
        
        Returns:
            Upload record
        """
        upload_id = f"upl_{uuid4().hex[:12]}"
        
        upload = {
            'upload_id': upload_id,
            'crm_id': crm_id,
            'crm_vendor': crm_vendor,
            'validation_mode': validation_mode,
            'status': 'pending_validation' if validation_mode == 'manual' else 'validating',
            'email_count': len(emails),
            'emails': emails,
            'crm_context': crm_context,
            'settings': settings or {},
            'job_id': None,
            'results': None,
            's3_delivery': None,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'validated_at': None
        }
        
        with self.lock:
            with json_file_lock(self.uploads_file):
                self._refresh_from_disk()
                self.uploads[upload_id] = upload
                self._save_uploads()
        
        return upload
    
    def get_upload(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Get upload by ID"""
        with self.lock:
            self._refresh_from_disk()
            return self.uploads.get(upload_id)
    
    def update_upload(self, upload_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update upload record"""
        with self.lock:
            with json_file_lock(self.uploads_file):
                self._refresh_from_disk()
                if upload_id not in self.uploads:
                    return None

                upload = self.uploads[upload_id]
                upload.update(updates)
                upload['updated_at'] = datetime.now().isoformat()

                self._save_uploads()
                return upload
    
    def start_validation(self, upload_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        """Mark upload as validating"""
        return self.update_upload(upload_id, {
            'status': 'validating',
            'job_id': job_id
        })
    
    def complete_validation(
        self,
        upload_id: str,
        results: Dict[str, Any],
        s3_delivery: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Mark validation as complete and store results"""
        return self.update_upload(upload_id, {
            'status': 'completed',
            'results': results,
            's3_delivery': s3_delivery,
            'validated_at': datetime.now().isoformat()
        })
    
    def fail_validation(self, upload_id: str, error: str) -> Optional[Dict[str, Any]]:
        """Mark validation as failed"""
        return self.update_upload(upload_id, {
            'status': 'failed',
            'error': error
        })
    
    def get_uploads_by_crm(self, crm_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent uploads for a CRM client"""
        with self.lock:
            self._refresh_from_disk()
            crm_uploads = [
                upload for upload in self.uploads.values()
                if upload.get('crm_id') == crm_id
            ]

            # Sort by created_at descending
            crm_uploads.sort(key=lambda x: x.get('created_at', ''), reverse=True)

            return crm_uploads[:limit]


# Global singleton instance
_lead_manager = None


def get_lead_manager() -> LeadManager:
    """Get global lead manager instance"""
    global _lead_manager
    if _lead_manager is None:
        _lead_manager = LeadManager()
    return _lead_manager

