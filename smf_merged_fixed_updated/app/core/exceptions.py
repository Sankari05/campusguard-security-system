"""
app.core.exceptions
Enterprise-grade centralized exception hierarchy for EduTrack Pro.
Provides structured, predictable error responses across all API endpoints.
"""

from typing import Any, Dict, Optional


class AppException(Exception):
    """Base application exception with HTTP status code and error taxonomy."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "BAD_REQUEST",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        resp = {
            "success": False,
            "error": {
                "code": self.error_code,
                "message": self.message,
            },
        }
        if self.details:
            resp["error"]["details"] = self.details
        return resp


class NotFoundError(AppException):
    """Resource not found (HTTP 404)."""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} with identifier '{identifier}' was not found.",
            status_code=404,
            error_code=f"{resource.upper()}_NOT_FOUND",
            details={"resource": resource, "identifier": str(identifier)},
        )


class UnauthorizedError(AppException):
    """Authentication required or token expired (HTTP 401)."""

    def __init__(self, message: str = "Authentication required or token is invalid"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="UNAUTHORIZED",
        )


class ForbiddenError(AppException):
    """Authenticated user lacks permission (HTTP 403)."""

    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(
            message=message,
            status_code=403,
            error_code="FORBIDDEN",
        )


class ConflictError(AppException):
    """Resource conflict, e.g. duplicate enrollment or timetable clash (HTTP 409)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT",
            details=details,
        )


class ValidationError(AppException):
    """Input payload validation failure (HTTP 422)."""

    def __init__(self, message: str, field_errors: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="VALIDATION_ERROR",
            details={"fields": field_errors or {}},
        )
