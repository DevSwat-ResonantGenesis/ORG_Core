"""
SENTRY ERROR TRACKING INTEGRATION
=================================

Centralized error tracking for all Resonant Genesis services.
Captures exceptions, performance data, and user context.

Usage:
    from shared.observability.sentry_integration import init_sentry
    init_sentry(service_name="agent_engine")
"""

import os
import logging
from typing import Dict, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)

# Global sentry SDK reference
_sentry_sdk = None


def init_sentry(
    service_name: str,
    dsn: str = None,
    environment: str = None,
    release: str = None,
    sample_rate: float = 1.0,
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
) -> bool:
    """
    Initialize Sentry for a service.
    
    Args:
        service_name: Name of the service (e.g., "agent_engine", "chat_service")
        dsn: Sentry DSN (or from SENTRY_DSN env var)
        environment: Environment name (or from SENTRY_ENVIRONMENT env var)
        release: Release version (or from SENTRY_RELEASE env var)
        sample_rate: Error sample rate (0.0-1.0)
        traces_sample_rate: Performance traces sample rate
        profiles_sample_rate: Profiling sample rate
    
    Returns:
        True if initialized successfully, False otherwise
    """
    global _sentry_sdk
    
    dsn = dsn or os.getenv("SENTRY_DSN")
    if not dsn:
        logger.info("Sentry DSN not configured, error tracking disabled")
        return False
    
    environment = environment or os.getenv("SENTRY_ENVIRONMENT", "development")
    release = release or os.getenv("SENTRY_RELEASE", "unknown")
    
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.httpx import HttpxIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            
            # Sampling
            sample_rate=sample_rate,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            
            # Integrations
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                RedisIntegration(),
                CeleryIntegration(),
                HttpxIntegration(),
                LoggingIntegration(level=logging.ERROR, event_level=logging.ERROR),
            ],
            
            # Context
            server_name=service_name,
            
            # Data scrubbing
            send_default_pii=False,
            
            # Before send hook for filtering
            before_send=_before_send,
            before_send_transaction=_before_send_transaction,
        )
        
        # Set service tag
        sentry_sdk.set_tag("service", service_name)
        
        _sentry_sdk = sentry_sdk
        logger.info(f"Sentry initialized for {service_name} ({environment})")
        return True
        
    except ImportError:
        logger.warning("sentry-sdk not installed. Run: pip install sentry-sdk[fastapi]")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")
        return False


def _before_send(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Filter events before sending to Sentry."""
    # Filter out health check errors
    if "exception" in event:
        exc_info = hint.get("exc_info")
        if exc_info:
            exc_type, exc_value, _ = exc_info
            
            # Skip common non-errors
            if exc_type.__name__ in ["CancelledError", "ConnectionResetError"]:
                return None
    
    # Scrub sensitive data
    if "request" in event:
        request = event["request"]
        
        # Remove auth headers
        if "headers" in request:
            headers = request["headers"]
            for sensitive in ["authorization", "cookie", "x-api-key"]:
                if sensitive in headers:
                    headers[sensitive] = "[Filtered]"
        
        # Remove sensitive query params
        if "query_string" in request:
            qs = request["query_string"]
            for sensitive in ["token", "key", "password", "secret"]:
                if sensitive in qs.lower():
                    request["query_string"] = "[Filtered]"
    
    return event


def _before_send_transaction(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Filter transactions before sending to Sentry."""
    # Skip health check transactions
    transaction = event.get("transaction", "")
    if "/health" in transaction or "/metrics" in transaction:
        return None
    
    return event


def set_user_context(user_id: str, email: str = None, org_id: str = None):
    """Set user context for error tracking."""
    if _sentry_sdk:
        _sentry_sdk.set_user({
            "id": user_id,
            "email": email,
            "org_id": org_id,
        })


def set_tag(key: str, value: str):
    """Set a tag on current scope."""
    if _sentry_sdk:
        _sentry_sdk.set_tag(key, value)


def set_context(name: str, data: Dict[str, Any]):
    """Set additional context."""
    if _sentry_sdk:
        _sentry_sdk.set_context(name, data)


def capture_exception(exception: Exception = None, **kwargs):
    """Capture an exception."""
    if _sentry_sdk:
        _sentry_sdk.capture_exception(exception, **kwargs)


def capture_message(message: str, level: str = "info", **kwargs):
    """Capture a message."""
    if _sentry_sdk:
        _sentry_sdk.capture_message(message, level=level, **kwargs)


def start_transaction(name: str, op: str = "task"):
    """Start a performance transaction."""
    if _sentry_sdk:
        return _sentry_sdk.start_transaction(name=name, op=op)
    return None


def add_breadcrumb(message: str, category: str = "custom", level: str = "info", data: Dict = None):
    """Add a breadcrumb for debugging."""
    if _sentry_sdk:
        _sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {},
        )


def track_errors(func):
    """Decorator to track errors in a function."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            capture_exception(e)
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            capture_exception(e)
            raise
    
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


class SentryMiddleware:
    """FastAPI middleware for Sentry context."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract user from headers (set by gateway)
        headers = dict(scope.get("headers", []))
        user_id = headers.get(b"x-user-id", b"").decode()
        org_id = headers.get(b"x-org-id", b"").decode()
        
        if user_id:
            set_user_context(user_id=user_id, org_id=org_id)
        
        # Set request context
        set_context("request", {
            "path": scope.get("path"),
            "method": scope.get("method"),
            "client": scope.get("client"),
        })
        
        await self.app(scope, receive, send)
