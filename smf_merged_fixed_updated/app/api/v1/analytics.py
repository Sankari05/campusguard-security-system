"""
app.api.v1.analytics
FastAPI router for analytics summary, engine diagnostics, timetable, reports, and system settings.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException

import config
import database as db
from app.services.analytics_service import AnalyticsService
from auth_utils import get_current_user, admin_required

router = APIRouter(tags=["Analytics & Reports"])
_analytics_service = AnalyticsService()


@router.get("/api/analytics/summary")
def api_analytics_summary(current_user: dict = Depends(get_current_user)):
    """Role-aware dashboard summary (college-wide for Admin, dept-scoped for HOD)."""
    role = (current_user.get("role") or "").lower()
    dept = (current_user.get("dept") or "").upper()

    if role == "admin":
        stats = db.get_dashboard_stats_by_role("admin")
        summary_rows = db.get_attendance_summary(30)
    else:
        stats = db.get_dashboard_stats_by_role("hod", dept=dept)
        summary_rows = db.get_attendance_summary_by_dept(dept, days=30)

    total_members = stats["total_members"]
    total_students = stats["total_students"]
    present_today = stats["present_today"]
    absent_today = stats["absent_today"]
    pct_today = stats["pct_today"]

    engine_rows = db.get_engine_stats(7)
    period_rows = db.get_period_stats()

    pcts = []
    for r in summary_rows:
        pc = r.get("present_count", 0)
        td = r.get("total_days", 1) or 1
        pcts.append(pc / td * 100)
    avg_att = round(sum(pcts) / len(pcts), 1) if pcts else 0

    critical = [r for r in summary_rows if (r.get("present_count", 0) / (r.get("total_days", 1) or 1)) < 0.65]

    return {
        "dashboard_role": role,
        "filtered_dept": stats.get("filtered_dept", ""),
        "total_members": total_members,
        "total_students": total_students,
        "student_count": stats.get("student_count", total_students),
        "faculty_count": stats.get("faculty_count", 0),
        "hod_count": stats.get("hod_count", 0),
        "present_today": present_today,
        "absent_today": absent_today,
        "pct_today": pct_today,
        "avg_attendance": avg_att,
        "critical_count": len(critical),
        "critical_students": [dict(r) for r in critical],
        "engine_stats": [dict(r) for r in engine_rows],
        "period_stats": [dict(r) for r in period_rows],
    }


@router.get("/api/analytics/engine")
def api_engine_stats(days: int = 7, _: dict = Depends(get_current_user)):
    return [dict(r) for r in db.get_engine_stats(days)]


@router.get("/api/analytics/period")
def api_period_stats(_: dict = Depends(get_current_user)):
    return [dict(r) for r in db.get_period_stats()]


@router.get("/api/analytics/twins")
def api_twin_log(days: int = 7, _: dict = Depends(get_current_user)):
    return [dict(r) for r in db.get_twin_analysis_log(days)]


@router.get("/api/timetable")
def api_timetable(_: dict = Depends(get_current_user)):
    return [dict(r) for r in db.get_timetable()]


@router.get("/api/settings")
def api_get_settings(_: dict = Depends(get_current_user)):
    return {
        "LBPH_THRESHOLD": config.LBPH_THRESHOLD,
        "DLIB_DISTANCE": config.DLIB_DISTANCE,
        "MIN_CONFIDENCE_PCT": config.MIN_CONFIDENCE_PCT,
        "CONFIRM_FRAMES_REQUIRED": config.CONFIRM_FRAMES_REQUIRED,
        "LIVENESS_THRESHOLD": config.LIVENESS_THRESHOLD,
        "LIVENESS_ON": config.LIVENESS_ON,
        "CAMERA_INDEX": config.CAMERA_INDEX,
    }


@router.post("/api/settings")
def api_save_settings(data: dict, user: dict = Depends(admin_required)):
    for key, cast in {
        "LBPH_THRESHOLD": float,
        "DLIB_DISTANCE": float,
        "MIN_CONFIDENCE_PCT": float,
        "CONFIRM_FRAMES_REQUIRED": int,
        "LIVENESS_THRESHOLD": float,
        "LIVENESS_ON": bool,
        "CAMERA_INDEX": int,
    }.items():
        if key in data:
            setattr(config, key, cast(data[key]))
    return {"status": "ok", "message": "Settings updated"}


@router.get("/api/override/log")
def api_override_log(limit: int = 200, _: dict = Depends(get_current_user)):
    return db.get_override_log(limit)


@router.get("/api/reports/critical")
def api_reports_critical(threshold: float = 75.0, days: int = 180, _: dict = Depends(get_current_user)):
    return db.get_low_attendance_students(threshold, days)


@router.get("/health")
def api_health():
    """Enterprise application health check."""
    return {"status": "ok"}


@router.get("/api/reports/analytics")
def api_reports_analytics(
    days: int = Query(default=30, ge=1, le=365),
    dept: str = Query(default=""),
    current_user: dict = Depends(get_current_user),
):
    """Aggregated department attendance report with year distributions and trends."""
    return _analytics_service.get_reports_analytics(current_user=current_user, days=days, dept=dept)

