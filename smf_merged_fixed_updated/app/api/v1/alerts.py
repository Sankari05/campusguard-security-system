"""
app.api.v1.alerts
FastAPI router for low-attendance triggers, Gmail alerts, and diagnostics.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends
from app.services.alert_service import AlertService
from auth_utils import get_current_user, teacher_required, uname

router = APIRouter(prefix="/api/alerts", tags=["Attendance Alerts"])


@router.post("/send-mail")
def api_send_alert_mail(data: dict, user: dict = Depends(teacher_required)):
    """Send real-time HTML alert to student + parent (attendance < 75%)."""
    username = uname(user) if callable(uname) else user.get("sub", "teacher")
    return AlertService.send_single_alert(data, username)


@router.post("/auto-send")
def api_auto_send_alerts(user: dict = Depends(teacher_required)):
    """Auto-send real-time HTML alerts to all students with attendance < 75%."""
    username = uname(user) if callable(uname) else user.get("sub", "teacher")
    return AlertService.send_bulk_alerts(username)


@router.get("/test-gmail")
def api_test_gmail(user: dict = Depends(teacher_required)):
    """Test Gmail SMTP connection without sending email."""
    return AlertService.test_connection()


@router.get("/low-attendance")
def api_low_attendance(
    threshold: float = 75.0,
    days: int = 180,
    _: dict = Depends(get_current_user)
):
    """Return all students with attendance below threshold."""
    return AlertService.get_low_attendance(threshold, days)
