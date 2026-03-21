"""
CASCADE Control Plane - Enforcement Layer
Hard constraints that cannot be bypassed without explicit override
"""

from typing import List, Dict, Optional, Set
from enum import Enum
from pydantic import BaseModel


class EffectBoundary(str, Enum):
    """Irreversible effect categories - the ONLY valid protected zone criteria"""
    AUTH = "auth"           # Authentication, sessions, tokens
    MONEY = "money"         # Payments, billing, subscriptions
    IDENTITY = "identity"   # User data, PII, profiles
    IRREVERSIBLE = "irreversible"  # Database migrations, deletions, external API calls


# Effect boundary to file pattern mapping
EFFECT_BOUNDARIES: Dict[EffectBoundary, List[str]] = {
    EffectBoundary.AUTH: [
        "*/auth_service/*",
        "*/jwt*.py",
        "*/oauth*.py",
        "*/session*.py",
        "*/security.py",
        "*/permissions.py",
        "*/gateway/app/auth*.py",
    ],
    EffectBoundary.MONEY: [
        "*/billing_service/*",
        "*/stripe*.py",
        "*/payment*.py",
        "*/subscription*.py",
        "*/invoice*.py",
        "*/marketplace_service/app/checkout*.py",
        "*/marketplace_service/app/order*.py",
    ],
    EffectBoundary.IDENTITY: [
        "*/user_service/app/models.py",
        "*/user_service/app/routers/profile*.py",
        "*/user_memory_service/*",
        "**/pii*.py",
        "**/gdpr*.py",
    ],
    EffectBoundary.IRREVERSIBLE: [
        "*/migrations/*",
        "*/alembic/*",
        "*/*.sql",
        "*/models.py",  # Schema changes
        "**/delete*.py",
        "**/purge*.py",
    ],
}


class FileClassification(BaseModel):
    """Classification result for a file"""
    file_path: str
    effect_boundary: Optional[EffectBoundary] = None
    is_classified: bool = False
    requires_approval: bool = False
    reason: str = ""


class EnforcementResult(BaseModel):
    """Result of enforcement check"""
    allowed: bool
    blocked_files: List[FileClassification] = []
    unclassified_files: List[str] = []
    warnings: List[str] = []
    requires_approval: bool = False
    approval_reason: str = ""


def classify_file(file_path: str) -> FileClassification:
    """
    Classify a file by its effect boundary.
    Returns unclassified if file doesn't match any boundary.
    """
    import fnmatch
    
    for boundary, patterns in EFFECT_BOUNDARIES.items():
        for pattern in patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return FileClassification(
                    file_path=file_path,
                    effect_boundary=boundary,
                    is_classified=True,
                    requires_approval=True,
                    reason=f"Matches {boundary.value} boundary: {pattern}"
                )
    
    # Check if it's a test file (always allowed)
    if any(x in file_path.lower() for x in ['test', 'spec', 'mock', 'fixture']):
        return FileClassification(
            file_path=file_path,
            is_classified=True,
            requires_approval=False,
            reason="Test file - always allowed"
        )
    
    # Check if it's documentation (always allowed)
    if any(x in file_path.lower() for x in ['.md', '.rst', '.txt', 'docs/', 'readme']):
        return FileClassification(
            file_path=file_path,
            is_classified=True,
            requires_approval=False,
            reason="Documentation - always allowed"
        )
    
    # UNCLASSIFIED - DEFAULT DENY
    return FileClassification(
        file_path=file_path,
        is_classified=False,
        requires_approval=True,  # Default deny
        reason="Unclassified file - requires zone assignment"
    )


def enforce_changes(file_paths: List[str], approved_boundaries: Set[EffectBoundary] = None) -> EnforcementResult:
    """
    Enforce effect boundary constraints on a set of file changes.
    
    Args:
        file_paths: List of files being changed
        approved_boundaries: Set of boundaries that have been pre-approved
    
    Returns:
        EnforcementResult with allowed/blocked status
    """
    approved_boundaries = approved_boundaries or set()
    
    blocked_files = []
    unclassified_files = []
    warnings = []
    requires_approval = False
    approval_reasons = []
    
    for file_path in file_paths:
        classification = classify_file(file_path)
        
        if not classification.is_classified:
            # DEFAULT DENY for unclassified
            unclassified_files.append(file_path)
            blocked_files.append(classification)
            requires_approval = True
            approval_reasons.append(f"Unclassified: {file_path}")
            
        elif classification.requires_approval:
            # Check if this boundary is pre-approved
            if classification.effect_boundary and classification.effect_boundary in approved_boundaries:
                warnings.append(f"Pre-approved {classification.effect_boundary.value}: {file_path}")
            else:
                blocked_files.append(classification)
                requires_approval = True
                if classification.effect_boundary:
                    approval_reasons.append(f"{classification.effect_boundary.value}: {file_path}")
    
    return EnforcementResult(
        allowed=len(blocked_files) == 0,
        blocked_files=blocked_files,
        unclassified_files=unclassified_files,
        warnings=warnings,
        requires_approval=requires_approval,
        approval_reason="; ".join(approval_reasons) if approval_reasons else ""
    )


# Zone classification registry - maps files to zones
# New files start as UNCLASSIFIED and must be assigned
ZONE_REGISTRY: Dict[str, str] = {}


def register_zone(file_pattern: str, zone: str):
    """Register a file pattern to a zone"""
    ZONE_REGISTRY[file_pattern] = zone


def get_zone(file_path: str) -> Optional[str]:
    """Get the zone for a file path"""
    import fnmatch
    for pattern, zone in ZONE_REGISTRY.items():
        if fnmatch.fnmatch(file_path, pattern):
            return zone
    return None  # Unclassified
