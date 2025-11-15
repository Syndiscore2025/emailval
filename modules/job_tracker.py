"""
Job Tracking System for Async Validation
Tracks progress of long-running validation jobs
"""
import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from threading import Lock

class JobTracker:
    """Track validation job progress"""
    
    def __init__(self, data_file: str = "data/validation_jobs.json"):
        self.data_file = data_file
        self.lock = Lock()
        self.jobs = self._load_jobs()
    
    def _load_jobs(self) -> Dict[str, Any]:
        """Load jobs from disk"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_jobs(self):
        """Save jobs to disk"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, 'w') as f:
            json.dump(self.jobs, f, indent=2)
    
    def create_job(self, total_emails: int, session_info: Dict[str, Any] = None) -> str:
        """Create a new validation job"""
        job_id = str(uuid.uuid4())[:8]

        with self.lock:
            self.jobs[job_id] = {
                "job_id": job_id,
                "status": "pending",  # pending, running, completed, failed
                "total_emails": total_emails,
                "validated_count": 0,
                "valid_count": 0,
                "invalid_count": 0,
                "disposable_count": 0,
                "role_based_count": 0,
                "personal_count": 0,
                "started_at": datetime.now().isoformat(),
                "completed_at": None,
                "session_info": session_info or {},
                "webhook_url": None,
                "error": None
            }
            self._save_jobs()

        return job_id
    
    def update_progress(self, job_id: str, validated_count: int, valid_count: int = None, invalid_count: int = None,
                       disposable_count: int = None, role_based_count: int = None, personal_count: int = None):
        """Update job progress with detailed stats"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]["validated_count"] = validated_count
                if valid_count is not None:
                    self.jobs[job_id]["valid_count"] = valid_count
                if invalid_count is not None:
                    self.jobs[job_id]["invalid_count"] = invalid_count
                if disposable_count is not None:
                    self.jobs[job_id]["disposable_count"] = disposable_count
                if role_based_count is not None:
                    self.jobs[job_id]["role_based_count"] = role_based_count
                if personal_count is not None:
                    self.jobs[job_id]["personal_count"] = personal_count
                if self.jobs[job_id]["status"] == "pending":
                    self.jobs[job_id]["status"] = "running"
                self._save_jobs()
    
    def complete_job(self, job_id: str, success: bool = True, error: str = None):
        """Mark job as completed"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]["status"] = "completed" if success else "failed"
                self.jobs[job_id]["completed_at"] = datetime.now().isoformat()
                if error:
                    self.jobs[job_id]["error"] = error
                self._save_jobs()
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        return self.jobs.get(job_id)
    
    def set_webhook(self, job_id: str, webhook_url: str):
        """Set webhook URL for job completion notification"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]["webhook_url"] = webhook_url
                self._save_jobs()
    
    def get_progress_percent(self, job_id: str) -> float:
        """Get progress as percentage"""
        job = self.get_job(job_id)
        if not job or job["total_emails"] == 0:
            return 0.0
        return (job["validated_count"] / job["total_emails"]) * 100
    
    def estimate_time_remaining(self, job_id: str) -> Optional[int]:
        """Estimate seconds remaining based on current progress"""
        job = self.get_job(job_id)
        if not job or job["status"] != "running":
            return None
        
        validated = job["validated_count"]
        total = job["total_emails"]
        
        if validated == 0:
            return None
        
        # Calculate elapsed time
        started = datetime.fromisoformat(job["started_at"])
        elapsed = (datetime.now() - started).total_seconds()
        
        # Estimate time per email
        time_per_email = elapsed / validated
        
        # Estimate remaining time
        remaining_emails = total - validated
        return int(remaining_emails * time_per_email)


# Global instance
_job_tracker = None

def get_job_tracker() -> JobTracker:
    """Get global job tracker instance"""
    global _job_tracker
    if _job_tracker is None:
        _job_tracker = JobTracker()
    return _job_tracker

