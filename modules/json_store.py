import copy
import json
import os
import tempfile
from contextlib import contextmanager
from typing import Any, Iterator


if os.name == 'nt':
    import msvcrt
else:
    import fcntl


def _clone_default(default_value: Any) -> Any:
    return copy.deepcopy(default_value)


@contextmanager
def json_file_lock(data_file: str) -> Iterator[None]:
    """Acquire an exclusive lock file for a JSON-backed state file."""
    lock_file_path = f"{data_file}.lock"
    lock_dir = os.path.dirname(lock_file_path)
    if lock_dir:
        os.makedirs(lock_dir, exist_ok=True)

    lock_file = open(lock_file_path, 'a+b')
    try:
        if os.name == 'nt':
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b'0')
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        yield
    finally:
        try:
            if os.name == 'nt':
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()


def load_json_data(data_file: str, default_value: Any) -> Any:
    """Load JSON data and fall back to a deep-copied default value."""
    if not os.path.exists(data_file):
        return _clone_default(default_value)

    try:
        with open(data_file, 'r', encoding='utf-8') as file_handle:
            return json.load(file_handle)
    except Exception:
        return _clone_default(default_value)


def save_json_data_atomic(data_file: str, data: Any) -> None:
    """Persist JSON data using a temp file plus atomic replacement."""
    data_dir = os.path.dirname(data_file) or '.'
    os.makedirs(data_dir, exist_ok=True)

    file_name = os.path.basename(data_file)
    file_descriptor, temp_file = tempfile.mkstemp(
        prefix=f'.{file_name}.',
        suffix='.tmp',
        dir=data_dir,
    )

    try:
        with os.fdopen(file_descriptor, 'w', encoding='utf-8') as file_handle:
            json.dump(data, file_handle, indent=2)
            file_handle.flush()
            os.fsync(file_handle.fileno())

        os.replace(temp_file, data_file)
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)