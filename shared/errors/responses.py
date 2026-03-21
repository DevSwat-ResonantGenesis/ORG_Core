"""
Standardized Error Response Models.

These Pydantic models define the structure of error responses.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Individual error detail."""
    
    field: Optional[str] = Field(None, description="Field that caused the error")
    message: str = Field(..., description="Error message")
    type: Optional[str] = Field(None, description="Error type code")


class ErrorInfo(BaseModel):
    """Error information structure."""
    
    code: str = Field(..., description="Error code (e.g., VALIDATION_ERROR)")
    message: str = Field(..., description="Human-readable error message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional error details")


class ErrorResponse(BaseModel):
    """Standardized error response format."""
    
    error: ErrorInfo = Field(..., description="Error information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {
                        "errors": [
                            {
                                "field": "email",
                                "message": "Invalid email format",
                                "type": "value_error"
                            }
                        ]
                    }
                }
            }
        }


class SuccessResponse(BaseModel):
    """Standardized success response format."""
    
    success: bool = Field(default=True, description="Success indicator")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    message: Optional[str] = Field(None, description="Success message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": "123", "name": "Example"},
                "message": "Operation completed successfully"
            }
        }


class PaginatedResponse(BaseModel):
    """Standardized paginated response format."""
    
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=20, description="Items per page")
    has_more: bool = Field(default=False, description="Whether more items exist")
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [{"id": "1"}, {"id": "2"}],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "has_more": True
            }
        }
