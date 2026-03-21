"""
DSID Core - Decentralized Sovereign Identity

This is the ONLY module that may create or validate DSIDs.
"""

import hashlib
import secrets
import re
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass(frozen=True)
class DSID:
    """
    Decentralized Sovereign Identity - OPAQUE outside this module.
    
    Other modules must NOT:
    - Access internal fields directly
    - Construct DSIDs manually
    - Parse DSID strings
    
    Use create_dsid() and validate_dsid() only.
    """
    _value: str
    _created_at: datetime
    _checksum: str
    
    def __str__(self) -> str:
        return self._value
    
    def __hash__(self) -> int:
        return hash(self._value)
    
    def __eq__(self, other) -> bool:
        if isinstance(other, DSID):
            return self._value == other._value
        return False
    
    @property
    def opaque_id(self) -> str:
        """Return opaque identifier - the ONLY external access point"""
        return self._value


# DSID format: dsid_<type>_<random>_<checksum>
DSID_PATTERN = re.compile(r'^dsid_(user|agent|system|service)_[a-f0-9]{16}_[a-f0-9]{8}$')

VALID_TYPES = {"user", "agent", "system", "service"}


def create_dsid(dsid_type: str, seed: Optional[str] = None) -> DSID:
    """
    Create a new DSID. THIS IS THE ONLY WAY TO CREATE A DSID.
    
    Args:
        dsid_type: One of "user", "agent", "system", "service"
        seed: Optional seed for deterministic generation (testing only)
    
    Returns:
        A new DSID instance
    
    Raises:
        ValueError: If dsid_type is invalid
    """
    if dsid_type not in VALID_TYPES:
        raise ValueError(f"Invalid DSID type: {dsid_type}. Must be one of {VALID_TYPES}")
    
    # Generate random component
    if seed:
        random_part = hashlib.sha256(seed.encode()).hexdigest()[:16]
    else:
        random_part = secrets.token_hex(8)
    
    # Generate checksum
    base = f"dsid_{dsid_type}_{random_part}"
    checksum = hashlib.sha256(base.encode()).hexdigest()[:8]
    
    value = f"{base}_{checksum}"
    
    return DSID(
        _value=value,
        _created_at=datetime.utcnow(),
        _checksum=checksum
    )


def validate_dsid(dsid: DSID) -> bool:
    """
    Validate a DSID. THIS IS THE ONLY WAY TO VALIDATE A DSID.
    
    Args:
        dsid: The DSID to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(dsid, DSID):
        return False
    
    value = dsid._value
    
    # Check format
    if not DSID_PATTERN.match(value):
        return False
    
    # Verify checksum
    parts = value.rsplit('_', 1)
    if len(parts) != 2:
        return False
    
    base, checksum = parts
    expected_checksum = hashlib.sha256(base.encode()).hexdigest()[:8]
    
    return checksum == expected_checksum


def parse_dsid_string(dsid_string: str) -> Optional[DSID]:
    """
    Parse a DSID from string representation.
    
    This is for deserializing stored DSIDs only.
    Do NOT use this to create new DSIDs.
    
    Args:
        dsid_string: String representation of a DSID
    
    Returns:
        DSID if valid, None otherwise
    """
    if not DSID_PATTERN.match(dsid_string):
        return None
    
    # Verify checksum
    parts = dsid_string.rsplit('_', 1)
    if len(parts) != 2:
        return None
    
    base, checksum = parts
    expected_checksum = hashlib.sha256(base.encode()).hexdigest()[:8]
    
    if checksum != expected_checksum:
        return None
    
    return DSID(
        _value=dsid_string,
        _created_at=datetime.utcnow(),  # Unknown, use current
        _checksum=checksum
    )
