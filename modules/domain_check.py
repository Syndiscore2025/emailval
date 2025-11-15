"""
Email Domain Validation Module
Validates email domains using DNS MX and A record lookups
"""
import dns.resolver
import dns.exception
from typing import Dict, Any, List
from .utils import extract_domain

# Simple in-memory cache to avoid repeated DNS lookups for the same domain
# This dramatically speeds up large validations where many emails share
# the same domain (e.g., gmail.com) while keeping behavior identical.
_DOMAIN_CACHE: Dict[str, Dict[str, Any]] = {}


def validate_domain(email: str) -> Dict[str, Any]:
    """Validate email domain by checking DNS MX and A records with caching."""
    errors = []
    domain = extract_domain(email)

    if not domain:
        errors.append("Could not extract domain from email")
        return {
            "valid": False,
            "has_mx": False,
            "has_a": False,
            "mx_records": [],
            "errors": errors,
        }

    # Return cached result if we've already validated this domain
    cached = _DOMAIN_CACHE.get(domain)
    if cached is not None:
        return cached

    has_mx = False
    has_a = False
    mx_records: List[str] = []

    # Check for MX records
    try:
        mx_answers = dns.resolver.resolve(domain, 'MX')
        has_mx = True
        mx_records = [str(rdata.exchange) for rdata in mx_answers]
    except dns.resolver.NXDOMAIN:
        errors.append(f"Domain {domain} does not exist")
    except dns.resolver.NoAnswer:
        # No MX records, will check A records
        pass
    except dns.resolver.NoNameservers:
        errors.append(f"No nameservers available for domain {domain}")
    except dns.exception.Timeout:
        errors.append(f"DNS lookup timeout for domain {domain}")
    except Exception as e:
        errors.append(f"DNS MX lookup error: {str(e)}")

    # Check for A records (fallback if no MX)
    if not has_mx:
        try:
            a_answers = dns.resolver.resolve(domain, 'A')
            has_a = True
        except dns.resolver.NXDOMAIN:
            if "does not exist" not in str(errors):
                errors.append(f"Domain {domain} does not exist")
        except dns.resolver.NoAnswer:
            errors.append(f"Domain {domain} has no A records")
        except dns.resolver.NoNameservers:
            if "No nameservers" not in str(errors):
                errors.append(f"No nameservers available for domain {domain}")
        except dns.exception.Timeout:
            if "timeout" not in str(errors):
                errors.append(f"DNS lookup timeout for domain {domain}")
        except dns.exception.Timeout:
            if "timeout" not in str(errors):
                errors.append(f"DNS lookup timeout for domain {domain}")
        except Exception as e:
            errors.append(f"DNS A lookup error: {str(e)}")

    # Domain is valid if it has either MX or A records
    valid = has_mx or has_a

    if not valid and not errors:
        errors.append(f"Domain {domain} has no valid MX or A records")

    result = {
        "valid": valid,
        "has_mx": has_mx,
        "has_a": has_a,
        "mx_records": mx_records,
        "errors": errors,
    }

    # Cache result for subsequent lookups of the same domain
    _DOMAIN_CACHE[domain] = result
    return result


def is_valid_domain(email: str) -> bool:
    """
    Quick boolean check for domain validity
    
    Args:
        email: Email address to validate
        
    Returns:
        True if domain is valid, False otherwise
    """
    result = validate_domain(email)
    return result["valid"]

