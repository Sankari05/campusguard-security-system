# app/schemas/organization.py
"""
Pydantic Schemas for Multi-Tenant Organizations, Gates, Shifts, Guards, and Security Incidents.
"""

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class OrganizationRegisterRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=150, description="Organization name")
    org_type: str = Field(..., description="COLLEGE | HOSPITAL | APARTMENT | FACTORY | OFFICE")
    contact_person: str = Field(..., min_length=2, max_length=100)
    contact_email: str = Field(..., min_length=5, max_length=120)
    contact_phone: str = Field(..., min_length=7, max_length=30)
    address: Optional[str] = None
    city: Optional[str] = "Chennai"
    gate_count: int = Field(default=1, ge=1, le=50)
    expected_guards: int = Field(default=2, ge=1, le=200)
    security_requirements: Optional[str] = None


class OrganizationGateResponse(BaseModel):
    id: int
    gate_number: str
    gate_name: str
    gate_type: str
    is_active: bool

    class Config:
        from_attributes = True


class OrganizationShiftResponse(BaseModel):
    id: int
    shift_name: str
    start_time: str
    end_time: str
    is_active: bool

    class Config:
        from_attributes = True


class OrganizationResponse(BaseModel):
    id: int
    slug: str
    name: str
    org_type: str
    contact_person: str
    contact_email: str
    contact_phone: str
    address: Optional[str] = None
    city: Optional[str] = None
    gate_count: int
    expected_guards: int
    security_requirements: Optional[str] = None
    status: str
    rejection_reason: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    gates: List[OrganizationGateResponse] = []
    shifts: List[OrganizationShiftResponse] = []

    class Config:
        from_attributes = True


class OrganizationApproveRequest(BaseModel):
    admin_username: Optional[str] = None
    admin_password: Optional[str] = "pass123"


class OrganizationRejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=250)


class GateCreateRequest(BaseModel):
    gate_number: str = Field(..., min_length=1, max_length=50)
    gate_name: str = Field(..., min_length=2, max_length=100)
    gate_type: str = Field(default="MAIN", description="MAIN | VEHICLE | PEDESTRIAN | EMERGENCY | CARGO")


class ShiftCreateRequest(BaseModel):
    shift_name: str = Field(..., min_length=2, max_length=80)
    start_time: str = Field(..., description="e.g. 06:00")
    end_time: str = Field(..., description="e.g. 14:00")


class GuardCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=100)
    phone_number: str = Field(..., min_length=7, max_length=20)
    assigned_gate: str = Field(..., min_length=1, max_length=50)
    assigned_shift: str = Field(..., min_length=2, max_length=50)
    password: str = Field(default="pass123", min_length=6)


class GuardUserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    email: str
    phone_number: Optional[str]
    role: str
    organization_id: Optional[int]
    assigned_gate: Optional[str]
    assigned_shift: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class IncidentCreateRequest(BaseModel):
    incident_type: str = Field(..., description="TRESPASSING | FIGHT | THEFT | FIRE_SMOKE | MEDICAL_EMERGENCY | PROPERTY_DAMAGE | OTHER")
    severity: str = Field(default="MEDIUM", description="LOW | MEDIUM | HIGH | CRITICAL")
    gate_number: Optional[str] = None
    description: str = Field(..., min_length=5, max_length=1000)
    action_taken: Optional[str] = None


class IncidentResponse(BaseModel):
    id: int
    organization_id: Optional[int]
    reported_by_id: Optional[int]
    reported_by_name: Optional[str]
    gate_number: Optional[str]
    incident_type: str
    severity: str
    description: str
    action_taken: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
