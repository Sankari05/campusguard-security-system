"""
app.services.alert_service
Service layer handling automated email notifications, Gmail SMTP verification, and low-attendance triggers.
"""

from typing import Dict, Any, List
from fastapi import HTTPException
import database as db
from app.core.logger import get_logger

log = get_logger("alert_service")


class AlertService:
    """Enterprise service for attendance notification alerts and SMTP diagnostics."""

    @staticmethod
    def send_single_alert(data: dict, username: str) -> Dict[str, Any]:
        from email_alerts import send_low_attendance_alert

        student_id = data.get("student_id", "")
        pct = float(data.get("pct", 0))

        student = {
            "student_id": student_id,
            "name": data.get("name", "Student"),
            "roll_number": data.get("roll", ""),
            "dept": data.get("dept", ""),
            "section": data.get("section", ""),
            "attendance_percentage": pct,
            "student_email": data.get("student_email", ""),
            "parent_email": data.get("parent_email", ""),
        }

        result = send_low_attendance_alert(student)

        db.log_audit(
            username,
            "alert_mail_sent",
            student_id,
            f"pct={pct}% sent_to={','.join(result['sent_to']) or 'none'} errors={len(result['errors'])}",
            "",
        )

        return {
            "status": "sent" if result["sent"] else ("skipped" if not result["errors"] else "failed"),
            "sent_to": result["sent_to"],
            "errors": result["errors"],
            "message": result["message"],
        }

    @staticmethod
    def send_bulk_alerts(username: str) -> Dict[str, Any]:
        from email_alerts import send_bulk_alerts

        try:
            low_students = db.get_low_attendance_students(75.0, 30)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        summary = send_bulk_alerts(low_students)

        for r in summary["results"]:
            if r["status"] not in ("skipped",):
                db.log_audit(
                    username,
                    "auto_alert_sent",
                    r["student_id"],
                    f"pct={r['pct']}% sent_to={','.join(r['sent_to']) or 'none'} errors={len(r['errors'])}",
                    "",
                )

        return {
            "status": "done",
            "count": summary["total"],
            "emails_sent": summary["emails_sent"],
            "skipped": summary["skipped"],
            "failed": summary["failed"],
            "results": summary["results"],
            "message": summary["message"],
        }

    @staticmethod
    def test_connection() -> Dict[str, Any]:
        from email_alerts import test_gmail_connection
        return test_gmail_connection()

    @staticmethod
    def get_low_attendance(threshold: float = 75.0, days: int = 180) -> List[Dict[str, Any]]:
        try:
            return db.get_low_attendance_students(threshold, days)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
