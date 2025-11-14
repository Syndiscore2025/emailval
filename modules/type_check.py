"""
Email Type Classification Module
Detects disposable and role-based email addresses
"""
from typing import Dict, Any, Set
from .utils import extract_domain


# Common disposable email domains
DISPOSABLE_DOMAINS: Set[str] = {
    '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'tempmail.com',
    'throwaway.email', 'temp-mail.org', 'fakeinbox.com', 'trashmail.com',
    'yopmail.com', 'maildrop.cc', 'getnada.com', 'sharklasers.com',
    'guerrillamail.info', 'grr.la', 'guerrillamail.biz', 'guerrillamail.de',
    'spam4.me', 'mailnesia.com', 'emailondeck.com', 'mintemail.com',
    'mytemp.email', 'mohmal.com', 'emailfake.com', 'throwawaymail.com',
    'tempinbox.com', 'dispostable.com', 'mailcatch.com', 'burnermail.io',
    'guerrillamailblock.com', 'pokemail.net', 'spamgourmet.com', 'mailexpire.com',
    'tempr.email', 'getairmail.com', 'anonbox.net', 'anonymbox.com'
}

# Common role-based email prefixes
ROLE_BASED_PREFIXES: Set[str] = {
    'admin', 'administrator', 'info', 'support', 'sales', 'contact',
    'help', 'service', 'office', 'webmaster', 'postmaster', 'hostmaster',
    'noreply', 'no-reply', 'donotreply', 'do-not-reply', 'marketing',
    'billing', 'accounts', 'hr', 'jobs', 'careers', 'press', 'media',
    'legal', 'privacy', 'security', 'abuse', 'feedback', 'hello',
    'team', 'general', 'enquiries', 'inquiries', 'customerservice',
    'customersupport', 'techsupport', 'tech', 'it', 'notifications'
}


def validate_type(email: str) -> Dict[str, Any]:
    """
    Classify email type and detect disposable/role-based addresses
    
    Args:
        email: Email address to validate
        
    Returns:
        Dictionary with validation results:
        {
            "is_disposable": bool,
            "is_role_based": bool,
            "warnings": list of warning messages,
            "email_type": str (personal/role/disposable)
        }
    """
    warnings = []
    domain = extract_domain(email)
    
    if not domain:
        return {
            "is_disposable": False,
            "is_role_based": False,
            "warnings": ["Could not extract domain from email"],
            "email_type": "unknown"
        }
    
    # Check if disposable
    is_disposable = domain.lower() in DISPOSABLE_DOMAINS
    if is_disposable:
        warnings.append(f"Email uses disposable domain: {domain}")
    
    # Check if role-based
    local_part = email.split('@')[0].lower()
    is_role_based = local_part in ROLE_BASED_PREFIXES
    if is_role_based:
        warnings.append(f"Email appears to be role-based: {local_part}")
    
    # Determine email type
    if is_disposable:
        email_type = "disposable"
    elif is_role_based:
        email_type = "role"
    else:
        email_type = "personal"
    
    return {
        "is_disposable": is_disposable,
        "is_role_based": is_role_based,
        "warnings": warnings,
        "email_type": email_type
    }


def is_disposable(email: str) -> bool:
    """
    Quick check if email is from a disposable domain
    
    Args:
        email: Email address to check
        
    Returns:
        True if disposable, False otherwise
    """
    result = validate_type(email)
    return result["is_disposable"]


def is_role_based(email: str) -> bool:
    """
    Quick check if email is role-based
    
    Args:
        email: Email address to check
        
    Returns:
        True if role-based, False otherwise
    """
    result = validate_type(email)
    return result["is_role_based"]

