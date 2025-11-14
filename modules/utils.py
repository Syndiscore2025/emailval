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


def calculate_deliverability_score(validation_result: Dict[str, Any]) -> int:
    """
    Calculate deliverability score (0-100) based on validation checks.

    Weighting:
    - Syntax valid: 20 points
    - Domain valid + MX records: 30 points
    - Not disposable + not role-based: 20 points
    - SMTP valid: 30 points

    Args:
        validation_result: Validation result dictionary from validate_email

    Returns:
        Deliverability score (0-100)
    """
    score = 0

    # Syntax check (20 points)
    if validation_result.get('checks', {}).get('syntax', {}).get('valid'):
        score += 20

    # Domain check (30 points)
    domain_check = validation_result.get('checks', {}).get('domain', {})
    if domain_check.get('valid') and domain_check.get('has_mx'):
        score += 30

    # Type check (20 points)
    type_check = validation_result.get('checks', {}).get('type', {})
    if not type_check.get('is_disposable') and not type_check.get('is_role_based'):
        score += 20

    # SMTP check (30 points)
    if validation_result.get('checks', {}).get('smtp', {}).get('valid'):
        score += 30

    return score


def get_deliverability_rating(score: int) -> str:
    """
    Get deliverability rating based on score.

    Args:
        score: Deliverability score (0-100)

    Returns:
        Rating string: 'Excellent', 'Good', 'Fair', or 'Poor'
    """
    if score >= 90:
        return 'Excellent'
    elif score >= 70:
        return 'Good'
    elif score >= 50:
        return 'Fair'
    else:
        return 'Poor'

