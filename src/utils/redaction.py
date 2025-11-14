import re
from typing import Dict, Any, List


# Patterns for sensitive data
REDACTION_PATTERNS = [
    # Email addresses
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
    # Credit card numbers (basic pattern)
    (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CC_REDACTED]'),
    # SSN (US)
    (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]'),
    # API keys (common patterns)
    (r'[aA][pP][iI][-_]?[kK][eE][yY]\s*[:=]\s*["\']?[\w\-]+["\']?', '[API_KEY_REDACTED]'),
    # Bearer tokens
    (r'[bB]earer\s+[\w\-\.]+', '[BEARER_TOKEN_REDACTED]'),
    # JWT tokens
    (r'eyJ[\w\-_]+\.[\w\-_]+\.[\w\-_]+', '[JWT_REDACTED]'),
]


def redact_sensitive_data(text: str) -> str:
    """Redact potentially sensitive information from text."""
    redacted = text
    
    for pattern, replacement in REDACTION_PATTERNS:
        redacted = re.sub(pattern, replacement, redacted)
    
    return redacted


def redact_logs(log_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Redact sensitive data from log entries."""
    redacted_entries = []
    
    for entry in log_entries:
        redacted_entry = entry.copy()
        
        # Redact message
        if 'message' in redacted_entry:
            redacted_entry['message'] = redact_sensitive_data(redacted_entry['message'])
        
        # Redact raw line
        if 'raw' in redacted_entry:
            redacted_entry['raw'] = redact_sensitive_data(redacted_entry['raw'])
        
        redacted_entries.append(redacted_entry)
    
    return redacted_entries
