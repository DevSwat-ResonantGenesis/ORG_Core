"""Shared Configuration Module"""
import os
from pathlib import Path

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./genesis.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Service configuration
SERVICE_TIMEOUT = int(os.getenv("SERVICE_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable must be set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
