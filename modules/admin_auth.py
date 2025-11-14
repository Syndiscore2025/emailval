"""
Admin Authentication Module
Handles admin login, session management, and password hashing
"""
import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import session, redirect, url_for, request, jsonify
from typing import Optional, Dict, Any


# Admin credentials file
ADMIN_CREDS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'admin_creds.json')


def hash_password(password: str, salt: Optional[str] = None) -> tuple:
    """
    Hash password with salt using SHA-256.
    
    Args:
        password: Plain text password
        salt: Optional salt (generated if not provided)
        
    Returns:
        Tuple of (hashed_password, salt)
    """
    if salt is None:
        salt = secrets.token_hex(32)
    
    # Hash password with salt
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return pwd_hash, salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """
    Verify password against stored hash.
    
    Args:
        password: Plain text password to verify
        stored_hash: Stored password hash
        salt: Salt used for hashing
        
    Returns:
        True if password matches
    """
    pwd_hash, _ = hash_password(password, salt)
    return pwd_hash == stored_hash


def load_admin_credentials() -> Dict[str, Any]:
    """Load admin credentials from file"""
    if os.path.exists(ADMIN_CREDS_FILE):
        try:
            with open(ADMIN_CREDS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    
    # Default admin credentials (change in production!)
    default_password = os.getenv('ADMIN_PASSWORD', 'admin123')
    pwd_hash, salt = hash_password(default_password)
    
    return {
        "username": "admin",
        "password_hash": pwd_hash,
        "salt": salt,
        "created_at": datetime.now().isoformat()
    }


def save_admin_credentials(creds: Dict[str, Any]):
    """Save admin credentials to file"""
    os.makedirs(os.path.dirname(ADMIN_CREDS_FILE), exist_ok=True)
    with open(ADMIN_CREDS_FILE, 'w') as f:
        json.dump(creds, f, indent=2)


def authenticate_admin(username: str, password: str) -> bool:
    """
    Authenticate admin user.
    
    Args:
        username: Admin username
        password: Admin password
        
    Returns:
        True if authentication successful
    """
    creds = load_admin_credentials()
    
    if username != creds.get('username'):
        return False
    
    return verify_password(password, creds['password_hash'], creds['salt'])


def create_admin_session(username: str):
    """Create admin session"""
    session['admin_logged_in'] = True
    session['admin_username'] = username
    session['admin_login_time'] = datetime.now().isoformat()
    session.permanent = True


def destroy_admin_session():
    """Destroy admin session"""
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    session.pop('admin_login_time', None)


def is_admin_logged_in() -> bool:
    """Check if admin is logged in"""
    return session.get('admin_logged_in', False)


def require_admin_login(f):
    """
    Decorator to require admin login for routes.
    Redirects to login page if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin_logged_in():
            return redirect(url_for('admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def require_admin_api(f):
    """
    Decorator to require admin authentication for API endpoints.
    Returns 401 if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin_logged_in():
            return jsonify({"error": "Unauthorized - Admin login required"}), 401
        return f(*args, **kwargs)
    return decorated_function


def change_admin_password(old_password: str, new_password: str) -> bool:
    """
    Change admin password.
    
    Args:
        old_password: Current password
        new_password: New password
        
    Returns:
        True if password changed successfully
    """
    creds = load_admin_credentials()
    
    # Verify old password
    if not verify_password(old_password, creds['password_hash'], creds['salt']):
        return False
    
    # Hash new password
    pwd_hash, salt = hash_password(new_password)
    creds['password_hash'] = pwd_hash
    creds['salt'] = salt
    creds['updated_at'] = datetime.now().isoformat()
    
    save_admin_credentials(creds)
    return True

