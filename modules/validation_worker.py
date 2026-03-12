"""Shared worker-backed queue for validation jobs."""

import logging
import os
import queue
import threading
from typing import Any, Callable, Optional


logger = logging.getLogger(__name__)


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


class ValidationWorker:
    """Run validation work on a small shared daemon worker pool."""

    def __init__(self, worker_count: Optional[int] = None, max_queue_size: Optional[int] = None):
        self.worker_count = worker_count if worker_count is not None else _int_env('VALIDATION_WORKERS', 1)
        self.max_queue_size = max_queue_size if max_queue_size is not None else _int_env('VALIDATION_QUEUE_SIZE', 500)
        self.queue: queue.Queue = queue.Queue(maxsize=self.max_queue_size)
        self._lock = threading.Lock()
        self._started = False
        self._threads = []

    def ensure_started(self) -> None:
        with self._lock:
            if self._started:
                return
            for index in range(self.worker_count):
                thread = threading.Thread(
                    target=self._worker_loop,
                    args=(index + 1,),
                    daemon=True,
                    name=f'validation-worker-{index + 1}',
                )
                thread.start()
                self._threads.append(thread)
            self._started = True

    def submit(self, func: Callable[..., Any], *args, job_name: str = 'validation_job', **kwargs) -> bool:
        self.ensure_started()
        try:
            self.queue.put_nowait((func, args, kwargs, job_name))
            return True
        except queue.Full:
            logger.warning('Validation queue full; using fallback thread', extra={'job_name': job_name})
            return False

    def get_status(self) -> dict:
        """Return lightweight worker health details for monitoring endpoints."""
        return {
            'started': self._started,
            'configured_workers': self.worker_count,
            'alive_workers': sum(1 for thread in self._threads if thread.is_alive()),
            'queue_size': self.queue.qsize(),
            'queue_capacity': self.max_queue_size,
        }

    def _worker_loop(self, worker_number: int) -> None:
        while True:
            func, args, kwargs, job_name = self.queue.get()
            try:
                func(*args, **kwargs)
            except Exception:
                logger.exception('Validation job crashed', extra={
                    'job_name': job_name,
                    'worker_number': worker_number,
                })
            finally:
                self.queue.task_done()


_validation_worker = None


def get_validation_worker() -> ValidationWorker:
    global _validation_worker
    if _validation_worker is None:
        _validation_worker = ValidationWorker()
    return _validation_worker


def dispatch_validation_job(func: Callable[..., Any], *args, job_name: str = 'validation_job', **kwargs) -> bool:
    """Queue validation work, falling back to a one-off daemon thread if needed."""
    worker = get_validation_worker()
    queued = worker.submit(func, *args, job_name=job_name, **kwargs)
    if queued:
        return True

    def _run_fallback() -> None:
        try:
            func(*args, **kwargs)
        except Exception:
            logger.exception('Fallback validation job crashed', extra={'job_name': job_name})

    thread = threading.Thread(target=_run_fallback, daemon=True, name=f'{job_name}-fallback')
    thread.start()
    return False