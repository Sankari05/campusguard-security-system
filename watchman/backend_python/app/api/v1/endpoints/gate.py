# app/api/v1/endpoints/gate.py
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, validate_gate_scope
from app.db.session import get_db
from app.models.user import User
from app.schemas.gate import GateEntryRequest, GateLogResponse
from app.services.gate_service import GateService
from app.services.student_service import StudentService

router = APIRouter(prefix="/gate", tags=["Gate Operations"])


@router.get("/lookup-student/{roll_number}")
def lookup_student(
    roll_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Instant lookup and verification of student by roll number."""
    service = StudentService(db)
    return service.verify_student_by_roll(roll_number)


@router.post("/check-in", response_model=GateLogResponse)
def check_in(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Log an inward or outward gate passage.
    Enforces gate scope: Guards can only record entries for their assigned gate.
    """
    requested_gate = payload.get("gate_number") or payload.get("gateNumber") or current_user.assigned_gate or "Main Gate 1"
    effective_gate = validate_gate_scope(current_user, requested_gate)

    req = GateEntryRequest(
        person_type=payload.get("person_type")
        or payload.get("personType")
        or payload.get("category")
        or "STUDENT",
        identifier=payload.get("identifier")
        or payload.get("rollOrId")
        or payload.get("rollNumber")
        or "",
        person_name=payload.get("person_name")
        or payload.get("personName")
        or payload.get("name")
        or "Visitor",
        purpose=payload.get("purpose") or payload.get("reason"),
        direction=payload.get("direction") or "IN",
        gate_number=effective_gate,
        remarks=payload.get("remarks"),
    )
    service = GateService(db)
    return service.log_entry(req)


@router.post("/check-out/{log_id}", response_model=GateLogResponse)
def check_out(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    service = GateService(db)
    return service.log_exit(log_id)


@router.get("/recent", response_model=list[GateLogResponse])
@router.get("/recent-logs", response_model=list[GateLogResponse])
def get_recent(
    limit: int = 50,
    gate_number: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Retrieve recent gate logs.
    Guards are automatically filtered to their assigned gate.
    Admins can view all gates or filter by a specific gate.
    """
    scoped_gate = validate_gate_scope(current_user, gate_number)
    service = GateService(db)
    return service.get_recent_entries(limit=limit, gate_number=scoped_gate)


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    service = GateService(db)
    return service.get_stats()


@router.post("/anpr/recognize")
def recognize_anpr(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
) -> Any:
    """
    ANPR v2 Recognition Endpoint:
    Accepts image frame (base64 or data URI) and optional raw OCR text.
    Performs dynamic computer vision localization, MoRTH Indian plate validation,
    and returns gate barrier authorization decision.
    """
    from app.services.anpr_service import ANPRService
    image_data = payload.get("image") or payload.get("frame")
    ocr_text = payload.get("text") or payload.get("raw_text")
    return ANPRService.process_anpr_frame(image_data, raw_ocr_text=ocr_text)

