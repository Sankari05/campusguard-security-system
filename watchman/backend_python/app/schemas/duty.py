# app/schemas/duty.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClockInRequest(BaseModel):
    guard_id: str
    guard_name: str
    shift_name: str = "Morning Shift (06:00 AM - 02:00 PM)"
    gate_assigned: str = "Main Campus Gate"


class ClockOutRequest(BaseModel):
    guard_id: str
    supervisor_notes: str | None = None


class DutyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    guard_id: str
    guard_name: str
    shift_name: str
    gate_assigned: str
    clock_in: datetime
    clock_out: datetime | None
    is_active: bool
    total_patrols_done: int
    total_incidents_handled: int
    handover_completed: bool
    supervisor_notes: str | None
