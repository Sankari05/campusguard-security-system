# app/api/v1/endpoints/emergency.py
from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.emergency import EmergencyAlertCreateRequest, EmergencyAlertResponse
from app.services.emergency_service import EmergencyService

router = APIRouter(prefix="/emergency", tags=["Emergency & SOS Alerts"])


@router.post("", response_model=EmergencyAlertResponse)
@router.post("/alert", response_model=EmergencyAlertResponse)
@router.post("/trigger", response_model=EmergencyAlertResponse)
def trigger_alert(payload: dict = Body(...), db: Session = Depends(get_db)) -> Any:
    req = EmergencyAlertCreateRequest(
        alert_type=payload.get("alert_type")
        or payload.get("alertType")
        or payload.get("type")
        or "GATE_EMERGENCY",
        location=payload.get("location") or "Main Gate",
        description=payload.get("description") or payload.get("reason"),
        reported_by=payload.get("reported_by") or payload.get("reportedBy") or "Security Guard",
    )
    service = EmergencyService(db)
    return service.trigger_alert(req)


@router.post("/{alert_id}/resolve", response_model=EmergencyAlertResponse)
@router.put("/{alert_id}/resolve", response_model=EmergencyAlertResponse)
def resolve_alert(alert_id: int, db: Session = Depends(get_db)) -> Any:
    service = EmergencyService(db)
    return service.resolve_alert(alert_id)


@router.get("/active", response_model=list[EmergencyAlertResponse])
def get_active(db: Session = Depends(get_db)) -> Any:
    service = EmergencyService(db)
    return service.get_active()


@router.get("", response_model=list[EmergencyAlertResponse])
@router.get("/list", response_model=list[EmergencyAlertResponse])
def get_all(db: Session = Depends(get_db)) -> Any:
    service = EmergencyService(db)
    return service.get_all()
