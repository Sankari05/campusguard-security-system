# app/schemas/maintenance.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MaintenanceCreate(BaseModel):
    category: str
    title: str
    description: str
    photo_url: str | None = None
    location: str
    urgency: str = "MEDIUM"
    reported_by: str = "Main Gate Watchman"


class MaintenanceUpdateStatus(BaseModel):
    status: str  # OPEN, IN_PROGRESS, RESOLVED
    assigned_to: str | None = None


class MaintenanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_number: str
    category: str
    title: str
    description: str
    photo_url: str | None
    location: str
    urgency: str
    status: str
    reported_by: str
    assigned_to: str | None
    created_at: datetime
    resolved_at: datetime | None
