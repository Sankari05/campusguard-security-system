# app/api/deps.py
"""
FastAPI Security & Authentication Dependencies.
Enforces JWT validation, server-side token revocation checks (blocklist),
user account active status, and Role-Based Access Control (RBAC).
"""

from typing import Any, Optional
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.revoked_token import RevokedToken
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def extract_raw_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Optional[str]:
    """Extract raw bearer token from Authorization header or HTTPBearer credentials."""
    if credentials and credentials.credentials:
        return credentials.credentials.strip()
    auth_hdr = request.headers.get("Authorization", "")
    if auth_hdr.lower().startswith("bearer "):
        return auth_hdr[7:].strip()
    return None


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Enforce JWT authentication.
    1. Validates signature and expiration.
    2. Checks server-side RevokedToken blocklist.
    3. Verifies user exists and account is active (is_active=True).
    """
    token = extract_raw_token(request, credentials)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Server-side token revocation blocklist check
    jti = payload.get("jti")
    if jti:
        revoked = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
        if revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    username: Optional[str] = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Access denied.",
        )

    return user


def require_roles(*allowed_roles: Any):
    """
    Role-Based Access Control (RBAC) dependency factory.
    Enforces that the authenticated user possesses one of the allowed roles.
    Accepts both *roles and list/tuple of roles.
    Raises 403 Forbidden on role mismatch.
    """
    roles = []
    for r in allowed_roles:
        if isinstance(r, (list, tuple, set)):
            roles.extend(r)
        else:
            roles.append(r)
    normalized_allowed = {str(r).upper() for r in roles}

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = (current_user.role or "").upper()
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {list(normalized_allowed)}. Your role: {current_user.role}",
            )
        return current_user

    return role_checker


# Standard role guards
require_admin = require_roles("ADMIN")
require_watchman = require_roles("WATCHMAN", "ADMIN")
require_staff = require_roles("WATCHMAN", "ADMIN", "FACULTY")


def validate_gate_scope(current_user: User, requested_gate: Optional[str] = None) -> Optional[str]:
    """
    Enforce Gate Isolation & Data Scoping.
    - ADMIN: Unrestricted access across all campus gates.
    - WATCHMAN: Confined strictly to their assigned_gate. Cross-gate queries are blocked with 403 Forbidden.
    """
    role = (current_user.role or "").upper()
    if role == "ADMIN":
        return requested_gate

    guard_gate = current_user.assigned_gate or "Main Gate 1"
    if requested_gate:
        # Normalize comparison
        clean_req = requested_gate.strip().lower()
        clean_assigned = guard_gate.strip().lower()
        if clean_req != clean_assigned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are assigned to '{guard_gate}' and cannot access data for '{requested_gate}'.",
            )
    return guard_gate

