# app/models/revoked_token.py
from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, String

from app.db.base import Base


class RevokedToken(Base):
    """
    Server-side Token Revocation Blocklist.
    Stores revoked JWT tokens (by their unique jti identifier) upon logout
    or administrative session termination.
    """

    __tablename__ = "revoked_tokens"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    jti = Column(String(100), unique=True, index=True, nullable=False)
    token = Column(String(500), nullable=True)
    user_id = Column(BigInteger, nullable=True)
    username = Column(String(50), nullable=True)
    revoked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<RevokedToken jti={self.jti!r} username={self.username!r}>"
