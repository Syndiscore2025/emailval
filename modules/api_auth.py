import os
import json
import secrets
import hashlib
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from flask import request, jsonify
from functools import wraps


API_KEYS_DB_FILE = os.path.join('data', 'api_keys.json')
API_AUTH_ENABLED = os.getenv('API_AUTH_ENABLED', 'false').lower() == 'true'


class APIKeyManager:
    """Simple JSON-backed API key store with per-key rate limiting."""

    def __init__(self, db_file: str = API_KEYS_DB_FILE):
        self.db_file = db_file
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.db_file):
            os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
            return {"keys": {}}
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and "keys" in data:
                    return data
        except Exception:
            pass
        return {"keys": {}}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)

    @property
    def keys(self) -> Dict[str, Dict[str, Any]]:
        return self.data.setdefault("keys", {})

    def generate_key(self, name: str, rate_limit_per_minute: int = 60) -> Dict[str, Any]:
        """Generate a new API key and persist it.

        Returns a dict containing the secret key (only once) and metadata.
        """
        api_key = "ev_" + secrets.token_urlsafe(32)
        key_id = "ak_" + secrets.token_hex(8)
        key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        now = datetime.utcnow().isoformat()

        self.keys[key_id] = {
            "key_hash": key_hash,
            "name": name,
            "created_at": now,
            "active": True,
            "rate_limit_per_minute": int(rate_limit_per_minute),
            "usage_total": 0,
            "window_start": None,
            "window_count": 0,
        }
        self._save()

        meta = {k: v for k, v in self.keys[key_id].items() if k != "key_hash"}
        meta["key_id"] = key_id
        return {"api_key": api_key, "metadata": meta}

    def get_key_by_secret(self, api_key: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Return (key_id, key_data) for the provided secret, if valid."""
        key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        for key_id, data in self.keys.items():
            if data.get("key_hash") == key_hash:
                return key_id, data
        return None

    def register_usage(self, key_id: str) -> Tuple[bool, Optional[int]]:
        """Increment usage counters and enforce per-minute rate limit.

        Returns (allowed, retry_after_seconds).
        """
        data = self.keys.get(key_id)
        if not data or not data.get("active", False):
            return False, None

        limit = int(data.get("rate_limit_per_minute", 60))
        now = datetime.utcnow()

        window_start_str = data.get("window_start")
        window_count = int(data.get("window_count") or 0)

        if window_start_str:
            try:
                window_start = datetime.fromisoformat(window_start_str)
            except Exception:
                window_start = now
                window_count = 0
        else:
            window_start = now
            window_count = 0

        elapsed = (now - window_start).total_seconds()
        if elapsed >= 60:
            window_start = now
            window_count = 0

        if window_count >= limit:
            retry_after = max(0, 60 - int(elapsed))
            return False, retry_after

        window_count += 1
        data["window_start"] = window_start.isoformat()
        data["window_count"] = window_count
        data["usage_total"] = int(data.get("usage_total", 0)) + 1
        self._save()

        return True, None

    def list_keys(self):
        result = []
        for key_id, data in self.keys.items():
            meta = {k: v for k, v in data.items() if k != "key_hash"}
            meta["key_id"] = key_id
            result.append(meta)
        return result

    def revoke_key(self, key_id: str) -> bool:
        data = self.keys.get(key_id)
        if not data:
            return False
        data["active"] = False
        self._save()
        return True

    def get_usage(self, key_id: str) -> Optional[Dict[str, Any]]:
        data = self.keys.get(key_id)
        if not data:
            return None
        meta = {k: v for k, v in data.items() if k != "key_hash"}
        meta["key_id"] = key_id
        return meta


_api_key_manager: Optional[APIKeyManager] = None


def get_key_manager() -> APIKeyManager:
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


def require_api_key(func):
    """Decorator that enforces API key auth when enabled.

    If API_AUTH_ENABLED is false (default in development), the wrapped
    endpoint behaves as usual without requiring a key.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not API_AUTH_ENABLED:
            return func(*args, **kwargs)

        api_key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if not api_key:
            return jsonify({"error": "Missing API key"}), 401

        manager = get_key_manager()
        resolved = manager.get_key_by_secret(api_key)
        if not resolved:
            return jsonify({"error": "Invalid API key"}), 401

        key_id, _ = resolved
        allowed, retry_after = manager.register_usage(key_id)
        if not allowed:
            response = jsonify({
                "error": "Rate limit exceeded for this API key",
                "key_id": key_id,
            })
            status_code = 429
            if retry_after is not None:
                response.headers["Retry-After"] = str(retry_after)
            return response, status_code

        return func(*args, **kwargs)

    return wrapper

