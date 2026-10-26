# app/api/v1/endpoints/maintenance.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.maintenance import MaintenanceCreate, MaintenanceResponse, MaintenanceUpdateStatus
from app.services.maintenance_service import MaintenanceService

router = APIRouter()


@router.get("/", response_model=list[MaintenanceResponse])
def get_maintenance_reports(status: str | None = None, db: Session = Depends(get_db)):
    service = MaintenanceService(db)
    return service.get_all(status=status)


@router.post("/", response_model=MaintenanceResponse, status_code=status.HTTP_201_CREATED)
def create_maintenance_report(data: MaintenanceCreate, db: Session = Depends(get_db)):
    service = MaintenanceService(db)
    return service.create_report(data)


@router.patch("/{report_id}/status", response_model=MaintenanceResponse)
def update_maintenance_status(report_id: int, data: MaintenanceUpdateStatus, db: Session = Depends(get_db)):
    service = MaintenanceService(db)
    updated = service.update_status(report_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Maintenance ticket not found")
    return updated
