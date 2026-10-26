# =============================================================
# app/models/patrol.py
# Purpose: Smart Patrolling and Checkpoint Verification Model (Pillar 10)
# =============================================================

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PatrolCheckpoint(Base):
    __tablename__ = "patrol_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    checkpoint_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # e.g., CP-LIB, CP-LAB
    name: Mapped[str] = mapped_column(String(100))
    zone: Mapped[str] = mapped_column(String(50))
    location_description: Mapped[str] = mapped_column(String(200))
    qr_token: Mapped[str] = mapped_column(String(100), unique=True)
    order_seq: Mapped[int] = mapped_column(Integer, default=1)
    scheduled_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PatrolLog(Base):
    __tablename__ = "patrol_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    checkpoint_id: Mapped[int] = mapped_column(Integer, ForeignKey("patrol_checkpoints.id"), nullable=False)
    checkpoint_code: Mapped[str] = mapped_column(String(30))
    checkpoint_name: Mapped[str] = mapped_column(String(100))
    guard_id: Mapped[str] = mapped_column(String(50))
    guard_name: Mapped[str] = mapped_column(String(100))
    scanned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(30), default="COMPLETED")  # COMPLETED, MISSED, DELAYED
    remarks: Mapped[str | None] = mapped_column(String(255), nullable=True)
