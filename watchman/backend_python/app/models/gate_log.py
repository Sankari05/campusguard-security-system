# app/models/gate_log.py  —  Replaces GateLog.java
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text

from app.db.base import Base


class GateLog(Base):
    """Live IN/OUT gate entries recorded by Watchman."""

    __tablename__ = "gate_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    person_type = Column(String(20), nullable=False)  # STUDENT|VISITOR|FACULTY|DELIVERY|VEHICLE
    identifier = Column(String(100), nullable=False)  # Roll Number / Phone / Vehicle Number
    person_name = Column(String(100), nullable=False)
    purpose = Column(String(255))
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    direction = Column(String(10), default="IN")  # IN | OUT
    gate_number = Column(String(20), default="Main Gate 1")
    watchman_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    status = Column(String(20), default="APPROVED")  # APPROVED|LATE_ENTRY|FLAGGED
    remarks = Column(Text)

    def __repr__(self) -> str:
        return f"<GateLog id={self.id} {self.person_type} {self.direction} at {self.entry_time}>"
