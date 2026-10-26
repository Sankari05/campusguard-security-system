# app/services/duty_service.py
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.duty_attendance import DutyAttendance
from app.schemas.duty import ClockInRequest, ClockOutRequest


class DutyService:
    def __init__(self, db: Session):
        self.db = db

    def clock_in(self, data: ClockInRequest) -> DutyAttendance:
        # End any previous active session for this guard
        active = self.db.query(DutyAttendance).filter(
            DutyAttendance.guard_id == data.guard_id,
            DutyAttendance.is_active
        ).first()
        if active:
            active.is_active = False
            active.clock_out = datetime.utcnow()

        duty = DutyAttendance(
            guard_id=data.guard_id,
            guard_name=data.guard_name,
            shift_name=data.shift_name,
            gate_assigned=data.gate_assigned,
            clock_in=datetime.utcnow(),
            is_active=True
        )
        self.db.add(duty)
        self.db.commit()
        self.db.refresh(duty)
        return duty

    def clock_out(self, data: ClockOutRequest) -> DutyAttendance | None:
        duty = self.db.query(DutyAttendance).filter(
            DutyAttendance.guard_id == data.guard_id,
            DutyAttendance.is_active
        ).first()
        if not duty:
            return None

        duty.clock_out = datetime.utcnow()
        duty.is_active = False
        if data.supervisor_notes:
            duty.supervisor_notes = data.supervisor_notes
        
        self.db.commit()
        self.db.refresh(duty)
        return duty

    def get_current_duty(self, guard_id: str) -> DutyAttendance | None:
        return self.db.query(DutyAttendance).filter(
            DutyAttendance.guard_id == guard_id,
            DutyAttendance.is_active
        ).first()

    def get_duty_history(self, limit: int = 30) -> list[DutyAttendance]:
        return self.db.query(DutyAttendance).order_by(DutyAttendance.clock_in.desc()).limit(limit).all()
