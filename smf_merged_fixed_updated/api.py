"""
api.py
======
Root Backward-Compatibility Facade for EduTrack Pro.
Re-exports the primary ASGI application instance and security helpers from app.main.
Allows legacy scripts, TestClient fixtures, and Uvicorn commands to run without modifications.
"""

from app.main import (
    app,
    create_app,
    create_access_token,
    decode_token,
    get_current_user,
    teacher_required,
    admin_required,
    AddStudentReq,
    FrontendLoginReq,
    FrontendOverrideReq,
    run_api,
)
from app.core import config

__all__ = [
    "app",
    "create_app",
    "config",
    "create_access_token",
    "decode_token",
    "get_current_user",
    "teacher_required",
    "admin_required",
    "AddStudentReq",
    "FrontendLoginReq",
    "FrontendOverrideReq",
    "run_api",
]

if __name__ == "__main__":
    run_api()