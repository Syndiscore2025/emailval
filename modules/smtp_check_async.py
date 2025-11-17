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


def validate_smtp_single(
    email: str,
    timeout: int = 3,
    sender: Optional[str] = None,
    domain_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Verify a single mailbox via SMTP (optimized for batch use).

    This function is used heavily in the threaded batch validator, so it is
    designed to:
    - Reuse DNS/domain results from phase 1 when provided (via ``domain_info``)
      so we don't do a second round of DNS lookups in each worker thread.
    - Fail *open* on network issues: if we can't complete SMTP due to our
      connection problems, we treat the mailbox as "unverifiable/assumed valid"
      instead of marking it invalid.
    """
    errors: List[str] = []
    domain = extract_domain(email)

    if sender is None:
        sender = os.getenv("SMTP_SENDER", "noreply@validator.local")

    if not domain:
        return {
            "email": email,
            "valid": False,
            "mailbox_exists": False,
            "smtp_response": "",
            "errors": ["Could not extract domain from email"],
            "skipped": False,
        }

    # -----------------------------
    # Domain / MX host resolution
    # -----------------------------
    # For large batch jobs we *always* do domain/DNS checks in phase 1.
    # When ``domain_info`` is provided we reuse those results here instead of
    # doing a second round of DNS lookups in every worker thread.
    if domain_info is not None:
        domain_check = {
            "valid": domain_info.get("valid", False),
            "has_mx": domain_info.get("has_mx", False),
            "has_a": domain_info.get("has_a", False),
            "mx_records": domain_info.get("mx_records", []),
            "errors": domain_info.get("errors", []),
        }
    else:
        domain_check = validate_domain(email)

    if not domain_check.get("valid", False):
        # Already known to be bad or unresolvable; skip SMTP and surface a
        # clear "skipped" flag so callers can distinguish this case.
        return {
            "email": email,
            "valid": False,
            "mailbox_exists": False,
            "smtp_response": "",
            "errors": domain_check.get("errors")
            or ["Domain has no valid MX or A records"],
            "skipped": True,
        }

    mx_records = domain_check.get("mx_records", [])
    if not mx_records:
        mx_host = domain
    else:
        mx_host = mx_records[0].rstrip(".")

    smtp_response = ""
    mailbox_exists = False
    smtp_status = "unknown"  # unknown, verified, unverifiable, invalid
    confidence = "low"  # low, medium, high

    try:
        # Connect to SMTP server with timeout. Passing host here ensures the
        # timeout is applied to the TCP connect() call itself.
        with smtplib.SMTP(host=mx_host, timeout=timeout) as smtp:
            smtp_response = smtp.helo()[1].decode("utf-8", errors="ignore")
            smtp.mail(sender)

            # Send RCPT TO - this checks if mailbox exists
            code, message = smtp.rcpt(email)
            smtp_response += f" | RCPT: {code} {message.decode('utf-8', errors='ignore')}"

            # Smart response code handling
            if code in [250, 251]:
                # Mailbox definitely exists
                mailbox_exists = True
                smtp_status = "verified"
                confidence = "high"
            elif code in [450, 451, 452]:
                # Temporary failure - assume valid but unverified
                mailbox_exists = True  # Don't reject on temporary errors
                smtp_status = "unverifiable"
                confidence = "medium"
                errors.append(f"Temporary failure (code {code}) - assuming valid")
            elif code == 550:
                # Could be "mailbox doesn't exist" OR "domain blocks verification"
                # Check if it's a major provider that blocks verification
                major_providers = [
                    "gmail.com",
                    "yahoo.com",
                    "hotmail.com",
                    "outlook.com",
                    "aol.com",
                    "icloud.com",
                    "live.com",
                    "msn.com",
                ]
                if any(provider in domain.lower() for provider in major_providers):
                    # Major provider blocking verification - assume valid
                    mailbox_exists = True
                    smtp_status = "unverifiable"
                    confidence = "medium"
                    errors.append(
                        f"Provider blocks verification (code {code}) - assuming valid"
                    )
                else:
                    # Smaller domain, likely invalid
                    mailbox_exists = False
                    smtp_status = "invalid"
                    confidence = "high"
                    errors.append(f"Mailbox doesn't exist (code {code})")
            elif code in [421, 554]:
                # Service unavailable or policy rejection - assume valid
                mailbox_exists = True
                smtp_status = "unverifiable"
                confidence = "low"
                errors.append(
                    f"Service unavailable (code {code}) - assuming valid"
                )
            else:
                # Unknown code - be conservative and assume valid
                mailbox_exists = True
                smtp_status = "unverifiable"
                confidence = "low"
                errors.append(f"Unknown SMTP code {code} - assuming valid")

    except (
        smtplib.SMTPServerDisconnected,
        smtplib.SMTPResponseException,
        socket.timeout,
        socket.gaierror,
        ConnectionRefusedError,
        Exception,
    ) as e:
        # Network/connection errors - assume valid (don't penalize for our
        # connection issues).
        mailbox_exists = True
        smtp_status = "unverifiable"
        confidence = "low"
        errors.append(f"SMTP error: {str(e)[:100]} - assuming valid")

    return {
        "email": email,
        "valid": mailbox_exists,
        "mailbox_exists": mailbox_exists,
        "smtp_status": smtp_status,  # verified, unverifiable, invalid, unknown
        "confidence": confidence,  # high, medium, low
        "smtp_response": smtp_response[:200],  # Limit response length
        "errors": errors,
        "skipped": False,
    }


def validate_smtp_batch(emails: List[str], max_workers: int = 50, timeout: int = 3,
                       sender: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Validate multiple emails concurrently using thread pool

    This is MUCH faster than sequential validation:
    - Sequential: 100 emails × 3 seconds = 5 minutes
    - Parallel (50 workers): 100 emails ÷ 50 × 3 seconds = 6 seconds

    Args:
        emails: List of email addresses to validate
        max_workers: Number of concurrent SMTP connections (default: 50, increased from 20)
        timeout: SMTP connection timeout per email (default: 3 seconds, reduced from 5)
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


def validate_smtp_batch_with_progress(
    emails: List[str],
    max_workers: int = 50,
    timeout: int = 3,
    sender: Optional[str] = None,
    progress_callback=None,
    email_domain_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Validate multiple emails concurrently with progress tracking.

    ``email_domain_map`` lets us pass in the domain/DNS results from phase 1 so
    we don't redo DNS resolution work inside each worker thread.
    """
    results: Dict[str, Dict[str, Any]] = {}
    total = len(emails)
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_email: Dict[Any, str] = {}
        for email in emails:
            domain_info = (
                email_domain_map.get(email) if email_domain_map is not None else None
            )
            future = executor.submit(
                validate_smtp_single,
                email,
                timeout,
                sender,
                domain_info,
            )
            future_to_email[future] = email

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
                    "smtp_status": "unknown",
                    "confidence": "low",
                    "smtp_response": "",
                    "errors": [f"Thread error: {str(e)}"],
                    "skipped": False,
                }

            completed += 1
            if progress_callback:
                progress_callback(completed, total)

    return results

