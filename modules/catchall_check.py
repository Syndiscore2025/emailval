"""
Catch-All Domain Detection Module

Detects if a domain is configured as catch-all (accept-all), which means it accepts
emails to ANY address regardless of whether the mailbox actually exists.

This is critical for email validation accuracy because catch-all domains will return
"250 OK" for SMTP verification even for non-existent mailboxes, causing false positives.
"""
import smtplib
import socket
import os
import random
import string
from typing import Dict, Any, Optional
from .utils import extract_domain


def generate_random_email(domain: str) -> str:
    """Generate a random email address for catch-all testing
    
    Args:
        domain: Domain to test (e.g., "example.com")
        
    Returns:
        Random email like "xk7j2m9q@example.com"
    """
    # Generate random string (very unlikely to be a real mailbox)
    random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
    return f"{random_string}@{domain}"


def check_catchall_domain(
    domain: str,
    mx_host: str,
    timeout: int = 3,
    sender: Optional[str] = None,
    num_tests: int = 2
) -> Dict[str, Any]:
    """Check if a domain is configured as catch-all
    
    Tests the domain by sending SMTP verification requests for random email addresses
    that are extremely unlikely to exist. If the server accepts them, it's catch-all.
    
    Args:
        domain: Domain to test (e.g., "example.com")
        mx_host: MX server hostname to connect to
        timeout: SMTP connection timeout in seconds
        sender: Email address to use as sender
        num_tests: Number of random emails to test (default: 2 for reliability)
        
    Returns:
        {
            "is_catchall": bool,
            "confidence": "high" | "medium" | "low",
            "test_results": [...],
            "errors": [...]
        }
    """
    if sender is None:
        sender = os.getenv("SMTP_SENDER", "noreply@validator.local")
    
    errors = []
    test_results = []
    accepts_count = 0
    rejects_count = 0
    
    # Test with multiple random emails to increase confidence
    for i in range(num_tests):
        random_email = generate_random_email(domain)
        
        try:
            with smtplib.SMTP(host=mx_host, timeout=timeout) as smtp:
                smtp.helo()
                smtp.mail(sender)
                code, message = smtp.rcpt(random_email)
                
                response = message.decode('utf-8', errors='ignore')
                
                test_results.append({
                    "email": random_email,
                    "code": code,
                    "response": response[:100]
                })
                
                # If server accepts the random email, it's likely catch-all
                if code in [250, 251]:
                    accepts_count += 1
                else:
                    rejects_count += 1
                    
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPResponseException,
                socket.timeout, socket.gaierror, ConnectionRefusedError, Exception) as e:
            errors.append(f"Test {i+1} failed: {str(e)[:100]}")
            # If we can't test, we can't determine catch-all status
            continue
    
    # Determine catch-all status based on test results
    is_catchall = False
    confidence = "low"
    
    if accepts_count == 0 and rejects_count == 0:
        # All tests failed - can't determine
        is_catchall = False
        confidence = "low"
        errors.append("Unable to determine catch-all status - all tests failed")
    elif accepts_count == num_tests:
        # All random emails accepted - definitely catch-all
        is_catchall = True
        confidence = "high"
    elif accepts_count > 0:
        # Some accepted, some rejected - likely catch-all but not certain
        is_catchall = True
        confidence = "medium"
    else:
        # All rejected - not catch-all
        is_catchall = False
        confidence = "high"
    
    return {
        "is_catchall": is_catchall,
        "confidence": confidence,
        "tests_run": num_tests,
        "accepts_count": accepts_count,
        "rejects_count": rejects_count,
        "test_results": test_results,
        "errors": errors
    }


def check_catchall_from_email(
    email: str,
    timeout: int = 3,
    sender: Optional[str] = None,
    mx_records: Optional[list] = None
) -> Dict[str, Any]:
    """Check if the domain of an email is catch-all
    
    Convenience wrapper that extracts domain and MX from email address.
    
    Args:
        email: Email address to check (e.g., "test@example.com")
        timeout: SMTP connection timeout in seconds
        sender: Email address to use as sender
        mx_records: Optional pre-fetched MX records (to avoid duplicate DNS lookups)
        
    Returns:
        Same as check_catchall_domain()
    """
    domain = extract_domain(email)
    
    if not domain:
        return {
            "is_catchall": False,
            "confidence": "low",
            "tests_run": 0,
            "accepts_count": 0,
            "rejects_count": 0,
            "test_results": [],
            "errors": ["Could not extract domain from email"]
        }
    
    # Get MX host
    if mx_records and len(mx_records) > 0:
        mx_host = mx_records[0].rstrip(".")
    else:
        # If no MX records provided, use domain directly
        # (caller should have already validated domain/MX in phase 1)
        mx_host = domain
    
    return check_catchall_domain(domain, mx_host, timeout, sender)

