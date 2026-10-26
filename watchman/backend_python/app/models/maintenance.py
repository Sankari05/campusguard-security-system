# =============================================================
# app/models/maintenance.py
# Purpose: Smart Maintenance Reporting Model (Pillar 3)
# =============================================================

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MaintenanceReport(Base):
    __tablename__ = "maintenance_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    ticket_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(50))  # ELECTRICAL, PLUMBING, GATE_BARRIER, CCTV, CIVIL, OTHER
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str] = mapped_column(String(100))  # Main Gate, North Gate, Parking B, Admin Block
    urgency: Mapped[str] = mapped_column(String(20), default="MEDIUM")  # LOW, MEDIUM, HIGH, EMERGENCY
    status: Mapped[str] = mapped_column(String(20), default="OPEN")  # OPEN, IN_PROGRESS, RESOLVED
    reported_by: Mapped[str] = mapped_column(String(100))
    assigned_to: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
