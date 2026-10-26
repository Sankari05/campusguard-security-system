# app/repositories/out_pass_repository.py
from typing import Optional

from sqlalchemy.orm import Session

from app.models.out_pass import OutPass
from app.repositories.base_repository import BaseRepository


class OutPassRepository(BaseRepository[OutPass]):
    def __init__(self, db: Session) -> None:
        super().__init__(OutPass, db)

    def find_by_pass_code(self, pass_code: str) -> Optional[OutPass]:
        return self.db.query(OutPass).filter(OutPass.pass_code == pass_code).first()

    def find_by_roll_number(self, roll_number: str) -> list[OutPass]:
        return (
            self.db.query(OutPass)
            .filter(OutPass.student_roll_number.ilike(roll_number))
            .order_by(OutPass.created_at.desc())
            .all()
        )
