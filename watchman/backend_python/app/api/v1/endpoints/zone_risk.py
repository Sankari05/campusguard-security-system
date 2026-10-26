# app/api/v1/endpoints/zone_risk.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.zone_risk import WeatherHazardAlert, ZoneMonitoringResponse
from app.services.zone_risk_service import ZoneRiskService

router = APIRouter()


@router.get("/zones", response_model=list[ZoneMonitoringResponse])
def get_zones(db: Session = Depends(get_db)):
    service = ZoneRiskService(db)
    return service.get_all_zones()


@router.post("/zones/{zone_id}/inspect", response_model=ZoneMonitoringResponse)
def inspect_zone(zone_id: int, resolved_issues: bool = False, db: Session = Depends(get_db)):
    service = ZoneRiskService(db)
    zone = service.inspect_zone(zone_id, resolved_issues=resolved_issues)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone


@router.get("/weather-telemetry", response_model=WeatherHazardAlert)
def get_weather_risk_telemetry(db: Session = Depends(get_db)):
    service = ZoneRiskService(db)
    return service.get_weather_risk_telemetry()
