"""
Quick superuser creator - works in auth_service container
"""
import asyncio
import os
import sys
sys.path.insert(0, '/app')

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models import User, Organization, OrgMembership
from app.security import hash_password
from datetime import datetime
from uuid import uuid4
import hashlib

async def main():
    DATABASE_URL = os.getenv("AUTH_DATABASE_URL") or os.getenv("DATABASE_URL")
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    
    email = "owner@resonantgenesis.com"
    password = "Genesis2026!SuperOwner"
    
    print(f"Creating superuser: {email}")
    
    async with session_maker() as session:
        # Check existing
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if user:
            print(f"User exists - updating to superuser")
            user.is_superuser = True
            user.password_hash = hash_password(password)
            user.email_verified = True
            user.is_active = True
            await session.commit()
            print(f"✅ Updated user {user.id} to superuser")
        else:
            # Get or create org
            result = await session.execute(select(Organization).limit(1))
            org = result.scalar_one_or_none()
            
            if not org:
                org = Organization(
                    name="Resonant Genesis Platform",
                    slug="resonant-genesis",
                    plan="unlimited",
                    status="active",
                    is_active=True,
                )
                session.add(org)
                await session.flush()
                print(f"✅ Created organization: {org.id}")
            
            # Create user
            user_id = uuid4()
            crypto_hash = hashlib.sha256(f"{user_id}:{email}".encode()).hexdigest()
            user_hash = hashlib.sha256(f"user:{email}".encode()).hexdigest()
            universe_id = hashlib.md5(str(user_id).encode()).hexdigest()
            
            user = User(
                id=user_id,
                email=email,
                username="owner",
                full_name="Platform Owner",
                password_hash=hash_password(password),
                is_active=True,
                is_superuser=True,
                default_org_id=org.id,
                status="active",
                email_verified=True,
                crypto_hash=crypto_hash,
                user_hash=user_hash,
                universe_id=universe_id,
            )
            session.add(user)
            await session.flush()
            print(f"✅ Created superuser: {user.id}")
            
            # Create membership
            membership = OrgMembership(
                user_id=user.id,
                org_id=org.id,
                role="owner",
                status="active",
            )
            session.add(membership)
            await session.commit()
            print(f"✅ Created org membership")
    
    print("\n" + "="*60)
    print("SUPERUSER ACCOUNT READY")
    print("="*60)
    print(f"URL: https://dev-swat.com/login")
    print(f"Email: {email}")
    print(f"Password: {password}")
    print("="*60)
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
