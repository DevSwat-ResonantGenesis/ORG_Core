"""
Exception Handlers for FastAPI Applications.

Use setup_exception_handlers(app) to register all handlers with your FastAPI app.
"""

import logging
import traceback
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import SQLAlchemyError

from .exceptions import ResonantError, ValidationError, DatabaseError
from .responses import ErrorResponse

logger = logging.getLogger(__name__)


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    """Create a standardized error response."""
    content = ErrorResponse(
        error={
            "code": code,
            "message": message,
            "details": details or {},
        }
    ).model_dump()
    
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=headers,
    )


async def resonant_error_handler(request: Request, exc: ResonantError) -> JSONResponse:
    """Handle ResonantError exceptions."""
    logger.warning(
        f"ResonantError: {exc.code} - {exc.message}",
        extra={
            "error_code": exc.code,
            "status_code": exc.status_code,
            "path": request.url.path,
            "details": exc.details,
        }
    )
    
    return error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        headers=exc.headers,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle FastAPI validation errors."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    
    logger.warning(
        f"Validation error on {request.url.path}",
        extra={"errors": errors}
    )
    
    return error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": errors},
    )


async def pydantic_error_handler(request: Request, exc: PydanticValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    
    return error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Data validation failed",
        details={"errors": errors},
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle SQLAlchemy database errors."""
    logger.error(
        f"Database error: {str(exc)}",
        extra={
            "path": request.url.path,
            "error_type": type(exc).__name__,
        }
    )
    
    return error_response(
        status_code=500,
        code="DATABASE_ERROR",
        message="A database error occurred",
        details={"operation": "database_query"},
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    # Log full traceback for debugging
    logger.error(
        f"Unexpected error: {str(exc)}",
        extra={
            "path": request.url.path,
            "error_type": type(exc).__name__,
            "traceback": traceback.format_exc(),
        }
    )
    
    # Don't expose internal error details in production
    return error_response(
        status_code=500,
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        details={},
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with a FastAPI application.
    
    Usage:
        from shared.errors import setup_exception_handlers
        
        app = FastAPI()
        setup_exception_handlers(app)
    """
    # Custom ResonantGenesis errors
    app.add_exception_handler(ResonantError, resonant_error_handler)
    
    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(PydanticValidationError, pydantic_error_handler)
    
    # Database errors
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    
    # Generic fallback
    app.add_exception_handler(Exception, generic_error_handler)
    
    logger.info("Exception handlers registered")
