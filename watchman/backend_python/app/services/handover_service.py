# app/services/handover_service.py
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.handover_task import HandoverTask
from app.models.shift_handover import ShiftHandover
from app.repositories.handover_repository import (
    HandoverTaskRepository,
    ShiftHandoverRepository,
)
from app.schemas.handover import (
    AcknowledgeHandoverRequest,
    HandoverTaskResponse,
    ShiftHandoverCreateRequest,
    ShiftHandoverResponse,
    SupervisorSignOffRequest,
    TaskStatusUpdateRequest,
)


class HandoverService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.handover_repo = ShiftHandoverRepository(db)
        self.task_repo = HandoverTaskRepository(db)

    def create_handover(self, req: ShiftHandoverCreateRequest) -> dict:
        handover_code = f"HO-{uuid.uuid4().hex[:8].upper()}"
        tasks_count = len(req.tasks) if req.tasks else 0

        handover = ShiftHandover(
            handover_code=handover_code,
            shift_name=req.shift_name,
            outgoing_watchman_id=req.outgoing_watchman_id,
            outgoing_watchman_name=req.outgoing_watchman_name,
            incoming_watchman_id=req.incoming_watchman_id,
            incoming_watchman_name=req.incoming_watchman_name,
            handover_time=datetime.utcnow(),
            handover_notes=req.handover_notes,
            status="PENDING_ACKNOWLEDGEMENT",
            total_pending_tasks=tasks_count,
            unresolved_tasks_count=tasks_count,
        )
        saved_ho = self.handover_repo.create(handover)

        created_tasks = []
        if req.tasks:
            for idx, t_input in enumerate(req.tasks, 1):
                t_code = t_input.task_code or f"{handover_code}-T{idx:02d}"
                task = HandoverTask(
                    task_code=t_code,
                    handover_code=handover_code,
                    category=t_input.category or "EQUIPMENT",
                    title=t_input.title,
                    description=t_input.description,
                    source_reference_id=t_input.source_reference_id,
                    status=t_input.status or "OPEN",
                    priority=t_input.priority or "MEDIUM",
                    next_required_action=t_input.next_required_action,
                    created_at=datetime.utcnow(),
                    last_updated_at=datetime.utcnow(),
                )
                saved_task = self.task_repo.create(task)
                created_tasks.append(HandoverTaskResponse.model_validate(saved_task))

        res = ShiftHandoverResponse.model_validate(saved_ho).model_dump()
        res["tasks"] = [t.model_dump() for t in created_tasks]
        return res

    def acknowledge_handover(
        self, handover_code: str, req: AcknowledgeHandoverRequest
    ) -> ShiftHandoverResponse:
        ho = self.handover_repo.find_by_code(handover_code)
        if not ho:
            raise NotFoundException("Shift handover", handover_code)

        ho.status = "ACKNOWLEDGED"
        ho.acknowledged_at = datetime.utcnow()
        ho.acknowledged_by_watchman_id = req.watchman_id
        ho.acknowledged_by_watchman_name = req.watchman_name
        updated = self.handover_repo.update(ho)
        return ShiftHandoverResponse.model_validate(updated)

    def update_task_status(
        self, task_code: str, req: TaskStatusUpdateRequest
    ) -> HandoverTaskResponse:
        task = self.task_repo.find_by_task_code(task_code)
        if not task:
            raise NotFoundException("Handover task", task_code)

        old_status = task.status
        task.status = req.status or "RESOLVED"
        task.last_updated_at = datetime.utcnow()
        if req.resolved_by:
            task.resolved_by = req.resolved_by
        if req.notes:
            task.resolution_notes = req.notes
        if task.status == "RESOLVED":
            task.resolved_at = datetime.utcnow()

        updated_task = self.task_repo.update(task)

        # Update unresolved count on parent handover
        if old_status != "RESOLVED" and task.status == "RESOLVED":
            ho = self.handover_repo.find_by_code(task.handover_code)
            if ho and ho.unresolved_tasks_count > 0:
                ho.unresolved_tasks_count -= 1
                self.handover_repo.update(ho)

        return HandoverTaskResponse.model_validate(updated_task)

    def supervisor_signoff(
        self, handover_code: str, req: SupervisorSignOffRequest
    ) -> ShiftHandoverResponse:
        ho = self.handover_repo.find_by_code(handover_code)
        if not ho:
            raise NotFoundException("Shift handover", handover_code)

        ho.status = "SUPERVISOR_REVIEWED"
        ho.supervisor_signed_by = req.supervisor_name
        ho.supervisor_signed_at = datetime.utcnow()
        ho.supervisor_notes = req.supervisor_notes
        updated = self.handover_repo.update(ho)
        return ShiftHandoverResponse.model_validate(updated)

    def get_by_code(self, handover_code: str) -> dict:
        ho = self.handover_repo.find_by_code(handover_code)
        if not ho:
            raise NotFoundException("Shift handover", handover_code)
        tasks = self.task_repo.find_by_handover_code(handover_code)
        res = ShiftHandoverResponse.model_validate(ho).model_dump()
        res["tasks"] = [HandoverTaskResponse.model_validate(t).model_dump() for t in tasks]
        return res

    def get_latest(self) -> dict:
        ho = self.handover_repo.find_latest()
        if not ho:
            # Seed a default initial handover record for UI demo
            sample_req = ShiftHandoverCreateRequest(
                shift_name="Morning Shift (06:00 AM - 02:00 PM)",
                outgoing_watchman_id="WM-01",
                outgoing_watchman_name="Ramasamy (Main Gate Security)",
                incoming_watchman_id="WM-02",
                incoming_watchman_name="Murugan (Gate Guard - Shift B)",
                handover_notes="All perimeter gates secure. Battery low on handheld metal detector.",
            )
            return self.create_handover(sample_req)

        tasks = self.task_repo.find_by_handover_code(ho.handover_code)
        res = ShiftHandoverResponse.model_validate(ho).model_dump()
        res["tasks"] = [HandoverTaskResponse.model_validate(t).model_dump() for t in tasks]
        return res

    def get_open_tasks(self) -> list[HandoverTaskResponse]:
        tasks = self.task_repo.find_open_tasks()
        return [HandoverTaskResponse.model_validate(t) for t in tasks]
