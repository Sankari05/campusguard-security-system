# app/models/situation.py
# Purpose: Security Situation Card & Pattern Intelligence Model (Cognitive Co-Pilot)

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SituationTelemetry(Base):
    __tablename__ = "situation_telemetries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    location: Mapped[str] = mapped_column(String(100), index=True)  # e.g., North Parking Bay, Main Gate Ingress, Labs
    status: Mapped[str] = mapped_column(String(30))  # NORMAL, ATTENTION_NEEDED, SUSPICIOUS, EMERGENCY
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(100))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    pattern_alert_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
