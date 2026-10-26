# app/services/zone_risk_service.py
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.zone_risk import ZoneMonitoring
from app.schemas.zone_risk import WeatherHazardAlert


class ZoneRiskService:
    def __init__(self, db: Session):
        self.db = db

    def seed_initial_zones_if_empty(self) -> None:
        if self.db.query(ZoneMonitoring).count() == 0:
            zones = [
                ZoneMonitoring(
                    zone_code="ZONE_PARKING",
                    zone_name="Open North Parking Lot",
                    risk_level="HIGH",
                    repeated_complaints_count=4,
                    attention_needed=True,
                    recommendation="Frequent lighting failures reported. Water accumulation detected near Drainage Bay #2 during heavy rains.",
                    weather_hazard="Waterlogging Advisory",
                    last_inspected_at=datetime.utcnow()
                ),
                ZoneMonitoring(
                    zone_code="ZONE_GATE",
                    zone_name="Main Gate & Barrier Ingress",
                    risk_level="LOW",
                    repeated_complaints_count=1,
                    attention_needed=False,
                    recommendation="Boom barrier and ANPR camera operating at optimal 99.4% precision.",
                    weather_hazard="Normal",
                    last_inspected_at=datetime.utcnow()
                ),
                ZoneMonitoring(
                    zone_code="ZONE_HOSTEL",
                    zone_name="Hostel Rear Perimeter & Mess Gate",
                    risk_level="MODERATE",
                    repeated_complaints_count=3,
                    attention_needed=True,
                    recommendation="Overdue student curfew checks. Increase night patrol between 09:30 PM and 11:30 PM.",
                    weather_hazard="Normal",
                    last_inspected_at=datetime.utcnow()
                ),
                ZoneMonitoring(
                    zone_code="ZONE_LABS",
                    zone_name="Chemical & Mechanical Engineering Labs",
                    risk_level="LOW",
                    repeated_complaints_count=0,
                    attention_needed=False,
                    recommendation="Emergency fire exits verified and clear of obstruction.",
                    weather_hazard="Normal",
                    last_inspected_at=datetime.utcnow()
                )
            ]
            self.db.add_all(zones)
            self.db.commit()

    def get_all_zones(self) -> list[ZoneMonitoring]:
        self.seed_initial_zones_if_empty()
        return self.db.query(ZoneMonitoring).order_by(ZoneMonitoring.risk_level.desc()).all()

    def inspect_zone(self, zone_id: int, resolved_issues: bool = False) -> ZoneMonitoring | None:
        zone = self.db.query(ZoneMonitoring).filter(ZoneMonitoring.id == zone_id).first()
        if not zone:
            return None
        zone.last_inspected_at = datetime.utcnow()
        if resolved_issues:
            zone.repeated_complaints_count = max(0, zone.repeated_complaints_count - 1)
            if zone.repeated_complaints_count == 0:
                zone.attention_needed = False
                zone.risk_level = "LOW"
        self.db.commit()
        self.db.refresh(zone)
        return zone

    def get_weather_risk_telemetry(self) -> WeatherHazardAlert:
        # Campus Weather Station Live Telemetry
        return WeatherHazardAlert(
            temperature_celsius=27.4,
            condition="Monsoon Rain Warning",
            rainfall_probability=85,
            wind_speed_kmh=34.2,
            hazard_level="WARNING",
            hazard_title="Heavy Monsoon Precipitation & Waterlogging Alert",
            affected_zones=["Open North Parking Lot", "Main Gate Drainage Canal", "Hostel Perimeter Rear Gate"],
            safety_checklist=[
                "Inspect North Parking drains to prevent vehicle water submersion.",
                "Verify CCTV camera lens weather-shielding at Main Gate.",
                "Ensure emergency solar lanterns and raincoats are issued at Watchman Kiosk.",
                "Double-check emergency contact numbers for PWD and campus electrician."
            ]
        )
