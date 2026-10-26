# app/services/maintenance_service.py
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.maintenance import MaintenanceReport
from app.schemas.maintenance import MaintenanceCreate, MaintenanceUpdateStatus


class MaintenanceService:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, status: str | None = None) -> list[MaintenanceReport]:
        query = self.db.query(MaintenanceReport)
        if status:
            query = query.filter(MaintenanceReport.status == status.upper())
        return query.order_by(MaintenanceReport.created_at.desc()).all()

    def create_report(self, data: MaintenanceCreate) -> MaintenanceReport:
        ticket = f"MNT-{datetime.utcnow().strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        report = MaintenanceReport(
            ticket_number=ticket,
            category=data.category.upper(),
            title=data.title,
            description=data.description,
            photo_url=data.photo_url,
            location=data.location,
            urgency=data.urgency.upper(),
            status="OPEN",
            reported_by=data.reported_by,
            created_at=datetime.utcnow()
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def update_status(self, report_id: int, data: MaintenanceUpdateStatus) -> MaintenanceReport | None:
        report = self.db.query(MaintenanceReport).filter(MaintenanceReport.id == report_id).first()
        if not report:
            return None
        
        report.status = data.status.upper()
        if data.assigned_to:
            report.assigned_to = data.assigned_to
        if report.status == "RESOLVED":
            report.resolved_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(report)
        return report
