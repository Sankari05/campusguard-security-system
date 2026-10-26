# =============================================================
# app/core/dependencies.py
# Purpose : Reusable FastAPI dependency functions
# Pattern : Dependency Injection (same concept as Spring's @Autowired)
# Usage   : Inject into any route via Depends()
# =============================================================

from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token

# Bearer token extractor (auto_error=False so we can give a custom error message)
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """
    FastAPI dependency: Extracts and validates the JWT Bearer token.
    Replaces: Spring Security filter chain + @PreAuthorize annotations.

    Usage:
        @router.get("/me")
        def me(user: dict = Depends(get_current_user)):
            return user
    """
    if credentials is None:
        raise UnauthorizedException()

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise UnauthorizedException("Token is invalid or has expired.")

    return payload


def require_roles(*allowed_roles: str):
    """
    Role-based access control dependency factory.
    Replaces: @PreAuthorize("hasRole('ADMIN')") in Spring Security.

    Usage:
        # Single role
        @router.get("/admin", dependencies=[Depends(require_roles("ADMIN"))])

        # Multiple roles
        @router.get("/staff", dependencies=[Depends(require_roles("ADMIN", "FACULTY"))])
    """

    def _check(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role", "")
        if user_role not in allowed_roles:
            raise ForbiddenException(required_roles=allowed_roles)
        return current_user

    return _check
