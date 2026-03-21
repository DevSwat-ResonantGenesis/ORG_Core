"""
Tier-Aware Database Isolation

CRITICAL: Database queries must respect tier structure:
- Developer/Plus: Single user (query by user_id ONLY)
- Enterprise: Multi-user organization (query by org_id)

This module provides helpers to ensure correct isolation.
"""

from typing import Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Select
from typing import Any


class TierIsolation:
    """
    Tier-aware database query isolation using Hash Sphere universe_id.
    
    Developer/Plus tiers: Query by universe_id (isolated semantic universe)
    Enterprise tier: Query by org_id (shared multi-user organization)
    
    This provides true semantic isolation via Hash Sphere:
    - Each user has their own universe_id (semantic universe)
    - Memories, agents, workflows are isolated by universe
    - Enterprise orgs share a universe across all members
    
    Usage:
        from shared.tier_isolation import TierIsolation
        
        isolation = TierIsolation.from_request(request)
        stmt = isolation.apply_filter(select(Memory))
    """
    
    # Single-user tiers (query by universe_id only)
    SINGLE_USER_TIERS = {"free", "developer", "plus"}
    
    # Multi-user tiers (query by org_id)
    MULTI_USER_TIERS = {"enterprise"}
    
    def __init__(
        self,
        tier: str,
        user_id: str,
        org_id: str,
        universe_id: Optional[str] = None,
        user_agent_hashes: Optional[List[str]] = None,
        org_agent_hashes: Optional[List[str]] = None,
    ):
        self.tier = tier
        self.user_id = user_id
        self.org_id = org_id
        self.universe_id = universe_id
        self.user_agent_hashes = user_agent_hashes or []
        self.org_agent_hashes = org_agent_hashes or []

    @classmethod
    def is_single_user_tier(cls, tier: str) -> bool:
        """Check if tier is single-user (Developer/Plus)."""
        return tier.lower() in cls.SINGLE_USER_TIERS
    
    @classmethod
    def is_multi_user_tier(cls, tier: str) -> bool:
        """Check if tier is multi-user (Enterprise)."""
        return tier.lower() in cls.MULTI_USER_TIERS
    
    def apply_filter(self, stmt: Select, model: Any, include_agent_memories: bool = True) -> Select:
        """
        Apply tier-aware filter to SQLAlchemy query with multi-dimensional isolation.
        
        Developer/Plus: Filter by universe_id + agent_hash (user's universe + user's agents)
        Enterprise: Filter by org_id + agent_hash (org's data + org's agents)
        
        This provides multi-dimensional isolation:
        - User's personal memories (universe_id)
        - User's agent memories (agent_hash)
        - Enterprise org memories (org_id)
        """
        from sqlalchemy import or_
        
        if self.tier in ["developer", "plus"]:
            # Hash Sphere universe isolation + agent memories
            filters = []
            
            # User's universe memories
            if self.universe_id and hasattr(model, 'universe_id'):
                filters.append(model.universe_id == self.universe_id)
            elif hasattr(model, 'user_id'):
                # Fallback to user_id
                filters.append(model.user_id == self.user_id)
            else:
                raise ValueError(f"Model {model.__name__} missing universe_id or user_id column")
            
            # User's agent memories
            if include_agent_memories and self.user_agent_hashes and hasattr(model, 'agent_hash'):
                filters.append(model.agent_hash.in_(self.user_agent_hashes))
            
            return stmt.where(or_(*filters)) if len(filters) > 1 else stmt.where(filters[0])
        else:
            # Enterprise: Multi-user organization (shared universe) + org agents
            filters = []
            
            # Org memories
            if hasattr(model, 'org_id'):
                filters.append(model.org_id == self.org_id)
            else:
                raise ValueError(f"Model {model.__name__} missing org_id column")
            
            # Org's agent memories
            if include_agent_memories and self.org_agent_hashes and hasattr(model, 'agent_hash'):
                filters.append(model.agent_hash.in_(self.org_agent_hashes))
            
            return stmt.where(or_(*filters)) if len(filters) > 1 else stmt.where(filters[0])

    @classmethod
    def get_isolation_info(cls, tier: str) -> dict:
        """
        Get isolation strategy for a tier.
        
        Returns:
            {
                "tier": "plus",
                "isolation_type": "user",
                "query_field": "universe_id",
                "description": "Single-user isolation"
            }
        """
        if cls.is_single_user_tier(tier):
            return {
                "tier": tier,
                "isolation_type": "user",
                "query_field": "universe_id",
                "description": "Single-user isolation (Developer/Plus)",
                "allows_org_sharing": False,
            }
        else:
            return {
                "tier": tier,
                "isolation_type": "org",
                "query_field": "org_id",
                "description": "Multi-user organization isolation (Enterprise)",
                "allows_org_sharing": True,
            }

    @classmethod
    def from_request(cls, request: Request, user_agent_hashes: Optional[List[str]] = None, org_agent_hashes: Optional[List[str]] = None) -> "TierIsolation":
        """Extract tier isolation info from request headers."""
        return cls(
            tier=request.headers.get("x-user-plan", "developer"),
            user_id=request.headers.get("x-user-id", ""),
            org_id=request.headers.get("x-org-id", ""),
            universe_id=request.headers.get("x-universe-id"),
            user_agent_hashes=user_agent_hashes,
            org_agent_hashes=org_agent_hashes,
        )


# Convenience functions for common patterns

def get_user_filter(model, user_id: str, org_id: Optional[str], tier: str):
    """
    Get SQLAlchemy filter for user data isolation.
    
    Usage in service:
        from shared.tier_isolation import get_user_filter
        
        # In endpoint:
        user_id = request.headers.get("x-user-id")
        org_id = request.headers.get("x-org-id")
        tier = request.headers.get("x-user-plan", "developer")
        
        # Build query
        stmt = select(Conversation).where(
            get_user_filter(Conversation, user_id, org_id, tier)
        )
        
        result = await db.execute(stmt)
    """
    return TierIsolation.build_filter(model, user_id, org_id, tier)


def should_use_org_isolation(tier: str) -> bool:
    """
    Check if tier should use org-level isolation.
    
    Returns:
        True for Enterprise (multi-user)
        False for Developer/Plus (single-user)
    """
    return TierIsolation.is_multi_user_tier(tier)


def should_use_user_isolation(tier: str) -> bool:
    """
    Check if tier should use user-level isolation.
    
    Returns:
        True for Developer/Plus (single-user)
        False for Enterprise (multi-user)
    """
    return TierIsolation.is_single_user_tier(tier)
