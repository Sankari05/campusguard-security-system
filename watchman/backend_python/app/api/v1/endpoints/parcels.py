# app/api/v1/endpoints/parcels.py
from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.parcel import ParcelCreateRequest, ParcelResponse
from app.services.parcel_service import ParcelService

router = APIRouter(prefix="/parcels", tags=["Parcels & Courier Desk"])


@router.post("", response_model=ParcelResponse)
@router.post("/create", response_model=ParcelResponse)
@router.post("/receive", response_model=ParcelResponse)
def create_parcel(payload: dict = Body(...), db: Session = Depends(get_db)) -> Any:
    req = ParcelCreateRequest(
        courier_company=payload.get("courier_company")
        or payload.get("courierCompany")
        or "COURIER",
        tracking_number=payload.get("tracking_number") or payload.get("trackingNumber"),
        recipient_name=payload.get("recipient_name")
        or payload.get("recipientName")
        or "Student / Faculty",
        department_or_hostel=payload.get("department_or_hostel")
        or payload.get("departmentOrHostel")
        or "Hostel",
        recipient_phone=payload.get("recipient_phone") or payload.get("recipientPhone"),
        received_by_watchman=payload.get("received_by_watchman")
        or payload.get("receivedByWatchman"),
    )
    service = ParcelService(db)
    return service.register_parcel(req)


@router.post("/{parcel_id}/pickup", response_model=ParcelResponse)
@router.post("/{parcel_id}/handover", response_model=ParcelResponse)
@router.put("/{parcel_id}/handover", response_model=ParcelResponse)
def pickup_parcel(
    parcel_id: int, payload: dict = Body(default={}), db: Session = Depends(get_db)
) -> Any:
    otp = str(payload.get("otp") or payload.get("handoverOtp") or "").strip()
    service = ParcelService(db)
    return service.deliver_parcel(parcel_id, otp)


@router.get("/pending", response_model=list[ParcelResponse])
def get_pending(db: Session = Depends(get_db)) -> Any:
    service = ParcelService(db)
    return service.get_pending()


@router.get("", response_model=list[ParcelResponse])
@router.get("/list", response_model=list[ParcelResponse])
def get_all(db: Session = Depends(get_db)) -> Any:
    service = ParcelService(db)
    return service.get_all()
