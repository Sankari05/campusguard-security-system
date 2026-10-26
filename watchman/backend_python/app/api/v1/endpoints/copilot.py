# app/api/v1/endpoints/copilot.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.copilot import (
    CarryForwardResponse,
    GateCongestionAnalytics,
    PatternAlert,
    PrioritizedQueueResponse,
    SectorProfile,
    SituationCreate,
    SituationResponse,
    VoiceIncidentRequest,
    VoiceIncidentResponse,
)
from app.services.copilot_service import CopilotService

router = APIRouter()


@router.post("/situation", response_model=SituationResponse, status_code=status.HTTP_201_CREATED)
def record_situation_card(data: SituationCreate, db: Session = Depends(get_db)):
    service = CopilotService(db)
    return service.record_situation(data)


@router.get("/situation/patterns", response_model=list[PatternAlert])
def get_situation_pattern_alerts(db: Session = Depends(get_db)):
    service = CopilotService(db)
    return service.get_active_pattern_alerts()


@router.get("/situation/latest", response_model=list[SituationResponse])
def get_latest_situations(limit: int = 15, db: Session = Depends(get_db)):
    service = CopilotService(db)
    return service.get_latest_situations(limit=limit)


@router.post("/voice-incident", response_model=VoiceIncidentResponse, status_code=status.HTTP_201_CREATED)
def parse_voice_incident(data: VoiceIncidentRequest, db: Session = Depends(get_db)):
    service = CopilotService(db)
    return service.parse_voice_incident(data)


@router.get("/tasks/prioritized", response_model=PrioritizedQueueResponse)
def get_prioritized_tasks(db: Session = Depends(get_db)):
    service = CopilotService(db)
    return service.get_prioritized_task_queue()


@router.get("/carry-forward", response_model=CarryForwardResponse)
def get_carry_forward_tasks(db: Session = Depends(get_db)):
    service = CopilotService(db)
    return service.get_carry_forward_tasks()


@router.get("/sectors", response_model=list[SectorProfile])
def get_sector_profiles(db: Session = Depends(get_db)):
    service = CopilotService(db)
    return service.get_sector_profiles()


@router.get("/analytics/congestion", response_model=GateCongestionAnalytics)
def get_gate_congestion_analytics(db: Session = Depends(get_db)):
    service = CopilotService(db)
    return service.get_gate_congestion_analytics()

