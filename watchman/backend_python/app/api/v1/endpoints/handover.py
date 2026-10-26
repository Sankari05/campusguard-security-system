# app/api/v1/endpoints/handover.py
from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.handover import (
    AcknowledgeHandoverRequest,
    HandoverTaskInput,
    HandoverTaskResponse,
    ShiftHandoverCreateRequest,
    ShiftHandoverResponse,
    SupervisorSignOffRequest,
    TaskStatusUpdateRequest,
)
from app.services.handover_service import HandoverService

router = APIRouter(prefix="/handovers", tags=["Shift Handover"])


@router.get("/current")
def get_current(db: Session = Depends(get_db)) -> Any:
    service = HandoverService(db)
    data = service.get_latest()
    return {
        "hasActiveHandover": True,
        "handover": data,
        "tasks": data.get("tasks", []),
    }


@router.get("/list")
def get_all(db: Session = Depends(get_db)) -> Any:
    service = HandoverService(db)
    handovers = service.handover_repo.get_all(limit=100)
    return [ShiftHandoverResponse.model_validate(h) for h in handovers]


@router.get("/unresolved-tasks", response_model=list[HandoverTaskResponse])
def get_unresolved_tasks(db: Session = Depends(get_db)) -> Any:
    service = HandoverService(db)
    return service.get_open_tasks()


@router.post("/create")
def create_handover(payload: dict = Body(...), db: Session = Depends(get_db)) -> Any:
    tasks_raw = payload.get("tasks") or []
    tasks = []
    for t in tasks_raw:
        tasks.append(
            HandoverTaskInput(
                task_code=t.get("taskCode") or t.get("task_code"),
                category=t.get("category") or "EQUIPMENT",
                title=t.get("title") or "Task",
                description=t.get("description") or "",
                source_reference_id=t.get("sourceReferenceId")
                or t.get("source_reference_id")
                or "",
                status=t.get("status") or "OPEN",
                priority=t.get("priority") or "MEDIUM",
                next_required_action=t.get("nextRequiredAction")
                or t.get("next_required_action")
                or "",
            )
        )

    req = ShiftHandoverCreateRequest(
        shift_name=payload.get("shiftName") or payload.get("shift_name") or "Morning Shift",
        outgoing_watchman_id=payload.get("outgoingWatchmanId")
        or payload.get("outgoing_watchman_id")
        or "WM-01",
        outgoing_watchman_name=payload.get("outgoingWatchmanName")
        or payload.get("outgoing_watchman_name")
        or "Ramasamy",
        incoming_watchman_id=payload.get("incomingWatchmanId")
        or payload.get("incoming_watchman_id")
        or "WM-02",
        incoming_watchman_name=payload.get("incomingWatchmanName")
        or payload.get("incoming_watchman_name")
        or "Murugan",
        handover_notes=payload.get("handoverNotes") or payload.get("handover_notes") or "",
        tasks=tasks,
    )
    service = HandoverService(db)
    res = service.create_handover(req)
    return {
        "success": True,
        "message": "Shift Handover created successfully. Awaiting acknowledgement.",
        "handover": res,
    }


@router.post("/{handover_id_or_code}/acknowledge")
def acknowledge(
    handover_id_or_code: str, payload: dict = Body(default={}), db: Session = Depends(get_db)
) -> Any:
    service = HandoverService(db)
    if handover_id_or_code.isdigit():
        ho_obj = service.handover_repo.get_by_id(int(handover_id_or_code))
        code = ho_obj.handover_code if ho_obj else handover_id_or_code
    else:
        code = handover_id_or_code

    req = AcknowledgeHandoverRequest(
        watchman_id=payload.get("watchmanId") or payload.get("watchman_id") or "WM-02",
        watchman_name=payload.get("watchmanName")
        or payload.get("watchman_name")
        or "Murugan (Gate Guard - Shift B)",
    )
    res = service.acknowledge_handover(code, req)
    return {
        "success": True,
        "message": "Handover acknowledged! Shift transfer complete. All unresolved tasks remain active.",
        "handover": res,
    }


@router.put("/tasks/{task_code}/status")
def update_task_status(
    task_code: str, payload: dict = Body(default={}), db: Session = Depends(get_db)
) -> Any:
    service = HandoverService(db)
    req = TaskStatusUpdateRequest(
        status=payload.get("status") or "RESOLVED",
        resolved_by=payload.get("resolvedBy") or payload.get("resolved_by") or "Guard on Duty",
        notes=payload.get("notes") or payload.get("resolutionNotes") or "Task resolved.",
    )
    task = service.update_task_status(task_code, req)
    return {
        "success": True,
        "task": task,
    }


@router.post("/{handover_id_or_code}/supervisor-signoff")
def supervisor_signoff(
    handover_id_or_code: str, payload: dict = Body(default={}), db: Session = Depends(get_db)
) -> Any:
    service = HandoverService(db)
    if handover_id_or_code.isdigit():
        ho_obj = service.handover_repo.get_by_id(int(handover_id_or_code))
        code = ho_obj.handover_code if ho_obj else handover_id_or_code
    else:
        code = handover_id_or_code

    req = SupervisorSignOffRequest(
        supervisor_name=payload.get("supervisorName")
        or payload.get("supervisor_name")
        or "Dr. Sundaram (Chief Security Officer)",
        supervisor_notes=payload.get("supervisorNotes")
        or payload.get("supervisor_notes")
        or "Shift handover verified and approved.",
    )
    res = service.supervisor_signoff(code, req)
    return {
        "success": True,
        "message": "Supervisor sign-off recorded.",
        "handover": res,
    }
