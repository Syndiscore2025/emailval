"""Heuristics for detecting obviously garbage email addresses.

Used mainly in CRM/webhook flows to immediately drop clearly bad emails
into the disposable bucket without wasting SMTP resources.
"""

import re
from typing import Tuple, Optional


def is_obviously_invalid(email: str) -> Tuple[bool, Optional[str]]:
    """Return (True, reason_code) if the email is clearly invalid junk.

    This is intentionally conservative: it only catches patterns that are
    almost certainly useless and should be treated as disposable right away.
    """
    if not email or not isinstance(email, str):
        return True, "empty"

    e = email.strip()
    lower = e.lower()

    # Double @ or wrong number of @ symbols
    if "@@" in lower:
        return True, "double_at"
    if lower.count("@") != 1:
        return True, "invalid_at_count"

    local, domain = lower.split("@", 1)
    if not local or not domain:
        return True, "missing_local_or_domain"

    # Domain must contain at least one dot
    if "." not in domain:
        return True, "no_dot_in_domain"

    # Obvious multi-TLD junk like .net.com, .com.net, etc.
    multi_tld_patterns = [
        ".net.com",
        ".com.net",
        ".org.com",
        ".edu.com",
        ".gov.com",
    ]
    if any(p in domain for p in multi_tld_patterns):
        return True, "multi_tld"

    # Free providers with numeric garbage suffix in the domain, e.g. gmail1234.com
    providers = ("gmail", "yahoo", "hotmail", "outlook", "aol", "live")
    for p in providers:
        if domain.startswith(p) and len(domain) > len(p):
            # Next character after provider should not be a digit in normal domains
            if domain[len(p)].isdigit():
                return True, "provider_with_numbers"

    # Completely numeric local-part on common free providers is usually garbage
    if local.isdigit() and any(domain.startswith(p) for p in providers):
        return True, "numeric_local_on_free_provider"

    # Very short local-part + very short domain often indicates junk (e.g. a@b.com)
    if len(local) == 1 and len(domain.split(".")[0]) == 1:
        return True, "too_short"

    return False, None

