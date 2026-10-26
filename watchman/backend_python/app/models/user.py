# app/models/user.py  —  Replaces User.java
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String

from app.db.base import Base


class User(Base):
    """System users: WATCHMAN, ADMIN, FACULTY, STUDENT with RBAC and Gate Scoping."""

    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone_number = Column(String(20))
    role = Column(String(30), nullable=False)  # WATCHMAN|ADMIN|FACULTY|STUDENT
    department = Column(String(50))
    organization_id = Column(BigInteger, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    assigned_gate = Column(String(50), default="Main Gate 1", nullable=True)
    assigned_shift = Column(String(50), default="Morning Shift", nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role!r} gate={self.assigned_gate!r}>"
