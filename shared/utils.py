"""
Utility functions for Genesis2026
"""

import hashlib
import secrets
import time
from typing import Any, Dict, Optional
from datetime import datetime, timezone

def generate_id() -> str:
    """Generate unique ID"""
    return secrets.token_hex(16)

def hash_string(s: str) -> str:
    """Hash a string"""
    return hashlib.sha256(s.encode()).hexdigest()

def get_timestamp() -> str:
    """Get current timestamp"""
    return datetime.now(timezone.utc).isoformat()

def safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get value from dict"""
    return data.get(key, default)

def validate_required(data: Dict[str, Any], required_keys: list) -> None:
    """Validate required keys in dict"""
    missing = [key for key in required_keys if key not in data]
    if missing:
        raise ValidationError(f"Missing required fields: {missing}")
