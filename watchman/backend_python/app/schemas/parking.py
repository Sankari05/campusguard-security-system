# app/schemas/parking.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ParkingOccupy(BaseModel):
    vehicle_number: str
    driver_name: str | None = None
    phone_number: str | None = None
    is_unauthorized: bool = False


class ParkingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slot_code: str
    zone: str
    slot_type: str
    is_occupied: bool
    vehicle_number: str | None
    driver_name: str | None
    phone_number: str | None
    is_unauthorized: bool
    parked_at: datetime | None
    last_updated: datetime


class ParkingSummary(BaseModel):
    total_slots: int
    occupied_slots: int
    available_slots: int
    unauthorized_count: int
