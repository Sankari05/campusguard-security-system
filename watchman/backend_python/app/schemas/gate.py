# app/schemas/gate.py  —  Replaces GateEntryRequest.java
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class GateEntryRequest(BaseModel):
    person_type: str  # STUDENT|VISITOR|FACULTY|DELIVERY|VEHICLE
    identifier: str
    person_name: str
    purpose: Optional[str] = None
    direction: Optional[str] = "IN"
    gate_number: Optional[str] = "Main Gate"
    remarks: Optional[str] = None


class GateLogResponse(BaseModel):
    id: int
    person_type: str
    identifier: str
    person_name: str
    purpose: Optional[str]
    entry_time: datetime
    exit_time: Optional[datetime]
    direction: str
    gate_number: Optional[str]
    status: str
    remarks: Optional[str]

    model_config = {"from_attributes": True}
