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
from modules.runtime_state_backend import (
    get_runtime_state_table_name,
    postgres_transaction,
    use_postgres_runtime_state,
)


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
        self.backend = 'postgres' if use_postgres_runtime_state() else 'json'
        self.postgres_table = get_runtime_state_table_name('api_keys')
        self._postgres_table_ready = False
        self.data = self._empty_data()
        if self._use_postgres():
            self._ensure_postgres_table()
        else:
            self.data = self._load()

    def _use_postgres(self) -> bool:
        return self.backend == 'postgres'

    def _empty_data(self) -> Dict[str, Any]:
        return {"keys": {}}

    def _load(self) -> Dict[str, Any]:
        data = load_json_data(self.db_file, self._empty_data())
        if isinstance(data, dict) and isinstance(data.get("keys"), dict):
            return data
        return self._empty_data()

    def _refresh_from_disk(self) -> None:
        if self._use_postgres():
            return
        self.data = self._load()

    def _save(self) -> None:
        if self._use_postgres():
            return
        save_json_data_atomic(self.db_file, self.data)

    def _ensure_postgres_table(self) -> None:
        if not self._use_postgres() or self._postgres_table_ready:
            return

        with postgres_transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.postgres_table} (
                        key_id TEXT PRIMARY KEY,
                        key_hash TEXT NOT NULL UNIQUE,
                        key_data TEXT NOT NULL
                    )
                    """
                )

        self._postgres_table_ready = True

    def _deserialize_key_data(self, raw_value: Any) -> Dict[str, Any]:
        if isinstance(raw_value, dict):
            return dict(raw_value)
        if isinstance(raw_value, (bytes, bytearray)):
            raw_value = raw_value.decode('utf-8')
        if not raw_value:
            return {}
        data = json.loads(raw_value)
        return data if isinstance(data, dict) else {}

    def _postgres_fetch_key_record(self, cursor, *, key_id: Optional[str] = None,
                                   key_hash: Optional[str] = None,
                                   for_update: bool = False) -> Optional[Tuple[str, Dict[str, Any]]]:
        clauses = []
        params = []
        if key_id is not None:
            clauses.append('key_id = %s')
            params.append(key_id)
        if key_hash is not None:
            clauses.append('key_hash = %s')
            params.append(key_hash)
        if not clauses:
            raise ValueError('A Postgres API key lookup requires key_id or key_hash')

        query = (
            f"SELECT key_id, key_hash, key_data FROM {self.postgres_table} "
            f"WHERE {' AND '.join(clauses)}"
        )
        if for_update:
            query += ' FOR UPDATE'

        cursor.execute(query, tuple(params))
        row = cursor.fetchone()
        if not row:
            return None

        resolved_key_id, resolved_key_hash, raw_data = row
        data = self._deserialize_key_data(raw_data)
        if resolved_key_hash and 'key_hash' not in data:
            data['key_hash'] = resolved_key_hash
        return resolved_key_id, data

    def _postgres_upsert_key(self, cursor, key_id: str, key_data: Dict[str, Any]) -> None:
        cursor.execute(
            f"""
            INSERT INTO {self.postgres_table} (key_id, key_hash, key_data)
            VALUES (%s, %s, %s)
            ON CONFLICT (key_id) DO UPDATE
            SET key_hash = EXCLUDED.key_hash,
                key_data = EXCLUDED.key_data
            """,
            (key_id, key_data.get('key_hash'), json.dumps(key_data)),
        )

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
        key_data = {
            "key_hash": key_hash,
            "name": name,
            "created_at": now,
            "active": True,
            "rate_limit_per_minute": int(rate_limit_per_minute),
            "usage_total": 0,
            "window_start": None,
            "window_count": 0,
        }

        with self.lock:
            if self._use_postgres():
                self._ensure_postgres_table()
                with postgres_transaction() as connection:
                    with connection.cursor() as cursor:
                        self._postgres_upsert_key(cursor, key_id, key_data)
                meta = {k: v for k, v in key_data.items() if k != 'key_hash'}
            else:
                with json_file_lock(self.db_file):
                    self._refresh_from_disk()
                    self.keys[key_id] = key_data
                    self._save()
                    meta = {k: v for k, v in self.keys[key_id].items() if k != "key_hash"}

        meta["key_id"] = key_id
        return {"api_key": api_key, "metadata": meta}

    def get_key_by_secret(self, api_key: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Return (key_id, key_data) for the provided secret, if valid."""
        key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        with self.lock:
            if self._use_postgres():
                self._ensure_postgres_table()
                with postgres_transaction() as connection:
                    with connection.cursor() as cursor:
                        return self._postgres_fetch_key_record(cursor, key_hash=key_hash)

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
            if self._use_postgres():
                self._ensure_postgres_table()
                with postgres_transaction() as connection:
                    with connection.cursor() as cursor:
                        resolved = self._postgres_fetch_key_record(cursor, key_id=key_id, for_update=True)
                        if not resolved:
                            return False, None
                        _, data = resolved
                        if not data.get("active", False):
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
                        self._postgres_upsert_key(cursor, key_id, data)
                        return True, None

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
            if self._use_postgres():
                self._ensure_postgres_table()
                with postgres_transaction() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            f"SELECT key_id, key_data FROM {self.postgres_table}"
                        )
                        result = []
                        for key_id, raw_data in cursor.fetchall():
                            data = self._deserialize_key_data(raw_data)
                            meta = {k: v for k, v in data.items() if k != "key_hash"}
                            meta["key_id"] = key_id
                            result.append(meta)
                        return result

            self._refresh_from_disk()
            result = []
            for key_id, data in self.keys.items():
                meta = {k: v for k, v in data.items() if k != "key_hash"}
                meta["key_id"] = key_id
                result.append(meta)
            return result

    def revoke_key(self, key_id: str) -> bool:
        with self.lock:
            if self._use_postgres():
                self._ensure_postgres_table()
                with postgres_transaction() as connection:
                    with connection.cursor() as cursor:
                        resolved = self._postgres_fetch_key_record(cursor, key_id=key_id, for_update=True)
                        if not resolved:
                            return False
                        _, data = resolved
                        data["active"] = False
                        self._postgres_upsert_key(cursor, key_id, data)
                        return True

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
            if self._use_postgres():
                self._ensure_postgres_table()
                with postgres_transaction() as connection:
                    with connection.cursor() as cursor:
                        resolved = self._postgres_fetch_key_record(cursor, key_id=key_id)
                        if not resolved:
                            return None
                        _, data = resolved
                        meta = {k: v for k, v in data.items() if k != "key_hash"}
                        meta["key_id"] = key_id
                        return meta

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

