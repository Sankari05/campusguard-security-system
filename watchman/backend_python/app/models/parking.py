# =============================================================
# app/models/parking.py
# Purpose: Smart Parking Management Model (Pillar 6)
# =============================================================

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ParkingSlot(Base):
    __tablename__ = "parking_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    slot_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # e.g., A-01, ST-12, V-03
    zone: Mapped[str] = mapped_column(String(30))  # ZONE_A, ZONE_B, STAFF, VISITOR
    slot_type: Mapped[str] = mapped_column(String(30), default="FOUR_WHEELER")  # FOUR_WHEELER, TWO_WHEELER, EV_CHARGING
    is_occupied: Mapped[bool] = mapped_column(Boolean, default=False)
    vehicle_number: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    driver_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_unauthorized: Mapped[bool] = mapped_column(Boolean, default=False)
    parked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
