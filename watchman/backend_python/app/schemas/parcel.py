# app/schemas/parcel.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ParcelCreateRequest(BaseModel):
    courier_company: str
    tracking_number: Optional[str] = None
    recipient_name: str
    department_or_hostel: str
    recipient_phone: Optional[str] = None
    received_by_watchman: Optional[str] = None


class ParcelResponse(BaseModel):
    id: int
    courier_company: str
    tracking_number: Optional[str]
    recipient_name: str
    department_or_hostel: str
    recipient_phone: Optional[str]
    status: str
    handover_otp: Optional[str]
    received_at: datetime
    picked_up_at: Optional[datetime]

    model_config = {"from_attributes": True}
