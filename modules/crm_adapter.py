"""
CRM Compatibility Layer

Provides standardized request/response formats for CRM integrations
(Salesforce, HubSpot, custom CRM, etc.)
"""
from typing import Dict, Any, List, Optional


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

        enriched = {
            'email': result.get('email'),
            'status': 'valid' if result.get('valid') else 'invalid',
            'checks': result.get('checks', {}),
            'errors': result.get('errors', []),
        }

        # Add CRM-specific identifiers
        if crm_record:
            enriched['crm_record_id'] = crm_record.get('record_id') or crm_record.get('id')
            enriched['crm_metadata'] = {
                k: v for k, v in crm_record.items()
                if k not in ['email', 'record_id', 'id']
            }

        records.append(enriched)

    # Build summary
    summary = {
        'total': len(records),
        'valid': sum(1 for r in records if r['status'] == 'valid'),
        'invalid': sum(1 for r in records if r['status'] == 'invalid'),
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

