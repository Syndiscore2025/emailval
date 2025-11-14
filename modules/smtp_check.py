"""
SMTP Email Verification Module
Verifies mailbox existence via SMTP (optional, can be slow)
"""
import smtplib
import socket
import os
from typing import Dict, Any, Optional
from .utils import extract_domain
from .domain_check import validate_domain


def validate_smtp(email: str, timeout: int = 10, sender: Optional[str] = None) -> Dict[str, Any]:
    """
    Verify email mailbox existence via SMTP

    Args:
        email: Email address to validate
        timeout: SMTP connection timeout in seconds
        sender: Email address to use as sender in SMTP verification (uses env var SMTP_SENDER if not provided)

    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "mailbox_exists": bool,
            "smtp_response": str,
            "errors": list of error messages,
            "skipped": bool
        }
    """
    errors = []
    domain = extract_domain(email)

    # Use provided sender, or get from environment, or use default
    if sender is None:
        sender = os.getenv('SMTP_SENDER', 'noreply@validator.local')
    
    if not domain:
        return {
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
            "valid": False,
            "mailbox_exists": False,
            "smtp_response": "",
            "errors": ["Domain has no valid MX or A records"],
            "skipped": True
        }
    
    # Get MX server
    mx_records = domain_check.get("mx_records", [])
    if not mx_records:
        # If no MX records, try domain directly
        mx_host = domain
    else:
        # Use first MX record (highest priority)
        mx_host = mx_records[0].rstrip('.')
    
    smtp_response = ""
    mailbox_exists = False
    
    try:
        # Connect to SMTP server
        with smtplib.SMTP(timeout=timeout) as smtp:
            smtp.connect(mx_host)
            smtp_response = smtp.helo()[1].decode('utf-8', errors='ignore')
            
            # Send MAIL FROM
            smtp.mail(sender)
            
            # Send RCPT TO - this is where we check if mailbox exists
            code, message = smtp.rcpt(email)
            smtp_response += f" | RCPT: {code} {message.decode('utf-8', errors='ignore')}"
            
            # 250 = mailbox exists, 251 = user not local (but will forward)
            if code in [250, 251]:
                mailbox_exists = True
            else:
                errors.append(f"Mailbox verification failed: {code} {message.decode('utf-8', errors='ignore')}")
            
    except smtplib.SMTPServerDisconnected:
        errors.append("SMTP server disconnected")
    except smtplib.SMTPResponseException as e:
        errors.append(f"SMTP error: {e.smtp_code} {e.smtp_error.decode('utf-8', errors='ignore')}")
        smtp_response = f"{e.smtp_code} {e.smtp_error.decode('utf-8', errors='ignore')}"
    except socket.timeout:
        errors.append(f"SMTP connection timeout to {mx_host}")
    except socket.gaierror:
        errors.append(f"Could not resolve SMTP server: {mx_host}")
    except ConnectionRefusedError:
        errors.append(f"SMTP connection refused by {mx_host}")
    except Exception as e:
        errors.append(f"SMTP verification error: {str(e)}")
    
    return {
        "valid": mailbox_exists,
        "mailbox_exists": mailbox_exists,
        "smtp_response": smtp_response,
        "errors": errors,
        "skipped": False
    }


def is_valid_smtp(email: str, timeout: int = 10) -> bool:
    """
    Quick boolean check for SMTP mailbox validity
    
    Args:
        email: Email address to validate
        timeout: SMTP connection timeout in seconds
        
    Returns:
        True if mailbox exists, False otherwise
    """
    result = validate_smtp(email, timeout=timeout)
    return result["valid"]

