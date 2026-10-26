"""
app.repositories.enrollment_repository
Encapsulates all database operations for student/faculty enrollment OTP sessions.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.repositories.base import BaseRepository
import database as db


class EnrollmentRepository(BaseRepository):
    """Data repository for OTP verification and enrollment tracking."""

    def __init__(self):
        super().__init__()
        self._ensure_table()

    def _ensure_table(self):
        with db.db(write=True) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS enroll_otp_sessions (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    email        TEXT NOT NULL,
                    otp_hash     TEXT NOT NULL,
                    expires_at   TEXT NOT NULL,
                    attempts     INTEGER DEFAULT 0,
                    resend_count INTEGER DEFAULT 0,
                    is_verified  INTEGER DEFAULT 0,
                    created_at   TEXT DEFAULT (datetime('now','utc'))
                )
            """)

    def get_latest_session(self, email: str, is_verified: int = 0) -> Optional[Dict[str, Any]]:
        query = """
            SELECT * FROM enroll_otp_sessions
            WHERE email = ? AND is_verified = ?
            ORDER BY created_at DESC LIMIT 1
        """
        return self.fetch_one(query, (email.strip().lower(), is_verified))

    def create_session(self, email: str, otp_hash: str, expires_at: str, resend_count: int) -> int:
        norm_email = email.strip().lower()
        with db.db(write=True) as conn:
            conn.execute(
                "UPDATE enroll_otp_sessions SET is_verified = 2 WHERE email = ? AND is_verified = 0",
                (norm_email,)
            )
            cur = conn.execute(
                """INSERT INTO enroll_otp_sessions
                   (email, otp_hash, expires_at, resend_count)
                   VALUES (?, ?, ?, ?)""",
                (norm_email, otp_hash, expires_at, resend_count)
            )
            return cur.lastrowid

    def update_attempts(self, session_id: int, attempts: int):
        self.execute_write("UPDATE enroll_otp_sessions SET attempts = ? WHERE id = ?", (attempts, session_id))

    def lock_session(self, session_id: int):
        self.execute_write("UPDATE enroll_otp_sessions SET is_verified = 2 WHERE id = ?", (session_id,))

    def mark_session_verified(self, session_id: int):
        self.execute_write("UPDATE enroll_otp_sessions SET is_verified = 1 WHERE id = ?", (session_id,))

    def is_email_verified(self, email: str) -> bool:
        if not email:
            return False
        rec = self.fetch_one(
            """SELECT expires_at FROM enroll_otp_sessions
               WHERE email = ? AND is_verified = 1
               ORDER BY created_at DESC LIMIT 1""",
            (email.strip().lower(),)
        )
        if not rec:
            return False
        try:
            expires_at = datetime.fromisoformat(rec["expires_at"])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) < expires_at
        except Exception:
            return False
