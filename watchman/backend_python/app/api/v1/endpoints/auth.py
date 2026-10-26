# app/api/v1/endpoints/auth.py
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.deps import bearer_scheme, extract_raw_token, get_current_user, require_admin
from app.db.session import get_db
from app.models.audit_log import SecurityAuditLog
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _client_ip(request: Request) -> str:
    """Safely extract remote client IP address."""
    if request.client:
        return request.client.host
    return request.headers.get("x-forwarded-for", "127.0.0.1").split(",")[0].strip()


@router.post("/login", response_model=LoginResponse)
def login(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)) -> Any:
    """
    Authenticate user with credentials.
    Enforces Account Lockout (5 attempts cooldown) and generic anti-enumeration messages.
    """
    username_or_email = payload.get("username_or_email") or payload.get("usernameOrEmail") or ""
    password = payload.get("password") or ""
    role = payload.get("role")
    req = LoginRequest(username_or_email=username_or_email, password=password, role=role)
    service = AuthService(db)
    return service.login(
        req,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/verify-mfa", response_model=LoginResponse)
def verify_mfa(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)) -> Any:
    """
    2-Step Verification (MFA) endpoint for Administrative roles.
    Verifies the 6-digit OTP code against the ephemeral mfa_token session.
    """
    mfa_token = payload.get("mfa_token") or payload.get("mfaToken") or ""
    otp = payload.get("otp") or payload.get("otp_token") or payload.get("otpToken") or ""
    service = AuthService(db)
    return service.verify_mfa(
        mfa_token=mfa_token,
        otp=otp,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/logout")
def logout(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Server-side token revocation. Revokes the active JWT token and stores its JTI in the blocklist.
    """
    token = extract_raw_token(request, credentials)
    service = AuthService(db)
    return service.logout(
        token,
        current_user,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/me")
def get_current_user_profile(current_user: User = Depends(get_current_user)) -> Any:
    """
    Get profile information of the currently authenticated user with assigned gate.
    """
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "fullName": current_user.full_name,
        "role": current_user.role,
        "department": current_user.department,
        "assignedGate": current_user.assigned_gate or "Main Gate 1",
        "isActive": current_user.is_active,
    }


@router.get("/audit-logs")
def get_security_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
) -> Any:
    """
    Retrieve security audit event trail (Admin only).
    """
    logs = (
        db.query(SecurityAuditLog)
        .order_by(SecurityAuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "eventType": log.event_type,
            "username": log.username,
            "ipAddress": log.ip_address,
            "userAgent": log.user_agent,
            "gateNumber": log.gate_number,
            "status": log.status,
            "details": log.details,
        }
        for log in logs
    ]


@router.post("/forgot-password")
def forgot_password(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)) -> Any:
    email_or_user = (
        payload.get("email_or_username")
        or payload.get("emailOrUsername")
        or payload.get("email")
        or ""
    )
    service = AuthService(db)
    return service.forgot_password(
        email_or_user,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/reset-password")
def reset_password(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)) -> Any:
    email_or_user = payload.get("email_or_username") or payload.get("emailOrUsername") or ""
    otp = payload.get("otp_token") or payload.get("otp") or payload.get("otpToken") or ""
    new_pw = payload.get("new_password") or payload.get("newPassword") or ""
    service = AuthService(db)
    return service.reset_password(
        email_or_user,
        otp,
        new_pw,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
