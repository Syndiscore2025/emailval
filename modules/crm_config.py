"""
CRM Configuration Management

Manages CRM client settings including:
- Auto-validation preferences
- S3 delivery configuration
- Premium feature toggles
- Validation settings
"""
import json
import os
from copy import deepcopy
from threading import Lock
from typing import Dict, Any, Optional
from datetime import datetime
from cryptography.fernet import Fernet
import base64

from modules.json_store import json_file_lock, load_json_data, save_json_data_atomic
from modules.runtime_state_backend import (
    get_runtime_state_table_name,
    postgres_transaction,
    use_postgres_runtime_state,
)


# Configuration file path
CRM_CONFIG_FILE = os.path.join('data', 'crm_configs.json')

# Encryption key for AWS credentials (stored in environment variable)
ENCRYPTION_KEY = os.getenv('CRM_CONFIG_ENCRYPTION_KEY')


def get_encryption_key() -> bytes:
    """Get or generate encryption key for AWS credentials"""
    if ENCRYPTION_KEY:
        return base64.urlsafe_b64decode(ENCRYPTION_KEY.encode())
    
    # Generate new key if not set (for development only)
    # In production, this should be set in environment variables
    key = Fernet.generate_key()
    print(f"[WARNING] No CRM_CONFIG_ENCRYPTION_KEY set. Generated temporary key.")
    print(f"[WARNING] Set this in production: CRM_CONFIG_ENCRYPTION_KEY={base64.urlsafe_b64encode(key).decode()}")
    return key


def encrypt_value(value: str) -> str:
    """Encrypt sensitive value (AWS credentials)"""
    if not value:
        return ""
    
    key = get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(value.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt sensitive value"""
    if not encrypted_value:
        return ""
    
    try:
        key = get_encryption_key()
        f = Fernet(key)
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode())
        decrypted = f.decrypt(encrypted_bytes)
        return decrypted.decode()
    except Exception as e:
        print(f"[ERROR] Failed to decrypt value: {e}")
        return ""


class CRMConfigManager:
    """Manages CRM client configurations"""

    def __init__(self, config_file: str = CRM_CONFIG_FILE):
        self.config_file = config_file
        self.lock = Lock()
        self.postgres_table = get_runtime_state_table_name('crm_configs')
        self._postgres_table_ready = False
        self.configs = self._load_configs()

    def _use_postgres(self) -> bool:
        return use_postgres_runtime_state()

    def _empty_configs(self) -> Dict[str, Any]:
        return {}

    # ------------------------------------------------------------------
    # Postgres helpers
    # ------------------------------------------------------------------

    def _ensure_postgres_table(self, cursor) -> None:
        if self._postgres_table_ready:
            return
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.postgres_table} (
                crm_id TEXT PRIMARY KEY,
                config_data TEXT NOT NULL
            )
            """
        )
        self._postgres_table_ready = True

    def _postgres_fetch_config(self, cursor, crm_id: str) -> Optional[Dict[str, Any]]:
        cursor.execute(
            f"SELECT config_data FROM {self.postgres_table} WHERE crm_id = %s",
            (crm_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        try:
            raw = row[0]
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode('utf-8')
            data = json.loads(raw) if raw else None
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _postgres_save_config(self, cursor, crm_id: str, config: Dict[str, Any]) -> None:
        cursor.execute(
            f"""
            INSERT INTO {self.postgres_table} (crm_id, config_data)
            VALUES (%s, %s)
            ON CONFLICT (crm_id) DO UPDATE
            SET config_data = EXCLUDED.config_data
            """,
            (crm_id, json.dumps(config)),
        )

    def _postgres_delete_config(self, cursor, crm_id: str) -> None:
        cursor.execute(
            f"DELETE FROM {self.postgres_table} WHERE crm_id = %s",
            (crm_id,),
        )

    # ------------------------------------------------------------------
    # JSON helpers
    # ------------------------------------------------------------------

    def _load_configs(self) -> Dict[str, Any]:
        """Load CRM configurations from file (no-op for Postgres path)"""
        if self._use_postgres():
            return {}
        data = load_json_data(self.config_file, self._empty_configs())
        return data if isinstance(data, dict) else self._empty_configs()

    def _refresh_from_disk(self):
        self.configs = self._load_configs()

    def _save_configs(self):
        """Save CRM configurations to file"""
        save_json_data_atomic(self.config_file, self.configs)
    
    def _decrypt_config_for_return(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt AWS credentials in a config copy before returning."""
        config = deepcopy(config)
        if 's3_delivery' in config.get('settings', {}):
            s3_config = config['settings']['s3_delivery']
            if 'secret_access_key_encrypted' in s3_config:
                s3_config['secret_access_key'] = decrypt_value(
                    s3_config['secret_access_key_encrypted']
                )
        return config

    def get_config(self, crm_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific CRM client"""
        if self._use_postgres():
            with self.lock:
                with postgres_transaction() as conn:
                    with conn.cursor() as cursor:
                        self._ensure_postgres_table(cursor)
                        config = self._postgres_fetch_config(cursor, crm_id)
            if not config:
                return None
            return self._decrypt_config_for_return(config)

        with self.lock:
            self._refresh_from_disk()
            config = deepcopy(self.configs.get(crm_id))
            if not config:
                return None
            return self._decrypt_config_for_return(config)

    def create_config(self, crm_id: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new CRM configuration"""
        config_data = deepcopy(config_data)

        # Encrypt AWS credentials if present
        if 's3_delivery' in config_data.get('settings', {}):
            s3_config = config_data['settings']['s3_delivery']
            if 'secret_access_key' in s3_config:
                s3_config['secret_access_key_encrypted'] = encrypt_value(
                    s3_config['secret_access_key']
                )
                del s3_config['secret_access_key']

        config = {
            'crm_id': crm_id,
            'crm_vendor': config_data.get('crm_vendor', 'other'),
            'api_key': config_data.get('api_key'),
            'settings': config_data.get('settings', self._get_default_settings()),
            'premium_features': config_data.get('premium_features', self._get_default_premium_features()),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

        if self._use_postgres():
            with self.lock:
                with postgres_transaction() as conn:
                    with conn.cursor() as cursor:
                        self._ensure_postgres_table(cursor)
                        self._postgres_save_config(cursor, crm_id, config)
            return self.get_config(crm_id)

        with self.lock:
            with json_file_lock(self.config_file):
                self._refresh_from_disk()
                self.configs[crm_id] = config
                self._save_configs()

        return self.get_config(crm_id)

    def update_config(self, crm_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update existing CRM configuration"""
        updates = deepcopy(updates)

        # Encrypt AWS credentials if being updated
        if 's3_delivery' in updates.get('settings', {}):
            s3_config = updates['settings']['s3_delivery']
            if 'secret_access_key' in s3_config:
                s3_config['secret_access_key_encrypted'] = encrypt_value(
                    s3_config['secret_access_key']
                )
                del s3_config['secret_access_key']

        if self._use_postgres():
            with self.lock:
                with postgres_transaction() as conn:
                    with conn.cursor() as cursor:
                        self._ensure_postgres_table(cursor)
                        config = self._postgres_fetch_config(cursor, crm_id)
                        if config is None:
                            return None
                        if 'settings' in updates:
                            config['settings'].update(updates['settings'])
                        if 'premium_features' in updates:
                            config['premium_features'].update(updates['premium_features'])
                        config['updated_at'] = datetime.now().isoformat()
                        self._postgres_save_config(cursor, crm_id, config)
            return self.get_config(crm_id)

        with self.lock:
            with json_file_lock(self.config_file):
                self._refresh_from_disk()
                if crm_id not in self.configs:
                    return None

                config = self.configs[crm_id]
                if 'settings' in updates:
                    config['settings'].update(updates['settings'])
                if 'premium_features' in updates:
                    config['premium_features'].update(updates['premium_features'])

                config['updated_at'] = datetime.now().isoformat()
                self._save_configs()

        return self.get_config(crm_id)

    def delete_config(self, crm_id: str) -> bool:
        """Delete CRM configuration"""
        if self._use_postgres():
            with self.lock:
                with postgres_transaction() as conn:
                    with conn.cursor() as cursor:
                        self._ensure_postgres_table(cursor)
                        existing = self._postgres_fetch_config(cursor, crm_id)
                        if existing is None:
                            return False
                        self._postgres_delete_config(cursor, crm_id)
            return True

        with self.lock:
            with json_file_lock(self.config_file):
                self._refresh_from_disk()
                if crm_id in self.configs:
                    del self.configs[crm_id]
                    self._save_configs()
                    return True
                return False

    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default CRM settings"""
        return {
            'auto_validate': False,
            'enable_smtp': True,
            'enable_catchall': True,
            'include_catchall_in_clean': False,
            'include_role_based_in_clean': False,
            'callback_url': None,
            'callback_signature_secret': None,
            'max_concurrent_validations': 5,
            's3_delivery': {
                'enabled': False,
                'bucket_name': None,
                'region': 'us-east-1',
                'access_key_id': None,
                'secret_access_key_encrypted': None,
                'prefix': 'validated-leads/',
                'file_format': 'csv',
                'encryption': {
                    'enabled': True,
                    'type': 'SSE-S3',
                    'kms_key_id': None
                },
                'upload_lists': {
                    'clean': True,
                    'catchall': False,
                    'invalid': False,
                    'disposable': False,
                    'role_based': False
                }
            }
        }

    def _get_default_premium_features(self) -> Dict[str, bool]:
        """Get default premium features (all disabled)"""
        return {
            'auto_validate': False,
            'smtp_verification': True,
            'catchall_detection': True,
            's3_delivery': False,
            'priority_processing': False
        }


# Global singleton instance
_config_manager = None


def get_crm_config_manager() -> CRMConfigManager:
    """Get global CRM config manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = CRMConfigManager()
    return _config_manager

