# app/repositories/handover_repository.py
from typing import Optional

from sqlalchemy.orm import Session

from app.models.handover_task import HandoverTask
from app.models.shift_handover import ShiftHandover
from app.repositories.base_repository import BaseRepository


class ShiftHandoverRepository(BaseRepository[ShiftHandover]):
    def __init__(self, db: Session) -> None:
        super().__init__(ShiftHandover, db)

    def find_by_code(self, handover_code: str) -> Optional[ShiftHandover]:
        return (
            self.db.query(ShiftHandover)
            .filter(ShiftHandover.handover_code == handover_code)
            .first()
        )

    def find_latest(self) -> Optional[ShiftHandover]:
        return self.db.query(ShiftHandover).order_by(ShiftHandover.handover_time.desc()).first()


class HandoverTaskRepository(BaseRepository[HandoverTask]):
    def __init__(self, db: Session) -> None:
        super().__init__(HandoverTask, db)

    def find_by_handover_code(self, handover_code: str) -> list[HandoverTask]:
        return (
            self.db.query(HandoverTask)
            .filter(HandoverTask.handover_code == handover_code)
            .order_by(HandoverTask.created_at.asc())
            .all()
        )

    def find_by_task_code(self, task_code: str) -> Optional[HandoverTask]:
        return self.db.query(HandoverTask).filter(HandoverTask.task_code == task_code).first()

    def find_open_tasks(self) -> list[HandoverTask]:
        return (
            self.db.query(HandoverTask)
            .filter(HandoverTask.status != "RESOLVED")
            .order_by(HandoverTask.created_at.desc())
            .all()
        )
