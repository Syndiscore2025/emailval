import os
import json
import secrets
import hashlib
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional, Tuple

from flask import request, jsonify
from functools import wraps

from modules.json_store import json_file_lock, load_json_data, save_json_data_atomic


API_KEYS_DB_FILE = os.path.join('data', 'api_keys.json')


def _env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean feature flag from the environment."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() == 'true'


def is_api_auth_enabled() -> bool:
    """Return whether API key auth is currently enabled."""
    return _env_flag('API_AUTH_ENABLED', default=False)


def allow_api_key_query_param() -> bool:
    """Allow query-param API keys only outside production by default.

    This preserves local/development convenience while making it easy to run
    header-only auth in production without changing code.
    """
    configured = os.getenv('API_KEY_ALLOW_QUERY_PARAM')
    if configured is not None:
        return configured.lower() == 'true'

    environment = (os.getenv('FLASK_ENV') or os.getenv('ENVIRONMENT') or '').lower()
    return environment != 'production'


class APIKeyManager:
    """Simple JSON-backed API key store with per-key rate limiting."""

    def __init__(self, db_file: str = API_KEYS_DB_FILE):
        self.db_file = db_file
        self.lock = Lock()
        self.data = self._load()

    def _empty_data(self) -> Dict[str, Any]:
        return {"keys": {}}

    def _load(self) -> Dict[str, Any]:
        data = load_json_data(self.db_file, self._empty_data())
        if isinstance(data, dict) and isinstance(data.get("keys"), dict):
            return data
        return self._empty_data()

    def _refresh_from_disk(self) -> None:
        self.data = self._load()

    def _save(self) -> None:
        save_json_data_atomic(self.db_file, self.data)

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

        with self.lock:
            with json_file_lock(self.db_file):
                self._refresh_from_disk()
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
        with self.lock:
            self._refresh_from_disk()
            for key_id, data in self.keys.items():
                if data.get("key_hash") == key_hash:
                    return key_id, data
        return None

    def register_usage(self, key_id: str) -> Tuple[bool, Optional[int]]:
        """Increment usage counters and enforce per-minute rate limit.

        Returns (allowed, retry_after_seconds).
        """
        with self.lock:
            with json_file_lock(self.db_file):
                self._refresh_from_disk()
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
        with self.lock:
            self._refresh_from_disk()
            result = []
            for key_id, data in self.keys.items():
                meta = {k: v for k, v in data.items() if k != "key_hash"}
                meta["key_id"] = key_id
                result.append(meta)
            return result

    def revoke_key(self, key_id: str) -> bool:
        with self.lock:
            with json_file_lock(self.db_file):
                self._refresh_from_disk()
                data = self.keys.get(key_id)
                if not data:
                    return False
                data["active"] = False
                self._save()
                return True

    def get_usage(self, key_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            self._refresh_from_disk()
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
        if not is_api_auth_enabled():
            return func(*args, **kwargs)

        api_key = request.headers.get("X-API-Key")
        query_param_key = request.args.get("api_key")

        if not api_key and query_param_key and not allow_api_key_query_param():
            return jsonify({
                "error": "API key query parameters are disabled. Use the X-API-Key header.",
            }), 401

        if not api_key and allow_api_key_query_param():
            api_key = query_param_key

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

