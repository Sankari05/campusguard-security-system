# app/repositories/parcel_repository.py
from typing import Optional

from sqlalchemy.orm import Session

from app.models.parcel_log import ParcelLog
from app.repositories.base_repository import BaseRepository


class ParcelRepository(BaseRepository[ParcelLog]):
    def __init__(self, db: Session) -> None:
        super().__init__(ParcelLog, db)

    def find_pending_deliveries(self) -> list[ParcelLog]:
        return (
            self.db.query(ParcelLog)
            .filter(ParcelLog.status == "WAITING_COLLECTION")
            .order_by(ParcelLog.received_at.desc())
            .all()
        )

    def find_by_tracking_number(self, tracking_number: str) -> Optional[ParcelLog]:
        return self.db.query(ParcelLog).filter(ParcelLog.tracking_number == tracking_number).first()
