# app/models/emergency_alert.py  —  Replaces EmergencyAlert.java
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, String, Text

from app.db.base import Base


class EmergencyAlert(Base):
    """SOS and emergency alert records."""

    __tablename__ = "emergency_alerts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    alert_type = Column(String(50), nullable=False)  # UNAUTHORIZED_ENTRY|MEDICAL_EMERGENCY|FIRE
    location = Column(String(100), nullable=False)
    description = Column(Text)
    reported_by = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="ACTIVE")  # ACTIVE|RESOLVED

    def __repr__(self) -> str:
        return f"<EmergencyAlert type={self.alert_type!r} status={self.status!r}>"
