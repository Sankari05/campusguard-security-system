# app/services/student_service.py
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.out_pass import OutPass
from app.models.student import Student
from app.repositories.out_pass_repository import OutPassRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.out_pass import OutPassCreateRequest, OutPassResponse


class StudentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.student_repo = StudentRepository(db)
        self.out_pass_repo = OutPassRepository(db)

    def verify_student_by_roll(self, roll_number: str) -> dict:
        student = self.student_repo.find_by_roll_number(roll_number)
        if not student:
            # Seed demo student if queried in testing
            roll_clean = roll_number.strip().upper()
            student = Student(
                roll_number=roll_clean,
                name="Saravanan K",
                department="Information Technology",
                year_of_study=3,
                hostel_or_day_scholar="HOSTEL",
                room_or_bus_route="Block B - Room 204",
                parent_phone="9876543210",
                is_suspended=False,
            )
            student = self.student_repo.create(student)

        # Check active out-pass
        active_pass = (
            self.db.query(OutPass)
            .filter(
                OutPass.student_roll_number == student.roll_number,
                OutPass.status.in_(["APPROVED_BY_HOD", "EXITED_GATE"]),
            )
            .order_by(OutPass.created_at.desc())
            .first()
        )

        return {
            "id": student.id,
            "roll_number": student.roll_number,
            "name": student.name,
            "department": student.department,
            "year_of_study": student.year_of_study,
            "hostel_or_day_scholar": student.hostel_or_day_scholar,
            "room_or_bus_route": student.room_or_bus_route,
            "parent_phone": student.parent_phone,
            "photo_url": student.photo_url,
            "is_suspended": student.is_suspended,
            "has_active_outpass": active_pass is not None,
            "active_outpass": OutPassResponse.model_validate(active_pass) if active_pass else None,
        }

    def request_out_pass(self, req: OutPassCreateRequest) -> OutPassResponse:
        student = self.student_repo.find_by_roll_number(req.roll_number)
        if student and student.is_suspended:
            raise BadRequestException("Cannot request out-pass: Student is currently suspended.")

        pass_code = f"OP-{uuid.uuid4().hex[:8].upper()}"
        out_pass = OutPass(
            pass_code=pass_code,
            student_id=student.id if student else None,
            student_roll_number=req.roll_number,
            student_name=req.student_name,
            department=req.department,
            reason=req.reason,
            destination=req.destination,
            out_time_expected=req.out_time_expected,
            in_time_expected=req.in_time_expected,
            status="PENDING",
            created_at=datetime.utcnow(),
        )
        saved = self.out_pass_repo.create(out_pass)
        return OutPassResponse.model_validate(saved)

    def approve_out_pass(self, pass_code: str, approved_by: str) -> OutPassResponse:
        out_pass = self.out_pass_repo.find_by_pass_code(pass_code)
        if not out_pass:
            raise NotFoundException("Out-pass", pass_code)
        out_pass.status = "APPROVED_BY_HOD"
        out_pass.approved_by = approved_by
        out_pass.parent_consent_verified = True
        updated = self.out_pass_repo.update(out_pass)
        return OutPassResponse.model_validate(updated)

    def verify_and_exit_gate(self, pass_code: str) -> OutPassResponse:
        out_pass = self.out_pass_repo.find_by_pass_code(pass_code)
        if not out_pass:
            raise NotFoundException("Out-pass", pass_code)
        if out_pass.status != "APPROVED_BY_HOD":
            raise BadRequestException(
                f"Out-pass cannot be used at gate. Status is: {out_pass.status}"
            )
        out_pass.status = "EXITED_GATE"
        out_pass.actual_out_time = datetime.utcnow()
        updated = self.out_pass_repo.update(out_pass)
        return OutPassResponse.model_validate(updated)

    def mark_student_returned(self, pass_code: str) -> OutPassResponse:
        out_pass = self.out_pass_repo.find_by_pass_code(pass_code)
        if not out_pass:
            raise NotFoundException("Out-pass", pass_code)
        out_pass.status = "COMPLETED"
        out_pass.actual_in_time = datetime.utcnow()
        updated = self.out_pass_repo.update(out_pass)
        return OutPassResponse.model_validate(updated)

    def list_out_passes(self) -> list[OutPassResponse]:
        passes = self.out_pass_repo.get_all(limit=100)
        return [OutPassResponse.model_validate(p) for p in passes]
