# app/services/emergency_service.py
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.emergency_alert import EmergencyAlert
from app.repositories.emergency_repository import EmergencyRepository
from app.schemas.emergency import EmergencyAlertCreateRequest, EmergencyAlertResponse


class EmergencyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.emergency_repo = EmergencyRepository(db)

    def trigger_alert(self, req: EmergencyAlertCreateRequest) -> EmergencyAlertResponse:
        alert = EmergencyAlert(
            alert_type=req.alert_type.upper(),
            location=req.location,
            description=req.description,
            reported_by=req.reported_by,
            timestamp=datetime.utcnow(),
            status="ACTIVE",
        )
        saved = self.emergency_repo.create(alert)
        return EmergencyAlertResponse.model_validate(saved)

    def resolve_alert(self, alert_id: int) -> EmergencyAlertResponse:
        alert = self.emergency_repo.get_by_id(alert_id)
        if not alert:
            raise NotFoundException("Emergency alert", alert_id)
        alert.status = "RESOLVED"
        updated = self.emergency_repo.update(alert)
        return EmergencyAlertResponse.model_validate(updated)

    def get_active(self) -> list[EmergencyAlertResponse]:
        active = self.emergency_repo.find_active_alerts()
        return [EmergencyAlertResponse.model_validate(a) for a in active]

    def get_all(self) -> list[EmergencyAlertResponse]:
        alerts = self.emergency_repo.get_all(limit=100)
        return [EmergencyAlertResponse.model_validate(a) for a in alerts]
