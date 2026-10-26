"""
app/main.py
============
Enterprise FastAPI Application Entrypoint & ASGI Factory for EduTrack Pro.
Mounts all modular routers, services, and middleware.
"""

import os
import sys
import time
import base64
import json
import hmac
import hashlib
import logging
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

import app
from app.core import config
from app.core.logger import get_logger
from app.database import database as db
from app.services.vision import attendance_session as _sess

log = get_logger("app.main")
BASE_DIR = config.BASE_DIR

# ── SlowAPI Rate Limiting ─────────────────────────────────────
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    SLOWAPI_OK = True
except ImportError:
    SLOWAPI_OK = False

# ── Auth & User Route Subsystems ──────────────────────────────
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
from app.api.v1.features.auth_routes import router as _auth_ext_router, init_otp_table
from app.api.v1.features.user_routes import router as _user_router

# ── Modular Router Registry ───────────────────────────────────
from app.api.v1 import (
    v1_router,
    auth_router,
    students_router,
    attendance_router,
    session_router,
    enrollment_router,
    training_router,
    alerts_router,
    analytics_router,
    frontend_router,
)


# =============================================================
# BACKWARD COMPATIBILITY: TOKENS & SECURITY HELPERS
# =============================================================
def _get_known_secrets() -> list:
    secrets_list = []
    if getattr(config, "API_SECRET_KEY", None):
        secrets_list.append(config.API_SECRET_KEY)
    legacy = [
        os.environ.get("API_SECRET_KEY", "").strip(),
        "362dda3755d5202320fb2af95f7a52f504e958ec6f6f2da8b8283f5d07d3022e",
        "smf-super-secret-key-change-in-prod!",
        "smf-secret",
        "secret",
        "changeme",
    ]
    for s in legacy:
        if s and s not in secrets_list:
            secrets_list.append(s)
    return secrets_list


def _make_token(payload: dict) -> str:
    data_b = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    sig = hmac.new(config.API_SECRET_KEY.encode(), data_b.encode(), hashlib.sha256).hexdigest()
    return f"{data_b}.{sig}"


def _verify_token(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid token format. Please sign in again.")
    data_b, sig = parts
    try:
        valid = False
        for secret_key in _get_known_secrets():
            expected = hmac.new(secret_key.encode(), data_b.encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig, expected):
                valid = True
                break
        if not valid:
            raise ValueError("invalid signature")
        data = json.loads(base64.urlsafe_b64decode(data_b).decode())
        if data.get("exp", 0) < time.time():
            raise ValueError("token expired")
        return data
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def create_access_token(username: str, role: str, dept: str = "", name: str = "") -> str:
    payload = {
        "sub": username,
        "role": role,
        "dept": dept.upper() if dept else "",
        "name": name or username,
        "exp": time.time() + config.API_TOKEN_EXPIRY_HOURS * 3600,
        "iat": time.time(),
    }
    return _auth_create_token(payload)


def decode_token(token: str) -> dict:
    return _auth_decode_token(token)


def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="No authorization token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_header[7:].strip()
    return decode_token(token)


def teacher_required(user: dict = Depends(get_current_user)) -> dict:
    return _auth_teacher_req(user)


def admin_required(user: dict = Depends(get_current_user)) -> dict:
    return _auth_admin_req(user)


# =============================================================
# BACKWARD COMPATIBILITY: REQUEST SCHEMAS
# =============================================================
class AddStudentReq(BaseModel):
    register_number: str
    roll_number: str = ""
    first_name: str = ""
    last_name: str = ""
    gender: str = ""
    date_of_birth: str = ""
    department: str = ""
    course: str = ""
    year: str = ""
    section: str = "A"
    student_email: str = ""
    parent_email: str = ""
    student_mobile: str = ""
    parent_mobile: str = ""
    twin_of: Optional[str] = None
    status: Optional[str] = "Active"
    name: str = ""
    mobile: str = ""


class FrontendLoginReq(BaseModel):
    email: str = ""
    password: str = ""
    role: str = "admin"
    fac_id: str = ""
    portal: str = ""


class FrontendOverrideReq(BaseModel):
    student_id: str
    period: str
    action: str
    reason: str = ""
    modifier_id: str = ""
    category: str = ""


# =============================================================
# FASTAPI APPLICATION FACTORY
# =============================================================
def create_app() -> FastAPI:
    """Create and assemble the enterprise FastAPI application."""
    app_instance = FastAPI(
        title="EduTrack Pro · Smart Attendance API",
        version="9.6",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 0. Production Observability (Sentry / Fallback Logger)
    try:
        from app.core.observability import init_observability, global_exception_handler
        init_observability()
        app_instance.add_exception_handler(Exception, global_exception_handler)
    except Exception as _obs_err:
        log.warning("[OBSERVABILITY] Notice: %s", _obs_err)

    # 1. Initialize SQLite tables and schemas
    try:
        db.init_all_tables()
    except Exception as _init_err:
        log.warning("[DB-STARTUP] init_all_tables notice: %s", _init_err)

    # 2. CORS Middleware
    app_instance.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Rate-limiting setup (SlowAPI)
    if SLOWAPI_OK:
        limiter = Limiter(key_func=get_remote_address, default_limits=[])
        app_instance.state.limiter = limiter
        app_instance.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app_instance.add_middleware(SlowAPIMiddleware)

    # 4. Attach Extended Auth & User Management Routers
    try:
        app_instance.include_router(_auth_ext_router)
        app_instance.include_router(_user_router, prefix="/user")
        init_otp_table()
    except Exception as _auth_err:
        log.warning("External auth routes attachment notice: %s", _auth_err)

    # 5. Attach Centralized V1 Modular Domain Routers
    # (Auth, Students, Attendance, Session, Enrollment, Training, Alerts, Analytics, Frontend)
    app_instance.include_router(v1_router)

    # 6. Avatars Static Mount
    avatars_dir = os.path.join(config.BASE_DIR, "data", "avatars")
    if os.path.isdir(avatars_dir):
        app_instance.mount("/avatars", StaticFiles(directory=avatars_dir), name="avatars")

    # 7. Pluggable Feature Subsystems
    _register_feature_modules(app_instance)

    log.info("EduTrack Pro API successfully assembled with 9 modular domain routers.")
    return app_instance


def _register_feature_modules(target_app: FastAPI):
    """Attach pluggable domain feature modules cleanly."""
    modules = [
        ("app.api.v1.features.api_role_attendance", "register_role_attendance_routes", (target_app, db, config)),
        ("app.api.v1.features.api_override", "register_override_routes", (target_app, get_current_user, teacher_required, admin_required, _uname)),
        ("app.api.v1.features.api_hod", "register_hod_routes", (target_app, get_current_user, admin_required, _uname)),
        ("app.api.v1.features.api_features", "register_feature_routes", (target_app, get_current_user, teacher_required, admin_required)),
        ("app.api.v1.features.api_faculty_requests", "register_faculty_request_routes", (target_app, get_current_user, teacher_required, _uname)),
        ("app.api.v1.features.api_compliance", "register_compliance_routes", (target_app, get_current_user, admin_required)),
        ("app.api.v1.features.api_academic", "register_academic_routes", (target_app, get_current_user, teacher_required)),
        ("app.api.v1.features.api_extras", "register_extra_routes", (target_app, get_current_user, teacher_required, admin_required)),
        ("app.api.v1.features.api_anomaly", "register_anomaly_routes", (target_app, get_current_user, teacher_required)),
        ("app.api.v1.features.api_clash", "register_clash_routes", (target_app, get_current_user,)),
        ("app.api.v1.features.api_workload", "register_workload_routes", (target_app, get_current_user, admin_required)),
        ("app.api.v1.features.api_ai_reports", "register_ai_report_routes", (target_app, get_current_user,)),
    ]
    for mod_name, fn_name, args in modules:
        try:
            mod = __import__(mod_name, fromlist=[fn_name])
            fn = getattr(mod, fn_name, None)
            if callable(fn):
                fn(*args)
        except Exception as e:
            log.warning("Feature module %s attachment notice: %s", mod_name, e)


# =============================================================
# MODULE-LEVEL ASGI INSTANCE & RUNNER
# =============================================================
app = create_app()


def run_api():
    """CLI launcher for Uvicorn ASGI server with port detection and banner."""
    try:
        _migrated = db.migrate_plaintext_passwords()
        if _migrated:
            log.info("Startup migration: %d password(s) upgraded to bcrypt.", _migrated)
    except Exception as _mig_err:
        log.warning("Startup password migration notice: %s", _mig_err)

    import socket
    port = config.API_PORT
    for p in [port, port + 1, port + 2, 8080, 8888, 9000]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", p))
            port = p
            break
        except OSError:
            continue
    else:
        print("  ERROR: No free port. Kill old server and retry.")
        return

    print("\n  ┌──────────────────────────────────────────────────────┐")
    print("  │  EduTrack Pro  ·  Smart Attendance System  v9.6      │")
    print("  │  Modular Clean Architecture (FastAPI + Layered)      │")
    print(f"  │  Dashboard  : http://localhost:{port}/app             │")
    print(f"  │  API Docs   : http://localhost:{port}/docs            │")
    print(f"  │  Video Feed : http://localhost:{port}/video_feed      │")
    print("  └──────────────────────────────────────────────────────┘\n")

    try:
        uvicorn.run(app, host=config.API_HOST, port=port, log_level="warning")
    except OSError as e:
        print(f"\n  ERROR: {e}")


if __name__ == "__main__":
    run_api()
