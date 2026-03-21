#!/usr/bin/env python3
"""
Database Connection Test for Chat Service Analytics
Tests database connectivity and verifies analytics data availability
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

async def test_chat_db_connection():
    """Test chat service database connection and analytics queries."""
    print("=" * 60)
    print("Chat Service Database Connection Test")
    print("=" * 60)
    print()
    
    try:
        # Import chat service components
        from chat_service.app.db import engine, async_session
        from chat_service.app.models import ResonantChat, ResonantChatMessage
        from sqlalchemy import select, func
        
        print("✓ Successfully imported chat service modules")
        print()
        
        # Test database connection
        print("Testing database connection...")
        async with async_session() as session:
            # Test basic query
            result = await session.execute(select(func.count(ResonantChat.id)))
            total_chats = result.scalar() or 0
            print(f"✓ Database connected successfully")
            print(f"  Total conversations in database: {total_chats}")
            print()
            
            # Test message count
            result = await session.execute(select(func.count(ResonantChatMessage.id)))
            total_messages = result.scalar() or 0
            print(f"  Total messages in database: {total_messages}")
            print()
            
            # Test user data availability
            result = await session.execute(
                select(func.count(func.distinct(ResonantChat.user_id)))
            )
            unique_users = result.scalar() or 0
            print(f"  Unique users with conversations: {unique_users}")
            print()
            
            # Test recent activity
            from datetime import datetime, timedelta
            yesterday = datetime.utcnow() - timedelta(days=1)
            result = await session.execute(
                select(func.count(ResonantChatMessage.id))
                .where(ResonantChatMessage.created_at >= yesterday)
            )
            recent_messages = result.scalar() or 0
            print(f"  Messages in last 24 hours: {recent_messages}")
            print()
            
            # Test analytics data availability
            print("Testing analytics data availability...")
            
            # Check for messages with resonance scores
            result = await session.execute(
                select(func.count(ResonantChatMessage.id))
                .where(ResonantChatMessage.resonance_score.isnot(None))
            )
            messages_with_resonance = result.scalar() or 0
            print(f"  Messages with resonance scores: {messages_with_resonance}")
            
            # Check for messages with hash
            result = await session.execute(
                select(func.count(ResonantChatMessage.id))
                .where(ResonantChatMessage.hash.isnot(None))
            )
            messages_with_hash = result.scalar() or 0
            print(f"  Messages with hash: {messages_with_hash}")
            
            # Check for messages with XYZ coordinates
            result = await session.execute(
                select(func.count(ResonantChatMessage.id))
                .where(ResonantChatMessage.xyz_x.isnot(None))
            )
            messages_with_xyz = result.scalar() or 0
            print(f"  Messages with XYZ coordinates: {messages_with_xyz}")
            print()
            
            # Sample a recent conversation if available
            if total_chats > 0:
                print("Sampling recent conversation...")
                result = await session.execute(
                    select(ResonantChat)
                    .order_by(ResonantChat.created_at.desc())
                    .limit(1)
                )
                recent_chat = result.scalar_one_or_none()
                
                if recent_chat:
                    print(f"  Chat ID: {recent_chat.id}")
                    print(f"  User ID: {recent_chat.user_id}")
                    print(f"  Title: {recent_chat.title}")
                    print(f"  Created: {recent_chat.created_at}")
                    
                    # Get message count for this chat
                    result = await session.execute(
                        select(func.count(ResonantChatMessage.id))
                        .where(ResonantChatMessage.chat_id == recent_chat.id)
                    )
                    msg_count = result.scalar() or 0
                    print(f"  Messages in this chat: {msg_count}")
                print()
        
        print("=" * 60)
        print("✓ All database tests passed successfully!")
        print("=" * 60)
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("  Make sure you're running this from the project root")
        return False
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        print(f"  Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

async def test_analytics_endpoint():
    """Test the analytics endpoint logic."""
    print()
    print("=" * 60)
    print("Analytics Endpoint Logic Test")
    print("=" * 60)
    print()
    
    try:
        from chat_service.app.routers.analytics import TimeRange
        from datetime import datetime, timedelta
        
        print("Testing TimeRange helper...")
        
        # Test different time ranges
        ranges = ["1d", "7d", "30d", "90d", "1y", "all"]
        for range_str in ranges:
            start_date = TimeRange.get_start_date(range_str)
            days_ago = (datetime.utcnow() - start_date).days
            print(f"  {range_str:4s} -> {days_ago:4d} days ago")
        
        print()
        print("✓ Analytics endpoint logic tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Analytics logic test failed: {e}")
        return False

async def main():
    """Run all tests."""
    print()
    
    # Test 1: Database connection
    db_test = await test_chat_db_connection()
    
    # Test 2: Analytics logic
    analytics_test = await test_analytics_endpoint()
    
    # Summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Database Connection: {'✓ PASS' if db_test else '✗ FAIL'}")
    print(f"Analytics Logic:     {'✓ PASS' if analytics_test else '✗ FAIL'}")
    print()
    
    if db_test and analytics_test:
        print("✓ All tests passed! Analytics should work correctly.")
        return 0
    else:
        print("✗ Some tests failed. Please review the output above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
