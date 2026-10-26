# app/schemas/lost_found.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LostItemCreate(BaseModel):
    item_name: str
    category: str
    description: str
    lost_location: str
    reported_by_name: str
    contact_phone: str


class FoundItemCreate(BaseModel):
    item_name: str
    category: str
    description: str
    photo_url: str | None = None
    found_location: str
    stored_at: str = "Main Gate Security Locker"


class ClaimItemRequest(BaseModel):
    claimed_by_name: str
    claimed_by_phone: str


class LostItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_name: str
    category: str
    description: str
    lost_location: str
    date_lost: datetime
    reported_by_name: str
    contact_phone: str
    status: str


class FoundItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_code: str
    item_name: str
    category: str
    description: str
    photo_url: str | None
    found_location: str
    found_at: datetime
    stored_at: str
    status: str
    claimed_by_name: str | None
    claimed_by_phone: str | None
    returned_at: datetime | None


class MatchSuggestion(BaseModel):
    lost_id: int
    found_id: int
    item_name: str
    category: str
    confidence_score: float  # e.g., 0.95
    suggested_action: str
