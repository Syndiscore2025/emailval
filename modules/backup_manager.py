"""
Database Backup Manager

Provides automated backup functionality for JSON database files with:
- Manual backup triggering
- Scheduled automatic backups
- Backup retention management
- S3 upload support (optional)
- Backup verification
"""
import os
import json
import shutil
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import threading

try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


class BackupManager:
    """Manages database backups"""
    
    def __init__(self, data_dir: str = 'data', backup_dir: str = 'data/backups'):
        self.data_dir = data_dir
        self.backup_dir = backup_dir
        self.backup_config_file = os.path.join(data_dir, 'backup_config.json')
        
        # Create backup directory
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Load configuration
        self.config = self._load_config()
        
        # Files to backup
        self.backup_files = [
            'email_history.json',
            'validation_jobs.json',
            'api_keys.json',
            'crm_configs.json',
            'crm_uploads.json'
        ]
    
    def _load_config(self) -> Dict[str, Any]:
        """Load backup configuration"""
        if os.path.exists(self.backup_config_file):
            try:
                with open(self.backup_config_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # Default configuration
        return {
            'enabled': True,
            'retention_days': 30,
            'max_backups': 100,
            's3_enabled': False,
            's3_bucket': '',
            's3_prefix': 'backups/',
            'last_backup': None,
            'backup_count': 0
        }
    
    def _save_config(self):
        """Save backup configuration"""
        try:
            with open(self.backup_config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving backup config: {e}")
    
    def create_backup(self, upload_to_s3: bool = None) -> Dict[str, Any]:
        """Create a backup of all database files
        
        Args:
            upload_to_s3: Whether to upload to S3 (overrides config)
            
        Returns:
            Backup result with status and details
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_{timestamp}"
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        try:
            # Create backup directory
            os.makedirs(backup_path, exist_ok=True)
            
            backed_up_files = []
            errors = []
            
            # Backup each file
            for filename in self.backup_files:
                source_path = os.path.join(self.data_dir, filename)
                
                if not os.path.exists(source_path):
                    continue
                
                dest_path = os.path.join(backup_path, filename)
                
                try:
                    shutil.copy2(source_path, dest_path)
                    backed_up_files.append(filename)
                except Exception as e:
                    errors.append(f"Failed to backup {filename}: {str(e)}")
            
            # Create backup metadata
            metadata = {
                'timestamp': timestamp,
                'created_at': datetime.now().isoformat(),
                'files': backed_up_files,
                'errors': errors,
                'backup_path': backup_path
            }
            
            metadata_path = os.path.join(backup_path, 'metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Update config
            self.config['last_backup'] = datetime.now().isoformat()
            self.config['backup_count'] = self.config.get('backup_count', 0) + 1
            self._save_config()
            
            # Upload to S3 if enabled
            s3_result = None
            if upload_to_s3 or (upload_to_s3 is None and self.config.get('s3_enabled')):
                s3_result = self._upload_to_s3(backup_path, backup_name)
            
            # Clean old backups
            self._cleanup_old_backups()
            
            return {
                'success': True,
                'backup_name': backup_name,
                'backup_path': backup_path,
                'files_backed_up': len(backed_up_files),
                'files': backed_up_files,
                'errors': errors,
                's3_upload': s3_result,
                'timestamp': timestamp
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timestamp': timestamp
            }
    
    def _upload_to_s3(self, backup_path: str, backup_name: str) -> Optional[Dict[str, Any]]:
        """Upload backup to S3
        
        Args:
            backup_path: Local path to backup directory
            backup_name: Name of the backup
            
        Returns:
            Upload result or None if S3 not configured
        """
        if not HAS_BOTO3:
            return {'success': False, 'error': 'boto3 not installed'}
        
        bucket = self.config.get('s3_bucket')
        if not bucket:
            return {'success': False, 'error': 'S3 bucket not configured'}
        
        try:
            s3_client = boto3.client('s3')
            prefix = self.config.get('s3_prefix', 'backups/')
            
            uploaded_files = []
            
            # Upload each file in the backup
            for filename in os.listdir(backup_path):
                file_path = os.path.join(backup_path, filename)
                if not os.path.isfile(file_path):
                    continue
                
                s3_key = f"{prefix}{backup_name}/{filename}"
                
                s3_client.upload_file(
                    file_path,
                    bucket,
                    s3_key,
                    ExtraArgs={'ServerSideEncryption': 'AES256'}
                )
                
                uploaded_files.append(s3_key)
            
            return {
                'success': True,
                'bucket': bucket,
                'files_uploaded': len(uploaded_files),
                'files': uploaded_files
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _cleanup_old_backups(self):
        """Remove old backups based on retention policy"""
        try:
            retention_days = self.config.get('retention_days', 30)
            max_backups = self.config.get('max_backups', 100)
            
            # Get all backups
            backups = []
            for item in os.listdir(self.backup_dir):
                item_path = os.path.join(self.backup_dir, item)
                if os.path.isdir(item_path) and item.startswith('backup_'):
                    metadata_path = os.path.join(item_path, 'metadata.json')
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                            backups.append({
                                'name': item,
                                'path': item_path,
                                'created_at': metadata.get('created_at'),
                                'timestamp': metadata.get('timestamp')
                            })
            
            # Sort by creation time (newest first)
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            
            # Remove backups beyond max count
            if len(backups) > max_backups:
                for backup in backups[max_backups:]:
                    shutil.rmtree(backup['path'])
            
            # Remove backups older than retention period
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            for backup in backups:
                created_at = datetime.fromisoformat(backup['created_at'])
                if created_at < cutoff_date:
                    if os.path.exists(backup['path']):
                        shutil.rmtree(backup['path'])
            
        except Exception as e:
            print(f"Error cleaning up old backups: {e}")
    
    def list_backups(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List available backups
        
        Args:
            limit: Maximum number of backups to return
            
        Returns:
            List of backup metadata
        """
        backups = []
        
        try:
            for item in os.listdir(self.backup_dir):
                item_path = os.path.join(self.backup_dir, item)
                if os.path.isdir(item_path) and item.startswith('backup_'):
                    metadata_path = os.path.join(item_path, 'metadata.json')
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                            backups.append(metadata)
            
            # Sort by creation time (newest first)
            backups.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return backups[:limit]
            
        except Exception as e:
            print(f"Error listing backups: {e}")
            return []
    
    def get_config(self) -> Dict[str, Any]:
        """Get backup configuration"""
        return self.config.copy()
    
    def update_config(self, updates: Dict[str, Any]):
        """Update backup configuration
        
        Args:
            updates: Configuration updates
        """
        self.config.update(updates)
        self._save_config()


# Singleton instance
_backup_manager = None

def get_backup_manager() -> BackupManager:
    """Get the singleton backup manager instance"""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager

