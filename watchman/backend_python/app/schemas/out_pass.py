# app/schemas/out_pass.py  —  Replaces OutPassRequest.java
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OutPassCreateRequest(BaseModel):
    roll_number: str
    student_name: str
    department: str
    reason: str
    destination: Optional[str] = None
    out_time_expected: Optional[datetime] = None
    in_time_expected: Optional[datetime] = None


class OutPassResponse(BaseModel):
    id: int
    pass_code: str
    student_roll_number: Optional[str]
    student_name: Optional[str]
    department: Optional[str]
    reason: str
    destination: Optional[str]
    status: str
    approved_by: Optional[str]
    out_time_expected: Optional[datetime]
    in_time_expected: Optional[datetime]
    actual_out_time: Optional[datetime]
    actual_in_time: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
