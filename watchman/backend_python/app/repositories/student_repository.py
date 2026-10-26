# app/repositories/student_repository.py
from typing import Optional

from sqlalchemy.orm import Session

from app.models.student import Student
from app.repositories.base_repository import BaseRepository


class StudentRepository(BaseRepository[Student]):
    def __init__(self, db: Session) -> None:
        super().__init__(Student, db)

    def find_by_roll_number(self, roll_number: str) -> Optional[Student]:
        return self.db.query(Student).filter(Student.roll_number.ilike(roll_number)).first()
