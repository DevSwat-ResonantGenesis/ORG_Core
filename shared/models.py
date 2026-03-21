"""Shared Models Module"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

class BaseRecord(BaseModel):
    """Base record model"""
    id: str
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

class User(BaseRecord):
    """User model"""
    username: str
    email: str
    is_active: bool = True

class Service(BaseRecord):
    """Service model"""
    name: str
    type: str
    status: str = "active"
    endpoint: Optional[str] = None

class Task(BaseRecord):
    """Task model"""
    name: str
    description: str
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
