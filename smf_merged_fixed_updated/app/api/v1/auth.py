# =============================================================
# routers/auth.py
# Authentication Router — Modular Auth, Tokens & Access Controls
# =============================================================
import os
import time
import hmac
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from app.core import config
from app.database import database as db
from app.core.auth_utils import (
    create_access_token as _auth_create_token,
    decode_token as _auth_decode_token,
    get_current_user as _auth_get_user,
    teacher_required as _auth_teacher_req,
    admin_required as _auth_admin_req,
    uname as _uname,
    hash_password as _hash_password,
    verify_password as _verify_password,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])


# ── Schemas ───────────────────────────────────────────────────
class FrontendLoginReq(BaseModel):
    email: str = ""
    password: str = ""
    role: str = ""
    fac_id: str = ""
    portal: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


# ── Password Verification Helpers ─────────────────────────────
def check_admin_password(plain_or_hash: str) -> bool:
    """Enterprise bcrypt-aware Admin password verification."""
    stored = config.ADMIN_PASSWORD
    if config.is_bcrypt(stored):
        try:
            import bcrypt
            return bcrypt.checkpw(plain_or_hash.encode(), stored.encode())
        except Exception:
            return False
    # Plain text check with auto-upgrade
    if plain_or_hash == stored:
        try:
            import bcrypt
            hashed = bcrypt.hashpw(plain_or_hash.encode(), bcrypt.gensalt()).decode()
            config.ADMIN_PASSWORD = hashed
            # Persist to .env
            env_path = os.path.join(config.BASE_DIR, ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    content = f.read()
                import re
                content = re.sub(r"^ADMIN_PASSWORD=.*", f"ADMIN_PASSWORD={hashed}", content, flags=re.MULTILINE)
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(content)
        except Exception:
            pass
        return True
    return False


# ── Auth Dependencies (Re-exported for app-wide use) ──────────
def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No authorization token provided")
    token = auth[7:]
    return _auth_decode_token(token)


def teacher_required(user: dict = Depends(get_current_user)) -> dict:
    return _auth_teacher_req(user)


def admin_required(user: dict = Depends(get_current_user)) -> dict:
    return _auth_admin_req(user)


# ── Endpoints ─────────────────────────────────────────────────
@router.post("/api/login")
@router.post("/auth/login")
@router.post("/login")
def api_login(req: FrontendLoginReq, request: Request):
    """
    Centralized Login endpoint for all roles:
    Admin, HOD, Faculty, Incharge, Teacher.
    Enforces brute-force lockout, rate limiting, and password hashing.
    """
    ip = request.client.host if request.client else "?"
    role = None
    username = ""
    display_name = ""
    req_portal = (getattr(req, "portal", "") or req.role or "").strip().lower()

    # 1. Brute-force lockout identifier check
    _raw_id = (req.fac_id or req.email or getattr(req, "username", "") or "").strip()
    _bf_identifier = (req.fac_id.strip().upper() if req.fac_id else _raw_id.lower())
    _fail_count, _is_locked, _lock_until = db.get_login_fail_count(_bf_identifier)
    if _is_locked:
        _now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if _lock_until and _lock_until > _now_str:
            db.log_audit(_bf_identifier, "login_blocked", "", "brute_force_lockout", ip)
            raise HTTPException(
                status_code=429,
                detail=f"Account locked due to too many failed attempts. Try again after {_lock_until}."
            )
        else:
            db.reset_login_fail(_bf_identifier)

    # 2. Faculty portal login (fac_id provided)
    if req.fac_id and req.fac_id.strip():
        fac_id = req.fac_id.strip().upper()
        fac = db.get_faculty_by_id(fac_id)
        if not fac:
            db.log_audit(fac_id, "login_fail", "", "unknown_fac_id", ip)
            db.increment_login_fail(fac_id)
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        if fac.get("is_active") is not None and not fac.get("is_active"):
            raise HTTPException(status_code=403, detail="Faculty account is deactivated.")

        stored_pw = fac.get("password") or ""
        is_valid_pw = False
        if _verify_password(req.password, stored_pw):
            is_valid_pw = True
        elif not config.is_bcrypt(stored_pw) and stored_pw and req.password == stored_pw:
            # Auto-upgrade legacy plain text in DB to secure BCrypt
            is_valid_pw = True
            db.update_faculty_password(fac_id, _hash_password(req.password))
        elif stored_pw == config.FACULTY_DEFAULT_PASSWORD and req.password == config.FACULTY_DEFAULT_PASSWORD:
            is_valid_pw = True
            db.update_faculty_password(fac_id, _hash_password(req.password))

        if not is_valid_pw:
            db.log_audit(fac_id, "login_fail", "", "wrong_password", ip)
            db.increment_login_fail(fac_id)
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        db.reset_login_fail(fac_id)
        _fac_name = fac.get("name") or fac.get("full_name") or fac_id
        db.log_audit(fac_id, "login_success", "faculty", "", ip)
        token = _auth_create_token({
            "sub": fac_id,
            "role": "faculty",
            "name": _fac_name,
            "email": fac.get("email", ""),
            "department": fac.get("department", ""),
        })
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": "faculty",
            "username": _fac_name,
        }

    # 3. Admin / HOD login
    email = (req.email or getattr(req, "username", "") or "").strip().lower()
    admin_email_configured = getattr(config, "ADMIN_EMAIL", os.environ.get("ADMIN_EMAIL", "admin@college.edu")).strip().lower()
    ALLOWED_ADMIN_EMAILS = {
        admin_email_configured,
        config.ADMIN_USERNAME.lower(),
        f"{config.ADMIN_USERNAME.lower()}@college.edu",
    }

    if email in ALLOWED_ADMIN_EMAILS:
        if check_admin_password(req.password):
            role = "admin"
            username = admin_email_configured or config.ADMIN_USERNAME
            display_name = "ADMIN"
        else:
            db.log_audit(email, "login_fail", "", "", ip)
            db.increment_login_fail(email)
            raise HTTPException(status_code=401, detail="Invalid username or password.")
        db.reset_login_fail(email)

        if req_portal in ("hod", "faculty"):
            db.log_audit(email, "login_role_mismatch", req_portal, "admin_on_wrong_portal", ip)
            raise HTTPException(
                status_code=403,
                detail=f"Admin account cannot log in via {req_portal.upper()} portal. Please use the Admin Portal."
            )
    else:
        # Check HOD DB
        hod_row = db.get_hod_by_id_or_email(email)
        if hod_row:
            if hod_row.get("is_active") is not None and not hod_row.get("is_active"):
                raise HTTPException(status_code=403, detail="HOD account is deactivated.")
            hod_pw = hod_row.get("password") or ""
            is_valid_hod = False
            if _verify_password(req.password, hod_pw):
                is_valid_hod = True
            elif not config.is_bcrypt(hod_pw) and req.password == hod_pw:
                # Upgrade legacy plaintext to bcrypt
                is_valid_hod = True
                db.update_hod_password(hod_row.get("hod_id", ""), _hash_password(req.password))

            if is_valid_hod:
                role = "hod"
                username = hod_row.get("email") or email
                display_name = hod_row.get("name") or "HOD"
                db.reset_login_fail(email)
            else:
                db.log_audit(email, "login_fail", "", "wrong_hod_password", ip)
                db.increment_login_fail(email)
                raise HTTPException(status_code=401, detail="Invalid username or password.")
        elif config.is_bcrypt(getattr(config, "TEACHER_PASSWORD", "")) and _verify_password(req.password, config.TEACHER_PASSWORD):
            role = "teacher"
            username = email or getattr(config, "TEACHER_USERNAME", "teacher")
            display_name = "Teacher"
            db.reset_login_fail(email)
        elif not config.is_bcrypt(getattr(config, "TEACHER_PASSWORD", "")) and req.password == getattr(config, "TEACHER_PASSWORD", ""):
            # Upgrade plain TEACHER_PASSWORD to BCrypt
            role = "teacher"
            username = email or getattr(config, "TEACHER_USERNAME", "teacher")
            display_name = "Teacher"
            config.TEACHER_PASSWORD = _hash_password(req.password)
            db.reset_login_fail(email)
        else:
            db.log_audit(email, "login_fail", "", "", ip)
            db.increment_login_fail(email)
            raise HTTPException(status_code=401, detail="Invalid username or password.")

    db.log_audit(email, "login_success", role, "", ip)
    token = _auth_create_token({
        "sub": username,
        "role": role,
        "name": display_name,
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role,
        "username": display_name or username,
    }


@router.get("/api/auth/me")
def api_auth_me(user: dict = Depends(get_current_user)):
    """Return the decoded claims of the current authenticated user."""
    return {
        "user_id": user.get("sub", ""),
        "role": user.get("role", ""),
        "name": user.get("name", ""),
        "department": user.get("department", ""),
    }


@router.get("/api/auth/verify")
def api_auth_verify(user: dict = Depends(get_current_user)):
    """Lightweight endpoint for frontend session verification."""
    return {"valid": True, "role": user.get("role", "")}


@router.get("/api/verify-token")
def api_verify_token(user: dict = Depends(get_current_user)):
    """Validates the JWT token from Authorization header and returns user claims."""
    return {
        "valid": True,
        "role": user.get("role", "admin"),
        "username": user.get("sub", ""),
        "fac_id": user.get("fac_id", ""),
        "name": user.get("name") or user.get("sub", ""),
    }


@router.get("/api/faculty/{fac_id}/email-hint", tags=["Faculty"])
def api_faculty_email_hint(fac_id: str):
    """Public endpoint returning masked email for forgot-password assistance."""
    fac = db.get_faculty_by_id(fac_id.strip().upper())
    if not fac:
        return {"found": False, "email_hint": None}

    raw_email = (fac.get("email") or "").strip()
    if not raw_email or "@" not in raw_email:
        return {"found": True, "email_hint": None}

    local, domain = raw_email.rsplit("@", 1)
    masked_local = local[:2] + "***" if len(local) > 2 else local[:1] + "***"
    return {"found": True, "email_hint": f"{masked_local}@{domain}"}

