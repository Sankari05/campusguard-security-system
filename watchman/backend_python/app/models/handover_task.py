# app/models/handover_task.py  —  Replaces HandoverTask.java
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, String, Text

from app.db.base import Base


class HandoverTask(Base):
    """Individual tasks linked to a shift handover (for task continuity)."""

    __tablename__ = "handover_tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_code = Column(String(30), unique=True, nullable=False)
    handover_code = Column(String(30), nullable=False)  # FK → shift_handovers.handover_code
    category = Column(String(50))  # EQUIPMENT|VISITOR|PARCEL|INCIDENT
    title = Column(String(200))
    description = Column(Text)
    source_reference_id = Column(String(100))
    status = Column(String(30), default="OPEN")  # OPEN|IN_PROGRESS|RESOLVED
    priority = Column(String(20), default="MEDIUM")  # LOW|MEDIUM|HIGH|CRITICAL
    next_required_action = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated_at = Column(DateTime, default=datetime.utcnow)
    resolved_by = Column(String(100))
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text)

    def __repr__(self) -> str:
        return f"<HandoverTask code={self.task_code!r} status={self.status!r}>"
