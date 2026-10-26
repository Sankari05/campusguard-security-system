"""
app/services/override_service.py
Enterprise Service for attendance override verification and auditing.
"""

from typing import Any, Dict, List, Optional
from app.repositories.override_repository import OverrideRepository
from app.schemas.override import OverrideCreate, OverrideStatsResponse
from app.core.exceptions import ForbiddenError, ValidationError


class OverrideService:
    """Business logic layer for Attendance Overrides."""

    def __init__(self, repository: Optional[OverrideRepository] = None):
        self.repo = repository or OverrideRepository()

    def get_history(self, limit: int = 200, dept: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve audit log history."""
        return self.repo.get_override_history(limit=limit, dept=dept)

    def get_stats(self) -> OverrideStatsResponse:
        """Retrieve aggregate override statistics."""
        data = self.repo.get_override_stats()
        return OverrideStatsResponse(
            total_overrides=data.get("total_overrides", 0),
            faculty_overrides=data.get("faculty_overrides", 0),
            incharge_overrides=data.get("incharge_overrides", 0),
            admin_overrides=data.get("admin_overrides", 0),
        )

    def validate_and_check_permission(self, actor_role: str, target_role: str) -> None:
        """Validate hierarchical access rules."""
        allowed, msg, _ = self.repo.check_hierarchical_permission(actor_role, target_role)
        if not allowed:
            raise ForbiddenError(f"Hierarchical access violation: {msg}")
