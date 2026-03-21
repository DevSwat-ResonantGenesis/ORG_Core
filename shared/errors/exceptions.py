"""
Custom Exception Classes for ResonantGenesis Backend.

All services should use these standardized exceptions for consistent error handling.
"""

from typing import Any, Dict, List, Optional


class ResonantError(Exception):
    """Base exception for all ResonantGenesis errors."""
    
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        self.headers = headers or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class ValidationError(ResonantError):
    """Raised when request validation fails."""
    
    def __init__(
        self,
        message: str = "Validation failed",
        field: Optional[str] = None,
        errors: Optional[List[Dict[str, Any]]] = None,
    ):
        details = {}
        if field:
            details["field"] = field
        if errors:
            details["errors"] = errors
        
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class AuthenticationError(ResonantError):
    """Raised when authentication fails."""
    
    def __init__(
        self,
        message: str = "Authentication required",
        reason: Optional[str] = None,
    ):
        details = {}
        if reason:
            details["reason"] = reason
        
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401,
            details=details,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(ResonantError):
    """Raised when user lacks permission for an action."""
    
    def __init__(
        self,
        message: str = "Permission denied",
        required_permission: Optional[str] = None,
        resource: Optional[str] = None,
    ):
        details = {}
        if required_permission:
            details["required_permission"] = required_permission
        if resource:
            details["resource"] = resource
        
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403,
            details=details,
        )


class NotFoundError(ResonantError):
    """Raised when a requested resource is not found."""
    
    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
        
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404,
            details=details,
        )


class ConflictError(ResonantError):
    """Raised when there's a conflict with existing resource."""
    
    def __init__(
        self,
        message: str = "Resource conflict",
        resource_type: Optional[str] = None,
        conflicting_field: Optional[str] = None,
    ):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if conflicting_field:
            details["conflicting_field"] = conflicting_field
        
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409,
            details=details,
        )


class RateLimitError(ResonantError):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        window_seconds: Optional[int] = None,
        retry_after: Optional[int] = None,
    ):
        details = {}
        if limit:
            details["limit"] = limit
        if window_seconds:
            details["window_seconds"] = window_seconds
        if retry_after:
            details["retry_after"] = retry_after
        
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details,
            headers=headers,
        )


class ServiceUnavailableError(ResonantError):
    """Raised when a service is temporarily unavailable."""
    
    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        service: Optional[str] = None,
        retry_after: Optional[int] = None,
    ):
        details = {}
        if service:
            details["service"] = service
        if retry_after:
            details["retry_after"] = retry_after
        
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        
        super().__init__(
            message=message,
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            details=details,
            headers=headers,
        )


class ExternalServiceError(ResonantError):
    """Raised when an external service call fails."""
    
    def __init__(
        self,
        message: str = "External service error",
        service: Optional[str] = None,
        original_error: Optional[str] = None,
    ):
        details = {}
        if service:
            details["service"] = service
        if original_error:
            details["original_error"] = original_error
        
        super().__init__(
            message=message,
            code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details=details,
        )


class DatabaseError(ResonantError):
    """Raised when a database operation fails."""
    
    def __init__(
        self,
        message: str = "Database operation failed",
        operation: Optional[str] = None,
    ):
        details = {}
        if operation:
            details["operation"] = operation
        
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=500,
            details=details,
        )


class ConfigurationError(ResonantError):
    """Raised when there's a configuration issue."""
    
    def __init__(
        self,
        message: str = "Configuration error",
        config_key: Optional[str] = None,
    ):
        details = {}
        if config_key:
            details["config_key"] = config_key
        
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            status_code=500,
            details=details,
        )
