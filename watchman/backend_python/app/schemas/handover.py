# app/schemas/handover.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class HandoverTaskInput(BaseModel):
    task_code: Optional[str] = None
    category: Optional[str] = "EQUIPMENT"
    title: str
    description: Optional[str] = ""
    source_reference_id: Optional[str] = ""
    status: Optional[str] = "OPEN"
    priority: Optional[str] = "MEDIUM"
    next_required_action: Optional[str] = ""


class HandoverTaskResponse(BaseModel):
    id: int
    task_code: str
    handover_code: str
    category: Optional[str]
    title: Optional[str]
    description: Optional[str]
    status: str
    priority: Optional[str]
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ShiftHandoverCreateRequest(BaseModel):
    shift_name: Optional[str] = "Morning Shift (06:00 AM - 02:00 PM)"
    outgoing_watchman_id: Optional[str] = "WM-01"
    outgoing_watchman_name: Optional[str] = "Ramasamy (Main Gate Security)"
    incoming_watchman_id: Optional[str] = "WM-02"
    incoming_watchman_name: Optional[str] = "Murugan (Gate Guard - Shift B)"
    handover_notes: Optional[str] = ""
    tasks: Optional[list[HandoverTaskInput]] = []


class ShiftHandoverResponse(BaseModel):
    id: int
    handover_code: str
    shift_name: Optional[str]
    gate_location: Optional[str]
    outgoing_watchman_id: Optional[str]
    outgoing_watchman_name: Optional[str]
    incoming_watchman_id: Optional[str]
    incoming_watchman_name: Optional[str]
    handover_time: datetime
    status: str
    total_pending_tasks: int
    unresolved_tasks_count: int
    acknowledged_at: Optional[datetime]
    supervisor_signed_by: Optional[str]

    model_config = {"from_attributes": True}


class AcknowledgeHandoverRequest(BaseModel):
    watchman_id: Optional[str] = "WM-02"
    watchman_name: Optional[str] = "Murugan (Gate Guard - Shift B)"


class TaskStatusUpdateRequest(BaseModel):
    status: Optional[str] = "RESOLVED"
    resolved_by: Optional[str] = "Guard on Duty"
    notes: Optional[str] = "Task resolved."


class SupervisorSignOffRequest(BaseModel):
    supervisor_name: Optional[str] = "Dr. Sundaram (Chief Security Officer)"
    supervisor_notes: Optional[str] = "Handover verified & approved."
