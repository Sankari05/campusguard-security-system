"""
app/repositories/override_repository.py
Repository for attendance override logs, audit trail, and hierarchical permissions.
"""

from typing import Any, Dict, List, Optional, Tuple
from app.repositories.base import BaseRepository

try:
    import database_override as ov_db
except ImportError:
    ov_db = None


class OverrideRepository(BaseRepository):
    """Encapsulates all database operations for Attendance Overrides."""

    def get_override_history(self, limit: int = 200, dept: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch latest attendance override audit records."""
        if ov_db and hasattr(ov_db, "get_attendance_overrides"):
            try:
                records = ov_db.get_attendance_overrides(limit=limit)
                if dept:
                    records = [r for r in records if (r.get("department") or "").upper() == dept.upper()]
                return records
            except Exception:
                pass

        query = "SELECT * FROM attendance_overrides ORDER BY timestamp DESC LIMIT ?"
        return self.fetch_all(query, (limit,))

    def get_override_stats(self) -> Dict[str, Any]:
        """Fetch total, approved, rejected, and role-wise breakdown of overrides."""
        if ov_db and hasattr(ov_db, "get_override_stats"):
            try:
                return ov_db.get_override_stats()
            except Exception:
                pass
        return {"total_overrides": 0, "faculty_overrides": 0, "incharge_overrides": 0, "admin_overrides": 0}

    def check_hierarchical_permission(self, actor_role: str, target_role: str) -> Tuple[bool, str, str]:
        """Check if actor is permitted to override target according to hierarchy."""
        if ov_db and hasattr(ov_db, "check_hierarchical_permission"):
            return ov_db.check_hierarchical_permission(actor_role, target_role)
        return True, "Authorized", target_role
