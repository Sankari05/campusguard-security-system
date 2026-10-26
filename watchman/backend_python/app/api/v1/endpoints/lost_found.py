# app/api/v1/endpoints/lost_found.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.lost_found import (
    ClaimItemRequest,
    FoundItemCreate,
    FoundItemResponse,
    LostItemCreate,
    LostItemResponse,
    MatchSuggestion,
)
from app.services.lost_found_service import LostFoundService

router = APIRouter()


@router.get("/lost", response_model=list[LostItemResponse])
def get_lost_items(status: str | None = None, db: Session = Depends(get_db)):
    service = LostFoundService(db)
    return service.get_lost_items(status=status)


@router.get("/found", response_model=list[FoundItemResponse])
def get_found_items(status: str | None = None, db: Session = Depends(get_db)):
    service = LostFoundService(db)
    return service.get_found_items(status=status)


@router.post("/lost", response_model=LostItemResponse, status_code=status.HTTP_201_CREATED)
def report_lost_item(data: LostItemCreate, db: Session = Depends(get_db)):
    service = LostFoundService(db)
    return service.report_lost(data)


@router.post("/found", response_model=FoundItemResponse, status_code=status.HTTP_201_CREATED)
def register_found_item(data: FoundItemCreate, db: Session = Depends(get_db)):
    service = LostFoundService(db)
    return service.register_found(data)


@router.post("/found/{found_id}/claim", response_model=FoundItemResponse)
def claim_found_item(found_id: int, data: ClaimItemRequest, db: Session = Depends(get_db)):
    service = LostFoundService(db)
    claimed = service.claim_item(found_id, data)
    if not claimed:
        raise HTTPException(status_code=404, detail="Found item record not found")
    return claimed


@router.get("/matches", response_model=list[MatchSuggestion])
def get_smart_item_matches(db: Session = Depends(get_db)):
    service = LostFoundService(db)
    return service.get_smart_matches()
