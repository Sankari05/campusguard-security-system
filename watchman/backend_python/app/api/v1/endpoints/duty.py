# app/api/v1/endpoints/duty.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.duty import ClockInRequest, ClockOutRequest, DutyResponse
from app.services.duty_service import DutyService

router = APIRouter()


@router.post("/clock-in", response_model=DutyResponse, status_code=status.HTTP_201_CREATED)
def clock_in(data: ClockInRequest, db: Session = Depends(get_db)):
    service = DutyService(db)
    return service.clock_in(data)


@router.post("/clock-out", response_model=DutyResponse)
def clock_out(data: ClockOutRequest, db: Session = Depends(get_db)):
    service = DutyService(db)
    duty = service.clock_out(data)
    if not duty:
        raise HTTPException(status_code=400, detail="No active duty shift found to clock out")
    return duty


@router.get("/current/{guard_id}", response_model=DutyResponse | None)
def get_current_duty(guard_id: str, db: Session = Depends(get_db)):
    service = DutyService(db)
    return service.get_current_duty(guard_id)


@router.get("/history", response_model=list[DutyResponse])
def get_duty_history(limit: int = 30, db: Session = Depends(get_db)):
    service = DutyService(db)
    return service.get_duty_history(limit=limit)
