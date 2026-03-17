"""
CRM Compatibility Layer

Provides standardized request/response formats for CRM integrations
(Salesforce, HubSpot, custom CRM, etc.)
"""
from typing import Dict, Any, List, Optional
from datetime import datetime


INTEGRATION_CONTRACT_VERSION = 'v1'


def build_contract_metadata(response_format: str = 'standard') -> Dict[str, str]:
    """Build stable integration-contract metadata for API consumers."""
    return {
        'version': INTEGRATION_CONTRACT_VERSION,
        'response_format': response_format,
        'change_policy': 'additive',
    }


def segregate_validation_results(
    validation_results: List[Dict[str, Any]],
    include_catchall_in_clean: bool = False,
    include_role_based_in_clean: bool = False
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Segregate validation results into separate lists

    Args:
        validation_results: List of validation results
        include_catchall_in_clean: Whether to include catch-all emails in clean list
        include_role_based_in_clean: Whether to include role-based emails in clean list

    Returns:
        Dict with segregated lists: clean, catchall, invalid, disposable, role_based
    """
    segregated = {
        'clean': [],
        'catchall': [],
        'invalid': [],
        'disposable': [],
        'role_based': []
    }

    for result in validation_results:
        email = result.get('email')
        is_valid = result.get('valid', False)
        checks = result.get('checks', {})

        # Extract flags
        is_catchall = checks.get('catchall', {}).get('is_catchall', False)
        is_disposable = checks.get('type', {}).get('is_disposable', False)
        is_role_based = checks.get('type', {}).get('is_role_based', False)

        # Categorize email
        if not is_valid:
            segregated['invalid'].append(result)
        elif is_disposable:
            segregated['disposable'].append(result)
        elif is_catchall:
            segregated['catchall'].append(result)
            # Optionally include in clean list
            if include_catchall_in_clean:
                segregated['clean'].append(result)
        elif is_role_based:
            segregated['role_based'].append(result)
            # Optionally include in clean list
            if include_role_based_in_clean:
                segregated['clean'].append(result)
        else:
            # Valid, non-catchall, non-disposable, non-role-based
            segregated['clean'].append(result)

    return segregated


# ---------------------------------------------------------------------------
# Private helpers for multi-email support
# ---------------------------------------------------------------------------

def _build_email_to_record(crm_context: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Build a mapping of normalised email address → crm_context record.

    Handles both the legacy single-email field (``email``) and the new
    multi-email field (``emails``), so callers can pass either format.
    """
    mapping: Dict[str, Dict[str, Any]] = {}
    if not isinstance(crm_context, list):
        return mapping
    for record in crm_context:
        if not isinstance(record, dict):
            continue
        # Multi-email field (new format)
        if isinstance(record.get('emails'), list):
            for em in record['emails']:
                if em and isinstance(em, str):
                    mapping[em.strip().lower()] = record
        # Single-email field (legacy format)
        elif record.get('email') and isinstance(record['email'], str):
            mapping[record['email'].strip().lower()] = record
    return mapping


def _get_verdict(enriched_result: Dict[str, Any]) -> str:
    """Return the bucket name (verdict) for an already-enriched result dict."""
    if enriched_result.get('status') == 'invalid':
        return 'invalid'
    checks = enriched_result.get('checks', {})
    if checks.get('type', {}).get('is_disposable'):
        return 'disposable'
    if enriched_result.get('is_catchall'):
        return 'catchall'
    if checks.get('type', {}).get('is_role_based'):
        return 'role_based'
    return 'clean'


def _pick_best_email(email_results: List[Dict[str, Any]]) -> Optional[str]:
    """Return the highest-quality email from a record's email_results list.

    Priority: clean > catchall > role_based > disposable > invalid.
    """
    priority = ['clean', 'catchall', 'role_based', 'disposable', 'invalid']
    for verdict in priority:
        for er in email_results:
            if er.get('verdict') == verdict:
                return er.get('email')
    return None


def _build_records_by_id(
    enriched_results: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Group enriched email-level results by their CRM record_id.

    Returns a dict keyed by record_id.  Each value contains:
    - record_id
    - crm_metadata  (non-id, non-email fields from the crm_context record)
    - email_results (list of per-email verdict summaries)
    - best_email    (highest-quality email for this record)
    - has_clean     (True if at least one email is clean)
    - all_invalid   (True if every email is invalid)
    - email_count
    """
    records_by_id: Dict[str, Dict[str, Any]] = {}

    for result in enriched_results:
        rec_id = result.get('crm_record_id')
        if not rec_id:
            continue

        if rec_id not in records_by_id:
            records_by_id[rec_id] = {
                'record_id': rec_id,
                'crm_metadata': result.get('crm_metadata', {}),
                'email_results': [],
            }

        verdict = _get_verdict(result)
        records_by_id[rec_id]['email_results'].append({
            'email': result.get('email'),
            'verdict': verdict,
            'status': result.get('status'),
            'is_catchall': result.get('is_catchall', False),
        })

    # Compute per-record summary fields
    for rec in records_by_id.values():
        verdicts = [e['verdict'] for e in rec['email_results']]
        rec['best_email'] = _pick_best_email(rec['email_results'])
        rec['has_clean'] = 'clean' in verdicts
        rec['all_invalid'] = all(v == 'invalid' for v in verdicts)
        rec['email_count'] = len(rec['email_results'])

    return records_by_id


def parse_crm_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse incoming CRM webhook request and extract metadata.

    Args:
        data: Raw JSON payload from CRM webhook

    Returns:
        Dict with:
            - integration_mode: "crm" or "single_use"
            - crm_vendor: "salesforce", "hubspot", "custom", "other"
            - crm_context: list of record metadata
            - emails: extracted email addresses
    """
    integration_mode = data.get('integration_mode', 'single_use')
    crm_vendor = data.get('crm_vendor', 'other')
    crm_context = data.get('crm_context', [])

    # Extract emails from crm_context (handles both 'email' and 'emails' fields)
    emails = []
    if isinstance(crm_context, list):
        for record in crm_context:
            if not isinstance(record, dict):
                continue
            if isinstance(record.get('emails'), list):
                emails.extend([e for e in record['emails'] if e])
            elif record.get('email'):
                emails.append(record['email'])

    return {
        'integration_mode': integration_mode,
        'crm_vendor': crm_vendor,
        'crm_context': crm_context,
        'emails': emails,
    }


def build_crm_response(
    validation_results: List[Dict[str, Any]],
    crm_context: List[Dict[str, Any]],
    integration_mode: str = 'crm',
    crm_vendor: str = 'other',
    job_id: Optional[str] = None,
    event: str = 'validation.completed'
) -> Dict[str, Any]:
    """Build standardized CRM-friendly response.

    Args:
        validation_results: List of validation results from validate_email_complete
        crm_context: Original CRM context records
        integration_mode: "crm" or "single_use"
        crm_vendor: CRM vendor identifier
        job_id: Optional job ID for async operations
        event: Event type (validation.completed, validation.failed)

    Returns:
        Standardized CRM response with record mapping
    """
    # Build email -> crm_record mapping (handles single 'email' and multi 'emails')
    email_to_record = _build_email_to_record(crm_context)

    # Enrich validation results with CRM metadata
    records = []
    for result in validation_results:
        email = result.get('email', '').strip().lower()
        crm_record = email_to_record.get(email, {})

        # Extract catch-all status
        catchall_checks = result.get('checks', {}).get('catchall', {})
        is_catchall = catchall_checks.get('is_catchall', False)
        catchall_confidence = catchall_checks.get('confidence', 'low')

        enriched = {
            'email': result.get('email'),
            'status': 'valid' if result.get('valid') else 'invalid',
            'checks': result.get('checks', {}),
            'errors': result.get('errors', []),
            'is_catchall': is_catchall,
            'catchall_confidence': catchall_confidence,
        }

        # Add warnings if present
        if result.get('warnings'):
            enriched['warnings'] = result.get('warnings', [])

        # Add CRM-specific identifiers
        if crm_record:
            enriched['crm_record_id'] = crm_record.get('record_id') or crm_record.get('id')
            enriched['crm_metadata'] = {
                k: v for k, v in crm_record.items()
                if k not in ['email', 'emails', 'record_id', 'id']
            }

        records.append(enriched)

    # Build summary with catch-all count
    catchall_count = sum(1 for r in records if r.get('is_catchall', False))

    summary = {
        'total': len(records),
        'valid': sum(1 for r in records if r['status'] == 'valid'),
        'invalid': sum(1 for r in records if r['status'] == 'invalid'),
        'catchall': catchall_count,
    }

    response = {
        'event': event,
        'integration_mode': integration_mode,
        'crm_vendor': crm_vendor,
        'contract': build_contract_metadata('standard'),
        'summary': summary,
        'records': records,
        'timestamp': datetime.now().isoformat(),
    }

    if job_id:
        response['job_id'] = job_id

    return response


def get_crm_event_type(success: bool, has_errors: bool = False) -> str:
    """Determine CRM webhook event type.

    Args:
        success: Whether the validation completed successfully
        has_errors: Whether there were processing errors

    Returns:
        Event type string
    """
    if not success or has_errors:
        return 'validation.failed'
    return 'validation.completed'


def validate_crm_vendor(vendor: str) -> str:
    """Normalize and validate CRM vendor identifier.

    Args:
        vendor: Raw vendor string from request

    Returns:
        Normalized vendor identifier
    """
    if not vendor or not isinstance(vendor, str):
        return 'other'

    vendor_lower = vendor.lower().strip()

    known_vendors = {
        'salesforce': 'salesforce',
        'hubspot': 'hubspot',
        'custom': 'custom',
    }

    return known_vendors.get(vendor_lower, 'other')


def build_segregated_crm_response(
    validation_results: List[Dict[str, Any]],
    crm_context: List[Dict[str, Any]],
    integration_mode: str = 'crm',
    crm_vendor: str = 'other',
    upload_id: Optional[str] = None,
    job_id: Optional[str] = None,
    s3_delivery: Optional[Dict[str, Any]] = None,
    include_catchall_in_clean: bool = False,
    include_role_based_in_clean: bool = False,
    event: str = 'validation.completed'
) -> Dict[str, Any]:
    """
    Build CRM response with segregated lists

    Args:
        validation_results: List of validation results
        crm_context: Original CRM context records
        integration_mode: "crm" or "single_use"
        crm_vendor: CRM vendor identifier
        upload_id: Upload identifier
        job_id: Job identifier
        s3_delivery: S3 delivery information
        include_catchall_in_clean: Include catch-all in clean list
        include_role_based_in_clean: Include role-based in clean list
        event: Event type

    Returns:
        Segregated CRM response
    """
    # Build email -> crm_record mapping (handles single 'email' and multi 'emails')
    email_to_record = _build_email_to_record(crm_context)

    # Enrich validation results with CRM metadata
    enriched_results = []
    for result in validation_results:
        email = result.get('email', '').strip().lower()
        crm_record = email_to_record.get(email, {})

        # Extract catch-all status
        catchall_checks = result.get('checks', {}).get('catchall', {})
        is_catchall = catchall_checks.get('is_catchall', False)
        catchall_confidence = catchall_checks.get('confidence', 'low')

        enriched = {
            'email': result.get('email'),
            'status': 'valid' if result.get('valid') else 'invalid',
            'checks': result.get('checks', {}),
            'errors': result.get('errors', []),
            'is_catchall': is_catchall,
            'catchall_confidence': catchall_confidence,
        }

        # Add warnings if present
        if result.get('warnings'):
            enriched['warnings'] = result.get('warnings', [])

        # Add CRM-specific identifiers
        if crm_record:
            enriched['crm_record_id'] = crm_record.get('record_id') or crm_record.get('id')
            enriched['crm_metadata'] = {
                k: v for k, v in crm_record.items()
                if k not in ['email', 'emails', 'record_id', 'id']
            }

        enriched_results.append(enriched)

    # Segregate results
    segregated = segregate_validation_results(
        enriched_results,
        include_catchall_in_clean,
        include_role_based_in_clean
    )

    # Group results by CRM record_id (populated when crm_context is provided)
    records_by_id = _build_records_by_id(enriched_results)

    # Build summary
    summary = {
        'total': len(enriched_results),
        'clean': len(segregated['clean']),
        'catchall': len(segregated['catchall']),
        'invalid': len(segregated['invalid']),
        'disposable': len(segregated['disposable']),
        'role_based': len(segregated['role_based']),
        'valid': sum(1 for r in enriched_results if r['status'] == 'valid'),
        'record_count': len(records_by_id),
    }

    response = {
        'event': event,
        'integration_mode': integration_mode,
        'crm_vendor': crm_vendor,
        'contract': build_contract_metadata('segregated'),
        'summary': summary,
        'lists': segregated,
        'timestamp': datetime.now().isoformat()
    }

    # Include records_by_id only when there is CRM context to group by
    if records_by_id:
        response['records_by_id'] = records_by_id

    if upload_id:
        response['upload_id'] = upload_id

    if job_id:
        response['job_id'] = job_id

    if s3_delivery:
        response['s3_delivery'] = s3_delivery

    return response

