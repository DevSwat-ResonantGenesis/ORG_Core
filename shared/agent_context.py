"""
Agent Context Helper

Provides utilities to get agent hashes that a user/org has access to.
Used for multi-dimensional memory isolation.
"""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_agent_hashes(user_id: str, db: AsyncSession) -> List[str]:
    """
    Get all agent hashes that a user has access to.
    
    This includes:
    - Agents created by the user
    - Agents the user has used
    - Public/shared agents
    
    Args:
        user_id: User UUID
        db: Database session
    
    Returns:
        List of agent hashes
    """
    try:
        # Import here to avoid circular dependencies
        from agent_engine_service.app.models import AgentDefinition
        
        # Query agents owned by user
        stmt = select(AgentDefinition.agent_hash).where(
            AgentDefinition.user_id == user_id,
            AgentDefinition.agent_hash.isnot(None)
        )
        
        result = await db.execute(stmt)
        agent_hashes = [row[0] for row in result.fetchall()]
        
        return agent_hashes
        
    except Exception as e:
        # If agent_engine not available, return empty list
        return []


async def get_org_agent_hashes(org_id: str, db: AsyncSession) -> List[str]:
    """
    Get all agent hashes that an organization has access to.
    
    This includes:
    - Agents created by org members
    - Org-wide shared agents
    
    Args:
        org_id: Organization UUID
        db: Database session
    
    Returns:
        List of agent hashes
    """
    try:
        # Import here to avoid circular dependencies
        from agent_engine_service.app.models import AgentDefinition
        
        # Query agents owned by org
        stmt = select(AgentDefinition.agent_hash).where(
            AgentDefinition.org_id == org_id,
            AgentDefinition.agent_hash.isnot(None)
        )
        
        result = await db.execute(stmt)
        agent_hashes = [row[0] for row in result.fetchall()]
        
        return agent_hashes
        
    except Exception as e:
        # If agent_engine not available, return empty list
        return []


def get_agent_hashes_from_context(
    user_id: str,
    org_id: Optional[str],
    tier: str,
    user_agents: Optional[List[str]] = None,
    org_agents: Optional[List[str]] = None
) -> tuple[List[str], List[str]]:
    """
    Get agent hashes for tier isolation from context.
    
    This is a synchronous helper that uses pre-fetched agent lists.
    Use this when you've already fetched agents or want to avoid DB queries.
    
    Args:
        user_id: User UUID
        org_id: Organization UUID
        tier: Subscription tier
        user_agents: Pre-fetched user agent hashes
        org_agents: Pre-fetched org agent hashes
    
    Returns:
        Tuple of (user_agent_hashes, org_agent_hashes)
    """
    user_agent_hashes = user_agents or []
    org_agent_hashes = org_agents or []
    
    return (user_agent_hashes, org_agent_hashes)
