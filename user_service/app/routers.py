from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import UserProfile


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/health")
async def health():
    return {"service": "users", "status": "ok"}


class UserProfileCreate(BaseModel):
    user_id: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    settings_json: Optional[str] = None


class UserProfileResponse(BaseModel):
    id: str
    user_id: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    settings_json: Optional[str]

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=str(obj.id),
            user_id=str(obj.user_id),
            display_name=obj.display_name,
            avatar_url=obj.avatar_url,
            settings_json=obj.settings_json,
        )


@router.post("/", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: UserProfileCreate,
    session: AsyncSession = Depends(get_session),
):
    profile = UserProfile(
        user_id=payload.user_id,
        display_name=payload.display_name,
        avatar_url=payload.avatar_url,
        settings_json=payload.settings_json,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return UserProfileResponse.from_orm(profile)


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Get current user's profile using x-user-id header."""
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        # Create profile if it doesn't exist
        profile = UserProfile(user_id=user_id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    return UserProfileResponse.from_orm(profile)


@router.get("/{profile_id}", response_model=UserProfileResponse)
async def get_profile(profile_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(UserProfile).where(UserProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return UserProfileResponse.from_orm(profile)


@router.get("/by-user/{user_id}", response_model=UserProfileResponse)
async def get_profile_by_user(user_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return UserProfileResponse.from_orm(profile)
