"""
Standardized Error Handling Module for ResonantGenesis Backend.

This module provides consistent error handling across all microservices.
"""

from .exceptions import (
    ResonantError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    RateLimitError,
    ServiceUnavailableError,
    ExternalServiceError,
    DatabaseError,
    ConfigurationError,
)

from .handlers import (
    setup_exception_handlers,
    error_response,
)

from .responses import (
    ErrorResponse,
    ErrorDetail,
)

__all__ = [
    # Exceptions
    "ResonantError",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "ServiceUnavailableError",
    "ExternalServiceError",
    "DatabaseError",
    "ConfigurationError",
    # Handlers
    "setup_exception_handlers",
    "error_response",
    # Responses
    "ErrorResponse",
    "ErrorDetail",
]
