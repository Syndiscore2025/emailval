"""
Email Syntax Validation Module
Validates email addresses against RFC 5322 standards
"""
import re
from typing import Dict, Any


# RFC 5322 compliant email regex pattern
EMAIL_REGEX = re.compile(
    r'^(?:[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+)*|'
    r'"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")'
    r'@(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?|'
    r'\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
    r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-zA-Z0-9-]*[a-zA-Z0-9]:'
    r'(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])$'
)


def validate_syntax(email: str) -> Dict[str, Any]:
    """
    Validate email syntax according to RFC 5322
    
    Args:
        email: Email address to validate
        
    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "errors": list of error messages
        }
    """
    errors = []
    
    # Basic checks
    if not email:
        errors.append("Email is empty")
        return {"valid": False, "errors": errors}
    
    if not isinstance(email, str):
        errors.append("Email must be a string")
        return {"valid": False, "errors": errors}
    
    # Length check
    if len(email) > 320:  # RFC 5321 limit
        errors.append("Email exceeds maximum length of 320 characters")
    
    # Must contain @
    if '@' not in email:
        errors.append("Email must contain @ symbol")
        return {"valid": False, "errors": errors}
    
    # Split into local and domain parts
    parts = email.rsplit('@', 1)
    if len(parts) != 2:
        errors.append("Email has invalid format")
        return {"valid": False, "errors": errors}
    
    local_part, domain_part = parts
    
    # Local part checks
    if not local_part:
        errors.append("Local part (before @) is empty")
    elif len(local_part) > 64:
        errors.append("Local part exceeds maximum length of 64 characters")
    
    # Domain part checks
    if not domain_part:
        errors.append("Domain part (after @) is empty")
    elif len(domain_part) > 255:
        errors.append("Domain part exceeds maximum length of 255 characters")
    elif '.' not in domain_part:
        errors.append("Domain must contain at least one dot")
    elif domain_part.startswith('.') or domain_part.endswith('.'):
        errors.append("Domain cannot start or end with a dot")
    elif '..' in domain_part:
        errors.append("Domain cannot contain consecutive dots")
    
    # Check against RFC 5322 regex
    if not EMAIL_REGEX.match(email):
        if not errors:  # Only add generic error if no specific errors found
            errors.append("Email does not match RFC 5322 format")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def is_valid_syntax(email: str) -> bool:
    """
    Quick boolean check for email syntax validity
    
    Args:
        email: Email address to validate
        
    Returns:
        True if syntax is valid, False otherwise
    """
    result = validate_syntax(email)
    return result["valid"]

