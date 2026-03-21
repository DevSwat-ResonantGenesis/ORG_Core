#!/usr/bin/env python3
"""
Create Platform Owner Superuser Account
Grants full dashboard and system access
"""
import asyncio
import sys
import os
from datetime import datetime
from uuid import uuid4
import hashlib
import bcrypt

# Add parent directory to path for imports
sys.path.insert(0, "/app")

from sqlalchemy import select, Column, String, Boolean, Integer, DateTime, JSON, UniqueConstraint
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID

Base = declarative_base()

# Define models inline
class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(320), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=True)
    full_name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=True)
    status = Column(String(50), default="active", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    default_org_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    token_version = Column(Integer, default=1, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(500), nullable=True)
    mfa_backup_codes = Column(JSON, nullable=True)
    mfa_verified_at = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_failed_login_at = Column(DateTime(timezone=True), nullable=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    email_verification_token = Column(String(128), nullable=True)
    email_verification_sent_at = Column(DateTime(timezone=True), nullable=True)
    anchor_seed = Column(String(500), nullable=True)
    universe_id = Column(String(32), nullable=True, index=True)
    seed_encrypted = Column(Boolean, default=False)
    crypto_hash = Column(String(64), nullable=True, index=True)
    user_hash = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("slug", name="uq_organizations_slug"),)
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), index=True, nullable=False)
    slug = Column(String(128), index=True, nullable=False)
    plan = Column(String(50), default="free", nullable=False)
    status = Column(String(50), default="active", nullable=False)
    meta = Column(JSON, default=dict, nullable=False)
    settings = Column(JSON, default=dict, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class OrgMembership(Base):
    __tablename__ = "org_memberships"
    __table_args__ = (UniqueConstraint("user_id", "org_id", name="uq_memberships_user_org"),)
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    role = Column(String(50), default="viewer", nullable=False)
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@shared_postgres:5432/genesis_auth")

async def create_superuser():
    """Create platform owner superuser account."""
    
    # Credentials
    email = "owner@resonantgenesis.com"
    password = "Genesis2026!SuperOwner"  # Strong password
    full_name = "Platform Owner"
    org_name = "Resonant Genesis Platform"
    
    print("=" * 60)
    print("CREATING PLATFORM OWNER SUPERUSER ACCOUNT")
    print("=" * 60)
    print(f"Email: {email}")
    print(f"Password: {password}")
    print(f"Organization: {org_name}")
    print(f"Role: platform_owner (superuser)")
    print("=" * 60)
    
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    
    async with session_maker() as session:
        # Check if user exists
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"\n⚠️  User {email} already exists!")
            print(f"User ID: {existing.id}")
            print(f"Is Superuser: {existing.is_superuser}")
            
            # Update to superuser if not already
            if not existing.is_superuser:
                existing.is_superuser = True
                existing.password_hash = hash_password(password)
                await session.commit()
                print(f"✅ Updated to superuser with new password")
            else:
                print(f"✅ Already a superuser")
            
            user = existing
        else:
            # Create organization
            org = Organization(
                name=org_name,
                slug="resonant-genesis-platform",
                plan="unlimited",
                status="active",
                is_active=True,
            )
            session.add(org)
            await session.flush()
            
            print(f"\n✅ Created organization: {org_name} (ID: {org.id})")
            
            # Generate cryptographic identity
            user_id = uuid4()
            combined = f"{user_id}:{email}:{datetime.utcnow().isoformat()}"
            crypto_hash = hashlib.sha256(combined.encode()).hexdigest()
            user_hash = hashlib.sha256(f"user:{email}".encode()).hexdigest()
            universe_id = hashlib.md5(str(user_id).encode()).hexdigest()
            
            # Create superuser
            user = User(
                id=user_id,
                email=email,
                username="owner",
                full_name=full_name,
                password_hash=hash_password(password),
                is_active=True,
                is_superuser=True,  # SUPERUSER FLAG
                default_org_id=org.id,
                status="active",
                email_verified=True,  # Auto-verify owner
                crypto_hash=crypto_hash,
                user_hash=user_hash,
                universe_id=universe_id,
            )
            session.add(user)
            await session.flush()
            
            print(f"✅ Created superuser: {email} (ID: {user.id})")
            
            # Create org membership with owner role
            membership = OrgMembership(
                user_id=user.id,
                org_id=org.id,
                role="owner",
                status="active",
            )
            session.add(membership)
            
            await session.commit()
            print(f"✅ Created org membership with 'owner' role")
        
        print("\n" + "=" * 60)
        print("SUPERUSER ACCOUNT READY")
        print("=" * 60)
        print(f"Login URL: https://dev-swat.com/login")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print(f"\nDashboards accessible:")
        print(f"  - Main Dashboard: /dashboard")
        print(f"  - Autonomous Agents: /autonomous-agents")
        print(f"  - Admin Panel: /admin")
        print(f"  - All services and features: FULL ACCESS")
        print("=" * 60)
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_superuser())
