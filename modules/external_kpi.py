"""Helpers for optional external KPI export and polling summaries."""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


SUPPORTED_RANGES = {
    '24h': timedelta(hours=24),
    '7d': timedelta(days=7),
    '30d': timedelta(days=30),
    '90d': timedelta(days=90),
}


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() == 'true'


def external_kpi_enabled() -> bool:
    return _env_flag('EXTERNAL_KPI_ENABLED', default=False)


def get_external_kpi_event_url() -> str:
    return (os.getenv('EXTERNAL_KPI_EVENT_URL') or '').strip()


def get_external_kpi_api_key() -> str:
    return (os.getenv('EXTERNAL_KPI_API_KEY') or '').strip()


def get_external_kpi_auth_header() -> str:
    return (os.getenv('EXTERNAL_KPI_AUTH_HEADER') or 'X-Switchbox-Key').strip() or 'X-Switchbox-Key'


def get_external_kpi_app_slug() -> str:
    return (os.getenv('EXTERNAL_KPI_APP_SLUG') or 'email-validator').strip() or 'email-validator'


def external_kpi_configured() -> bool:
    return bool(get_external_kpi_event_url() and get_external_kpi_api_key())


def normalize_kpi_range(range_value: str) -> str:
    value = (range_value or '7d').strip().lower()
    aliases = {'1d': '24h', '1day': '24h', '7days': '7d', '30days': '30d', '90days': '90d'}
    normalized = aliases.get(value, value)
    return normalized if normalized in SUPPORTED_RANGES else '7d'


def _parse_timestamp(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _format_occurred_at(value: str) -> str:
    parsed = _parse_timestamp(value) or datetime.utcnow()
    return parsed.replace(microsecond=0).isoformat() + 'Z'


def filter_events_for_range(events: List[Dict[str, Any]], range_value: str) -> List[Dict[str, Any]]:
    normalized = normalize_kpi_range(range_value)
    cutoff = datetime.utcnow() - SUPPORTED_RANGES[normalized]
    filtered = []
    for event in events:
        parsed = _parse_timestamp(event.get('timestamp'))
        if parsed is None or parsed >= cutoff:
            filtered.append(event)
    return filtered


def get_event_status(event: Dict[str, Any]) -> str:
    status = str(event.get('status') or '').lower()
    if status in {'failed', 'rejected'}:
        return 'failed'
    if status in {'queued', 'retrying', 'received', 'accepted', 'replayed'}:
        return 'warning'
    return 'success'


def get_event_category(event: Dict[str, Any]) -> str:
    event_type = str(event.get('event_type') or '')
    if event_type == 'callback_delivery':
        return 'reliability'
    if 'failed' in event_type or 'conflict' in event_type:
        return 'reliability'
    if get_event_status(event) == 'failed':
        return 'reliability'
    return 'usage'


def get_feature_slug(event: Dict[str, Any]) -> str:
    event_type = str(event.get('event_type') or 'unknown')
    if event_type.startswith('webhook'):
        return 'webhook_validation'
    if event_type == 'callback_delivery':
        return str(event.get('source') or 'callback_delivery')
    return event_type


def build_external_kpi_payload(event: Dict[str, Any], app_slug: Optional[str] = None) -> Dict[str, Any]:
    metadata = {
        'internal_event_id': event.get('event_id'),
        'source': event.get('source'),
        'response_status': event.get('response_status') or event.get('status_code'),
        'integration_mode': event.get('integration_mode'),
        'crm_vendor': event.get('crm_vendor'),
        'job_id': event.get('job_id'),
        'idempotency_key': event.get('idempotency_key'),
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, '')}

    payload = {
        'app_slug': app_slug or get_external_kpi_app_slug(),
        'event_name': event.get('event') or event.get('event_type') or 'unknown',
        'event_category': get_event_category(event),
        'status': get_event_status(event),
        'occurred_at': _format_occurred_at(event.get('timestamp')),
        'feature_slug': get_feature_slug(event),
        'metadata': metadata,
    }
    if isinstance(event.get('email_count'), int):
        payload['numeric_value'] = event['email_count']
    return payload


def build_kpi_summary(
    events: List[Dict[str, Any]],
    range_value: str = '7d',
    activity_limit: int = 20,
    app_slug: Optional[str] = None,
) -> Dict[str, Any]:
    normalized = normalize_kpi_range(range_value)
    filtered = filter_events_for_range(events, normalized)
    totals = {
        'total_events': len(filtered),
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
    }
    features: Dict[str, Dict[str, int]] = {}

    for event in filtered:
        event_type = event.get('event_type')
        status = event.get('status')
        if event_type == 'webhook_received':
            totals['webhook_received'] += 1
        elif event_type == 'webhook_processed':
            if status == 'completed':
                totals['webhook_completed'] += 1
            elif status == 'accepted':
                totals['webhook_accepted'] += 1
            elif status == 'failed':
                totals['webhook_failed'] += 1
        elif event_type == 'webhook_idempotent_replay':
            totals['idempotent_replays'] += 1
        elif event_type == 'webhook_idempotency_conflict':
            totals['idempotency_conflicts'] += 1
        elif event_type == 'callback_delivery':
            if status == 'queued':
                totals['callback_queued'] += 1
            elif status == 'delivered':
                totals['callback_delivered'] += 1
            elif status == 'retrying':
                totals['callback_retrying'] += 1
            elif status == 'failed':
                totals['callback_failed'] += 1

        feature_slug = get_feature_slug(event)
        feature = features.setdefault(feature_slug, {'events': 0, 'success': 0, 'warning': 0, 'failed': 0})
        feature['events'] += 1
        feature[get_event_status(event)] += 1

    terminal_callbacks = totals['callback_delivered'] + totals['callback_failed']
    totals['callback_success_rate'] = (
        round((totals['callback_delivered'] / terminal_callbacks) * 100, 1)
        if terminal_callbacks else None
    )

    sorted_events = sorted(
        filtered,
        key=lambda event: _parse_timestamp(event.get('timestamp')) or datetime.min,
        reverse=True,
    )
    recent_activity = [
        build_external_kpi_payload(event, app_slug=app_slug)
        for event in sorted_events[:max(1, activity_limit)]
    ]

    return {
        'app_slug': app_slug or get_external_kpi_app_slug(),
        'range': normalized,
        'totals': totals,
        'features': features,
        'recent_activity': recent_activity,
    }