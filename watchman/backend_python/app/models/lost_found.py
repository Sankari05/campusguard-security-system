# =============================================================
# app/models/lost_found.py
# Purpose: Smart Lost and Found System Model (Pillar 9)
# =============================================================

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LostItem(Base):
    __tablename__ = "lost_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    item_name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))  # ELECTRONICS, BOOKS, ID_CARD, WALLET, ACCESSORY, OTHER
    description: Mapped[str] = mapped_column(Text)
    lost_location: Mapped[str] = mapped_column(String(100))
    date_lost: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reported_by_name: Mapped[str] = mapped_column(String(100))
    contact_phone: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="LOST")  # LOST, FOUND_MATCHED, CLAIMED


class FoundItem(Base):
    __tablename__ = "found_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    item_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    item_name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    found_location: Mapped[str] = mapped_column(String(100))
    found_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    stored_at: Mapped[str] = mapped_column(String(100), default="Main Gate Security Kiosk Locker")
    status: Mapped[str] = mapped_column(String(30), default="UNCLAIMED")  # UNCLAIMED, CLAIM_REQUESTED, RETURNED
    claimed_by_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    claimed_by_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
