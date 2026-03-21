"""
DSID Contracts - Identity invariants and error handling

This module defines the contracts that all DSID operations must follow.
"""

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class IdentityError(Exception):
    """Base exception for all identity-related errors"""
    pass


class DSIDCreationError(IdentityError):
    """Raised when DSID creation fails"""
    pass


class DSIDValidationError(IdentityError):
    """Raised when DSID validation fails"""
    pass


class DSIDResolutionError(IdentityError):
    """Raised when DSID resolution fails"""
    pass


class DSIDPermissionError(IdentityError):
    """Raised when DSID permission check fails"""
    pass


class DSIDType(Enum):
    """Valid DSID types"""
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    SERVICE = "service"


@dataclass(frozen=True)
class DSIDContract:
    """
    Contract defining DSID invariants.
    
    INVARIANTS (MUST NEVER BE VIOLATED):
    
    1. CREATION: DSIDs may only be created via create_dsid()
    2. VALIDATION: DSIDs may only be validated via validate_dsid()
    3. RESOLUTION: DSIDs may only be resolved via resolve_dsid()
    4. OPACITY: Outside shared/identity/, DSID is opaque
    5. IMMUTABILITY: DSID values never change after creation
    6. UNIQUENESS: No two DSIDs may have the same value
    7. CHECKSUM: All DSIDs must pass checksum validation
    
    PERMISSIONS:
    
    - auth_service: May create user DSIDs
    - agent_engine_service: May create agent DSIDs
    - gateway: May validate DSIDs (read-only)
    - All other services: May only pass DSIDs through
    """
    
    # Services allowed to create DSIDs
    CREATION_AUTHORITIES: List[str] = None
    
    # Services allowed to resolve DSIDs
    RESOLUTION_AUTHORITIES: List[str] = None
    
    # Services allowed to validate DSIDs
    VALIDATION_AUTHORITIES: List[str] = None
    
    def __post_init__(self):
        # Set defaults using object.__setattr__ for frozen dataclass
        if self.CREATION_AUTHORITIES is None:
            object.__setattr__(self, 'CREATION_AUTHORITIES', [
                "auth_service",
                "agent_engine_service",
            ])
        
        if self.RESOLUTION_AUTHORITIES is None:
            object.__setattr__(self, 'RESOLUTION_AUTHORITIES', [
                "auth_service",
                "agent_engine_service",
                "gateway",
                "chat_service",
            ])
        
        if self.VALIDATION_AUTHORITIES is None:
            object.__setattr__(self, 'VALIDATION_AUTHORITIES', [
                "auth_service",
                "agent_engine_service",
                "gateway",
                "chat_service",
                "memory_service",
                "billing_service",
            ])


# Singleton contract instance
DSID_CONTRACT = DSIDContract()


def check_creation_permission(service_name: str) -> bool:
    """Check if a service is allowed to create DSIDs"""
    return service_name in DSID_CONTRACT.CREATION_AUTHORITIES


def check_resolution_permission(service_name: str) -> bool:
    """Check if a service is allowed to resolve DSIDs"""
    return service_name in DSID_CONTRACT.RESOLUTION_AUTHORITIES


def check_validation_permission(service_name: str) -> bool:
    """Check if a service is allowed to validate DSIDs"""
    return service_name in DSID_CONTRACT.VALIDATION_AUTHORITIES
