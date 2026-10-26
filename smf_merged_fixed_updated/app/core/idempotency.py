"""
app.core.idempotency
Enterprise Attendance Idempotency & Concurrency Shield.

Provides two-tier protection against duplicate attendance recordings:
1. Tier 1 (In-Memory Sliding TTL Debounce): Thread-safe cache absorbing camera frame bursts in <0.01ms.
2. Tier 2 (Atomic Database Constraint): SQLite UNIQUE(student_id, period, date) with INSERT OR IGNORE.
"""

import time
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import database as db

log = logging.getLogger(__name__)


class AttendanceIdempotencyGuard:
    """Thread-safe in-memory cache and atomic concurrency lock for attendance."""

    def __init__(self, ttl_seconds: int = 86400):
        self._cache: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds

    def _make_key(self, student_id: str, period: str, date: str) -> str:
        return f"{str(student_id).strip().upper()}:{str(period).strip().upper()}:{str(date).strip()}"

    def is_cached(self, student_id: str, period: str, date: str) -> bool:
        """Check if attendance is already recorded in the memory cache within TTL."""
        key = self._make_key(student_id, period, date)
        now = time.time()
        with self._lock:
            ts = self._cache.get(key)
            if ts and (now - ts) < self._ttl_seconds:
                return True
            elif ts:
                del self._cache[key]
        return False

    def mark_cache(self, student_id: str, period: str, date: str) -> None:
        """Record attendance key in thread-safe memory cache."""
        key = self._make_key(student_id, period, date)
        with self._lock:
            self._cache[key] = time.time()

    def clear(self) -> None:
        """Clear the in-memory cache (primarily for tests)."""
        with self._lock:
            self._cache.clear()

    def record_attendance(
        self,
        student_id: str,
        period: str,
        name: str = "",
        date_str: Optional[str] = None,
        confidence: float = 1.0,
        engine: str = "ArcFace",
        camera_id: str = "CAM1",
        liveness_score: float = 0.0,
        twin_verified: bool = False,
        skeleton_score: float = 0.0,
        department: str = "CSE",
        status: str = "Present"
    ) -> Dict[str, Any]:
        """
        Record attendance with full idempotency guarantee.
        If already marked for the period/date (either in memory or in DB), returns duplicate=True.
        Guarantees zero duplicate rows in the database.
        """
        target_date = date_str or datetime.now().strftime("%Y-%m-%d")
        now_time = datetime.now().strftime("%H:%M:%S")

        # ── Step 1: In-Memory Fast Path (<0.01ms) ──────────────────────────
        if self.is_cached(student_id, period, target_date):
            return {
                "status": "already_marked",
                "duplicate": True,
                "student_id": student_id,
                "period": period,
                "date": target_date,
                "message": "Attendance already recorded for this period (Memory Guard)"
            }

        # ── Step 2: Atomic DB Check & Write ────────────────────────────────
        result = db.mark_attendance_atomic(
            student_id=student_id,
            name=name,
            period=period,
            confidence=confidence,
            engine=engine,
            camera_id=camera_id,
            liveness_score=liveness_score,
            twin_verified=twin_verified,
            skeleton_score=skeleton_score,
            date_str=target_date,
            time_str=now_time,
            status=status,
            department=department
        )

        # ── Step 3: Populate Memory Cache ──────────────────────────────────
        self.mark_cache(student_id, period, target_date)
        return result


# Singleton global idempotency guard
attendance_guard = AttendanceIdempotencyGuard()
