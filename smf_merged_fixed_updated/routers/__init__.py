"""
routers/__init__.py
Compatibility Facade delegating to app.api.v1.
Preserves backward compatibility for legacy imports.
"""
from app.api.v1 import (
    v1_router as api_router,
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

__all__ = [
    "api_router",
    "auth_router",
    "students_router",
    "attendance_router",
    "session_router",
    "enrollment_router",
    "training_router",
    "alerts_router",
    "analytics_router",
    "frontend_router",
]
