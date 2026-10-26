# app/models/organization.py
"""
GuardMate Multi-Tenant Organization, Gate, Shift & Incident Models.
Supports full multi-industry categorization: COLLEGE, HOSPITAL, APARTMENT, FACTORY, OFFICE.
"""

from datetime import datetime
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Organization(Base):
    """Registered Organization Tenant in GuardMate platform."""

    __tablename__ = "organizations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    slug = Column(String(80), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    org_type = Column(String(50), nullable=False)  # COLLEGE | HOSPITAL | APARTMENT | FACTORY | OFFICE
    contact_person = Column(String(100), nullable=False)
    contact_email = Column(String(120), nullable=False, index=True)
    contact_phone = Column(String(30), nullable=False)
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    gate_count = Column(Integer, default=1, nullable=False)
    expected_guards = Column(Integer, default=2, nullable=False)
    security_requirements = Column(Text, nullable=True)
    status = Column(String(30), default="PENDING_APPROVAL", nullable=False, index=True)  # PENDING_APPROVAL | APPROVED | REJECTED | SUSPENDED
    rejection_reason = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    gates = relationship("OrganizationGate", back_populates="organization", cascade="all, delete-orphan")
    shifts = relationship("OrganizationShift", back_populates="organization", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Organization id={self.id} slug={self.slug!r} type={self.org_type!r} status={self.status!r}>"


class OrganizationGate(Base):
    """Configured Gate / Entry Point for an Organization."""

    __tablename__ = "organization_gates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    gate_number = Column(String(50), nullable=False)  # e.g. "Gate 1", "Ambulance Bay", "North Cargo"
    gate_name = Column(String(100), nullable=False)   # e.g. "Main Campus Entrance", "Emergency Trauma Gate"
    gate_type = Column(String(50), default="MAIN", nullable=False)  # MAIN | VEHICLE | PEDESTRIAN | EMERGENCY | CARGO
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="gates")

    def __repr__(self) -> str:
        return f"<OrganizationGate id={self.id} org_id={self.organization_id} gate={self.gate_number!r}>"


class OrganizationShift(Base):
    """Security Duty Shift configured for an Organization."""

    __tablename__ = "organization_shifts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    shift_name = Column(String(80), nullable=False)  # e.g. "Morning Shift", "Evening Shift", "Night Shift"
    start_time = Column(String(10), nullable=False)  # e.g. "06:00"
    end_time = Column(String(10), nullable=False)    # e.g. "14:00"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="shifts")

    def __repr__(self) -> str:
        return f"<OrganizationShift id={self.id} org_id={self.organization_id} shift={self.shift_name!r}>"


class IncidentReport(Base):
    """Security Incident & Threat Record scoped to Organization."""

    __tablename__ = "security_incidents"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    reported_by_id = Column(BigInteger, nullable=True)
    reported_by_name = Column(String(100), nullable=True)
    gate_number = Column(String(50), nullable=True)
    incident_type = Column(String(60), nullable=False)  # TRESPASSING | FIGHT | THEFT | FIRE_SMOKE | MEDICAL_EMERGENCY | PROPERTY_DAMAGE | OTHER
    severity = Column(String(20), default="MEDIUM", nullable=False)  # LOW | MEDIUM | HIGH | CRITICAL
    description = Column(Text, nullable=False)
    action_taken = Column(Text, nullable=True)
    status = Column(String(30), default="OPEN", nullable=False)  # OPEN | INVESTIGATING | RESOLVED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<IncidentReport id={self.id} org_id={self.organization_id} type={self.incident_type!r} severity={self.severity!r}>"
