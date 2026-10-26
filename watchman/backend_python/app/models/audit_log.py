# app/models/audit_log.py
from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, String, Text

from app.db.base import Base


class SecurityAuditLog(Base):
    """
    Security Audit Event Log.
    Records all authentication events, lockout actions, access violations,
    and administrative privilege usage for SOC2/ISO27001 compliance.
    """

    __tablename__ = "security_audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    username = Column(String(50), nullable=True, index=True)
    user_id = Column(BigInteger, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    gate_number = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False)  # SUCCESS | FAILURE | BLOCKED | WARNING
    details = Column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<SecurityAuditLog id={self.id} event={self.event_type} user={self.username} status={self.status}>"
