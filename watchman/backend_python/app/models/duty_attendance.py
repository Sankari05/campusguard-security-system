# =============================================================
# app/models/duty_attendance.py
# Purpose: Smart Duty Attendance and Work Log Model (Pillar 7)
# =============================================================

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DutyAttendance(Base):
    __tablename__ = "duty_attendances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    guard_id: Mapped[str] = mapped_column(String(50), index=True)
    guard_name: Mapped[str] = mapped_column(String(100))
    shift_name: Mapped[str] = mapped_column(String(50))  # Morning Shift (06:00 - 14:00), Evening, Night
    gate_assigned: Mapped[str] = mapped_column(String(50), default="Main Campus Gate")
    clock_in: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    clock_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    total_patrols_done: Mapped[int] = mapped_column(Integer, default=0)
    total_incidents_handled: Mapped[int] = mapped_column(Integer, default=0)
    handover_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    supervisor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
