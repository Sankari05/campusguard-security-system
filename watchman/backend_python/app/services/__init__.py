# app/services/__init__.py
"""
Business Logic Layer (Service Pattern).
Controllers/Routers call Services, Services call Repositories.
Decouples business rules from HTTP framework (FastAPI).
Pattern used by: Amazon, Qualcomm, Microsoft enterprise architectures.
"""

from app.services.auth_service import AuthService
from app.services.emergency_service import EmergencyService
from app.services.gate_service import GateService
from app.services.handover_service import HandoverService
from app.services.parcel_service import ParcelService
from app.services.student_service import StudentService
from app.services.visitor_service import VisitorService

__all__ = [
    "AuthService",
    "GateService",
    "StudentService",
    "VisitorService",
    "ParcelService",
    "EmergencyService",
    "HandoverService",
]
