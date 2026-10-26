# app/api/v1/endpoints/patrol.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.patrol import CheckpointResponse, PatrolLogResponse, PatrolScanRequest, PatrolStatusResponse
from app.services.patrol_service import PatrolService

router = APIRouter()


@router.get("/checkpoints", response_model=list[CheckpointResponse])
def get_patrol_checkpoints(db: Session = Depends(get_db)):
    service = PatrolService(db)
    return service.get_checkpoints()


@router.get("/logs", response_model=list[PatrolLogResponse])
def get_patrol_logs(limit: int = 50, db: Session = Depends(get_db)):
    service = PatrolService(db)
    return service.get_logs(limit=limit)


@router.get("/status", response_model=PatrolStatusResponse)
def get_patrol_status(db: Session = Depends(get_db)):
    service = PatrolService(db)
    return service.get_status_overview()


@router.post("/scan", response_model=PatrolLogResponse, status_code=status.HTTP_201_CREATED)
def scan_patrol_checkpoint(data: PatrolScanRequest, db: Session = Depends(get_db)):
    service = PatrolService(db)
    log = service.scan_checkpoint(data)
    if not log:
        raise HTTPException(status_code=400, detail="Invalid checkpoint QR token or code")
    return log
