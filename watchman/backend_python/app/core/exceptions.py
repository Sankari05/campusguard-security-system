# =============================================================
# app/core/exceptions.py
# Purpose : Custom application exceptions with structured error responses
# Pattern : Domain Exception Hierarchy (used at Google, Meta)
# Benefit : Consistent error format across ALL endpoints
# =============================================================

from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base application exception. All custom errors inherit from this."""

    pass


class NotFoundException(AppException):
    """Raised when a requested resource does not exist (HTTP 404)."""

    def __init__(self, resource: str, identifier: str | int = ""):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} not found." + (f" ID: {identifier}" if identifier else ""),
        )


class ConflictException(AppException):
    """Raised when a duplicate or conflicting resource exists (HTTP 409)."""

    def __init__(self, message: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=message)


class UnauthorizedException(AppException):
    """Raised when authentication fails (HTTP 401)."""

    def __init__(self, message: str = "Authentication token is missing or invalid."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(AppException):
    """Raised when authenticated user lacks required role (HTTP 403)."""

    def __init__(self, required_roles: tuple[str, ...] = ()):
        roles_str = ", ".join(required_roles) if required_roles else "sufficient"
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Required role(s): {roles_str}.",
        )


class BadRequestException(AppException):
    """Raised for invalid input not caught by Pydantic (HTTP 400)."""

    def __init__(self, message: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


class GoneException(AppException):
    """Raised when a resource has expired (HTTP 410) e.g. OTP timeout."""

    def __init__(self, message: str):
        super().__init__(status_code=status.HTTP_410_GONE, detail=message)
