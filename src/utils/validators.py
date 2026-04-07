"""
Validation utilities for research queries and inputs
"""

from typing import Tuple
import re


def validate_query(query: str) -> Tuple[bool, str]:
    """
    Validate research query
    
    Returns:
        (is_valid, error_message)
    """
    # Check empty
    if not query or not query.strip():
        return False, "Query cannot be empty"

    # Check length
    if len(query) < 3:
        return False, "Query must be at least 3 characters"

    if len(query) > 500:
        return False, "Query must be less than 500 characters"

    # Check for valid characters
    if not re.match(r"^[a-zA-Z0-9\s\?\!\-\.\,\&\(\)]+$", query):
        return False, "Query contains invalid characters"

    return True, ""


def validate_url(url: str) -> bool:
    """Validate if string is a valid URL"""
    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
        r"localhost|"  # localhost
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # or IP address
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$", re.IGNORECASE
    )
    return url_pattern.match(url) is not None
