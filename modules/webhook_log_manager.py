"""Webhook logging and lightweight idempotency persistence."""

import json
import os
import uuid
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

from modules.json_store import json_file_lock, load_json_data, save_json_data_atomic


WEBHOOK_LOGS_FILE = os.path.join('data', 'webhook_logs.json')
MAX_WEBHOOK_EVENTS = 1000
MAX_IDEMPOTENCY_RECORDS = 500


class WebhookLogManager:
    """Persist webhook events and idempotent responses in a JSON file."""

    def __init__(self, data_file: str = WEBHOOK_LOGS_FILE):
        self.data_file = data_file
        self.lock = Lock()
        self.data = self._load_data()

    def _empty_data(self) -> Dict[str, Any]:
        return {
            'events': [],
            'idempotency_keys': {},
            'external_deliveries': {},
        }

    def _load_data(self) -> Dict[str, Any]:
        data = load_json_data(self.data_file, self._empty_data())
        return data if isinstance(data, dict) else self._empty_data()

    def _refresh_from_disk(self):
        if os.path.exists(self.data_file):
            try:
                self.data = self._load_data()
            except Exception:
                pass

    def _save_data(self):
        save_json_data_atomic(self.data_file, self.data)

    def _trim(self):
        events = self.data.setdefault('events', [])
        if len(events) > MAX_WEBHOOK_EVENTS:
            self.data['events'] = events[-MAX_WEBHOOK_EVENTS:]

        keys = self.data.setdefault('idempotency_keys', {})
        while len(keys) > MAX_IDEMPOTENCY_RECORDS:
            oldest_key = next(iter(keys), None)
            if oldest_key is None:
                break
            keys.pop(oldest_key, None)

        active_event_ids = {event.get('event_id') for event in self.data.get('events', [])}
        deliveries = self.data.setdefault('external_deliveries', {})
        for event_id in list(deliveries.keys()):
            if event_id not in active_event_ids:
                deliveries.pop(event_id, None)

    def record_event(self, event_type: str, **details) -> Dict[str, Any]:
        with self.lock:
            with json_file_lock(self.data_file):
                self._refresh_from_disk()
                event = {
                    'event_id': f"wh_{uuid.uuid4().hex[:12]}",
                    'timestamp': datetime.now().isoformat(),
                    'event_type': event_type,
                    **details,
                }
                self.data.setdefault('events', []).append(event)
                self._trim()
                self._save_data()
                return event

    def store_idempotent_response(
        self,
        idempotency_key: str,
        request_hash: str,
        response_status: int,
        response_body: Dict[str, Any],
        response_headers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with self.lock:
            with json_file_lock(self.data_file):
                self._refresh_from_disk()
                entry = {
                    'idempotency_key': idempotency_key,
                    'request_hash': request_hash,
                    'response_status': response_status,
                    'response_body': response_body,
                    'response_headers': response_headers or {},
                    'stored_at': datetime.now().isoformat(),
                }
                self.data.setdefault('idempotency_keys', {})[idempotency_key] = entry
                self._trim()
                self._save_data()
                return entry

    def get_idempotent_response(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            self._refresh_from_disk()
            return self.data.get('idempotency_keys', {}).get(idempotency_key)

    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.lock:
            self._refresh_from_disk()
            events = self.data.get('events', [])
            return list(reversed(events))[:limit]

    def get_events(self) -> List[Dict[str, Any]]:
        with self.lock:
            self._refresh_from_disk()
            return list(self.data.get('events', []))

    def get_external_delivery(self, event_id: str, destination_key: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            self._refresh_from_disk()
            return self.data.get('external_deliveries', {}).get(event_id, {}).get(destination_key)

    def store_external_delivery(
        self,
        event_id: str,
        destination_key: str,
        status: str,
        response_status: Optional[int] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.lock:
            with json_file_lock(self.data_file):
                self._refresh_from_disk()
                entry = {
                    'status': status,
                    'response_status': response_status,
                    'error': error,
                    'updated_at': datetime.now().isoformat(),
                }
                deliveries = self.data.setdefault('external_deliveries', {})
                deliveries.setdefault(event_id, {})[destination_key] = entry
                self._trim()
                self._save_data()
                return entry

    def get_summary(self) -> Dict[str, Any]:
        """Return aggregate webhook and callback metrics for admin visibility."""
        with self.lock:
            self._refresh_from_disk()
            events = self.data.get('events', [])
            summary = {
                'total_events': len(events),
                'total_idempotency_keys': len(self.data.get('idempotency_keys', {})),
                'last_event_at': events[-1].get('timestamp') if events else None,
                'webhook_received': 0,
                'webhook_completed': 0,
                'webhook_accepted': 0,
                'webhook_failed': 0,
                'idempotent_replays': 0,
                'idempotency_conflicts': 0,
                'callback_queued': 0,
                'callback_delivered': 0,
                'callback_retrying': 0,
                'callback_failed': 0,
                'event_type_counts': {},
            }

            for event in events:
                event_type = event.get('event_type', 'unknown')
                status = event.get('status')
                summary['event_type_counts'][event_type] = (
                    summary['event_type_counts'].get(event_type, 0) + 1
                )

                if event_type == 'webhook_received':
                    summary['webhook_received'] += 1
                elif event_type == 'webhook_processed':
                    if status == 'completed':
                        summary['webhook_completed'] += 1
                    elif status == 'accepted':
                        summary['webhook_accepted'] += 1
                    elif status == 'failed':
                        summary['webhook_failed'] += 1
                elif event_type == 'webhook_idempotent_replay':
                    summary['idempotent_replays'] += 1
                elif event_type == 'webhook_idempotency_conflict':
                    summary['idempotency_conflicts'] += 1
                elif event_type == 'callback_delivery':
                    if status == 'queued':
                        summary['callback_queued'] += 1
                    elif status == 'delivered':
                        summary['callback_delivered'] += 1
                    elif status == 'retrying':
                        summary['callback_retrying'] += 1
                    elif status == 'failed':
                        summary['callback_failed'] += 1

            terminal_callbacks = summary['callback_delivered'] + summary['callback_failed']
            summary['callback_success_rate'] = (
                round((summary['callback_delivered'] / terminal_callbacks) * 100, 1)
                if terminal_callbacks
                else None
            )
            return summary


_webhook_log_manager = None


def get_webhook_log_manager() -> WebhookLogManager:
    global _webhook_log_manager
    if _webhook_log_manager is None:
        _webhook_log_manager = WebhookLogManager()
    return _webhook_log_manager