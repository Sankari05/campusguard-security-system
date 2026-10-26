# app/services/parking_service.py
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.parking import ParkingSlot
from app.schemas.parking import ParkingOccupy, ParkingSummary


class ParkingService:
    def __init__(self, db: Session):
        self.db = db

    def seed_initial_slots_if_empty(self) -> None:
        if self.db.query(ParkingSlot).count() == 0:
            slots = [
                # Staff Slots
                ParkingSlot(slot_code="ST-01", zone="STAFF", slot_type="FOUR_WHEELER", is_occupied=True, vehicle_number="TN09CA1234", driver_name="Dr. Sundaram (Principal)", parked_at=datetime.utcnow()),
                ParkingSlot(slot_code="ST-02", zone="STAFF", slot_type="FOUR_WHEELER", is_occupied=False),
                ParkingSlot(slot_code="ST-03", zone="STAFF", slot_type="FOUR_WHEELER", is_occupied=True, vehicle_number="TN07BD4455", driver_name="Prof. Meenakshi (HOD)", parked_at=datetime.utcnow()),
                # Zone A Slots (Visitors / General)
                ParkingSlot(slot_code="A-01", zone="ZONE_A", slot_type="FOUR_WHEELER", is_occupied=True, vehicle_number="TN22AB9988", driver_name="L&T Inspector", parked_at=datetime.utcnow()),
                ParkingSlot(slot_code="A-02", zone="ZONE_A", slot_type="FOUR_WHEELER", is_occupied=False),
                ParkingSlot(slot_code="A-03", zone="ZONE_A", slot_type="FOUR_WHEELER", is_occupied=True, vehicle_number="KA01MJ7766", is_unauthorized=True, driver_name="Unknown Vehicle", parked_at=datetime.utcnow()),
                ParkingSlot(slot_code="A-04", zone="ZONE_A", slot_type="EV_CHARGING", is_occupied=False),
                # Two Wheeler Slots
                ParkingSlot(slot_code="TW-01", zone="ZONE_B", slot_type="TWO_WHEELER", is_occupied=True, vehicle_number="TN11Q1122", driver_name="Student Council Rep", parked_at=datetime.utcnow()),
                ParkingSlot(slot_code="TW-02", zone="ZONE_B", slot_type="TWO_WHEELER", is_occupied=False),
                ParkingSlot(slot_code="TW-03", zone="ZONE_B", slot_type="TWO_WHEELER", is_occupied=False),
            ]
            self.db.add_all(slots)
            self.db.commit()

    def get_all(self, zone: str | None = None) -> list[ParkingSlot]:
        self.seed_initial_slots_if_empty()
        query = self.db.query(ParkingSlot)
        if zone:
            query = query.filter(ParkingSlot.zone == zone.upper())
        return query.order_by(ParkingSlot.slot_code.asc()).all()

    def occupy_slot(self, slot_id: int, data: ParkingOccupy) -> ParkingSlot | None:
        slot = self.db.query(ParkingSlot).filter(ParkingSlot.id == slot_id).first()
        if not slot:
            return None
        slot.is_occupied = True
        slot.vehicle_number = data.vehicle_number.upper().replace(" ", "")
        slot.driver_name = data.driver_name
        slot.phone_number = data.phone_number
        slot.is_unauthorized = data.is_unauthorized
        slot.parked_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(slot)
        return slot

    def vacate_slot(self, slot_id: int) -> ParkingSlot | None:
        slot = self.db.query(ParkingSlot).filter(ParkingSlot.id == slot_id).first()
        if not slot:
            return None
        slot.is_occupied = False
        slot.vehicle_number = None
        slot.driver_name = None
        slot.phone_number = None
        slot.is_unauthorized = False
        slot.parked_at = None
        self.db.commit()
        self.db.refresh(slot)
        return slot

    def get_summary(self) -> ParkingSummary:
        self.seed_initial_slots_if_empty()
        total = self.db.query(ParkingSlot).count()
        occupied = self.db.query(ParkingSlot).filter(ParkingSlot.is_occupied).count()
        unauthorized = self.db.query(ParkingSlot).filter(ParkingSlot.is_unauthorized).count()
        return ParkingSummary(
            total_slots=total,
            occupied_slots=occupied,
            available_slots=max(0, total - occupied),
            unauthorized_count=unauthorized
        )
