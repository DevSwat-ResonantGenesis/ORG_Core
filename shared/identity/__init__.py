"""
DSID Identity Module - THE ONLY AUTHORITY FOR IDENTITY OPERATIONS

This module is the single choke point for all DSID operations.
No other module may:
- Create DSIDs
- Resolve DSIDs
- Validate DSIDs
- Mutate DSID state

All other modules must treat DSID as opaque.
"""

from .dsid import DSID, create_dsid, validate_dsid
from .resolution import resolve_dsid, lookup_dsid
from .contracts import DSIDContract, IdentityError

__all__ = [
    "DSID",
    "create_dsid",
    "validate_dsid",
    "resolve_dsid",
    "lookup_dsid",
    "DSIDContract",
    "IdentityError",
]
