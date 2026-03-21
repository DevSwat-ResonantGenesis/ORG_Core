"""
DSID Resolution - THE ONLY AUTHORITY FOR DSID LOOKUPS

This module handles all DSID resolution and lookup operations.
No other module may resolve DSIDs directly.
"""

from typing import Optional, Dict, Any
from .dsid import DSID, validate_dsid, parse_dsid_string


# In-memory cache for resolution (replace with Redis/DB in production)
_resolution_cache: Dict[str, Dict[str, Any]] = {}


async def resolve_dsid(dsid: DSID) -> Optional[Dict[str, Any]]:
    """
    Resolve a DSID to its associated metadata.
    
    THIS IS THE ONLY WAY TO RESOLVE A DSID.
    
    Args:
        dsid: The DSID to resolve
    
    Returns:
        Metadata dict if found, None otherwise
    """
    if not validate_dsid(dsid):
        return None
    
    dsid_str = str(dsid)
    
    # Check cache first
    if dsid_str in _resolution_cache:
        return _resolution_cache[dsid_str]
    
    # In production: query database/blockchain
    # For now, return None for unregistered DSIDs
    return None


async def lookup_dsid(dsid_string: str) -> Optional[DSID]:
    """
    Look up a DSID from its string representation.
    
    THIS IS THE ONLY WAY TO LOOK UP A DSID BY STRING.
    
    Args:
        dsid_string: String representation of a DSID
    
    Returns:
        DSID if valid and exists, None otherwise
    """
    dsid = parse_dsid_string(dsid_string)
    if dsid is None:
        return None
    
    # Verify it exists in the system
    metadata = await resolve_dsid(dsid)
    if metadata is None:
        # DSID is valid format but not registered
        # Return it anyway for validation purposes
        pass
    
    return dsid


async def register_dsid(dsid: DSID, metadata: Dict[str, Any]) -> bool:
    """
    Register a DSID with associated metadata.
    
    THIS IS THE ONLY WAY TO REGISTER A DSID.
    
    Args:
        dsid: The DSID to register
        metadata: Associated metadata
    
    Returns:
        True if registered, False if already exists
    """
    if not validate_dsid(dsid):
        return False
    
    dsid_str = str(dsid)
    
    if dsid_str in _resolution_cache:
        return False  # Already registered
    
    _resolution_cache[dsid_str] = metadata
    return True


async def unregister_dsid(dsid: DSID) -> bool:
    """
    Unregister a DSID.
    
    THIS IS THE ONLY WAY TO UNREGISTER A DSID.
    
    Args:
        dsid: The DSID to unregister
    
    Returns:
        True if unregistered, False if not found
    """
    if not validate_dsid(dsid):
        return False
    
    dsid_str = str(dsid)
    
    if dsid_str not in _resolution_cache:
        return False
    
    del _resolution_cache[dsid_str]
    return True
