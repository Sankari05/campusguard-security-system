# app/repositories/__init__.py
"""
Data Access Layer (Repository Pattern).
Each repository handles ONLY database queries for its own model.
No business logic here - that belongs in services/.
Pattern used by: Amazon, Google, Qualcomm enterprise backend services.
"""

from app.repositories.base_repository import BaseRepository
from app.repositories.emergency_repository import EmergencyRepository
from app.repositories.gate_repository import GateRepository
from app.repositories.handover_repository import (
    HandoverTaskRepository,
    ShiftHandoverRepository,
)
from app.repositories.out_pass_repository import OutPassRepository
from app.repositories.parcel_repository import ParcelRepository
from app.repositories.student_repository import StudentRepository
from app.repositories.user_repository import UserRepository
from app.repositories.visitor_repository import VisitorRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "StudentRepository",
    "GateRepository",
    "VisitorRepository",
    "ParcelRepository",
    "EmergencyRepository",
    "OutPassRepository",
    "ShiftHandoverRepository",
    "HandoverTaskRepository",
]
