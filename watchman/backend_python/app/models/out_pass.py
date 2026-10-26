# app/models/out_pass.py  —  Replaces OutPass.java
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, Text

from app.db.base import Base


class OutPass(Base):
    """Student out-pass with HOD approval workflow."""

    __tablename__ = "out_passes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    pass_code = Column(String(30), unique=True, nullable=False)
    student_id = Column(BigInteger, ForeignKey("students.id"), nullable=True)
    student_roll_number = Column(String(30))
    student_name = Column(String(100))
    department = Column(String(50))
    reason = Column(Text, nullable=False)
    destination = Column(String(150))
    out_time_expected = Column(DateTime)
    in_time_expected = Column(DateTime)
    status = Column(
        String(30), default="PENDING"
    )  # PENDING|APPROVED_BY_HOD|REJECTED|EXITED_GATE|COMPLETED
    approved_by = Column(String(100))
    parent_consent_verified = Column(Boolean, default=False)
    actual_out_time = Column(DateTime, nullable=True)
    actual_in_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<OutPass code={self.pass_code!r} status={self.status!r}>"
