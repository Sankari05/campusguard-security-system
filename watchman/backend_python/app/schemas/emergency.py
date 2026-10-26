# app/schemas/emergency.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EmergencyAlertCreateRequest(BaseModel):
    alert_type: str  # UNAUTHORIZED_ENTRY|MEDICAL_EMERGENCY|FIRE|STUDENT_ALTERCATION
    location: str
    description: Optional[str] = None
    reported_by: str


class EmergencyAlertResponse(BaseModel):
    id: int
    alert_type: str
    location: str
    description: Optional[str]
    reported_by: str
    timestamp: datetime
    status: str

    model_config = {"from_attributes": True}
