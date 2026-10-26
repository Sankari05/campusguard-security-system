# =============================================================
# app/models/zone_risk.py
# Purpose: Smart Campus Zone Monitoring & Risk Alert Model (Pillars 8 & 11)
# =============================================================

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ZoneMonitoring(Base):
    __tablename__ = "zone_monitorings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    zone_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # ZONE_PARKING, ZONE_LABS, ZONE_HOSTEL, ZONE_GATE
    zone_name: Mapped[str] = mapped_column(String(100))
    risk_level: Mapped[str] = mapped_column(String(20), default="LOW")  # LOW, MODERATE, HIGH, CRITICAL
    repeated_complaints_count: Mapped[int] = mapped_column(Integer, default=0)
    attention_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    recommendation: Mapped[str] = mapped_column(Text)
    weather_hazard: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Heavy Rain Risk, High Wind, Normal
    last_inspected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
