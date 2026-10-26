# app/models/visitor_pass.py  —  Replaces VisitorPass.java
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, String

from app.db.base import Base


class VisitorPass(Base):
    """QR-code based digital gate pass with OTP verification."""

    __tablename__ = "visitor_passes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    visitor_type = Column(String(30), default="STUDENT")  # STUDENT|STAFF|PARENT|OTHERS
    visitor_name = Column(String(100), nullable=False)
    identifier = Column(String(50))  # Roll Number / Staff ID
    phone_number = Column(String(20))
    department = Column(String(100))
    reason = Column(String(255))
    additional_details = Column(String(255))
    person_to_meet = Column(String(100))
    pass_number = Column(String(40), unique=True, nullable=False)
    otp = Column(String(10))  # 6-digit OTP
    created_at = Column(DateTime, default=datetime.utcnow)
    otp_expires_at = Column(DateTime, nullable=True)
    otp_verified_at = Column(DateTime, nullable=True)
    check_in_time = Column(DateTime, nullable=True)
    check_out_time = Column(DateTime, nullable=True)
    status = Column(String(30), default="PENDING_OTP")  # PENDING_OTP|APPROVED|CHECKED_OUT|EXPIRED
    verified_by_watchman_id = Column(String(50))
    verified_by_watchman_name = Column(String(100))
    badge_number = Column(String(20))
    vehicle_number = Column(String(20))

    def __repr__(self) -> str:
        return f"<VisitorPass pass={self.pass_number!r} status={self.status!r}>"
