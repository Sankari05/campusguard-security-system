# app/repositories/visitor_repository.py
from typing import Optional

from sqlalchemy.orm import Session

from app.models.visitor_pass import VisitorPass
from app.repositories.base_repository import BaseRepository


class VisitorRepository(BaseRepository[VisitorPass]):
    def __init__(self, db: Session) -> None:
        super().__init__(VisitorPass, db)

    def find_by_pass_number(self, pass_number: str) -> Optional[VisitorPass]:
        return self.db.query(VisitorPass).filter(VisitorPass.pass_number == pass_number).first()

    def find_pending_or_approved(self) -> list[VisitorPass]:
        return (
            self.db.query(VisitorPass)
            .filter(VisitorPass.status.in_(["PENDING_OTP", "APPROVED"]))
            .order_by(VisitorPass.created_at.desc())
            .all()
        )
