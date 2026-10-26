# app/api/v1/endpoints/parking.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.parking import ParkingOccupy, ParkingResponse, ParkingSummary
from app.services.parking_service import ParkingService

router = APIRouter()


@router.get("/slots", response_model=list[ParkingResponse])
def get_parking_slots(zone: str | None = None, db: Session = Depends(get_db)):
    service = ParkingService(db)
    return service.get_all(zone=zone)


@router.get("/summary", response_model=ParkingSummary)
def get_parking_summary(db: Session = Depends(get_db)):
    service = ParkingService(db)
    return service.get_summary()


@router.post("/slots/{slot_id}/occupy", response_model=ParkingResponse)
def occupy_parking_slot(slot_id: int, data: ParkingOccupy, db: Session = Depends(get_db)):
    service = ParkingService(db)
    slot = service.occupy_slot(slot_id, data)
    if not slot:
        raise HTTPException(status_code=404, detail="Parking slot not found")
    return slot


@router.post("/slots/{slot_id}/vacate", response_model=ParkingResponse)
def vacate_parking_slot(slot_id: int, db: Session = Depends(get_db)):
    service = ParkingService(db)
    slot = service.vacate_slot(slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Parking slot not found")
    return slot
