# app/repositories/gate_repository.py
from sqlalchemy.orm import Session

from app.models.gate_log import GateLog
from app.repositories.base_repository import BaseRepository


class GateRepository(BaseRepository[GateLog]):
    def __init__(self, db: Session) -> None:
        super().__init__(GateLog, db)

    def find_recent(self, limit: int = 50, gate_number: str = None) -> list[GateLog]:
        query = self.db.query(GateLog)
        if gate_number:
            query = query.filter(GateLog.gate_number == gate_number)
        return query.order_by(GateLog.entry_time.desc()).limit(limit).all()
