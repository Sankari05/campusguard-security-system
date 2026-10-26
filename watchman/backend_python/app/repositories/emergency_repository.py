# app/repositories/emergency_repository.py
from sqlalchemy.orm import Session

from app.models.emergency_alert import EmergencyAlert
from app.repositories.base_repository import BaseRepository


class EmergencyRepository(BaseRepository[EmergencyAlert]):
    def __init__(self, db: Session) -> None:
        super().__init__(EmergencyAlert, db)

    def find_active_alerts(self) -> list[EmergencyAlert]:
        return (
            self.db.query(EmergencyAlert)
            .filter(EmergencyAlert.status == "ACTIVE")
            .order_by(EmergencyAlert.timestamp.desc())
            .all()
        )
