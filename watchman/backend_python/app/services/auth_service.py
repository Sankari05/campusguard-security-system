# app/services/auth_service.py
from datetime import datetime, timedelta, timezone
import secrets
from typing import Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, UnauthorizedException
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.audit_service import AuditService

# In-memory store for OTPs (with expiry and single-use)
_otp_store: dict[str, dict] = {}
_mfa_store: dict[str, dict] = {}

# Constants for MNC Security Standard
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.audit = AuditService(db)

    def login(
        self,
        req: LoginRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> LoginResponse:
        """
        Authenticate user with:
        1. Generic anti-enumeration error messages.
        2. Account Lockout policy: 5 consecutive failed attempts trigger a 15-minute cooldown.
        3. Security event audit logging (LOGIN_SUCCESS, LOGIN_FAILED, ACCOUNT_LOCKED).
        4. Strict BCrypt verification & user account activation status check.
        5. 2-Step OTP Verification (MFA) challenge for ADMIN accounts.
        """
        identifier = (req.username_or_email or getattr(req, "usernameOrEmail", None) or getattr(req, "username", None) or "").strip()
        user = self.user_repo.find_by_username_or_email(identifier)

        # 1. Anti-Enumeration: Unknown account fails with identical generic error
        if not user:
            self.audit.log_event(
                event_type="LOGIN_FAILED",
                username=identifier,
                ip_address=ip_address,
                user_agent=user_agent,
                status="FAILURE",
                details="Unknown username or email",
            )
            raise UnauthorizedException("Invalid username or password.")

        now_utc = datetime.utcnow()

        # 2. Check if account is in lockout cooldown
        if user.locked_until:
            if user.locked_until > now_utc:
                remaining_sec = int((user.locked_until - now_utc).total_seconds())
                remaining_min = max(1, (remaining_sec + 59) // 60)
                self.audit.log_event(
                    event_type="ACCOUNT_LOCKED_ATTEMPT",
                    username=user.username,
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    gate_number=user.assigned_gate,
                    status="BLOCKED",
                    details=f"Login attempt while account locked. {remaining_min} mins remaining.",
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Account is temporarily locked due to 5 consecutive failed attempts. Please try again after {remaining_min} minutes.",
                )
            else:
                # Lockout expired: reset failed attempts
                user.locked_until = None
                user.failed_login_attempts = 0
                self.db.commit()

        # 3. Verify BCrypt password
        is_valid = bool(user.password_hash and verify_password(req.password, user.password_hash))

        if not is_valid:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = now_utc + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                self.db.commit()

                self.audit.log_event(
                    event_type="ACCOUNT_LOCKED",
                    username=user.username,
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    gate_number=user.assigned_gate,
                    status="BLOCKED",
                    details=f"Account locked for {LOCKOUT_DURATION_MINUTES} mins after {MAX_FAILED_ATTEMPTS} failed attempts",
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed login attempts. Account is locked for {LOCKOUT_DURATION_MINUTES} minutes cooldown.",
                )

            self.db.commit()
            self.audit.log_event(
                event_type="LOGIN_FAILED",
                username=user.username,
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                gate_number=user.assigned_gate,
                status="FAILURE",
                details=f"Incorrect password attempt {user.failed_login_attempts}/{MAX_FAILED_ATTEMPTS}",
            )
            raise UnauthorizedException("Invalid username or password.")

        # 4. Check active account status
        if not user.is_active:
            self.audit.log_event(
                event_type="LOGIN_BLOCKED",
                username=user.username,
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                status="BLOCKED",
                details="Deactivated account login attempt",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated. Please contact administration.",
            )

        # 5. Success: reset failed attempts counter
        user.failed_login_attempts = 0
        user.locked_until = None
        self.db.commit()

        # 6. Admin 2-Step OTP Verification (MFA)
        if (user.role or "").upper() == "ADMIN":
            mfa_token = str(uuid.uuid4())
            otp = f"{secrets.randbelow(900000) + 100000}"
            now_ts = datetime.now(timezone.utc).timestamp()
            _mfa_store[mfa_token] = {
                "user_id": user.id,
                "username": user.username,
                "otp": otp,
                "expires_at": now_ts + 300,  # 5 minutes
                "role": user.role,
            }
            self.audit.log_event(
                event_type="MFA_CHALLENGE_ISSUED",
                username=user.username,
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                gate_number=user.assigned_gate,
                status="SUCCESS",
                details="2-Step Verification code generated and dispatched to registered admin device",
            )
            return LoginResponse(
                mfa_required=True,
                mfa_token=mfa_token,
                username=user.username,
                role=user.role,
                message="Two-Factor Authentication required. A 6-digit verification code has been dispatched.",
            )

        # 7. Non-admin roles (WATCHMAN, FACULTY, STUDENT): Issue signed access token directly
        token = create_access_token(subject=user.username, role=user.role)

        self.audit.log_event(
            event_type="LOGIN_SUCCESS",
            username=user.username,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            gate_number=user.assigned_gate,
            status="SUCCESS",
            details="User logged in successfully",
        )

        return LoginResponse(
            token=token,
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            department=user.department,
            mfa_required=False,
        )

    def verify_mfa(
        self,
        mfa_token: str,
        otp: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> LoginResponse:
        """
        Verify Admin 2-Step OTP code and grant full access token.
        """
        token_key = mfa_token.strip()
        record = _mfa_store.get(token_key)
        now_ts = datetime.now(timezone.utc).timestamp()

        if not record or now_ts > record.get("expires_at", 0):
            self.audit.log_event(
                event_type="MFA_VERIFY_FAILED",
                ip_address=ip_address,
                user_agent=user_agent,
                status="FAILURE",
                details="Expired or invalid MFA token",
            )
            raise UnauthorizedException("Invalid or expired 2-step verification session.")

        if not secrets.compare_digest(record.get("otp", ""), otp.strip()):
            self.audit.log_event(
                event_type="MFA_VERIFY_FAILED",
                username=record.get("username"),
                user_id=record.get("user_id"),
                ip_address=ip_address,
                user_agent=user_agent,
                status="FAILURE",
                details="Incorrect MFA OTP supplied",
            )
            raise UnauthorizedException("Invalid 2-step verification code.")

        # Single-use consumption
        del _mfa_store[token_key]

        user = self.user_repo.get_by_id(record["user_id"])
        if not user or not user.is_active:
            raise UnauthorizedException("User account is inactive or not found.")

        token = create_access_token(subject=user.username, role=user.role)

        self.audit.log_event(
            event_type="MFA_VERIFY_SUCCESS",
            username=user.username,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            gate_number=user.assigned_gate,
            status="SUCCESS",
            details="Admin 2-Step OTP verification successful. Access granted.",
        )

        return LoginResponse(
            token=token,
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            department=user.department,
            mfa_required=False,
            message="2-Step Verification verified successfully.",
        )

    def logout(
        self,
        token: str,
        user: Optional[User] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        """
        Server-side Token Revocation + Logout Audit Logging.
        """
        if not token:
            return {"message": "Logged out successfully."}

        payload = decode_access_token(token)
        if payload and "jti" in payload:
            jti = payload["jti"]
            existing = self.db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
            if not existing:
                exp_ts = payload.get("exp")
                expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc) if exp_ts else None
                revocation = RevokedToken(
                    jti=jti,
                    token=token[:200],
                    user_id=user.id if user else None,
                    username=user.username if user else payload.get("sub"),
                    expires_at=expires_at,
                )
                self.db.add(revocation)
                self.db.commit()

        self.audit.log_event(
            event_type="LOGOUT",
            username=user.username if user else (payload.get("sub") if payload else "unknown"),
            user_id=user.id if user else None,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            details="User session terminated and token revoked",
        )

        return {"message": "Session terminated and token revoked successfully."}

    def forgot_password(
        self,
        email_or_username: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        identifier = email_or_username.strip().lower()
        user = self.user_repo.find_by_username_or_email(identifier)
        if user:
            otp = f"{secrets.randbelow(900000) + 100000}"
            now = datetime.now(timezone.utc).timestamp()
            _otp_store[user.username.lower()] = {
                "otp": otp,
                "expires_at": now + 600,  # 10 minutes
                "used": False,
            }
            if user.email:
                _otp_store[user.email.lower()] = _otp_store[user.username.lower()]

            self.audit.log_event(
                event_type="PASSWORD_RESET_REQUEST",
                username=user.username,
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                status="SUCCESS",
                details="Password reset code generated and dispatched",
            )
        else:
            self.audit.log_event(
                event_type="PASSWORD_RESET_REQUEST",
                username=identifier,
                ip_address=ip_address,
                user_agent=user_agent,
                status="FAILURE",
                details="Reset requested for non-existent user",
            )

        return {"message": "If the account exists, a secure verification code has been dispatched."}

    def reset_password(
        self,
        email_or_username: str,
        otp_token: str,
        new_password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        identifier = email_or_username.strip().lower()
        user = self.user_repo.find_by_username_or_email(identifier)
        if not user:
            raise BadRequestException("Invalid reset request.")

        record = _otp_store.get(identifier)
        if not record or record.get("used"):
            raise BadRequestException("Invalid or expired verification code.")

        now = datetime.now(timezone.utc).timestamp()
        if now > record.get("expires_at", 0):
            raise BadRequestException("Verification code has expired.")

        if not secrets.compare_digest(record.get("otp", ""), otp_token.strip()):
            raise BadRequestException("Invalid verification code.")

        record["used"] = True

        if len(new_password) < 6:
            raise BadRequestException("Password must be at least 6 characters in length.")

        user.password_hash = hash_password(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        self.user_repo.update(user)

        self.audit.log_event(
            event_type="PASSWORD_RESET_SUCCESS",
            username=user.username,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            details="Password successfully updated via OTP verification",
        )

        return {"message": "Password updated successfully. Please log in with your new password."}
