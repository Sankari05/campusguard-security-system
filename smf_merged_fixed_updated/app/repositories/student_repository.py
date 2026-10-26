"""
app/repositories/student_repository.py
Repository for student records and attendance aggregations.
"""

from typing import Any, Dict, List, Optional
from app.repositories.base import BaseRepository
import database as legacy_db


class StudentRepository(BaseRepository):
    """Encapsulates all database operations for Students."""

    def get_all_students(self) -> List[Dict[str, Any]]:
        """Fetch all students from database."""
        query = "SELECT * FROM students ORDER BY name"
        rows = self.fetch_all(query)
        if rows:
            return rows
        # Fallback to legacy database method if schema has special fallbacks
        try:
            return [dict(r) for r in legacy_db.get_all_students()]
        except Exception:
            return []

    def get_student_by_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Fetch single student by ID."""
        query = "SELECT * FROM students WHERE student_id = ?"
        return self.fetch_one(query, (student_id,))

    def get_student_by_reg_no(self, reg_no: str) -> Optional[Dict[str, Any]]:
        """Fetch student by registration / roll number."""
        query = "SELECT * FROM students WHERE roll_number = ? OR reg_no = ?"
        return self.fetch_one(query, (reg_no, reg_no))

    def get_attendance_summary(self, days: int = 180) -> List[Dict[str, Any]]:
        """Fetch attendance summary for all students over the given day range."""
        try:
            return legacy_db.get_attendance_summary(days=days)
        except Exception:
            return []

    def get_dashboard_stats(self, role: str, dept: str = "") -> Dict[str, Any]:
        """Fetch student dashboard aggregates scoped by role and department."""
        try:
            return legacy_db.get_dashboard_stats_by_role(role, dept=dept)
        except Exception:
            return {"student_count": 0, "present_today": 0, "absent_today": 0}

    def get_low_attendance_students(self, threshold: float = 75.0, days: int = 180) -> List[Dict[str, Any]]:
        """Fetch students whose attendance falls below the given threshold."""
        try:
            return [dict(s) for s in legacy_db.get_low_attendance_students(threshold=threshold, days=days)]
        except Exception:
            return []
