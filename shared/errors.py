"""
Error handling utilities for Genesis2026
"""

from fastapi import HTTPException
from typing import Any, Dict, Optional

def setup_exception_handlers(app):
    """Setup exception handlers for FastAPI app"""
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return {"error": str(exc.detail), "status_code": exc.status_code}, exc.status_code
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        return {"error": "Internal server error", "status_code": 500}, 500
    
    @app.exception_handler(404)
    async def not_found_handler(request, exc):
        return {"error": "Not found", "status_code": 404}, 404
    
    @app.exception_handler(500)
    async def internal_error_handler(request, exc):
        return {"error": "Internal server error", "status_code": 500}, 500

class GenesisError(Exception):
    """Base exception for Genesis2026"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class ValidationError(GenesisError):
    """Validation error"""
    def __init__(self, message: str):
        super().__init__(message, 400)

class AuthenticationError(GenesisError):
    """Authentication error"""
    def __init__(self, message: str):
        super().__init__(message, 401)

class AuthorizationError(GenesisError):
    """Authorization error"""
    def __init__(self, message: str):
        super().__init__(message, 403)

class NotFoundError(GenesisError):
    """Not found error"""
    def __init__(self, message: str):
        super().__init__(message, 404)
