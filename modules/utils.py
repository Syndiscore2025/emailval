"""
Utility functions for email validation system
"""
import re
from typing import Dict, Any, List


def normalize_email(email: str) -> str:
    """
    Normalize email address by stripping whitespace and converting to lowercase
    
    Args:
        email: Raw email string
        
    Returns:
        Normalized email string
    """
    if not email:
        return ""
    return email.strip().lower()


def is_email_like(text: str) -> bool:
    """
    Quick check if a string looks like an email address
    
    Args:
        text: String to check
        
    Returns:
        True if text appears to be an email
    """
    if not text or not isinstance(text, str):
        return False
    return '@' in text and '.' in text.split('@')[-1]


def deduplicate_emails(emails: List[str]) -> List[str]:
    """
    Remove duplicate emails while preserving order
    
    Args:
        emails: List of email addresses
        
    Returns:
        Deduplicated list of emails
    """
    seen = set()
    result = []
    for email in emails:
        normalized = normalize_email(email)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def create_validation_result(email: str, valid: bool, checks: Dict[str, Any], 
                            errors: List[str] = None) -> Dict[str, Any]:
    """
    Create standardized validation result dictionary
    
    Args:
        email: Email address validated
        valid: Overall validation status
        checks: Dictionary of individual check results
        errors: List of error messages
        
    Returns:
        Standardized result dictionary
    """
    return {
        "email": email,
        "valid": valid,
        "checks": checks,
        "errors": errors or []
    }


def extract_domain(email: str) -> str:
    """
    Extract domain from email address
    
    Args:
        email: Email address
        
    Returns:
        Domain portion of email
    """
    if '@' not in email:
        return ""
    return email.split('@')[-1]

