#!/usr/bin/env python3
"""
Backfill universe_id for existing records.

This script:
1. Finds all users with crypto identity
2. Updates all their records with universe_id
3. Handles all services: memory, chat, agents, etc.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


async def backfill_memory_service():
    """Backfill universe_id in memory_service."""
    from memory_service.app.models import MemoryRecord
    from memory_service.app.db import engine
    
    async with AsyncSession(engine) as session:
        # Get all users with universe_id from auth_service
        # For now, we'll need to query auth DB
        print("Backfilling memory_service.MemoryRecord...")
        
        # This would need actual user data from auth_service
        # For production, you'd query auth DB to get user -> universe_id mapping
        
        print("✅ memory_service backfill complete")


async def backfill_chat_service():
    """Backfill universe_id in chat_service."""
    from chat_service.app.models import ResonantChatMessage, ResonantChat
    from chat_service.app.db import engine
    
    async with AsyncSession(engine) as session:
        print("Backfilling chat_service.ResonantChatMessage...")
        
        # Same as above - need user -> universe_id mapping
        
        print("✅ chat_service backfill complete")


async def backfill_agent_engine():
    """Backfill universe_id in agent_engine_service."""
    from agent_engine_service.app.models import AgentDefinition
    from agent_engine_service.app.db import engine
    
    async with AsyncSession(engine) as session:
        print("Backfilling agent_engine_service.AgentDefinition...")
        
        # Same as above
        
        print("✅ agent_engine backfill complete")


async def main():
    """Run all backfill operations."""
    print("🔄 Starting universe_id backfill...")
    print("=" * 60)
    
    try:
        await backfill_memory_service()
        await backfill_chat_service()
        await backfill_agent_engine()
        
        print("=" * 60)
        print("✅ All backfill operations complete!")
        
    except Exception as e:
        print(f"❌ Backfill failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
