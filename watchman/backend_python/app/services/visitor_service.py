# app/services/visitor_service.py
import random
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, GoneException, NotFoundException
from app.models.visitor_pass import VisitorPass
from app.repositories.visitor_repository import VisitorRepository
from app.schemas.visitor import (
    ConfirmEntryRequest,
    VisitorPassResponse,
    VisitorSelfRegisterRequest,
)


class VisitorService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.visitor_repo = VisitorRepository(db)

    def self_register(self, req: VisitorSelfRegisterRequest) -> VisitorPassResponse:
        pass_number = f"VP-{uuid.uuid4().hex[:6].upper()}"
        otp = f"{random.randint(100000, 999999)}"
        expires_at = datetime.utcnow() + timedelta(hours=2)

        pass_obj = VisitorPass(
            visitor_type=req.visitor_type or "STUDENT",
            visitor_name=req.visitor_name,
            identifier=req.identifier,
            phone_number=req.phone_number,
            department=req.department,
            reason=req.reason,
            additional_details=req.additional_details,
            person_to_meet=req.person_to_meet,
            pass_number=pass_number,
            otp=otp,
            created_at=datetime.utcnow(),
            otp_expires_at=expires_at,
            status="PENDING_OTP",
            badge_number=req.badge_number,
            vehicle_number=req.vehicle_number,
        )
        saved = self.visitor_repo.create(pass_obj)
        return VisitorPassResponse.model_validate(saved)

    def verify_otp(self, pass_number: str, otp: str) -> VisitorPassResponse:
        pass_obj = self.visitor_repo.find_by_pass_number(pass_number)
        if not pass_obj:
            raise NotFoundException("Visitor pass", pass_number)

        if pass_obj.otp_expires_at and datetime.utcnow() > pass_obj.otp_expires_at:
            pass_obj.status = "EXPIRED"
            self.visitor_repo.update(pass_obj)
            raise GoneException("OTP has expired. Please request a new pass.")

        if pass_obj.otp != otp.strip():
            raise BadRequestException("Invalid OTP code.")

        pass_obj.status = "APPROVED"
        pass_obj.otp_verified_at = datetime.utcnow()
        updated = self.visitor_repo.update(pass_obj)
        return VisitorPassResponse.model_validate(updated)

    def confirm_entry(self, pass_number: str, req: ConfirmEntryRequest) -> VisitorPassResponse:
        pass_obj = self.visitor_repo.find_by_pass_number(pass_number)
        if not pass_obj:
            raise NotFoundException("Visitor pass", pass_number)

        if pass_obj.status not in ["APPROVED", "PENDING_OTP"]:
            raise BadRequestException(f"Cannot check in. Current pass status: {pass_obj.status}")

        pass_obj.check_in_time = datetime.utcnow()
        pass_obj.status = "APPROVED"
        pass_obj.verified_by_watchman_id = req.watchman_id
        pass_obj.verified_by_watchman_name = req.watchman_name
        if req.badge_number:
            pass_obj.badge_number = req.badge_number

        updated = self.visitor_repo.update(pass_obj)
        return VisitorPassResponse.model_validate(updated)

    def checkout(self, pass_number: str) -> VisitorPassResponse:
        pass_obj = self.visitor_repo.find_by_pass_number(pass_number)
        if not pass_obj:
            raise NotFoundException("Visitor pass", pass_number)

        pass_obj.check_out_time = datetime.utcnow()
        pass_obj.status = "CHECKED_OUT"
        updated = self.visitor_repo.update(pass_obj)
        return VisitorPassResponse.model_validate(updated)

    def get_by_pass_number(self, pass_number: str) -> VisitorPassResponse:
        pass_obj = self.visitor_repo.find_by_pass_number(pass_number)
        if not pass_obj:
            raise NotFoundException("Visitor pass", pass_number)
        return VisitorPassResponse.model_validate(pass_obj)

    def get_all(self) -> list[VisitorPassResponse]:
        passes = self.visitor_repo.get_all(limit=100)
        return [VisitorPassResponse.model_validate(p) for p in passes]
