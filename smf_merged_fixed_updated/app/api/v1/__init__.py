"""
app/api/v1 package
Modular Version 1 API Routers for EduTrack Pro.
Each router is isolated into its own domain with max 100-150 lines.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.students import router as students_router
from app.api.v1.attendance import router as attendance_router
from app.api.v1.session import router as session_router
from app.api.v1.enrollment import router as enrollment_router
from app.api.v1.training import router as training_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.frontend import router as frontend_router

v1_router = APIRouter()
v1_router.include_router(auth_router)
v1_router.include_router(students_router)
v1_router.include_router(attendance_router)
v1_router.include_router(session_router)
v1_router.include_router(enrollment_router)
v1_router.include_router(training_router)
v1_router.include_router(alerts_router)
v1_router.include_router(analytics_router)
v1_router.include_router(frontend_router)

__all__ = [
    "v1_router",
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
