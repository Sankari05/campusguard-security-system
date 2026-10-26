# app/models/__init__.py
"""SQLAlchemy ORM models - one class per database table."""

from app.models.audit_log import SecurityAuditLog
from app.models.duty_attendance import DutyAttendance
from app.models.emergency_alert import EmergencyAlert
from app.models.gate_log import GateLog
from app.models.handover_task import HandoverTask
from app.models.lost_found import FoundItem, LostItem
from app.models.maintenance import MaintenanceReport
from app.models.organization import IncidentReport, Organization, OrganizationGate, OrganizationShift
from app.models.out_pass import OutPass
from app.models.parcel_log import ParcelLog
from app.models.parking import ParkingSlot
from app.models.patrol import PatrolCheckpoint, PatrolLog
from app.models.revoked_token import RevokedToken
from app.models.shift_handover import ShiftHandover
from app.models.situation import SituationTelemetry
from app.models.student import Student
from app.models.user import User
from app.models.visitor_pass import VisitorPass
from app.models.zone_risk import ZoneMonitoring

__all__ = [
    "User",
    "Organization",
    "OrganizationGate",
    "OrganizationShift",
    "IncidentReport",
    "SecurityAuditLog",
    "RevokedToken",
    "Student",
    "GateLog",
    "VisitorPass",
    "OutPass",
    "ParcelLog",
    "EmergencyAlert",
    "ShiftHandover",
    "HandoverTask",
    "MaintenanceReport",
    "ParkingSlot",
    "PatrolCheckpoint",
    "PatrolLog",
    "LostItem",
    "FoundItem",
    "DutyAttendance",
    "ZoneMonitoring",
    "SituationTelemetry",
]
