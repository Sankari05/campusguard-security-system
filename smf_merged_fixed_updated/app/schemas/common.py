"""
app.schemas.common
Standardized Pydantic v2 schemas for consistent API response envelopes and pagination.
"""

from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int = Field(1, ge=1, description="Current page number (1-indexed)")
    per_page: int = Field(10, ge=1, le=100, description="Items per page")
    total: int = Field(0, ge=0, description="Total number of matching records")
    total_pages: int = Field(1, ge=1, description="Total number of pages")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None
    request_id: Optional[str] = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None
    request_id: Optional[str] = None


class ApiErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
