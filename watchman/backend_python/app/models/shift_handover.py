# app/models/shift_handover.py  —  Replaces ShiftHandover.java
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text

from app.db.base import Base


class ShiftHandover(Base):
    """Shift handover records between outgoing and incoming watchmen."""

    __tablename__ = "shift_handovers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    handover_code = Column(String(30), unique=True, nullable=False)
    shift_name = Column(String(100))
    gate_location = Column(String(100), default="Main Gate 1")
    outgoing_watchman_id = Column(String(50))
    outgoing_watchman_name = Column(String(100))
    incoming_watchman_id = Column(String(50))
    incoming_watchman_name = Column(String(100))
    handover_time = Column(DateTime, default=datetime.utcnow)
    handover_notes = Column(Text)
    status = Column(
        String(40), default="PENDING_ACKNOWLEDGEMENT"
    )  # PENDING_ACKNOWLEDGEMENT|ACKNOWLEDGED|SUPERVISOR_REVIEWED
    total_pending_tasks = Column(Integer, default=0)
    unresolved_tasks_count = Column(Integer, default=0)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by_watchman_id = Column(String(50))
    acknowledged_by_watchman_name = Column(String(100))
    supervisor_signed_by = Column(String(100))
    supervisor_signed_at = Column(DateTime, nullable=True)
    supervisor_notes = Column(Text)

    def __repr__(self) -> str:
        return f"<ShiftHandover code={self.handover_code!r} status={self.status!r}>"
