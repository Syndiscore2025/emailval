import importlib
import os
from contextlib import contextmanager
from typing import Iterator


RUNTIME_STATE_BACKEND_ENV = 'RUNTIME_STATE_BACKEND'
RUNTIME_STATE_DATABASE_URL_ENV = 'RUNTIME_STATE_DATABASE_URL'
RUNTIME_STATE_TABLE_PREFIX_ENV = 'RUNTIME_STATE_TABLE_PREFIX'
DEFAULT_RUNTIME_STATE_BACKEND = 'json'
DEFAULT_RUNTIME_STATE_TABLE_PREFIX = 'emailval'


def get_runtime_state_backend() -> str:
    """Return the configured runtime-state backend name."""
    configured = (os.getenv(RUNTIME_STATE_BACKEND_ENV) or DEFAULT_RUNTIME_STATE_BACKEND).strip().lower()
    return 'postgres' if configured == 'postgres' else 'json'


def use_postgres_runtime_state() -> bool:
    """Return whether runtime state should use Postgres."""
    return get_runtime_state_backend() == 'postgres'


def get_runtime_state_database_url() -> str:
    """Return the configured Postgres DSN for runtime state."""
    return (os.getenv(RUNTIME_STATE_DATABASE_URL_ENV) or os.getenv('DATABASE_URL') or '').strip()


def get_runtime_state_table_name(suffix: str) -> str:
    """Build a safe Postgres table name for runtime-state tables."""
    prefix = (os.getenv(RUNTIME_STATE_TABLE_PREFIX_ENV) or DEFAULT_RUNTIME_STATE_TABLE_PREFIX).strip().lower()
    safe_prefix = ''.join(ch if ch.isalnum() or ch == '_' else '_' for ch in prefix).strip('_')
    safe_suffix = ''.join(ch if ch.isalnum() or ch == '_' else '_' for ch in suffix.lower()).strip('_')

    if not safe_prefix:
        safe_prefix = DEFAULT_RUNTIME_STATE_TABLE_PREFIX
    if not safe_suffix:
        raise ValueError('Runtime state table suffix must not be empty')
    if safe_prefix[0].isdigit():
        safe_prefix = f'_{safe_prefix}'
    if safe_suffix[0].isdigit():
        safe_suffix = f'_{safe_suffix}'

    return f'{safe_prefix}_{safe_suffix}'


def load_psycopg_module():
    """Import psycopg lazily so JSON deployments need no DB dependency."""
    try:
        return importlib.import_module('psycopg')
    except ImportError as exc:  # pragma: no cover - exercised only when missing
        raise RuntimeError(
            'Postgres runtime state requires the psycopg package. '
            'Install it before setting RUNTIME_STATE_BACKEND=postgres.'
        ) from exc


def open_postgres_connection():
    """Open a Postgres connection for runtime-state operations."""
    database_url = get_runtime_state_database_url()
    if not database_url:
        raise RuntimeError(
            'Postgres runtime state requires RUNTIME_STATE_DATABASE_URL or DATABASE_URL.'
        )

    psycopg = load_psycopg_module()
    return psycopg.connect(database_url)


@contextmanager
def postgres_transaction() -> Iterator[object]:
    """Yield a Postgres connection inside a managed transaction."""
    connection = open_postgres_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()