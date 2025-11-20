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
from typing import Dict, Any, Optional
from datetime import datetime
from cryptography.fernet import Fernet
import base64


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
    
    def __init__(self):
        self.config_file = CRM_CONFIG_FILE
        self.configs = self._load_configs()
    
    def _load_configs(self) -> Dict[str, Any]:
        """Load CRM configurations from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ERROR] Failed to load CRM configs: {e}")
                return {}
        return {}
    
    def _save_configs(self):
        """Save CRM configurations to file"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.configs, f, indent=2)
    
    def get_config(self, crm_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific CRM client"""
        config = self.configs.get(crm_id)
        if not config:
            return None
        
        # Decrypt AWS credentials before returning
        if 's3_delivery' in config.get('settings', {}):
            s3_config = config['settings']['s3_delivery']
            if 'secret_access_key_encrypted' in s3_config:
                s3_config['secret_access_key'] = decrypt_value(
                    s3_config['secret_access_key_encrypted']
                )
        
        return config
    
    def create_config(self, crm_id: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new CRM configuration"""
        # Encrypt AWS credentials if present
        if 's3_delivery' in config_data.get('settings', {}):
            s3_config = config_data['settings']['s3_delivery']
            if 'secret_access_key' in s3_config:
                s3_config['secret_access_key_encrypted'] = encrypt_value(
                    s3_config['secret_access_key']
                )
                # Remove plain text secret
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
        
        self.configs[crm_id] = config
        self._save_configs()
        return self.get_config(crm_id)

    def update_config(self, crm_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update existing CRM configuration"""
        if crm_id not in self.configs:
            return None

        # Encrypt AWS credentials if being updated
        if 's3_delivery' in updates.get('settings', {}):
            s3_config = updates['settings']['s3_delivery']
            if 'secret_access_key' in s3_config:
                s3_config['secret_access_key_encrypted'] = encrypt_value(
                    s3_config['secret_access_key']
                )
                del s3_config['secret_access_key']

        # Merge updates
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

