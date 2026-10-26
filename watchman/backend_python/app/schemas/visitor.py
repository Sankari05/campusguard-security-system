# app/schemas/visitor.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class VisitorSelfRegisterRequest(BaseModel):
    visitor_type: Optional[str] = "STUDENT"
    visitor_name: str
    identifier: Optional[str] = None
    phone_number: Optional[str] = None
    department: Optional[str] = None
    reason: Optional[str] = None
    additional_details: Optional[str] = None
    person_to_meet: Optional[str] = None
    badge_number: Optional[str] = None
    vehicle_number: Optional[str] = None

    @field_validator("visitor_name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Visitor name is mandatory.")
        return v.strip()


class OtpVerifyRequest(BaseModel):
    otp: str


class ConfirmEntryRequest(BaseModel):
    watchman_id: Optional[str] = "WM-01"
    watchman_name: Optional[str] = "Ramasamy (Main Gate Security)"
    badge_number: Optional[str] = None


class VisitorPassResponse(BaseModel):
    id: int
    visitor_type: str
    visitor_name: str
    identifier: Optional[str]
    phone_number: Optional[str]
    department: Optional[str]
    reason: Optional[str]
    pass_number: str
    otp: Optional[str]
    status: str
    otp_expires_at: Optional[datetime]
    check_in_time: Optional[datetime]
    check_out_time: Optional[datetime]
    verified_by_watchman_name: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
