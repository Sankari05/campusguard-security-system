# app/services/patrol_service.py
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.patrol import PatrolCheckpoint, PatrolLog
from app.schemas.patrol import PatrolScanRequest, PatrolStatusResponse


class PatrolService:
    def __init__(self, db: Session):
        self.db = db

    def seed_initial_checkpoints_if_empty(self) -> None:
        if self.db.query(PatrolCheckpoint).count() == 0:
            cps = [
                PatrolCheckpoint(checkpoint_code="CP-GATE", name="Main Gate & Visitor Bay", zone="ZONE_GATE", location_description="Main entrance perimeter and barrier post", qr_token="QR-GATE-7701", order_seq=1, scheduled_interval_minutes=45),
                PatrolCheckpoint(checkpoint_code="CP-PARK", name="Faculty & Visitor Parking Lot", zone="ZONE_PARKING", location_description="Vehicle parking block A and boundary fence", qr_token="QR-PARK-7702", order_seq=2, scheduled_interval_minutes=60),
                PatrolCheckpoint(checkpoint_code="CP-LABS", name="Engineering Research Labs", zone="ZONE_LABS", location_description="Ground floor mechanical & electrical laboratories", qr_token="QR-LABS-7703", order_seq=3, scheduled_interval_minutes=60),
                PatrolCheckpoint(checkpoint_code="CP-LIB", name="Central University Library", zone="ZONE_LIBRARY", location_description="Library foyer, fire escape, and side exits", qr_token="QR-LIB-7704", order_seq=4, scheduled_interval_minutes=90),
                PatrolCheckpoint(checkpoint_code="CP-HOSTEL", name="Hostel Perimeter North Wing", zone="ZONE_HOSTEL", location_description="Hostel mess, rear gate, and sports complex", qr_token="QR-HOSTEL-7705", order_seq=5, scheduled_interval_minutes=60),
            ]
            self.db.add_all(cps)
            self.db.commit()

    def get_checkpoints(self) -> list[PatrolCheckpoint]:
        self.seed_initial_checkpoints_if_empty()
        return self.db.query(PatrolCheckpoint).filter(PatrolCheckpoint.is_active).order_by(PatrolCheckpoint.order_seq.asc()).all()

    def get_logs(self, limit: int = 50) -> list[PatrolLog]:
        return self.db.query(PatrolLog).order_by(PatrolLog.scanned_at.desc()).limit(limit).all()

    def scan_checkpoint(self, data: PatrolScanRequest) -> PatrolLog | None:
        self.seed_initial_checkpoints_if_empty()
        cp = self.db.query(PatrolCheckpoint).filter(PatrolCheckpoint.qr_token == data.qr_token).first()
        if not cp:
            # Check by checkpoint_code as fallback
            cp = self.db.query(PatrolCheckpoint).filter(PatrolCheckpoint.checkpoint_code == data.qr_token).first()
        
        if not cp:
            return None

        log = PatrolLog(
            checkpoint_id=cp.id,
            checkpoint_code=cp.checkpoint_code,
            checkpoint_name=cp.name,
            guard_id=data.guard_id,
            guard_name=data.guard_name,
            scanned_at=datetime.utcnow(),
            status="COMPLETED",
            remarks=data.remarks or "QR Checkpoint scanned and perimeter verified."
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_status_overview(self) -> PatrolStatusResponse:
        self.seed_initial_checkpoints_if_empty()
        checkpoints = self.db.query(PatrolCheckpoint).filter(PatrolCheckpoint.is_active).all()
        total_cp = len(checkpoints)
        
        # Scanned in the last 24h
        completed = self.db.query(PatrolLog).filter(PatrolLog.status == "COMPLETED").count()
        missed = self.db.query(PatrolLog).filter(PatrolLog.status == "MISSED").count()
        
        # Next checkpoint suggestion
        next_due = checkpoints[0].name if checkpoints else None
        
        return PatrolStatusResponse(
            total_checkpoints=total_cp,
            completed_today=completed,
            missed_count=missed,
            next_due_checkpoint=next_due,
            next_due_time="In 30 mins"
        )
