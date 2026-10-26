# app/schemas/zone_risk.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ZoneMonitoringResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_code: str
    zone_name: str
    risk_level: str
    repeated_complaints_count: int
    attention_needed: bool
    recommendation: str
    weather_hazard: str | None
    last_inspected_at: datetime


class WeatherHazardAlert(BaseModel):
    temperature_celsius: float
    condition: str
    rainfall_probability: int
    wind_speed_kmh: float
    hazard_level: str  # NORMAL, ADVISORY, WARNING, CRITICAL
    hazard_title: str
    affected_zones: list[str]
    safety_checklist: list[str]
