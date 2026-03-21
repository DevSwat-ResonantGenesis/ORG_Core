"""
INPUT VALIDATION MIDDLEWARE
===========================

Security middleware for input validation and sanitization.
Protects against injection attacks and malformed input.
"""

import re
import html
import logging
from typing import Any, Dict, List, Optional, Callable
from functools import wraps

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, validator, ValidationError

logger = logging.getLogger(__name__)


# ============== SANITIZATION FUNCTIONS ==============

def sanitize_string(value: str, max_length: int = 10000) -> str:
    """Sanitize a string input."""
    if not isinstance(value, str):
        return str(value)
    
    # Truncate to max length
    value = value[:max_length]
    
    # Remove null bytes
    value = value.replace('\x00', '')
    
    # Normalize whitespace
    value = ' '.join(value.split())
    
    return value


def sanitize_html(value: str) -> str:
    """Escape HTML entities."""
    return html.escape(value)


def sanitize_sql_like(value: str) -> str:
    """Escape SQL LIKE wildcards."""
    return value.replace('%', '\\%').replace('_', '\\_')


def sanitize_path(value: str) -> str:
    """Sanitize file path to prevent traversal attacks."""
    # Remove null bytes
    value = value.replace('\x00', '')
    
    # Normalize path separators
    value = value.replace('\\', '/')
    
    # Remove path traversal sequences
    while '../' in value or '/..' in value:
        value = value.replace('../', '').replace('/..', '')
    
    # Remove absolute path indicators
    value = value.lstrip('/')
    
    # Remove any remaining suspicious patterns
    value = re.sub(r'[<>:"|?*]', '', value)
    
    return value


def sanitize_email(value: str) -> str:
    """Validate and sanitize email."""
    value = value.lower().strip()
    
    # Basic email pattern
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, value):
        raise ValueError("Invalid email format")
    
    return value


def sanitize_url(value: str) -> str:
    """Validate and sanitize URL."""
    # Basic URL pattern
    url_pattern = r'^https?://[^\s<>"{}|\\^`\[\]]+$'
    if not re.match(url_pattern, value):
        raise ValueError("Invalid URL format")
    
    return value


# ============== VALIDATION PATTERNS ==============

PATTERNS = {
    'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    'slug': r'^[a-z0-9]+(?:-[a-z0-9]+)*$',
    'alphanumeric': r'^[a-zA-Z0-9]+$',
    'alphanumeric_underscore': r'^[a-zA-Z0-9_]+$',
    'phone': r'^\+?[1-9]\d{1,14}$',
    'semver': r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$',
}


def validate_pattern(value: str, pattern_name: str) -> bool:
    """Validate string against a named pattern."""
    pattern = PATTERNS.get(pattern_name)
    if not pattern:
        raise ValueError(f"Unknown pattern: {pattern_name}")
    return bool(re.match(pattern, value, re.IGNORECASE))


# ============== BLOCKED PATTERNS ==============

BLOCKED_PATTERNS = [
    # SQL Injection patterns
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)",
    r"(--|\#|\/\*)",
    r"(\bOR\b.*=.*)",
    r"(\bAND\b.*=.*)",
    
    # XSS patterns
    r"(<script[^>]*>)",
    r"(javascript:)",
    r"(on\w+\s*=)",
    
    # Command injection patterns
    r"(;|\||&|\$\(|\`)",
    r"(\.\./|\.\.\\)",
    
    # LDAP injection
    r"(\*\)|\(\||\(&)",
]

COMPILED_BLOCKED = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATTERNS]


def contains_blocked_pattern(value: str) -> bool:
    """Check if string contains blocked patterns."""
    for pattern in COMPILED_BLOCKED:
        if pattern.search(value):
            return True
    return False


# ============== MIDDLEWARE ==============

class InputValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for validating and sanitizing all incoming requests.
    """
    
    def __init__(
        self,
        app,
        max_body_size: int = 10 * 1024 * 1024,  # 10MB
        check_blocked_patterns: bool = True,
        exempt_paths: List[str] = None,
    ):
        super().__init__(app)
        self.max_body_size = max_body_size
        self.check_blocked_patterns = check_blocked_patterns
        self.exempt_paths = exempt_paths or ['/health', '/metrics', '/docs', '/openapi.json']
    
    async def dispatch(self, request: Request, call_next):
        # Skip exempt paths
        if any(request.url.path.startswith(p) for p in self.exempt_paths):
            return await call_next(request)
        
        # Check content length
        content_length = request.headers.get('content-length')
        if content_length and int(content_length) > self.max_body_size:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"}
            )
        
        # Validate query parameters
        if self.check_blocked_patterns:
            for key, value in request.query_params.items():
                if contains_blocked_pattern(value):
                    logger.warning(f"Blocked pattern in query param: {key}", extra={
                        "path": request.url.path,
                        "ip": request.client.host if request.client else "unknown",
                    })
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid characters in request"}
                    )
        
        # Validate path parameters
        if self.check_blocked_patterns:
            path = request.url.path
            if contains_blocked_pattern(path):
                logger.warning(f"Blocked pattern in path: {path}", extra={
                    "ip": request.client.host if request.client else "unknown",
                })
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid characters in request"}
                )
        
        return await call_next(request)


# ============== VALIDATORS ==============

class SecureString(str):
    """String type with automatic sanitization."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise ValueError("String required")
        
        # Check for blocked patterns
        if contains_blocked_pattern(v):
            raise ValueError("Invalid characters detected")
        
        return cls(sanitize_string(v))


class SecurePath(str):
    """Path string with traversal protection."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise ValueError("String required")
        
        return cls(sanitize_path(v))


class SecureEmail(str):
    """Email with validation."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        return cls(sanitize_email(v))


# ============== REQUEST VALIDATORS ==============

def validate_request_body(
    blocked_fields: List[str] = None,
    max_string_length: int = 10000,
):
    """
    Decorator to validate request body.
    
    Usage:
        @validate_request_body(blocked_fields=['password'])
        async def endpoint(request: Request, data: dict):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request from kwargs or args
            request = kwargs.get('request') or next(
                (arg for arg in args if isinstance(arg, Request)), None
            )
            
            if request:
                try:
                    body = await request.json()
                    _validate_dict(body, blocked_fields or [], max_string_length)
                except ValidationError as e:
                    raise HTTPException(status_code=400, detail=str(e))
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def _validate_dict(
    data: Dict[str, Any],
    blocked_fields: List[str],
    max_length: int,
    path: str = "",
):
    """Recursively validate dictionary values."""
    for key, value in data.items():
        current_path = f"{path}.{key}" if path else key
        
        # Skip blocked fields (like passwords)
        if key in blocked_fields:
            continue
        
        if isinstance(value, str):
            # Check length
            if len(value) > max_length:
                raise ValueError(f"Field {current_path} exceeds max length")
            
            # Check for blocked patterns
            if contains_blocked_pattern(value):
                raise ValueError(f"Invalid characters in field {current_path}")
        
        elif isinstance(value, dict):
            _validate_dict(value, blocked_fields, max_length, current_path)
        
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str):
                    if contains_blocked_pattern(item):
                        raise ValueError(f"Invalid characters in {current_path}[{i}]")
                elif isinstance(item, dict):
                    _validate_dict(item, blocked_fields, max_length, f"{current_path}[{i}]")


# ============== RATE LIMIT HELPERS ==============

def get_client_ip(request: Request) -> str:
    """Get client IP from request, handling proxies."""
    # Check X-Forwarded-For header (set by nginx/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct client
    return request.client.host if request.client else "unknown"


# ============== EXPORTS ==============

__all__ = [
    'InputValidationMiddleware',
    'sanitize_string',
    'sanitize_html',
    'sanitize_sql_like',
    'sanitize_path',
    'sanitize_email',
    'sanitize_url',
    'validate_pattern',
    'contains_blocked_pattern',
    'validate_request_body',
    'get_client_ip',
    'SecureString',
    'SecurePath',
    'SecureEmail',
    'PATTERNS',
]
