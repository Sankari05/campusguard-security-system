# app/schemas/patrol.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CheckpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    checkpoint_code: str
    name: str
    zone: str
    location_description: str
    qr_token: str
    order_seq: int
    scheduled_interval_minutes: int
    is_active: bool


class PatrolScanRequest(BaseModel):
    qr_token: str
    guard_id: str
    guard_name: str
    remarks: str | None = None


class PatrolLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    checkpoint_id: int
    checkpoint_code: str
    checkpoint_name: str
    guard_id: str
    guard_name: str
    scanned_at: datetime
    status: str
    remarks: str | None


class PatrolStatusResponse(BaseModel):
    total_checkpoints: int
    completed_today: int
    missed_count: int
    next_due_checkpoint: str | None
    next_due_time: str | None
