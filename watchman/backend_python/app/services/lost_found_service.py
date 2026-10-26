# app/services/lost_found_service.py
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.lost_found import FoundItem, LostItem
from app.schemas.lost_found import ClaimItemRequest, FoundItemCreate, LostItemCreate, MatchSuggestion


class LostFoundService:
    def __init__(self, db: Session):
        self.db = db

    def get_lost_items(self, status: str | None = None) -> list[LostItem]:
        query = self.db.query(LostItem)
        if status:
            query = query.filter(LostItem.status == status.upper())
        return query.order_by(LostItem.date_lost.desc()).all()

    def get_found_items(self, status: str | None = None) -> list[FoundItem]:
        query = self.db.query(FoundItem)
        if status:
            query = query.filter(FoundItem.status == status.upper())
        return query.order_by(FoundItem.found_at.desc()).all()

    def report_lost(self, data: LostItemCreate) -> LostItem:
        lost = LostItem(
            item_name=data.item_name,
            category=data.category.upper(),
            description=data.description,
            lost_location=data.lost_location,
            date_lost=datetime.utcnow(),
            reported_by_name=data.reported_by_name,
            contact_phone=data.contact_phone,
            status="LOST"
        )
        self.db.add(lost)
        self.db.commit()
        self.db.refresh(lost)
        return lost

    def register_found(self, data: FoundItemCreate) -> FoundItem:
        code = f"FND-{uuid.uuid4().hex[:6].upper()}"
        found = FoundItem(
            item_code=code,
            item_name=data.item_name,
            category=data.category.upper(),
            description=data.description,
            photo_url=data.photo_url,
            found_location=data.found_location,
            found_at=datetime.utcnow(),
            stored_at=data.stored_at,
            status="UNCLAIMED"
        )
        self.db.add(found)
        self.db.commit()
        self.db.refresh(found)
        return found

    def claim_item(self, found_id: int, data: ClaimItemRequest) -> FoundItem | None:
        found = self.db.query(FoundItem).filter(FoundItem.id == found_id).first()
        if not found:
            return None
        found.status = "RETURNED"
        found.claimed_by_name = data.claimed_by_name
        found.claimed_by_phone = data.claimed_by_phone
        found.returned_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(found)
        return found

    def get_smart_matches(self) -> list[MatchSuggestion]:
        lost_items = self.db.query(LostItem).filter(LostItem.status == "LOST").all()
        found_items = self.db.query(FoundItem).filter(FoundItem.status == "UNCLAIMED").all()
        
        matches: list[MatchSuggestion] = []
        for lost in lost_items:
            for found in found_items:
                # Basic similarity algorithm: category match and title substring match
                is_cat_match = lost.category.upper() == found.category.upper()
                name_overlap = any(word.lower() in found.item_name.lower() for word in lost.item_name.split() if len(word) > 2)
                
                if is_cat_match and name_overlap:
                    matches.append(MatchSuggestion(
                        lost_id=lost.id,
                        found_id=found.id,
                        item_name=f"{lost.item_name} ≈ {found.item_name}",
                        category=lost.category,
                        confidence_score=0.92,
                        suggested_action=f"Contact {lost.reported_by_name} ({lost.contact_phone}) to inspect Locker Item #{found.item_code}"
                    ))
        return matches
