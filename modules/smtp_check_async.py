"""
Async SMTP Email Verification Module
Verifies mailbox existence via SMTP using concurrent connections
This is 10-50x faster than sequential validation
"""
import smtplib
import socket
import os
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils import extract_domain
from .domain_check import validate_domain


def validate_smtp_single(email: str, timeout: int = 5, sender: Optional[str] = None) -> Dict[str, Any]:
    """
    Verify single email mailbox existence via SMTP (optimized version)
    
    Args:
        email: Email address to validate
        timeout: SMTP connection timeout in seconds (reduced from 10 to 5)
        sender: Email address to use as sender
        
    Returns:
        Dictionary with validation results
    """
    errors = []
    domain = extract_domain(email)
    
    if sender is None:
        sender = os.getenv('SMTP_SENDER', 'noreply@validator.local')
    
    if not domain:
        return {
            "email": email,
            "valid": False,
            "mailbox_exists": False,
            "smtp_response": "",
            "errors": ["Could not extract domain from email"],
            "skipped": False
        }
    
    # First check if domain has valid MX records
    domain_check = validate_domain(email)
    if not domain_check["valid"]:
        return {
            "email": email,
            "valid": False,
            "mailbox_exists": False,
            "smtp_response": "",
            "errors": ["Domain has no valid MX or A records"],
            "skipped": True
        }
    
    # Get MX server
    mx_records = domain_check.get("mx_records", [])
    if not mx_records:
        mx_host = domain
    else:
        mx_host = mx_records[0].rstrip('.')
    
    smtp_response = ""
    mailbox_exists = False
    
    try:
        # Connect to SMTP server with reduced timeout
        with smtplib.SMTP(timeout=timeout) as smtp:
            smtp.connect(mx_host)
            smtp_response = smtp.helo()[1].decode('utf-8', errors='ignore')
            smtp.mail(sender)
            
            # Send RCPT TO - this checks if mailbox exists
            code, message = smtp.rcpt(email)
            smtp_response += f" | RCPT: {code} {message.decode('utf-8', errors='ignore')}"
            
            if code in [250, 251]:
                mailbox_exists = True
            else:
                errors.append(f"Mailbox verification failed: {code}")
            
    except (smtplib.SMTPServerDisconnected, smtplib.SMTPResponseException, 
            socket.timeout, socket.gaierror, ConnectionRefusedError, Exception) as e:
        errors.append(f"SMTP error: {str(e)[:100]}")
    
    return {
        "email": email,
        "valid": mailbox_exists,
        "mailbox_exists": mailbox_exists,
        "smtp_response": smtp_response[:200],  # Limit response length
        "errors": errors,
        "skipped": False
    }


def validate_smtp_batch(emails: List[str], max_workers: int = 20, timeout: int = 5, 
                       sender: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Validate multiple emails concurrently using thread pool
    
    This is MUCH faster than sequential validation:
    - Sequential: 100 emails × 3 seconds = 5 minutes
    - Parallel (20 workers): 100 emails ÷ 20 × 3 seconds = 15 seconds
    
    Args:
        emails: List of email addresses to validate
        max_workers: Number of concurrent SMTP connections (default: 20)
        timeout: SMTP connection timeout per email (default: 5 seconds)
        sender: Email address to use as sender
        
    Returns:
        Dictionary mapping email -> validation result
    """
    results = {}
    
    # Use ThreadPoolExecutor for concurrent SMTP connections
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all validation tasks
        future_to_email = {
            executor.submit(validate_smtp_single, email, timeout, sender): email 
            for email in emails
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_email):
            email = future_to_email[future]
            try:
                result = future.result()
                results[email] = result
            except Exception as e:
                # If thread fails, return error result
                results[email] = {
                    "email": email,
                    "valid": False,
                    "mailbox_exists": False,
                    "smtp_response": "",
                    "errors": [f"Thread error: {str(e)}"],
                    "skipped": False
                }
    
    return results


def validate_smtp_batch_with_progress(emails: List[str], max_workers: int = 20, 
                                      timeout: int = 5, sender: Optional[str] = None,
                                      progress_callback=None) -> Dict[str, Dict[str, Any]]:
    """
    Validate multiple emails concurrently with progress tracking
    
    Args:
        emails: List of email addresses to validate
        max_workers: Number of concurrent SMTP connections
        timeout: SMTP connection timeout per email
        sender: Email address to use as sender
        progress_callback: Optional function(completed, total) to track progress
        
    Returns:
        Dictionary mapping email -> validation result
    """
    results = {}
    total = len(emails)
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_email = {
            executor.submit(validate_smtp_single, email, timeout, sender): email 
            for email in emails
        }
        
        for future in as_completed(future_to_email):
            email = future_to_email[future]
            try:
                result = future.result()
                results[email] = result
            except Exception as e:
                results[email] = {
                    "email": email,
                    "valid": False,
                    "mailbox_exists": False,
                    "smtp_response": "",
                    "errors": [f"Thread error: {str(e)}"],
                    "skipped": False
                }
            
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
    
    return results

