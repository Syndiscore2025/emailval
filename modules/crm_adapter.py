"""
CRM Compatibility Layer

Provides standardized request/response formats for CRM integrations
(Salesforce, HubSpot, custom CRM, etc.)
"""
from typing import Dict, Any, List, Optional
from datetime import datetime


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

    # Extract emails from crm_context if present
    emails = []
    if isinstance(crm_context, list):
        for record in crm_context:
            if isinstance(record, dict) and 'email' in record:
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
    # Build email -> crm_record mapping
    email_to_record = {}
    if isinstance(crm_context, list):
        for record in crm_context:
            if isinstance(record, dict) and 'email' in record:
                email_to_record[record['email'].strip().lower()] = record

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
                if k not in ['email', 'record_id', 'id']
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
        'summary': summary,
        'records': records,
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
    # Build email -> crm_record mapping
    email_to_record = {}
    if isinstance(crm_context, list):
        for record in crm_context:
            if isinstance(record, dict) and 'email' in record:
                email_to_record[record['email'].strip().lower()] = record

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
                if k not in ['email', 'record_id', 'id']
            }

        enriched_results.append(enriched)

    # Segregate results
    segregated = segregate_validation_results(
        enriched_results,
        include_catchall_in_clean,
        include_role_based_in_clean
    )

    # Build summary
    summary = {
        'total': len(enriched_results),
        'clean': len(segregated['clean']),
        'catchall': len(segregated['catchall']),
        'invalid': len(segregated['invalid']),
        'disposable': len(segregated['disposable']),
        'role_based': len(segregated['role_based']),
        'valid': sum(1 for r in enriched_results if r['status'] == 'valid'),
    }

    response = {
        'event': event,
        'integration_mode': integration_mode,
        'crm_vendor': crm_vendor,
        'summary': summary,
        'lists': segregated,
        'timestamp': datetime.now().isoformat()
    }

    if upload_id:
        response['upload_id'] = upload_id

    if job_id:
        response['job_id'] = job_id

    if s3_delivery:
        response['s3_delivery'] = s3_delivery

    return response

