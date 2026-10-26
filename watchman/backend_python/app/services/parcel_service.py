# app/services/parcel_service.py
import random
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.parcel_log import ParcelLog
from app.repositories.parcel_repository import ParcelRepository
from app.schemas.parcel import ParcelCreateRequest, ParcelResponse


class ParcelService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.parcel_repo = ParcelRepository(db)

    def register_parcel(self, req: ParcelCreateRequest) -> ParcelResponse:
        otp = f"{random.randint(1000, 9999)}"
        parcel = ParcelLog(
            courier_company=req.courier_company.upper(),
            tracking_number=req.tracking_number,
            recipient_name=req.recipient_name,
            department_or_hostel=req.department_or_hostel,
            recipient_phone=req.recipient_phone,
            received_at=datetime.utcnow(),
            status="WAITING_COLLECTION",
            handover_otp=otp,
            received_by_watchman=req.received_by_watchman or "Ramasamy (Main Gate Security)",
        )
        saved = self.parcel_repo.create(parcel)
        return ParcelResponse.model_validate(saved)

    def deliver_parcel(self, parcel_id: int, otp: str) -> ParcelResponse:
        parcel = self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise NotFoundException("Parcel", parcel_id)

        if parcel.status == "DELIVERED":
            raise BadRequestException("Parcel has already been collected.")

        if parcel.handover_otp and otp.strip() != parcel.handover_otp:
            raise BadRequestException("Invalid collection OTP.")

        parcel.status = "DELIVERED"
        parcel.picked_up_at = datetime.utcnow()
        updated = self.parcel_repo.update(parcel)
        return ParcelResponse.model_validate(updated)

    def get_pending(self) -> list[ParcelResponse]:
        pending = self.parcel_repo.find_pending_deliveries()
        return [ParcelResponse.model_validate(p) for p in pending]

    def get_all(self) -> list[ParcelResponse]:
        parcels = self.parcel_repo.get_all(limit=100)
        return [ParcelResponse.model_validate(p) for p in parcels]
