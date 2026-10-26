# app/models/student.py  —  Replaces Student.java
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String

from app.db.base import Base


class Student(Base):
    """Student master data used for gate verification and out-pass."""

    __tablename__ = "students"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    roll_number = Column(String(30), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    department = Column(String(50), nullable=False)
    year_of_study = Column(Integer)
    hostel_or_day_scholar = Column(String(20), nullable=False)  # HOSTEL | DAY_SCHOLAR
    room_or_bus_route = Column(String(50))
    parent_phone = Column(String(20), nullable=False)
    photo_url = Column(String(255))
    is_suspended = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Student roll={self.roll_number!r} name={self.name!r}>"
