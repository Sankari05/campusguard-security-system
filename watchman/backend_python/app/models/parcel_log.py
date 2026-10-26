# app/models/parcel_log.py  —  Replaces ParcelLog.java
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, String

from app.db.base import Base


class ParcelLog(Base):
    """Gate parcel / delivery tracking."""

    __tablename__ = "parcel_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    courier_company = Column(String(50), nullable=False)  # AMAZON|FLIPKART|BLUEDART
    tracking_number = Column(String(100))
    recipient_name = Column(String(100), nullable=False)
    department_or_hostel = Column(String(100), nullable=False)
    recipient_phone = Column(String(20))
    received_at = Column(DateTime, default=datetime.utcnow)
    picked_up_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="WAITING_COLLECTION")  # WAITING_COLLECTION|DELIVERED
    handover_otp = Column(String(6))
    received_by_watchman = Column(String(100))

    def __repr__(self) -> str:
        return f"<ParcelLog id={self.id} recipient={self.recipient_name!r} status={self.status!r}>"
