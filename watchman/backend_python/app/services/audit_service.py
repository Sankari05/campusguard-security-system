# app/services/audit_service.py
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.audit_log import SecurityAuditLog


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log_event(
        self,
        event_type: str,
        username: Optional[str] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        gate_number: Optional[str] = None,
        status: str = "SUCCESS",
        details: Optional[str] = None,
    ) -> Optional[SecurityAuditLog]:
        """
        Record a security event into security_audit_logs table.
        Safe against rollbacks.
        """
        try:
            entry = SecurityAuditLog(
                timestamp=datetime.now(timezone.utc),
                event_type=event_type,
                username=username,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                gate_number=gate_number,
                status=status,
                details=details,
            )
            self.db.add(entry)
            self.db.commit()
            return entry
        except Exception:
            self.db.rollback()
            return None
