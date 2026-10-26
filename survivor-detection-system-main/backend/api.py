"""
api.py
------
REST API layer for the AI-Based Multi-Sensor Survivor Detection & Rescue
Prioritization System, built on FastAPI.

Supports isolated multi-operation (multi-incident) execution via an
in-memory operations registry (`operations: Dict[str, ScenarioState]`).

Wires sensor_simulator.py -> fusion_engine.py so that every GET request
reflects freshly-simulated, freshly-fused data: each call to /operations/{op_id}/victims
or /operations/{op_id}/queue advances the running scenario by one sensor cycle,
re-runs the fusion engine over a short rolling window of recent readings (for
smoothing), and returns the current state.
"""

from __future__ import annotations

import uuid
import random
import math
import time
import asyncio
import sys
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union
from collections import defaultdict, deque

from pathlib import Path
from dotenv import load_dotenv

for _env_candidate in [
    Path(__file__).resolve().parent / ".env",
    Path("backend/.env"),
    Path(".env"),
]:
    if _env_candidate.exists():
        load_dotenv(_env_candidate)
        break

import logging

logger = logging.getLogger("ridgewatch.api")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from models import (
    GPSCoordinate,
    RiskLevel,
    RescueTeamStatus,
    TeamAvailability,
    SensorType,
    VictimProfile,
    ADMIN_PRIORITY_TEMPLATES,
    TeamMember,
    MemberStatus,
    GasType,
    GasConcentrationLevel,
    SmokeLevel,
    GasSmokeReading,
    PressureTrend,
    PressureDropSeverity,
    PressureAnomalyLevel,
    PressureConfig,
    PRESSURE_CONFIG,
    BarometricPressureReading,
    SensorHealthStatus,
    MoistureTrend,
    TiltTrend,
    LandslideRiskLevel,
    LandslideEventState,
    LandslideConfig,
    LANDSLIDE_CONFIG,
    SoilMoistureReading,
    TiltReading,
    LandslideRiskAssessment,
    CameraDetectionState,
    CameraClassification,
    CameraHealthStatus,
    ThermalDetectionType,
    ThermalClassification,
    ThermalHealthStatus,
    CameraCorrelationCase,
    CameraConfig,
    CAMERA_CONFIG,
    CameraReading,
    ThermalCameraReading,
    CameraThermalCorrelation,
    RainfallClassification,
    RainfallTrend,
    RainfallConfig,
    RAINFALL_CONFIG,
    RainfallReading,
    TemperatureTrend,
    HumidityTrend,
    TemperatureConfig,
    TEMPERATURE_CONFIG,
    HumidityConfig,
    HUMIDITY_CONFIG,
    TemperatureReading,
    HumidityReading,
    GPSMovementState,
    GPSConfig,
    GPS_CONFIG,
    GPSReading,
    WaterTrend,
    WaterLevelClassification,
    WaterLevelConfig,
    WATER_LEVEL_CONFIG,
    WaterLevelReading,
    SensorValidator,
    RejectedSensorReading,
)
from scenario_intelligence import (
    LandslideRiskAnalyzer,
    BarometricPressureAnalyzer,
    CameraThermalAnalyzer,
    RainfallAnalyzer,
    GPSAnalyzer,
)
from sensor_simulator import SensorSimulator
from sensor_simulator import DROPOUT_BATTERY_THRESHOLD_PCT as LOW_BATTERY_WARNING_PCT
from fusion_engine import (
    fuse_all,
    rank_victims,
    TriageClass,
    HazardContext,
    calculate_geospatial_distance,
    find_nearest_survivor,
    find_nearest_rescue_team,
)
from dataclasses import replace as _dataclass_replace
from rescue_dispatch import RescueDispatchAgent, SECONDS_PER_ADVANCE_STEP, haversine_distance_m, EARTH_RADIUS_M
from alert_dispatch import NetworkAlertDispatcher
from non_contact_pressure import (
    NonContactPressureEngine,
    NonContactPressureConfig,
    NonContactPressureEstimate,
    NonContactSensorReading,
    get_non_contact_pressure_engine,
)
import db
from wearable_gateway import global_wearable_gateway
import scenario_loader
from scenario_loader import ScenarioConfig, ScenarioNotFoundError, ScenarioConfigError, build_custom_scenario
from scenarios_master import (
    get_all_scenarios,
    get_scenario_by_id,
    is_staff_eligible_for_scenario,
    normalize_scenario_key,
)
from scenario_intelligence import (
    ScenarioIntelligenceEngine,
    global_scenario_intelligence,
    GasSmokeAnalyzer,
    BarometricPressureAnalyzer,
    CameraThermalAnalyzer,
)
from scenario_sensor_profiles import (
    ScenarioSensorProfile,
    SensorRole,
    get_scenario_sensor_profile,
    get_scenario_sensor_state_map,
)
import hardware_registry
import road_network
from road_network import global_road_network, RouteResult
from flood_intelligence_engine import (
    FloodIntelligenceEngine,
    get_flood_intelligence_engine,
    FloodRiskLevel,
    FloodIntelligenceReport,
    FloodRiskAssessment,
)
from landslide_detector import LandslideDetector, get_landslide_detector
from debris_flow_detector import DebrisFlowDetector, get_debris_flow_detector
from evacuation_engine import (
    EvacuationEngine,
    get_evacuation_engine,
    ZoneDangerLevel,
    RouteSafetyConfidence,
    EvacuationRouteRecommendation,
)
from communication_fallback import (
    CommunicationManager,
    get_communication_manager,
    BearerType,
    MessagePriority,
    MessageStatus,
)
from sensor_health_monitor import (
    SensorHealthMonitor,
    get_sensor_health_monitor,
)


class IngestGasSmokeReadingRequest(BaseModel):
    sensor_id: Optional[str] = "GAS-SMOKE-SITE"
    device_id: Optional[str] = "DEV-GAS-01"
    gas_type: Optional[str] = "GENERIC_SMOKE"
    gas_concentration: float
    smoke_density_pct: float
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class IngestBarometricPressureReadingRequest(BaseModel):
    sensor_id: Optional[str] = "ENV-BARO-01"
    device_id: Optional[str] = "DEV-BARO-01"
    pressure_hpa: float
    unit: Optional[str] = "hPa"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confidence: Optional[float] = 0.95
    status: Optional[str] = "ONLINE"


class IngestSoilMoistureReadingRequest(BaseModel):
    sensor_id: Optional[str] = "SLOPE-SOIL-01"
    node_id: Optional[str] = "SLOPE-NODE-01"
    device_id: Optional[str] = "DEV-SOIL-01"
    soil_moisture_pct: float
    unit: Optional[str] = "%"
    status: Optional[str] = "ONLINE"
    confidence: Optional[float] = 0.95
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class IngestTiltReadingRequest(BaseModel):
    sensor_id: Optional[str] = "SLOPE-TILT-01"
    node_id: Optional[str] = "SLOPE-NODE-01"
    device_id: Optional[str] = "DEV-TILT-01"
    tilt_x: Optional[float] = 0.0
    tilt_y: Optional[float] = 0.0
    tilt_z: Optional[float] = 1.0
    tilt_angle_deg: float
    unit: Optional[str] = "deg"
    status: Optional[str] = "ONLINE"
    confidence: Optional[float] = 0.95
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SetLandslideProfileRequest(BaseModel):
    profile: str
    node_id: Optional[str] = None


class SimulateCameraRequest(BaseModel):
    profile: Optional[str] = "NORMAL"
    camera_id: Optional[str] = None
    victim_id: Optional[str] = None
    confidence: Optional[float] = None
    visibility: Optional[float] = None
    occlusion: Optional[float] = None
    smoke_present: Optional[bool] = None
    person_count: Optional[int] = None


class SimulateThermalRequest(BaseModel):
    profile: Optional[str] = "HUMAN_HEAT"
    camera_id: Optional[str] = None
    victim_id: Optional[str] = None
    estimated_temperature: Optional[float] = None
    background_temperature: Optional[float] = None
    fire_hotspot: Optional[bool] = None
    hot_debris: Optional[bool] = None


class IngestCameraReadingRequest(BaseModel):
    camera_id: Optional[str] = "CAM-001"
    device_id: Optional[str] = "DEV-CAM-01"
    victim_id: Optional[str] = None
    detection_state: Optional[str] = "PERSON_DETECTED"
    classification: Optional[str] = "HUMAN"
    person_count: Optional[int] = 1
    confidence: float = 0.90
    visibility: Optional[float] = 1.0
    occlusion: Optional[float] = 0.0
    motion_detected: Optional[bool] = False
    smoke_present: Optional[bool] = False
    fire_visible: Optional[bool] = False
    debris_present: Optional[bool] = False
    status: Optional[str] = "ONLINE"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None


class IngestThermalReadingRequest(BaseModel):
    camera_id: Optional[str] = "THERMAL-001"
    device_id: Optional[str] = "DEV-THM-01"
    victim_id: Optional[str] = None
    detection_type: Optional[str] = "HUMAN_HEAT_SIGNATURE"
    classification: Optional[str] = "HUMAN_HEAT_SIGNATURE"
    estimated_temperature: float = 34.5
    background_temperature: Optional[float] = 18.0
    thermal_confidence: Optional[float] = 0.90
    thermal_visibility: Optional[float] = 1.0
    fire_hotspot: Optional[bool] = False
    hot_debris: Optional[bool] = False
    status: Optional[str] = "ONLINE"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None


class SimulateRainfallRequest(BaseModel):
    profile: Optional[str] = "HEAVY"
    rainfall_rate_mm_h: Optional[float] = None
    cumulative_rainfall_mm: Optional[float] = None


class IngestRainfallReadingRequest(BaseModel):
    sensor_id: Optional[str] = "ENV-RAIN-01"
    device_id: Optional[str] = "DEV-RAIN-01"
    rainfall_rate_mm_h: float = 25.4
    cumulative_rainfall_mm: Optional[float] = 0.0
    unit: Optional[str] = "mm/h"
    rate_of_change: Optional[float] = 0.0
    trend: Optional[str] = "STABLE"
    classification: Optional[str] = "HEAVY"
    severity: Optional[str] = "HIGH"
    status: Optional[str] = "ONLINE"
    confidence: Optional[float] = 0.98
    quality: Optional[float] = 0.98
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None


class SimulateTemperatureRequest(BaseModel):
    profile: Optional[str] = "NORMAL"
    temperature_c: Optional[float] = None


class IngestTemperatureReadingRequest(BaseModel):
    sensor_id: Optional[str] = "ENV-TEMP-01"
    device_id: Optional[str] = "DEV-TEMP-01"
    temperature_c: float = 15.0
    ambient_temp_c: Optional[float] = None
    unit: Optional[str] = "°C"
    rate_of_change: Optional[float] = 0.0
    trend: Optional[str] = "STABLE"
    status: Optional[str] = "ONLINE"
    confidence: Optional[float] = 0.98
    quality: Optional[float] = 0.98
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None


class SimulateHumidityRequest(BaseModel):
    profile: Optional[str] = "NORMAL"
    humidity_pct: Optional[float] = None


class IngestHumidityReadingRequest(BaseModel):
    sensor_id: Optional[str] = "ENV-HUMID-01"
    device_id: Optional[str] = "DEV-HUMID-01"
    humidity_pct: float = 50.0
    unit: Optional[str] = "%"
    rate_of_change: Optional[float] = 0.0
    trend: Optional[str] = "STABLE"
    status: Optional[str] = "ONLINE"
    confidence: Optional[float] = 0.98
    quality: Optional[float] = 0.98
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None


class SimulateGPSRequest(BaseModel):
    profile: Optional[str] = "STATIONARY"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None
    accuracy_m: Optional[float] = None
    speed_mps: Optional[float] = None
    heading_deg: Optional[float] = None
    satellites: Optional[int] = None


class IngestGPSReadingRequest(BaseModel):
    sensor_id: Optional[str] = "DEV-GPS-01"
    device_id: Optional[str] = "RESCUE-KIT-01"
    latitude: float
    longitude: float
    altitude_m: Optional[float] = 3950.0
    accuracy_m: Optional[float] = 2.5
    speed_mps: Optional[float] = 0.0
    heading_deg: Optional[float] = 0.0
    satellites: Optional[int] = 12
    movement_state: Optional[str] = "STATIONARY"
    is_valid_fix: Optional[bool] = True
    status: Optional[str] = "ONLINE"
    confidence: Optional[float] = 0.98
    quality: Optional[float] = 0.98
    entity_type: Optional[str] = "DEVICE"
    entity_id: Optional[str] = None


class SimulateWaterLevelRequest(BaseModel):
    profile: Optional[str] = "NORMAL"
    water_level_cm: Optional[float] = None
    water_flow_mps: Optional[float] = None


class IngestWaterLevelReadingRequest(BaseModel):
    sensor_id: Optional[str] = "ENV-WATER-01"
    device_id: Optional[str] = "DEV-WATER-01"
    water_level_cm: float = 0.0
    water_flow_mps: Optional[float] = 0.0
    unit: Optional[str] = "cm"
    rate_of_change: Optional[float] = 0.0
    trend: Optional[str] = "STABLE"
    classification: Optional[str] = "NORMAL"
    severity: Optional[str] = "LOW"
    status: Optional[str] = "ONLINE"
    confidence: Optional[float] = 0.98
    quality: Optional[float] = 0.98
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None


class EvaluateFloodRequest(BaseModel):
    measured_surface_distance_m: Optional[float] = None
    water_depth_m: Optional[float] = None
    sensor_mount_height_m: Optional[float] = 6.0
    rainfall_rate_mmh: Optional[float] = 0.0
    flow_velocity_mps: Optional[float] = 0.0
    upstream_surge_active: Optional[bool] = False
    soil_moisture_pct: Optional[float] = 40.0
    slope_tilt_deg: Optional[float] = 0.0
    acoustic_rumble_db: Optional[float] = 30.0
    is_live_sensor: Optional[bool] = False


class SendEmergencyAlertRequest(BaseModel):
    recipient: Optional[str] = "BROADCAST"
    payload: str
    priority: Optional[str] = "WARNING"
    idempotency_key: Optional[str] = None


# --------------------------------------------------------------------------- #
# App setup
# --------------------------------------------------------------------------- #

app = FastAPI(
    title="Survivor Detection & Rescue Prioritization API",
    description="AI-based multi-sensor fusion and triage system with Multi-Operation Isolation",
    version="2.0.0",
)

ALLOWED_ORIGINS = [
    "http://127.0.0.1:5000",
    "http://localhost:5000",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:5501",
    "http://localhost:5501",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/frontend/index.html")

db.init_db()  # idempotent - creates the SQLite schema on first import
db.seed_builtin_scenarios()  # ensure default disaster templates are in scenarios ledger
db.seed_builtin_teams()      # ensure default active rescue teams are in teams ledger

HISTORY_CYCLES = 3   # number of recent cycles kept per victim for fusion smoothing
SENSORS_PER_CYCLE = len(list(SensorType))
HISTORY_MAXLEN = HISTORY_CYCLES * SENSORS_PER_CYCLE  # each cycle emits one reading per sensor type

DEFAULT_SCENARIO_ID = "himalaya_avalanche"
TRACKED_MEMBER_SAMPLE_SIZE = 8

_FIRST_NAMES = ["Arjun", "Priya", "Karthik", "Deepa", "Ravi", "Meena", "Suresh", "Divya", "Vikram", "Anitha"]
_LAST_NAMES = ["Kumar", "Raj", "Iyer", "Reddy", "Pillai", "Menon", "Sharma", "Rao", "Das"]

NEAREST_SUGGESTION_COUNT = 5
MEMBER_WALK_SPEED_MPS = 1.2
MEMBER_ARRIVAL_THRESHOLD_M = 5.0
SECONDS_PER_COMMANDER_POLL = 4.0
MAX_RECENT_ARRIVALS = 30
GPS_STALE_THRESHOLD_SECONDS = 15

# Stage 4 Navigation & Guidance Parameters
GPS_ARRIVAL_DISTANCE_METERS = 15.0
GPS_MIN_SPEED_FOR_DIRECTION_MPS = 0.5
DIRECTION_TOLERANCE_DEGREES = 45.0
DIRECTION_CONFIRMATION_SAMPLES = 3
DIRECTION_ALERT_COOLDOWN_SECONDS = 30.0
DISTANCE_TREND_HYSTERESIS_METERS = 1.0

# In-memory authoritative cache for Alpha Member 1 real GPS telemetry
ALPHA_M001_LATEST_GPS: Dict[str, Any] = {
    "latitude": None,
    "longitude": None,
    "altitude_m": None,
    "accuracy_m": None,
    "speed_mps": None,
    "heading_deg": None,
    "gps_timestamp": None,
    "latest_gps_dt": None,
    "gps_status": "STANDBY",
    "location_source": "PHONE_GPS",
    "navigation_status": None,
    "target_bearing_deg": None,
    "heading_difference_deg": None,
    "direction_delta_deg": None,
    "distance_to_target_m": None,
    "distance_trend": "STABLE",
    "direction_guidance": None,
    "arrived_at": None,
    "is_arrived": False,
    "active_command_id": None,
    "assigned_victim_id": None,
}

ALPHA_M001_NAV_STATE: Dict[str, Any] = {
    "consecutive_wrong_samples": 0,
    "last_direction_alert_time": 0.0,
    "previous_coord": None,
    "previous_coord_time": 0.0,
    "previous_distance_m": None,
    "navigation_status": None,
    "target_bearing_deg": None,
    "heading_difference_deg": None,
    "direction_delta_deg": None,
    "distance_to_target_m": None,
    "distance_trend": "STABLE",
    "direction_guidance": None,
    "arrived_at": None,
    "is_arrived": False,
    "active_command_id": None,
    "assigned_victim_id": None,
}


def validate_gps_coordinates(lat: Any, lon: Any) -> bool:
    """Strictly validates latitude in [-90, 90] and longitude in [-180, 180], rejecting NaN and inf."""
    if lat is None or lon is None:
        return False
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return False
    if math.isnan(lat_f) or math.isinf(lat_f) or math.isnan(lon_f) or math.isinf(lon_f):
        return False
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
        return False
    return True


def reset_alpha_m001_mission_navigation_state(
    new_command_id: Optional[str] = None,
    new_victim_id: Optional[str] = None,
    preserve_hardware_fix: bool = True,
):
    """
    Stage 7 Mission-Scoped State Isolation:
    Resets Alpha Member 1 mission navigation calculations, arrival status, distance trend,
    and wrong-direction counters without losing valid physical GPS coordinates.
    """
    saved_lat = ALPHA_M001_LATEST_GPS.get("latitude") if preserve_hardware_fix else None
    saved_lon = ALPHA_M001_LATEST_GPS.get("longitude") if preserve_hardware_fix else None
    saved_alt = ALPHA_M001_LATEST_GPS.get("altitude_m") if preserve_hardware_fix else None
    saved_acc = ALPHA_M001_LATEST_GPS.get("accuracy_m") if preserve_hardware_fix else None
    saved_spd = ALPHA_M001_LATEST_GPS.get("speed_mps") if preserve_hardware_fix else None
    saved_ts = ALPHA_M001_LATEST_GPS.get("gps_timestamp") if preserve_hardware_fix else None
    saved_dt = ALPHA_M001_LATEST_GPS.get("latest_gps_dt") if preserve_hardware_fix else None

    ALPHA_M001_LATEST_GPS.update({
        "latitude": saved_lat,
        "longitude": saved_lon,
        "altitude_m": saved_alt,
        "accuracy_m": saved_acc,
        "speed_mps": saved_spd,
        "heading_deg": None,
        "gps_timestamp": saved_ts,
        "latest_gps_dt": saved_dt,
        "gps_status": "WAITING_FOR_PERMISSION" if (new_command_id and not saved_lat) else ("TRACKING" if saved_lat else "STANDBY"),
        "location_source": "PHONE_GPS",
        "navigation_status": "ON_TRACK" if new_command_id else None,
        "target_bearing_deg": None,
        "heading_difference_deg": None,
        "direction_delta_deg": None,
        "distance_to_target_m": None,
        "distance_trend": "STABLE",
        "direction_guidance": None,
        "arrived_at": None,
        "is_arrived": False,
        "active_command_id": new_command_id,
        "assigned_victim_id": new_victim_id,
    })

    ALPHA_M001_NAV_STATE.update({
        "consecutive_wrong_samples": 0,
        "last_direction_alert_time": 0.0,
        "previous_coord": None,
        "previous_coord_time": 0.0,
        "previous_distance_m": None,
        "navigation_status": "ON_TRACK" if new_command_id else None,
        "target_bearing_deg": None,
        "heading_difference_deg": None,
        "direction_delta_deg": None,
        "distance_to_target_m": None,
        "distance_trend": "STABLE",
        "direction_guidance": None,
        "arrived_at": None,
        "is_arrived": False,
        "active_command_id": new_command_id,
        "assigned_victim_id": new_victim_id,
    })


def reset_alpha_m001_telemetry():
    """Resets Alpha Member 1 authoritative GPS and navigation state dictionaries."""
    ALPHA_M001_LATEST_GPS.clear()
    ALPHA_M001_LATEST_GPS.update({
        "latitude": None,
        "longitude": None,
        "altitude_m": None,
        "accuracy_m": None,
        "speed_mps": None,
        "heading_deg": None,
        "gps_timestamp": None,
        "latest_gps_dt": None,
        "gps_status": "STANDBY",
        "location_source": "PHONE_GPS",
        "navigation_status": None,
        "target_bearing_deg": None,
        "heading_difference_deg": None,
        "direction_delta_deg": None,
        "distance_to_target_m": None,
        "distance_trend": "STABLE",
        "direction_guidance": None,
        "arrived_at": None,
        "is_arrived": False,
        "active_command_id": None,
        "assigned_victim_id": None,
    })
    ALPHA_M001_NAV_STATE.clear()
    ALPHA_M001_NAV_STATE.update({
        "consecutive_wrong_samples": 0,
        "last_direction_alert_time": 0.0,
        "previous_coord": None,
        "previous_coord_time": 0.0,
        "previous_distance_m": None,
        "navigation_status": None,
        "target_bearing_deg": None,
        "heading_difference_deg": None,
        "direction_delta_deg": None,
        "distance_to_target_m": None,
        "distance_trend": "STABLE",
        "direction_guidance": None,
        "arrived_at": None,
        "is_arrived": False,
        "active_command_id": None,
        "assigned_victim_id": None,
    })
    try:
        if hasattr(global_wearable_gateway, "active_commands"):
            global_wearable_gateway.active_commands.clear()
    except Exception:
        pass


def calculate_angular_difference(heading_deg: float, target_bearing_deg: float) -> float:
    """Calculates the smallest angular difference (0 to 180 degrees) between movement heading and target bearing."""
    diff = (target_bearing_deg - heading_deg + 180.0) % 360.0 - 180.0
    return abs(diff)


def calculate_direction_guidance(heading_deg: float, target_bearing_deg: float) -> tuple[str, float]:
    """
    Computes human-readable turn guidance based on relative angle between movement heading and target bearing.
    Returns (guidance_string, angular_delta_degrees).
    """
    delta = (target_bearing_deg - heading_deg + 180.0) % 360.0 - 180.0
    abs_delta = abs(delta)
    if abs_delta <= DIRECTION_TOLERANCE_DEGREES:
        return ("Continue straight toward survivor", abs_delta)
    elif abs_delta >= 135.0:
        return ("Turn around and head toward survivor", abs_delta)
    elif delta > 0:
        return ("Turn right toward survivor", abs_delta)
    else:
        return ("Turn left toward survivor", abs_delta)


def calculate_target_bearing(rescuer_lat: float, rescuer_lon: float, target_lat: float, target_lon: float) -> float:
    """Calculates the target bearing (0 to 360 degrees) from rescuer coordinates to target coordinates."""
    return _bearing_deg(GPSCoordinate(latitude=rescuer_lat, longitude=rescuer_lon), GPSCoordinate(latitude=target_lat, longitude=target_lon))


def calculate_distance_trend(
    current_distance_m: float,
    previous_distance_m: Optional[float],
    hysteresis_m: float = DISTANCE_TREND_HYSTERESIS_METERS,
) -> str:
    """
    Determines distance trend (APPROACHING, MOVING_AWAY, STABLE) between consecutive distance measurements.
    Uses hysteresis to prevent oscillating classification on minor GPS noise.
    """
    if previous_distance_m is None:
        return "STABLE"
    diff = previous_distance_m - current_distance_m
    if diff > hysteresis_m:
        return "APPROACHING"
    elif diff < -hysteresis_m:
        return "MOVING_AWAY"
    else:
        return "STABLE"


def send_direction_guidance_sms(
    member_id: str,
    team_id: str,
    command_id: str,
    victim_id: str,
    heading_deg: float,
    target_bearing_deg: float,
    guidance: str,
    distance_m: float,
    smsgate_only: bool = True,
    **kwargs,
) -> Optional[dict]:
    """
    Dispatches wrong-direction guidance SMS exclusively via SMSGate using existing dynamic contact resolution.
    Never hardcodes private phone numbers.
    """
    try:
        dispatch_smsgate_sms = None
        for mod_name in ("notification_dispatch", "backend.notification_dispatch"):
            m = sys.modules.get(mod_name)
            if m and hasattr(m, "dispatch_smsgate_sms"):
                fn = getattr(m, "dispatch_smsgate_sms")
                if hasattr(fn, "mock_calls") or hasattr(fn, "assert_called"):
                    dispatch_smsgate_sms = fn
                    break
        if dispatch_smsgate_sms is None:
            try:
                from notification_dispatch import dispatch_smsgate_sms
            except ImportError:
                from backend.notification_dispatch import dispatch_smsgate_sms

        contact = db.resolve_member_contact_info(member_id, team_id=team_id)
        phone = contact.get("phone_normalized")
        if not phone:
            logger.warning(f"[DIRECTION_SMS] No recipient phone resolved for {member_id}")
            return None

        sms_body = (
            f"RIDGEWATCH RESCUE GUIDANCE\n"
            f"Command: {command_id}\n"
            f"Target: {victim_id}\n"
            f"Status: WRONG DIRECTION\n"
            f"Current heading: {round(heading_deg)}°\n"
            f"Target bearing: {round(target_bearing_deg)}°\n"
            f"Guidance: {guidance.upper()}\n"
            f"Distance: approx {round(distance_m)} m"
        )

        res = dispatch_smsgate_sms(
            phone_normalized=phone,
            message_text=sms_body,
            rescue_command_id=command_id,
        )
        logger.info(f"[DIRECTION_SMS] Dispatched SMSGate guidance for {command_id}: status={res.get('status')}")
        return res
    except Exception as ex:
        logger.warning(f"[DIRECTION_SMS] Failed to dispatch guidance SMS: {ex}")
        return None


def _bearing_deg(a: GPSCoordinate, b: GPSCoordinate) -> float:
    lat1, lon1 = math.radians(a.latitude), math.radians(a.longitude)
    lat2, lon2 = math.radians(b.latitude), math.radians(b.longitude)
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


_COMPASS_POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _compass_label(bearing_deg: float) -> str:
    index = round(bearing_deg / 45.0) % 8
    return _COMPASS_POINTS[index]


def _move_along_bearing(loc: GPSCoordinate, bearing_deg: float, distance_m: float) -> GPSCoordinate:
    lat1 = math.radians(loc.latitude)
    lon1 = math.radians(loc.longitude)
    brg = math.radians(bearing_deg)
    ang_dist = distance_m / EARTH_RADIUS_M

    lat2 = math.asin(math.sin(lat1) * math.cos(ang_dist) + math.cos(lat1) * math.sin(ang_dist) * math.cos(brg))
    lon2 = lon1 + math.atan2(
        math.sin(brg) * math.sin(ang_dist) * math.cos(lat1),
        math.cos(ang_dist) - math.sin(lat1) * math.sin(lat2),
    )
    return GPSCoordinate(latitude=math.degrees(lat2), longitude=math.degrees(lon2), altitude_m=loc.altitude_m)


# --------------------------------------------------------------------------- #
# In-memory scenario state
# --------------------------------------------------------------------------- #

class ScenarioState:
    simulator: Any = None
    config: Any = None
    latest_assessment: Any = None

    def __init__(self):
        self.simulator: Any = None
        self.running: bool = False
        self.started_at: Optional[str] = None
        self.cycle_count: int = 0
        self.history: dict = defaultdict(lambda: deque(maxlen=HISTORY_MAXLEN))
        self.config: Any = None
        self.rescue_teams: list = []
        self.team_members: dict = {}   # team_id -> list[TeamMember], the tracked sample
        self.recent_member_arrivals: list = []
        self.dispatch_agent: RescueDispatchAgent = RescueDispatchAgent()
        self.alert_dispatcher: NetworkAlertDispatcher = NetworkAlertDispatcher()
        self.session_id: Optional[str] = None
        self.custom_operational_events: list = []
        self.intelligence_engine: ScenarioIntelligenceEngine = ScenarioIntelligenceEngine()
        self.latest_assessment: Any = None
        self.lock = asyncio.Lock()

    def _default_teams(self, config: ScenarioConfig) -> list:
        origin = config.site_origin
        return [
            RescueTeamStatus(
                team_id=t.team_id,
                team_name=t.team_name,
                location=GPSCoordinate(
                    latitude=origin.latitude + t.lat_offset,
                    longitude=origin.longitude + t.lon_offset,
                    altitude_m=origin.altitude_m,
                ),
                availability=TeamAvailability.AVAILABLE,
                members=t.members,
            )
            for t in config.rescue_team_templates
        ]

    def _spawn_tracked_members(self, team: RescueTeamStatus, count: int) -> list:
        rng = random.Random(f"{team.team_id}:{count}")
        members = []
        default_scenarios = [
            "earthquake", "avalanche", "flood", "building_collapse", "landslide",
            "wildfire", "chemical_leak", "tsunami", "cyclone", "urban_fire",
            "industrial_accident", "dam_failure", "drought", "heatwave",
            "cloudburst", "stampede", "transport_accident", "infrastructure_entrapment", "multi_hazard"
        ]

        for i in range(count):
            lat_jitter = rng.uniform(-0.0003, 0.0003)
            lon_jitter = rng.uniform(-0.0003, 0.0003)
            full_name = f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"
            members.append(TeamMember(
                member_id=f"{team.team_id}-M{i + 1:03d}",
                callsign=f"{team.team_name} #{i + 1}",
                team_id=team.team_id,
                full_name=full_name,
                role="Leader" if i == 0 else "Rescuer",
                location=GPSCoordinate(
                    latitude=team.location.latitude + lat_jitter,
                    longitude=team.location.longitude + lon_jitter,
                    altitude_m=team.location.altitude_m,
                ),
                scenarios=list(default_scenarios),
            ))
        return members

    def resize_team_roster(self, team_id: str, new_member_count: int) -> RescueTeamStatus:
        team = next((t for t in self.rescue_teams if t.team_id == team_id), None)
        if team is None:
            raise ValueError(f"Unknown team_id '{team_id}'")
        if new_member_count < 0:
            raise ValueError("member count cannot be negative")

        target_tracked = min(new_member_count, TRACKED_MEMBER_SAMPLE_SIZE)
        current = self.team_members.get(team_id, [])

        if target_tracked < len(current):
            droppable = [m for m in current if m.status == MemberStatus.HOLD]
            to_drop = len(current) - target_tracked
            if len(droppable) < to_drop:
                raise ValueError(
                    f"Cannot shrink tracked roster below {len(current) - len(droppable)} members - "
                    f"{len(current) - len(droppable)} are currently EN_ROUTE/ARRIVED. Wait for them to resolve."
                )
            non_hold = [m for m in current if m.status != MemberStatus.HOLD]
            hold = [m for m in current if m.status == MemberStatus.HOLD]
            self.team_members[team_id] = non_hold + hold[: max(0, target_tracked - len(non_hold))]
        elif target_tracked > len(current):
            additional = self._spawn_tracked_members(team, target_tracked - len(current))
            for offset, m in enumerate(additional):
                m.member_id = f"{team_id}-M{len(current) + offset + 1:03d}"
                m.callsign = f"{team.team_name} #{len(current) + offset + 1}"
            self.team_members[team_id] = current + additional

        team.members = new_member_count
        return team

    def register_team_from_db(self, team_ref_id: str) -> Optional[RescueTeamStatus]:
        """Dynamically register a team from the admin_teams database into this active operation."""
        team_data = db.get_admin_team(team_ref_id)
        if not team_data or not self.config:
            return None
        origin = self.config.site_origin
        team_id = team_data["team_ref_id"]
        team_name = team_data["team_name"]

        # Calculate a deterministic spatial offset around the disaster origin
        offset_idx = len(self.rescue_teams) + 1
        lat_offset = -0.0003 * (offset_idx % 3 + 1)
        lon_offset = 0.0003 * ((offset_idx // 3) % 3 + 1)

        personnel_members = team_data.get("members", [])
        members_count = len(personnel_members) if personnel_members else 2
        team_status = next((t for t in self.rescue_teams if t.team_id == team_id), None)
        if not team_status:
            team_status = RescueTeamStatus(
                team_id=team_id,
                team_name=team_name,
                location=GPSCoordinate(
                    latitude=origin.latitude + lat_offset,
                    longitude=origin.longitude + lon_offset,
                    altitude_m=origin.altitude_m,
                ),
                availability=TeamAvailability.AVAILABLE,
                members=members_count,
            )
            self.rescue_teams.append(team_status)
        else:
            team_status.members = members_count

        if personnel_members:
            rng = random.Random(f"{team_id}:{len(personnel_members)}")
            members = []
            for i, p in enumerate(personnel_members):
                lat_jitter = rng.uniform(-0.0003, 0.0003)
                lon_jitter = rng.uniform(-0.0003, 0.0003)
                m_id = f"{team_id}-M{i + 1:03d}"
                full_name = p.get("full_name") or f"Rescuer {i + 1}"
                role = p.get("role_on_team") or ("Leader" if i == 0 else "Rescuer")
                p_scenarios = p.get("scenarios")
                if not p_scenarios and p.get("person_id"):
                    p_db = db.get_personnel(p.get("person_id"))
                    if p_db:
                        p_scenarios = p_db.get("scenarios")
                if not p_scenarios:
                    p_scenarios = ["earthquake", "building_collapse"]

                members.append(TeamMember(
                    member_id=m_id,
                    callsign=f"{team_name} - {full_name}",
                    team_id=team_id,
                    full_name=full_name,
                    role=role,
                    personnel_id=p.get("person_id"),
                    location=GPSCoordinate(
                        latitude=team_status.location.latitude + lat_jitter,
                        longitude=team_status.location.longitude + lon_jitter,
                        altitude_m=team_status.location.altitude_m,
                    ),
                    scenarios=list(p_scenarios),
                ))
            self.team_members[team_id] = members
        else:
            self.team_members[team_id] = self._spawn_tracked_members(
                team_status, min(team_status.members, TRACKED_MEMBER_SAMPLE_SIZE)
            )

        if self.session_id:
            try:
                db.log_rescue_status_event(
                    session_id=self.session_id,
                    event_type="team_activated",
                    team_id=team_id,
                    notes=f"Rescue team '{team_name}' ({team_id}) activated for operations.",
                )
            except Exception:
                pass
        return team_status

    def advance_team_members(self) -> list:
        if not self.config or not self.config.victims:
            return []
        victim_locations = {v.victim_id: v.location for v in self.config.victims}
        newly_arrived = []

        for members in self.team_members.values():
            for m in members:
                if m.status != MemberStatus.EN_ROUTE or not m.assigned_victim_id:
                    continue
                target_loc = victim_locations.get(m.assigned_victim_id)
                if target_loc is None:
                    continue

                # Stage 3, 4 & 5 Real GPS Authority vs Simulation Isolation:
                # Alpha Member 1 only gets real GPS tracking; when active or stale, no synthetic movement is applied.
                if m.member_id == "ALPHA-M001":
                    has_real_gps = (
                        ALPHA_M001_LATEST_GPS.get("latitude") is not None
                        and ALPHA_M001_LATEST_GPS.get("longitude") is not None
                        and (m.location_source == "PHONE_GPS" or ALPHA_M001_LATEST_GPS.get("location_source") == "PHONE_GPS")
                    )
                    if has_real_gps:
                        m.location = GPSCoordinate(
                            latitude=ALPHA_M001_LATEST_GPS["latitude"],
                            longitude=ALPHA_M001_LATEST_GPS["longitude"],
                            altitude_m=ALPHA_M001_LATEST_GPS.get("altitude_m") if ALPHA_M001_LATEST_GPS.get("altitude_m") is not None else m.location.altitude_m,
                        )
                        m.location_source = "PHONE_GPS"
                        if ALPHA_M001_LATEST_GPS.get("accuracy_m") is not None:
                            m.accuracy_m = ALPHA_M001_LATEST_GPS["accuracy_m"]
                        if ALPHA_M001_LATEST_GPS.get("speed_mps") is not None:
                            m.speed_mps = ALPHA_M001_LATEST_GPS["speed_mps"]
                        if ALPHA_M001_LATEST_GPS.get("heading_deg") is not None:
                            m.heading_deg = ALPHA_M001_LATEST_GPS["heading_deg"]
                        if ALPHA_M001_LATEST_GPS.get("gps_timestamp") is not None:
                            m.gps_timestamp = ALPHA_M001_LATEST_GPS["gps_timestamp"]
                        if ALPHA_M001_LATEST_GPS.get("gps_status") is not None:
                            m.gps_status = ALPHA_M001_LATEST_GPS["gps_status"]
                        if ALPHA_M001_LATEST_GPS.get("navigation_status") is not None:
                            m.navigation_status = ALPHA_M001_LATEST_GPS["navigation_status"]
                        if ALPHA_M001_LATEST_GPS.get("target_bearing_deg") is not None:
                            m.target_bearing_deg = ALPHA_M001_LATEST_GPS["target_bearing_deg"]
                        if ALPHA_M001_LATEST_GPS.get("heading_difference_deg") is not None:
                            m.heading_difference_deg = ALPHA_M001_LATEST_GPS["heading_difference_deg"]
                        if ALPHA_M001_LATEST_GPS.get("direction_delta_deg") is not None:
                            m.direction_delta_deg = ALPHA_M001_LATEST_GPS["direction_delta_deg"]
                        if ALPHA_M001_LATEST_GPS.get("distance_trend") is not None:
                            m.distance_trend = ALPHA_M001_LATEST_GPS["distance_trend"]
                        if ALPHA_M001_LATEST_GPS.get("direction_guidance") is not None:
                            m.direction_guidance = ALPHA_M001_LATEST_GPS["direction_guidance"]
                        if ALPHA_M001_LATEST_GPS.get("arrived_at") is not None:
                            m.arrived_at = ALPHA_M001_LATEST_GPS["arrived_at"]

                        # Check stale condition if currently TRACKING
                        effective_ts = m.gps_timestamp or ALPHA_M001_LATEST_GPS.get("gps_timestamp")
                        if m.gps_status == "TRACKING" and effective_ts:
                            try:
                                ts = datetime.fromisoformat(effective_ts.replace("Z", "+00:00"))
                                age = (datetime.now(timezone.utc) - ts).total_seconds()
                                if age > GPS_STALE_THRESHOLD_SECONDS:
                                    m.gps_status = "STALE"
                                    ALPHA_M001_LATEST_GPS["gps_status"] = "STALE"
                                    if m.navigation_status != "ARRIVED":
                                        m.navigation_status = "STALE"
                                        ALPHA_M001_LATEST_GPS["navigation_status"] = "STALE"
                                        ALPHA_M001_NAV_STATE["navigation_status"] = "STALE"
                            except Exception:
                                pass

                        # Continuously calculate distance to target for Alpha Member 1
                        distance_m = haversine_distance_m(m.location, target_loc)
                        m.distance_to_target_m = round(distance_m, 1)
                        ALPHA_M001_LATEST_GPS["distance_to_target_m"] = round(distance_m, 1)
                        ALPHA_M001_NAV_STATE["distance_to_target_m"] = round(distance_m, 1)

                        # Check arrival radius (15.0m) - do NOT mark arrived from stale or unavailable GPS
                        if m.gps_status not in ("STALE", "GPS_UNAVAILABLE") and distance_m <= GPS_ARRIVAL_DISTANCE_METERS and m.status != MemberStatus.ARRIVED:
                            m.status = MemberStatus.ARRIVED
                            now_iso = datetime.now(timezone.utc).isoformat()
                            m.arrived_at = now_iso
                            m.navigation_status = "ARRIVED"
                            m.direction_guidance = "Arrived at survivor location"
                            m.distance_trend = "STABLE"
                            m.last_updated = now_iso
                            ALPHA_M001_LATEST_GPS["navigation_status"] = "ARRIVED"
                            ALPHA_M001_LATEST_GPS["arrived_at"] = now_iso
                            ALPHA_M001_LATEST_GPS["direction_guidance"] = "Arrived at survivor location"
                            ALPHA_M001_LATEST_GPS["distance_trend"] = "STABLE"
                            ALPHA_M001_LATEST_GPS["is_arrived"] = True
                            ALPHA_M001_NAV_STATE["navigation_status"] = "ARRIVED"
                            ALPHA_M001_NAV_STATE["arrived_at"] = now_iso
                            ALPHA_M001_NAV_STATE["direction_guidance"] = "Arrived at survivor location"
                            ALPHA_M001_NAV_STATE["distance_trend"] = "STABLE"
                            ALPHA_M001_NAV_STATE["is_arrived"] = True
                            ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] = 0
                            newly_arrived.append(m)
                            self.recent_member_arrivals.append({
                                "member_id": m.member_id,
                                "callsign": m.callsign,
                                "victim_id": m.assigned_victim_id,
                                "arrived_at": now_iso,
                            })
                            self.recent_member_arrivals = self.recent_member_arrivals[-MAX_RECENT_ARRIVALS:]
                            # Update active command in DB if present
                            try:
                                cmds = db.list_rescue_commands(member_id=m.member_id, limit=1)
                                if cmds:
                                    cmd_id = cmds[0]["command_id"]
                                    db.update_rescue_command_status(cmd_id, status="ARRIVED")
                                    db.update_rescue_command_navigation(
                                        cmd_id,
                                        navigation_status="ARRIVED",
                                        distance_to_target_m=round(distance_m, 1),
                                        direction_guidance="Arrived at survivor location",
                                        arrived_at=now_iso,
                                    )
                            except Exception:
                                pass

                        # Alpha Member 1 in real GPS mode: DO NOT apply synthetic movement!
                        # Preserve last known real location; do not fabricate coordinates.
                        continue

                # Simulated members (Alpha Member 2, Bravo 1, Bravo 2) continue synthetic movement
                distance_m = haversine_distance_m(m.location, target_loc)
                if distance_m <= MEMBER_ARRIVAL_THRESHOLD_M:
                    m.status = MemberStatus.ARRIVED
                    m.last_updated = datetime.now(timezone.utc).isoformat()
                    newly_arrived.append(m)
                    self.recent_member_arrivals.append({
                        "member_id": m.member_id,
                        "callsign": m.callsign,
                        "victim_id": m.assigned_victim_id,
                        "arrived_at": m.last_updated,
                    })
                    self.recent_member_arrivals = self.recent_member_arrivals[-MAX_RECENT_ARRIVALS:]
                    continue

                step_m = min(MEMBER_WALK_SPEED_MPS * SECONDS_PER_COMMANDER_POLL, distance_m)
                bearing = _bearing_deg(m.location, target_loc)
                m.location = _move_along_bearing(m.location, bearing, step_m)
                m.last_updated = datetime.now(timezone.utc).isoformat()

        return newly_arrived

    def start(
        self,
        scenario_id: str = DEFAULT_SCENARIO_ID,
        seed: Optional[int] = None,
        enable_degradation: bool = True,
        enable_solar_charging: bool = False,
        custom_config: Optional[ScenarioConfig] = None,
    ):
        config = custom_config if custom_config is not None else scenario_loader.load_scenario(scenario_id)

        enable_water_sensor = any(
            v.initial_water_level_cm > 0 or v.water_rising_rate_cm_per_cycle > 0
            for v in config.victims
        )
        enable_water_flow_sensor = any(
            v.initial_water_flow_ms > 0 for v in config.victims
        )

        self.config = config
        self.simulator = SensorSimulator(
            config.victims,
            seed=seed,
            enable_degradation=enable_degradation,
            enable_water_sensor=enable_water_sensor,
            enable_water_flow_sensor=enable_water_flow_sensor,
            enable_solar_charging=enable_solar_charging,
            site_environment=config.site_environment,
            scenario_id=config.scenario_id,
        )
        self.running = True
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.cycle_count = 0
        self.history = defaultdict(lambda: deque(maxlen=HISTORY_MAXLEN))
        self.rescue_teams = self._default_teams(config)
        self.team_members = {
            t.team_id: self._spawn_tracked_members(t, min(t.members, TRACKED_MEMBER_SAMPLE_SIZE))
            for t in self.rescue_teams
        }
        # Apply cached real GPS location for ALPHA-M001 if available
        if "ALPHA" in self.team_members and ALPHA_M001_LATEST_GPS.get("latitude") is not None:
            for m in self.team_members["ALPHA"]:
                if m.member_id == "ALPHA-M001":
                    m.location = GPSCoordinate(
                        latitude=ALPHA_M001_LATEST_GPS["latitude"],
                        longitude=ALPHA_M001_LATEST_GPS["longitude"],
                        altitude_m=ALPHA_M001_LATEST_GPS["altitude_m"] or m.location.altitude_m,
                    )
                    m.location_source = ALPHA_M001_LATEST_GPS.get("location_source", "PHONE_GPS")
                    m.accuracy_m = ALPHA_M001_LATEST_GPS.get("accuracy_m")
                    m.speed_mps = ALPHA_M001_LATEST_GPS.get("speed_mps")
                    m.heading_deg = ALPHA_M001_LATEST_GPS.get("heading_deg")
                    m.gps_timestamp = ALPHA_M001_LATEST_GPS.get("gps_timestamp")
                    m.gps_status = ALPHA_M001_LATEST_GPS.get("gps_status", "TRACKING")
                    m.navigation_status = ALPHA_M001_LATEST_GPS.get("navigation_status")
                    m.target_bearing_deg = ALPHA_M001_LATEST_GPS.get("target_bearing_deg")
                    m.direction_delta_deg = ALPHA_M001_LATEST_GPS.get("direction_delta_deg")
                    m.distance_to_target_m = ALPHA_M001_LATEST_GPS.get("distance_to_target_m")
                    m.direction_guidance = ALPHA_M001_LATEST_GPS.get("direction_guidance")
                    m.arrived_at = ALPHA_M001_LATEST_GPS.get("arrived_at")
        # Dynamically load and activate all teams registered in the database
        for admin_team in db.list_admin_teams():
            self.register_team_from_db(admin_team["team_ref_id"])

        self.dispatch_agent = RescueDispatchAgent(position=config.site_origin)
        self.alert_dispatcher = NetworkAlertDispatcher(seed=seed)

        self.session_id = str(uuid.uuid4())
        db.create_session(
            session_id=self.session_id,
            seed=seed,
            enable_degradation=enable_degradation,
            victim_count=config.victim_count,
            started_at=self.started_at,
            scenario_id=config.scenario_id,
            scenario_name=config.name,
        )

    def reset(self):
        self.simulator = None
        self.running = False
        self.started_at = None
        reset_alpha_m001_telemetry()
        self.cycle_count = 0
        self.history = defaultdict(lambda: deque(maxlen=HISTORY_MAXLEN))
        self.config = None
        self.rescue_teams = []
        self.team_members = {}
        self.recent_member_arrivals = []
        self.dispatch_agent = RescueDispatchAgent()
        self.alert_dispatcher = NetworkAlertDispatcher()
        self.session_id = None
        self.custom_operational_events = []
        self.intelligence_engine.reset()
        self.latest_assessment = None

    def tick(self):
        if not self.running or self.simulator is None:
            raise RuntimeError("Scenario is not running. Call POST /scenario/start first.")
        
        # 1. Generate survivor and environmental readings
        raw_victim_readings = self.simulator.generate_cycle()
        raw_env_readings = self.simulator.generate_environmental_readings()
        self.cycle_count += 1

        # 2. Validation and filtering stage (quarantine invalid readings)
        valid_victim_readings = []
        for r in raw_victim_readings:
            valid, err = SensorValidator.validate_reading(r)
            if valid:
                valid_victim_readings.append(r)
                self.history[r.victim_id].append(r)
            else:
                if self.session_id:
                    db.log_rejected_reading(
                        RejectedSensorReading(
                            session_id=self.session_id,
                            cycle=self.cycle_count,
                            sensor_type=r.sensor_type.value if hasattr(r.sensor_type, "value") else str(r.sensor_type),
                            sensor_id=r.device_id,
                            device_id=r.device_id,
                            victim_id=r.victim_id,
                            attempted_value=r.value if isinstance(r.value, (int, float)) else None,
                            unit=r.unit,
                            rejection_reason=err or "Survivor reading physical validation failed",
                            raw_payload=r.to_dict() if hasattr(r, "to_dict") else vars(r),
                        )
                    )

        valid_env_readings = []
        for r in raw_env_readings:
            valid, err = SensorValidator.validate_reading(r)
            if valid:
                valid_env_readings.append(r)
            else:
                if self.session_id:
                    db.log_rejected_reading(
                        RejectedSensorReading(
                            session_id=self.session_id,
                            cycle=self.cycle_count,
                            sensor_type=r.sensor_type.value if hasattr(r.sensor_type, "value") else str(r.sensor_type),
                            sensor_id=r.device_id,
                            device_id=r.device_id,
                            victim_id=r.victim_id,
                            attempted_value=r.value if isinstance(r.value, (int, float)) else None,
                            unit=r.unit,
                            rejection_reason=err or "Environmental reading physical validation failed",
                            raw_payload=r.to_dict() if hasattr(r, "to_dict") else vars(r),
                        )
                    )

        # 3. Scenario Intelligence and inference processing with verified readings
        all_valid_readings = list(valid_victim_readings) + valid_env_readings
        env_report = self.simulator.environmental_full_report()
        battery_map = self.simulator.battery_report()
        active_hint = self.config.scenario_id if self.config else None

        self.latest_assessment = self.intelligence_engine.process_cycle(
            session_id=self.session_id or "default-session",
            cycle=self.cycle_count,
            readings=all_valid_readings,
            env_report=env_report,
            battery_map=battery_map,
            active_scenario_hint=active_hint,
        )

        # 4. Multi-channel database persistence
        if self.session_id:
            fusion_results = self.fuse_current()
            db.log_detection_cycle(
                session_id=self.session_id,
                cycle=self.cycle_count,
                readings=all_valid_readings,
                fusion_results_by_victim=fusion_results,
            )

            # Persist Optical RGB Camera Telemetry
            cam_readings = self.simulator.generate_camera_readings() if self.simulator else []
            for cr in cam_readings:
                if cr.validate():
                    db.log_camera_reading(cr, session_id=self.session_id, cycle=self.cycle_count)
                else:
                    db.log_rejected_reading(
                        RejectedSensorReading(
                            session_id=self.session_id,
                            cycle=self.cycle_count,
                            sensor_type="camera",
                            sensor_id=cr.camera_id,
                            device_id=cr.device_id,
                            victim_id=cr.victim_id,
                            rejection_reason="Camera reading failed physical validation",
                            raw_payload=cr.to_dict() if hasattr(cr, "to_dict") else vars(cr),
                        )
                    )

            # Persist Thermal Infrared Camera Telemetry
            thm_readings = self.simulator.generate_thermal_readings() if self.simulator else []
            for tr in thm_readings:
                if tr.validate():
                    db.log_thermal_reading(tr, session_id=self.session_id, cycle=self.cycle_count)
                else:
                    db.log_rejected_reading(
                        RejectedSensorReading(
                            session_id=self.session_id,
                            cycle=self.cycle_count,
                            sensor_type="thermal_camera",
                            sensor_id=tr.camera_id,
                            device_id=tr.device_id,
                            victim_id=tr.victim_id,
                            rejection_reason="Thermal reading failed physical validation",
                            raw_payload=tr.to_dict() if hasattr(tr, "to_dict") else vars(tr),
                        )
                    )

            # Persist Gas/Smoke Reading to dedicated table
            gs_readings = self.simulator.generate_gas_smoke_readings() if self.simulator else []
            for gsr in gs_readings:
                if gsr.validate():
                    db.log_gas_smoke_reading(gsr, session_id=self.session_id)
                else:
                    db.log_rejected_reading(
                        RejectedSensorReading(
                            session_id=self.session_id,
                            cycle=self.cycle_count,
                            sensor_type="gas_smoke",
                            sensor_id=gsr.sensor_id,
                            device_id=gsr.device_id,
                            rejection_reason="Gas/smoke reading failed physical validation",
                            raw_payload=gsr.to_dict() if hasattr(gsr, "to_dict") else vars(gsr),
                        )
                    )

            # Persist Barometric Pressure Reading to dedicated table
            baro_readings = self.simulator.generate_barometric_readings() if self.simulator else []
            for baro in baro_readings:
                if baro.validate():
                    db.log_barometric_reading(baro, session_id=self.session_id)
                else:
                    db.log_rejected_reading(
                        RejectedSensorReading(
                            session_id=self.session_id,
                            cycle=self.cycle_count,
                            sensor_type="barometric_pressure",
                            sensor_id=baro.sensor_id,
                            device_id=baro.device_id,
                            rejection_reason="Barometric reading failed physical validation",
                            raw_payload=baro.to_dict() if hasattr(baro, "to_dict") else vars(baro),
                        )
                    )

            # Persist Landslide / Soil Moisture / Tilt Readings to dedicated table
            ls_readings = self.simulator.generate_landslide_readings() if self.simulator else []
            for lsr in ls_readings:
                if lsr.validate():
                    db.log_landslide_reading(lsr, session_id=self.session_id)
                else:
                    db.log_rejected_reading(
                        RejectedSensorReading(
                            session_id=self.session_id,
                            cycle=self.cycle_count,
                            sensor_type="landslide",
                            sensor_id=lsr.node_id,
                            device_id=getattr(lsr, "device_id", "DEV-SLOPE-01"),
                            rejection_reason="Landslide assessment failed physical validation",
                            raw_payload=lsr.to_dict() if hasattr(lsr, "to_dict") else vars(lsr),
                        )
                    )

            # Persist Rainfall Reading to dedicated table
            rain_readings = self.simulator.generate_rainfall_readings() if self.simulator else []
            for rnr in rain_readings:
                if rnr.validate():
                    db.log_rainfall_reading(rnr, session_id=self.session_id, cycle=self.cycle_count)
                else:
                    db.log_rejected_reading(
                        RejectedSensorReading(
                            session_id=self.session_id,
                            cycle=self.cycle_count,
                            sensor_type="rainfall",
                            sensor_id=rnr.sensor_id,
                            device_id=rnr.device_id,
                            rejection_reason="Rainfall reading failed physical validation",
                            raw_payload=rnr.to_dict() if hasattr(rnr, "to_dict") else vars(rnr),
                        )
                    )

            # Persist Temperature Reading to dedicated table
            temp_readings = self.simulator.generate_temperature_readings() if self.simulator else []
            for tmpr in temp_readings:
                if tmpr.validate():
                    db.log_temperature_reading(tmpr, session_id=self.session_id, cycle=self.cycle_count)
                else:
                    db.log_rejected_reading(
                        RejectedSensorReading(
                            session_id=self.session_id,
                            cycle=self.cycle_count,
                            sensor_type="temperature",
                            sensor_id=tmpr.sensor_id,
                            device_id=tmpr.device_id,
                            rejection_reason="Temperature reading failed physical validation",
                            raw_payload=tmpr.to_dict() if hasattr(tmpr, "to_dict") else vars(tmpr),
                        )
                    )

            # Persist Humidity Reading to dedicated table
            humid_readings = self.simulator.generate_humidity_readings() if self.simulator else []
            for hmdr in humid_readings:
                if hmdr.validate():
                    db.log_humidity_reading(hmdr, session_id=self.session_id, cycle=self.cycle_count)
                else:
                    db.log_rejected_reading(
                        RejectedSensorReading(
                            session_id=self.session_id,
                            cycle=self.cycle_count,
                            sensor_type="humidity",
                            sensor_id=hmdr.sensor_id,
                            device_id=hmdr.device_id,
                            rejection_reason="Humidity reading failed physical validation",
                            raw_payload=hmdr.to_dict() if hasattr(hmdr, "to_dict") else vars(hmdr),
                        )
                    )

            # Persist GPS Reading to dedicated table
            gps_readings = self.simulator.generate_gps_readings() if self.simulator else []
            for gps_r in gps_readings:
                if gps_r.validate():
                    db.log_gps_reading(gps_r, session_id=self.session_id, cycle=self.cycle_count)
                else:
                    db.log_rejected_reading(
                        RejectedSensorReading(
                            session_id=self.session_id,
                            cycle=self.cycle_count,
                            sensor_type="gps",
                            sensor_id=gps_r.sensor_id,
                            device_id=gps_r.device_id,
                            rejection_reason="GPS reading failed physical validation",
                            raw_payload=gps_r.to_dict() if hasattr(gps_r, "to_dict") else vars(gps_r),
                        )
                    )

            # Persist Sensor Health batch
            health_records = self.simulator.get_sensor_health_report() if self.simulator else []
            db.log_sensor_health_batch(health_records, session_id=self.session_id, cycle=self.cycle_count)

            # Persist Sensor Trends batch
            trends = getattr(self.intelligence_engine, "latest_trends", [])
            if trends:
                db.log_sensor_trends_batch(trends, session_id=self.session_id, cycle=self.cycle_count)

    def current_readings_by_victim(self) -> dict:
        return {vid: list(buf) for vid, buf in self.history.items()}

    def _live_hazard_by_victim(self) -> dict:
        base_hazards = self.config.hazards if self.config else {}
        water_now = self.simulator.water_report() if self.simulator else {}
        water_flow_now = self.simulator.water_flow_report() if self.simulator else {}
        rain_now = self.simulator.rain_report() if self.simulator else {}
        soil_now = self.simulator.soil_report() if self.simulator else {}
        seismic_now = self.simulator.seismic_report() if self.simulator else {}
        tilt_now = self.simulator.tilt_report() if self.simulator else {}
        temp_now = self.simulator.temperature_report() if self.simulator else {}
        humidity_now = self.simulator.humidity_report() if self.simulator else {}
        pressure_now = self.simulator.barometric_pressure_report() if self.simulator else {}
        imu_now = self.simulator.imu_report() if self.simulator else {}
        live_hazards = {}
        for vid, hazard in base_hazards.items():
            node = self.simulator.nodes.get(vid) if self.simulator else None
            rising_rate = node.victim.water_rising_rate_cm_per_cycle if node else 0.0
            live_hazards[vid] = _dataclass_replace(
                hazard,
                water_level_cm=water_now.get(vid, hazard.water_level_cm),
                water_rising_rate_cm_per_cycle=rising_rate,
                water_flow_ms=water_flow_now.get(vid, hazard.water_flow_ms),
                rainfall_mm_hr=rain_now.get("rainfall_mm_hr", hazard.rainfall_mm_hr),
                soil_moisture_pct=soil_now.get("soil_moisture_pct", hazard.soil_moisture_pct),
                vibration_mm_s=seismic_now.get("vibration_mm_s", hazard.vibration_mm_s),
                aftershock_active=seismic_now.get("aftershock_active", hazard.aftershock_active),
                tilt_deg=tilt_now.get("tilt_deg", hazard.tilt_deg),
                ambient_temp_c=temp_now.get("ambient_temp_c", hazard.ambient_temp_c),
                humidity_pct=humidity_now.get("humidity_pct", hazard.humidity_pct),
                barometric_pressure_hpa=pressure_now.get("pressure_hpa", getattr(hazard, "barometric_pressure_hpa", 1013.25)),
                kit_disturbed=imu_now.get(vid, {}).get("kit_disturbed", hazard.kit_disturbed),
            )
        return live_hazards

    def fuse_current(self) -> dict:
        readings_by_victim = self.current_readings_by_victim()
        if self.config and self.config.victims:
            for v in self.config.victims:
                readings_by_victim.setdefault(v.victim_id, [])
        return fuse_all(
            readings_by_victim,
            hazard_by_victim=self._live_hazard_by_victim(),
            scenario_id=self.config.scenario_id if self.config else None,
        )

    def _dispatch_alerts(self, ranked: list) -> list:
        new_alerts = []
        for r in ranked:
            if r.triage_class != TriageClass.HIGH:
                continue
            battery_pct = self.simulator.battery_report().get(r.victim_id, 100.0) if self.simulator else 100.0
            record = self.alert_dispatcher.send_alert(
                victim_id=r.victim_id,
                triage_class=r.triage_class.value,
                sps=r.sps,
                battery_pct=battery_pct,
                current_cycle=self.cycle_count,
            )
            if record is not None:
                new_alerts.append(record)
                if self.session_id:
                    db.log_network_alert(self.session_id, record.to_dict())
                    # Persist in active_alerts_ledger for continuous UI visibility
                    alert_key = f"SURVIVOR_{r.victim_id}"
                    db.upsert_active_alert(
                        alert_key=alert_key,
                        session_id=self.session_id,
                        hazard_type="SURVIVOR_DETECTED",
                        alert_title=f"🚨 High Priority Survivor: {r.victim_id}",
                        severity="HIGH",
                        confidence_pct=getattr(r, "confidence_pct", 90.0) or 90.0,
                        evidence_summary=f"Survival probability {r.sps:.1f}%. Immediate rescue dispatch required.",
                    )
                    # Parallel Real-Time Physical Watch Dispatch
                    try:
                        global_wearable_gateway.dispatch_alert_to_watch({
                            "alert_id": f"ALT-{r.victim_id}",
                            "command_id": f"CMD-{r.victim_id}",
                            "victim_id": r.victim_id,
                            "target_id": r.victim_id,
                            "priority": "HIGH",
                            "mission_id": self.session_id,
                            "location": f"Sector {r.victim_id}",
                            "command_type": "GO",
                            "command_text": f"High Priority Survivor Detected: {r.victim_id}",
                            "title": f"🚨 RESCUE ALERT — {r.victim_id}",
                            "body": f"Survivor {r.victim_id} detected with {r.sps:.0f}% survival probability.",
                        })
                    except Exception as ble_err:
                        logger.warning(f"Watch alert dispatch non-blocking notice: {ble_err}")
        return new_alerts

    def scenario_meta(self) -> dict:
        meta: dict[str, object] = {
            "session_id": self.session_id,
            "running": self.running,
            "started_at": self.started_at,
            "cycle": self.cycle_count,
            "victim_count": len(self.config.victims) if self.config else 0,
        }
        if self.config is not None:
            meta["scenario_id"] = self.config.scenario_id
            meta["scenario_name"] = self.config.name
            meta["site_label"] = self.config.site_label
            if getattr(self.config, "site_origin", None) is not None:
                origin = self.config.site_origin
                if hasattr(origin, "to_dict"):
                    meta["site_origin"] = origin.to_dict()
                elif isinstance(origin, dict):
                    meta["site_origin"] = origin
                else:
                    meta["site_origin"] = {
                        "latitude": getattr(origin, "latitude", 0.0),
                        "longitude": getattr(origin, "longitude", 0.0),
                        "altitude_m": getattr(origin, "altitude_m", None),
                    }
            profile = get_scenario_sensor_profile(self.config.scenario_id)
            if profile is not None:
                meta["sensor_profile"] = {
                    "primary_sensors": [s.value if hasattr(s, "value") else str(s) for s in profile.primary_sensors],
                    "supporting_sensors": [s.value if hasattr(s, "value") else str(s) for s in profile.supporting_sensors],
                    "inactive_sensors": [s.value if hasattr(s, "value") else str(s) for s in profile.inactive_sensors],
                }
        return meta

    def get_operational_events(self) -> dict:
        if not self.running or self.simulator is None or self.config is None:
            return {
                "events": [],
                "summary": {
                    "critical": 0, "warning": 0, "info": 0, "dispatch": 0,
                    "safety": 0, "arrival": 0, "system": 0, "total": 0,
                },
                "operation_status": {
                    "active_teams_count": 0,
                    "teams_en_route": 0,
                    "teams_available": 0,
                    "teams_arrived": 0,
                    "active_missions_count": 0,
                    "high_priority_victims_count": 0,
                    "system_status": "Standby",
                    "communication_status": "Offline",
                },
                "recent_activities": [],
            }

        events = []

        def add_event(ev):
            events.append(ev)

        for ev in self.custom_operational_events:
            add_event(ev)

        fusion_results = self.fuse_current()
        ranked = rank_victims(fusion_results.values())

        for r in ranked:
            sev = "CRITICAL" if r.triage_class == TriageClass.HIGH else ("WARNING" if r.triage_class == TriageClass.MEDIUM else "INFO")
            add_event({
                "id": f"det:{self.session_id}:{r.victim_id}:{self.cycle_count}",
                "timestamp": self.started_at or datetime.now(timezone.utc).isoformat(),
                "time": self.started_at or datetime.now(timezone.utc).isoformat(),
                "severity": sev,
                "type": "Victim Detected",
                "message": f"Victim {r.victim_id} evaluated with {r.triage_class.value} Priority (SPS {r.sps:.1f})",
                "source": "Fusion Engine",
                "target": "Commander",
                "victim_id": r.victim_id,
                "action_type": "view_victim",
                "action_label": "View Victim",
                "action_url": f"victims.html?victim_id={r.victim_id}",
                "category": "system",
            })

        for team_id, members in self.team_members.items():
            for m in members:
                if m.assigned_victim_id:
                    assigned_time = m.assigned_at or self.started_at or datetime.now(timezone.utc).isoformat()
                    add_event({
                        "id": f"assign:{self.session_id}:{m.member_id}:{m.assigned_victim_id}",
                        "timestamp": assigned_time,
                        "time": assigned_time,
                        "severity": "DISPATCH",
                        "type": "Team Assigned",
                        "message": f"{m.callsign} assigned to Victim {m.assigned_victim_id} (Status: {m.status.value.upper()})",
                        "source": "Commander",
                        "target": m.callsign,
                        "victim_id": m.assigned_victim_id,
                        "team_id": m.team_id,
                        "member_id": m.member_id,
                        "callsign": m.callsign,
                        "action_type": "view_team",
                        "action_label": "View Team",
                        "action_url": "teams.html",
                        "category": "dispatch",
                    })

                    if m.status in (MemberStatus.EN_ROUTE, MemberStatus.ARRIVED):
                        add_event({
                            "id": f"go:{self.session_id}:{m.member_id}:{m.assigned_victim_id}",
                            "timestamp": assigned_time,
                            "time": assigned_time,
                            "severity": "DISPATCH",
                            "type": "GO Command",
                            "message": f"GO command issued to {m.callsign} for Victim {m.assigned_victim_id}",
                            "source": "Commander",
                            "target": m.callsign,
                            "victim_id": m.assigned_victim_id,
                            "team_id": m.team_id,
                            "member_id": m.member_id,
                            "callsign": m.callsign,
                            "action_type": "view_mission",
                            "action_label": "View Mission",
                            "action_url": "commander.html",
                            "category": "dispatch",
                        })

        for t in self.rescue_teams:
            if t.assigned_victim_id and t.availability == TeamAvailability.EN_ROUTE:
                t_time = t.last_updated or self.started_at or datetime.now(timezone.utc).isoformat()
                add_event({
                    "id": f"team_auto_disp:{self.session_id}:{t.team_id}:{t.assigned_victim_id}",
                    "timestamp": t_time,
                    "time": t_time,
                    "severity": "DISPATCH",
                    "type": "Team Assigned",
                    "message": f"Team {t.team_name} auto-dispatched to Victim {t.assigned_victim_id} (ETA {t.eta_minutes:.1f}m)",
                    "source": "Auto-Dispatch",
                    "target": t.team_name,
                    "victim_id": t.assigned_victim_id,
                    "team_id": t.team_id,
                    "action_type": "view_team",
                    "action_label": "View Team",
                    "action_url": "teams.html",
                    "category": "dispatch",
                })

        for a in self.recent_member_arrivals:
            arr_time = a.get("arrived_at") or datetime.now(timezone.utc).isoformat()
            add_event({
                "id": f"arr:{self.session_id}:{a.get('member_id')}:{a.get('victim_id')}:{arr_time}",
                "timestamp": arr_time,
                "time": arr_time,
                "severity": "ARRIVAL",
                "type": "Team Arrived",
                "message": f"Team {a.get('callsign', 'Rescuer')} reached Victim {a.get('victim_id')}",
                "source": "Wearable",
                "target": "Commander",
                "victim_id": a.get("victim_id"),
                "member_id": a.get("member_id"),
                "callsign": a.get("callsign"),
                "action_type": "view_victim",
                "action_label": "View Victim",
                "action_url": f"victims.html?victim_id={a.get('victim_id')}",
                "category": "arrival",
            })
            add_event({
                "id": f"rescued:{self.session_id}:{a.get('victim_id')}:{arr_time}",
                "timestamp": arr_time,
                "time": arr_time,
                "severity": "ARRIVAL",
                "type": "Victim Rescued",
                "message": f"Victim {a.get('victim_id')} secured and marked as rescued by {a.get('callsign', 'Rescue Team')}",
                "source": "Field Team",
                "target": "Command Center",
                "victim_id": a.get("victim_id"),
                "member_id": a.get("member_id"),
                "callsign": a.get("callsign"),
                "action_type": "view_victim",
                "action_label": "View Victim",
                "action_url": f"victims.html?victim_id={a.get('victim_id')}",
                "category": "arrival",
            })

        tilt = self.simulator.tilt_report()
        if tilt.get("shift_event") or tilt.get("tilt_deg", 0.0) >= 12.0:
            deg = tilt.get("tilt_deg", 0.0)
            add_event({
                "id": f"safety_tilt:{self.session_id}:{int(deg)}",
                "timestamp": self.started_at or datetime.now(timezone.utc).isoformat(),
                "time": self.started_at or datetime.now(timezone.utc).isoformat(),
                "severity": "CRITICAL",
                "type": "Safety Warning",
                "message": f"Structure tilt warning ({deg:.1f}°) — Unstable ground/debris collapse danger",
                "source": "Sensors (Inclinometer)",
                "target": "Commander, Teams",
                "action_type": "view_hardware",
                "action_label": "View Hardware",
                "action_url": "hardware.html",
                "category": "safety",
            })

        seismic = self.simulator.seismic_report()
        if seismic.get("aftershock_active") or seismic.get("vibration_mm_s", 0.0) >= 8.0:
            vib = seismic.get("vibration_mm_s", 0.0)
            add_event({
                "id": f"safety_seismic:{self.session_id}:{int(vib)}",
                "timestamp": self.started_at or datetime.now(timezone.utc).isoformat(),
                "time": self.started_at or datetime.now(timezone.utc).isoformat(),
                "severity": "CRITICAL",
                "type": "Safety Warning",
                "message": f"Aftershock active ({vib:.1f} mm/s PGV) — Structural risk elevated, hold non-essential movements",
                "source": "Sensors (Seismic)",
                "target": "Commander, Teams",
                "action_type": "view_hardware",
                "action_label": "View Hardware",
                "action_url": "hardware.html",
                "category": "safety",
            })

        soil = self.simulator.soil_report()
        if soil.get("soil_moisture_pct", 0.0) >= 60.0:
            pct = soil.get("soil_moisture_pct", 0.0)
            add_event({
                "id": f"safety_soil:{self.session_id}:{int(pct // 10)}",
                "timestamp": self.started_at or datetime.now(timezone.utc).isoformat(),
                "time": self.started_at or datetime.now(timezone.utc).isoformat(),
                "severity": "WARNING",
                "type": "Safety Warning",
                "message": f"Soil saturation at {pct:.0f}% — Slope instability & landslide risk elevated",
                "source": "Sensors (Soil Probes)",
                "target": "Commander, Teams",
                "action_type": "view_hardware",
                "action_label": "View Hardware",
                "action_url": "hardware.html",
                "category": "safety",
            })

        rain = self.simulator.rain_report()
        if rain.get("rainfall_mm_hr", 0.0) >= 25.0:
            rf = rain.get("rainfall_mm_hr", 0.0)
            add_event({
                "id": f"safety_rain:{self.session_id}:{int(rf // 10)}",
                "timestamp": self.started_at or datetime.now(timezone.utc).isoformat(),
                "time": self.started_at or datetime.now(timezone.utc).isoformat(),
                "severity": "WARNING",
                "type": "Safety Warning",
                "message": f"Heavy rainfall ({rf:.1f} mm/hr) — Rapid water accumulation hazard",
                "source": "Sensors (Rain Gauge)",
                "target": "Commander, Teams",
                "action_type": "view_hardware",
                "action_label": "View Hardware",
                "action_url": "hardware.html",
                "category": "safety",
            })

        temp = self.simulator.temperature_report()
        if temp.get("ambient_temp_c", 20.0) <= 5.0:
            amb = temp.get("ambient_temp_c", 20.0)
            add_event({
                "id": f"safety_temp:{self.session_id}:{int(amb)}",
                "timestamp": self.started_at or datetime.now(timezone.utc).isoformat(),
                "time": self.started_at or datetime.now(timezone.utc).isoformat(),
                "severity": "WARNING",
                "type": "Safety Warning",
                "message": f"Low ambient temperature ({amb:.1f}°C) — Hypothermia risk for trapped survivors",
                "source": "Weather Station",
                "target": "Commander, Teams",
                "action_type": "view_hardware",
                "action_label": "View Hardware",
                "action_url": "hardware.html",
                "category": "safety",
            })

        imu = self.simulator.imu_report()
        for vid, imu_info in imu.items():
            if imu_info.get("kit_disturbed"):
                add_event({
                    "id": f"safety_imu:{self.session_id}:{vid}",
                    "timestamp": self.started_at or datetime.now(timezone.utc).isoformat(),
                    "time": self.started_at or datetime.now(timezone.utc).isoformat(),
                    "severity": "WARNING",
                    "type": "Safety Warning",
                    "message": f"Sensor kit disturbed for Victim {vid} — Shift or external motion detected",
                    "source": "IMU Sensor",
                    "target": "Commander, Teams",
                    "victim_id": vid,
                    "action_type": "view_victim",
                    "action_label": "View Victim",
                    "action_url": f"victims.html?victim_id={vid}",
                    "category": "safety",
                })

        battery = self.simulator.battery_report()
        for vid, pct in battery.items():
            if pct < LOW_BATTERY_WARNING_PCT:
                add_event({
                    "id": f"bat:{self.session_id}:{vid}:{int(pct // 5)}",
                    "timestamp": self.started_at or datetime.now(timezone.utc).isoformat(),
                    "time": self.started_at or datetime.now(timezone.utc).isoformat(),
                    "severity": "WARNING",
                    "type": "Sensor Warning",
                    "message": f"Battery low ({pct:.1f}%) on Node {vid} — Sensor reading reliability degraded",
                    "source": "Power Management",
                    "target": "Hardware Ops",
                    "victim_id": vid,
                    "action_type": "view_hardware",
                    "action_label": "View Hardware",
                    "action_url": "hardware.html",
                    "category": "system",
                })

        # Active Hazard Alerts from Active Alerts Ledger
        if self.session_id:
            try:
                active_ledger_alerts = db.list_active_alerts(session_id=self.session_id, status="ACTIVE")
                for alert in active_ledger_alerts:
                    add_event({
                        "id": f"alert_ledger:{alert['alert_key']}",
                        "timestamp": alert.get("last_updated_at") or self.started_at or datetime.now(timezone.utc).isoformat(),
                        "time": alert.get("last_updated_at") or self.started_at or datetime.now(timezone.utc).isoformat(),
                        "severity": alert.get("severity", "CRITICAL").upper(),
                        "type": alert.get("hazard_type", "Hazard Alert").replace("_", " ").title(),
                        "message": f"{alert.get('alert_title', 'Hazard Alert')}: {alert.get('evidence_summary', '')}",
                        "source": "Scenario Intelligence",
                        "target": "Commander, Rescue Teams",
                        "action_type": "view_alerts",
                        "action_label": "View Alert",
                        "action_url": "alerts.html",
                        "category": "critical" if alert.get("severity") == "CRITICAL" else "safety",
                    })
            except Exception:
                pass

        events.sort(key=lambda e: e["timestamp"], reverse=True)

        critical_count = sum(1 for e in events if e["severity"] == "CRITICAL")
        warning_count = sum(1 for e in events if e["severity"] == "WARNING")
        info_count = sum(1 for e in events if e["severity"] == "INFO")
        dispatch_count = sum(1 for e in events if e["severity"] == "DISPATCH")
        safety_count = sum(1 for e in events if e["category"] == "safety")
        arrival_count = sum(1 for e in events if e["category"] == "arrival")
        system_count = sum(1 for e in events if e["category"] == "system")

        all_members = [m for members in self.team_members.values() for m in members]
        en_route = sum(1 for m in all_members if m.status == MemberStatus.EN_ROUTE)
        available = sum(1 for m in all_members if m.status == MemberStatus.HOLD)
        arrived = sum(1 for m in all_members if m.status == MemberStatus.ARRIVED)
        high_pri_victims = sum(1 for f in fusion_results.values() if f.triage_class == TriageClass.HIGH)
        active_missions = len({m.assigned_victim_id for m in all_members if m.assigned_victim_id and m.status == MemberStatus.EN_ROUTE})

        team_event_types = {"Team Assigned", "GO Command", "Team Arrived", "Victim Rescued", "Safety Warning"}
        recent_activities = [e for e in events if e["type"] in team_event_types][:10]

        return {
            "events": events,
            "summary": {
                "critical": critical_count,
                "warning": warning_count,
                "info": info_count,
                "dispatch": dispatch_count,
                "safety": safety_count,
                "arrival": arrival_count,
                "system": system_count,
                "total": len(events),
            },
            "operation_status": {
                "active_teams_count": len(all_members) or len(self.rescue_teams),
                "teams_en_route": en_route,
                "teams_available": available,
                "teams_arrived": arrived,
                "active_missions_count": active_missions,
                "high_priority_victims_count": high_pri_victims,
                "system_status": "Degradation Active" if (self.simulator and self.simulator.enable_degradation) else "All Systems Operational",
                "communication_status": "Mesh & GSM Link Active",
            },
            "recent_activities": recent_activities,
        }


# --------------------------------------------------------------------------- #
# Operations Registry & Helpers
# --------------------------------------------------------------------------- #

operations: Dict[str, ScenarioState] = {}

# Custom scenarios built on the fly via POST /admin/scenario/create (Testing
# Console → Add Scenario). Kept in memory so the Dashboard's "Start Scenario"
# picker (GET /scenarios) can offer them too, and POST /scenario/start can
# start a *fresh* run of one without re-running the one auto-started at
# creation time. Ledger status (Active/Inactive, in admin_scenarios) decides
# whether a given entry is currently offered - see list_scenarios() below.
custom_scenario_configs: Dict[str, ScenarioConfig] = {}


class _StateProxy:
    """Compatibility proxy delegating to the most recently active operation."""
    def __getattr__(self, name):
        if operations:
            latest_op = list(operations.values())[-1]
            return getattr(latest_op, name)
        raise AttributeError(f"No active operation for state.{name}")

    def __setattr__(self, name, value):
        if operations:
            latest_op = list(operations.values())[-1]
            setattr(latest_op, name, value)
        else:
            super().__setattr__(name, value)


state = _StateProxy()


def _get_operation(operation_id: Optional[str] = None, not_running_status: int = 409) -> ScenarioState:
    if operation_id is not None:
        op = operations.get(operation_id)
        if op is None:
            if not operations:
                raise HTTPException(
                    status_code=not_running_status,
                    detail="Scenario is not running. Call POST /scenario/start first.",
                )
            raise HTTPException(
                status_code=404,
                detail=f"Unknown operation_id: {operation_id}",
            )
        return op
    else:
        if not operations:
            raise HTTPException(
                status_code=not_running_status,
                detail="Scenario is not running. Call POST /scenario/start first.",
            )
        return list(operations.values())[-1]


def _get_operation_optional(operation_id: Optional[str] = None) -> Optional[ScenarioState]:
    if operation_id is not None:
        return operations.get(operation_id)
    return list(operations.values())[-1] if operations else None


def _op_id(op: Optional[ScenarioState], operation_id: Optional[str] = None) -> str:
    if operation_id:
        return operation_id
    if op is not None:
        for k, v in operations.items():
            if v is op:
                return k
    return "default"


def _require_running(op: ScenarioState):
    if not op.running or op.simulator is None:
        raise HTTPException(
            status_code=409,
            detail="Scenario is not running. Call POST /scenario/start first.",
        )


def _auto_dispatch(op: ScenarioState, queue: list) -> None:
    assigned_ids = {t.assigned_victim_id for t in op.rescue_teams if t.assigned_victim_id}
    needs_rescue = [
        r for r in queue
        if r.triage_class in (TriageClass.HIGH, TriageClass.MEDIUM, TriageClass.LOW)
        and r.victim_id not in assigned_ids
    ]
    for team in op.rescue_teams:
        if team.availability != TeamAvailability.AVAILABLE:
            continue
        if not needs_rescue:
            break
        victim = needs_rescue.pop(0)
        team.assigned_victim_id = victim.victim_id
        team.availability = TeamAvailability.EN_ROUTE
        team.eta_minutes = round(8 + 4 * (victim.hazard_multiplier - 1.0) * 10, 1)
        team.last_updated = datetime.now(timezone.utc).isoformat()

        if op.session_id:
            db.log_rescue_status_event(
                session_id=op.session_id,
                event_type="team_dispatched",
                team_id=team.team_id,
                victim_id=team.assigned_victim_id,
                availability=team.availability.value,
                eta_minutes=team.eta_minutes,
                timestamp=team.last_updated,
                notes=f"{team.team_name} dispatched to {victim.victim_id} ({victim.triage_class.value})",
            )


# --------------------------------------------------------------------------- #
# Request/response models
# --------------------------------------------------------------------------- #

class ScenarioStartRequest(BaseModel):
    scenario: Optional[str] = None   # scenario_id, matches a scenarios/*.json file
    scenario_id: Optional[str] = None
    operation_id: Optional[str] = None
    seed: Optional[int] = None
    enable_degradation: bool = True
    enable_solar_charging: bool = False


class RescueAdvanceRequest(BaseModel):
    seconds: float = SECONDS_PER_ADVANCE_STEP
    steps: int = 1


class SetTargetRequest(BaseModel):
    victim_id: str


class ManualMoveRequest(BaseModel):
    bearing_deg: float
    distance_m: float


class AddVictimRequest(BaseModel):
    victim_id: Optional[str] = None
    label: str
    status: str
    latitude: float
    longitude: float
    altitude_m: Optional[float] = None
    burial_depth_m: Optional[float] = None
    consciousness: Optional[str] = None
    mobility: Optional[str] = None
    injury_notes: Optional[str] = None
    notes: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None


class AddUnassignedMemberRequest(BaseModel):
    person_id: str
    full_name: str
    role: Optional[str] = "Rescuer"
    badge_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    status: Optional[str] = "Active"
    address: Optional[str] = None
    scenarios: Optional[list[str] | str] = None


class ResizeRosterRequest(BaseModel):
    member_count: int


class AssignMemberRequest(BaseModel):
    member_id: str
    victim_id: str


class AssignTeamMemberRequest(BaseModel):
    member_id: str
    target_team_id: str
    role: Optional[str] = None


class CreateScenarioRequest(BaseModel):
    hazard_type: str
    victim_count: int
    latitude: float
    longitude: float
    altitude_m: Optional[float] = None
    scenario_name: Optional[str] = None
    seed: Optional[int] = None
    enable_degradation: bool = True
    operation_id: Optional[str] = None


class AddPersonnelRequest(BaseModel):
    full_name: str
    role: str
    dob: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    status: str = "Active"
    badge_id: Optional[str] = None
    scenarios: Optional[list[str] | str] = None


class UpdatePersonnelScenariosRequest(BaseModel):
    scenarios: list[str] | str


class IngestGasSmokeReadingRequest(BaseModel):
    gas_type: Optional[str] = "GENERIC_SMOKE"
    gas_concentration: float
    smoke_density_pct: float
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    sensor_id: Optional[str] = "GAS-SMOKE-SITE"
    device_id: Optional[str] = "DEV-GAS-01"


class CreateCommanderJobRequest(BaseModel):
    job_name: str
    scenario_id: str
    priority: Optional[str] = "HIGH"
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None
    victim_id: Optional[str] = None


class AssignCommanderJobRequest(BaseModel):
    job_id: str
    member_id: str
    notes: Optional[str] = None


class UpdateStaffJobStatusRequest(BaseModel):
    status: str
    progress_pct: Optional[int] = None
    result_notes: Optional[str] = None


class TeamMemberAssignment(BaseModel):
    person_id: str
    role_on_team: Optional[str] = None


class CreateAdminTeamRequest(BaseModel):
    team_name: str
    team_type: Optional[str] = None
    description: Optional[str] = None
    members: list[TeamMemberAssignment] = []


class InboundSmsWebhookRequest(BaseModel):
    message: Optional[str] = None
    text: Optional[str] = None
    message_body: Optional[str] = None
    phoneNumber: Optional[str] = None
    phone_number: Optional[str] = None
    sender: Optional[str] = None
    event: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    simNumber: Optional[int] = None


class SubsurfaceStepRequest(BaseModel):
    step_time: Optional[float] = 0.5
    seed: Optional[int] = None


class SubsurfaceControlRequest(BaseModel):
    action: str  # start, pause, resume, reset, set_preset
    preset_id: Optional[Any] = None


class SubsurfaceConfigRequest(BaseModel):
    soil_type: Optional[str] = None
    soil_moisture_pct: Optional[float] = None
    clay_fraction: Optional[float] = None
    soil_density_g_cm3: Optional[float] = None
    clutter_level: Optional[str] = None
    sensor_noise: Optional[str] = None
    survivor_mode: Optional[str] = None
    survivor_alive: Optional[bool] = None
    burial_depth_m: Optional[float] = None
    breathing_rate_rpm: Optional[float] = None
    heart_rate_bpm: Optional[float] = None
    micro_motion: Optional[bool] = None
    signal_strength_db: Optional[float] = None


class SubsurfaceReadingIngestRequest(BaseModel):
    victim_id: str
    session_id: Optional[str] = "SESSION-DEFAULT"
    estimated_depth_m: float
    ground_truth_depth_m: Optional[float] = None
    confidence: float
    respiration_rpm: Optional[float] = None
    heart_rate_bpm: Optional[float] = None
    soil_type: Optional[str] = "wet_soil"
    moisture_pct: Optional[float] = 50.0
    snr_db: Optional[float] = 15.0



# --------------------------------------------------------------------------- #
# Global & Operations Registry Endpoints
# --------------------------------------------------------------------------- #

@app.get("/health")
@app.get("/api/health")
@app.get("/api/v1/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/scenarios")
def list_scenarios():
    """Authoritative scenario list from the Scenarios Ledger (admin_scenarios).
    Returns all scenarios annotated with status ('Active' / 'Inactive') so the Dashboard
    and other clients can dynamically filter active scenarios."""
    ledger_rows = db.list_admin_scenarios()
    ledger_map = {r["scenario_ref_id"]: r for r in ledger_rows}
    builtin_meta = {s["scenario_id"]: s for s in scenario_loader.available_scenarios()}

    scenarios = []
    for ref_id, row in ledger_map.items():
        status = row.get("status") or "Active"
        if ref_id in builtin_meta:
            meta = dict(builtin_meta[ref_id])
            meta["status"] = status
            meta["id"] = ref_id
            scenarios.append(meta)
        elif ref_id in custom_scenario_configs:
            meta = custom_scenario_configs[ref_id].meta()
            meta["status"] = status
            meta["id"] = ref_id
            scenarios.append(meta)
        else:
            scenarios.append({
                "scenario_id": ref_id,
                "id": ref_id,
                "name": row.get("scenario_name") or ref_id,
                "description": f"{row.get('hazard_type', '').title()} scenario with {row.get('victim_count', 0)} victims.",
                "site_label": f"{row.get('hazard_type', '').title()} site",
                "victim_count": row.get("victim_count", 0),
                "hazard_type": row.get("hazard_type", ""),
                "status": status,
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            })

    for s_id, meta in builtin_meta.items():
        if s_id not in ledger_map:
            m = dict(meta)
            m["status"] = "Active"
            m["id"] = s_id
            scenarios.append(m)

    return {"scenarios": scenarios}


@app.get("/operations")
def list_operations():
    """List all currently active operations on the backend."""
    active_ops = []
    for op_id, op in operations.items():
        meta = op.scenario_meta()
        active_ops.append({
            "operation_id": op_id,
            "session_id": op.session_id,
            "running": op.running,
            "started_at": op.started_at,
            "cycle": op.cycle_count,
            "victim_count": meta.get("victim_count", 0),
            "scenario_id": meta.get("scenario_id"),
            "scenario_name": meta.get("scenario_name"),
            "site_label": meta.get("site_label"),
            "active_teams_count": len(op.rescue_teams),
        })
    return {"operations": active_ops}


@app.post("/scenario/start")
def scenario_start(req: ScenarioStartRequest = ScenarioStartRequest()):
    """Create and start a new isolated operation run.

    req.scenario or req.scenario_id can be a built-in scenario_id (backend/scenarios/*.json) or
    the id of a custom scenario created via the Testing Console, as long as
    it's currently marked Active in the Scenarios Ledger (see list_scenarios()).
    """
    target_scenario = req.scenario or req.scenario_id or DEFAULT_SCENARIO_ID
    op_id = req.operation_id.strip() if (req.operation_id and req.operation_id.strip()) else f"op-{uuid.uuid4().hex[:8]}"
    op = ScenarioState()

    ledger_row = db.get_admin_scenario(target_scenario)
    if ledger_row:
        status = (ledger_row.get("status") if ledger_row else "Active") or "Active"
        if status.lower() != "active":
            raise HTTPException(
                status_code=400,
                detail=f"Scenario '{target_scenario}' is marked Inactive in the Scenarios Ledger.",
            )

    custom_config = custom_scenario_configs.get(target_scenario)
    if custom_config is None and ledger_row and ledger_row["scenario_ref_id"].startswith("admin_custom_"):
        try:
            custom_config = scenario_loader.build_custom_scenario(
                hazard_type=ledger_row["hazard_type"],
                victim_count=ledger_row["victim_count"],
                site_origin=GPSCoordinate(
                    latitude=ledger_row.get("latitude") or 0.0,
                    longitude=ledger_row.get("longitude") or 0.0,
                ),
                scenario_name=ledger_row.get("scenario_name"),
            )
            custom_config.scenario_id = ledger_row["scenario_ref_id"]
            custom_scenario_configs[ledger_row["scenario_ref_id"]] = custom_config
        except Exception:
            pass

    try:
        if custom_config is not None:
            op.start(
                seed=req.seed,
                enable_degradation=req.enable_degradation,
                enable_solar_charging=req.enable_solar_charging,
                custom_config=custom_config,
            )
        else:
            op.start(
                scenario_id=target_scenario,
                seed=req.seed,
                enable_degradation=req.enable_degradation,
                enable_solar_charging=req.enable_solar_charging,
            )
    except ScenarioNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ScenarioConfigError as e:
        raise HTTPException(status_code=422, detail=f"Invalid scenario config: {e}")

    operations[op_id] = op
    return {"status": "started", "operation_id": op_id, "session_id": op.session_id, **op.scenario_meta()}


@app.post("/operations/{operation_id}/stop")
@app.post("/operations/{operation_id}/reset")
def stop_operation(operation_id: str):
    """Tear down and remove an operation instance from memory."""
    op = _get_operation(operation_id)
    op.reset()
    operations.pop(operation_id, None)
    return {"operation_id": operation_id, "status": "stopped"}


@app.post("/scenario/reset")
def scenario_reset(operation_id: Optional[str] = None):
    """Reset all active operations or a specific operation."""
    if operation_id:
        if operation_id in operations:
            operations[operation_id].reset()
            del operations[operation_id]
        return {"status": "reset", "operation_id": operation_id, "running": False}
    for op in list(operations.values()):
        op.reset()
    operations.clear()
    return {"status": "reset", "running": False, **ScenarioState().scenario_meta()}


@app.post("/scenario/tick")
@app.post("/operations/{operation_id}/scenario/tick")
def scenario_tick(operation_id: Optional[str] = None):
    """Advance simulation cycle by 1 step."""
    op = _get_operation(operation_id)
    _require_running(op)
    op.tick()
    return {"status": "ok", "cycle": op.cycle_count, "running": op.running, "operation_id": _op_id(op, operation_id)}


@app.get("/scenario/sensor-profile")
@app.get("/api/scenario/sensor-profile")
@app.get("/operations/{operation_id}/sensor-profile")
def get_scenario_sensor_profile_endpoint(
    scenario_id: Optional[str] = None,
    scenario: Optional[str] = None,
    operation_id: Optional[str] = None,
):
    """Return the active or requested scenario's sensor role classifications, weights, and live matrix."""
    target_id = scenario_id or scenario
    op = None
    if operation_id:
        op = _get_operation_optional(operation_id)
    elif operations:
        op = list(operations.values())[-1]

    if not target_id:
        if op and op.config and op.config.scenario_id:
            target_id = op.config.scenario_id
        else:
            target_id = DEFAULT_SCENARIO_ID

    profile = get_scenario_sensor_profile(target_id)
    matrix = get_scenario_sensor_state_map(target_id)

    # Populate live values from active simulation if available
    if op and op.running and op.simulator:
        sim = op.simulator
        live_val_map = {
            "gas_concentration": getattr(sim, "_gas_ppm", 0.0),
            "smoke_density": getattr(sim, "_smoke_pct", 0.0),
            "temperature": getattr(sim, "_ambient_temp_c", 15.0),
            "rainfall_intensity": getattr(sim, "_rain_mm_hr", 0.0),
            "soil_moisture": getattr(sim, "_soil_moisture_pct", 30.0),
            "imu_vibration": getattr(sim, "_vibration_mm_s", 0.0),
            "imu_tilt": getattr(sim, "_tilt_deg", 0.0),
            "barometric_pressure": getattr(sim, "_pressure_hpa", 1013.25),
        }
        for item in matrix:
            st = item["sensor_type"]
            if st in live_val_map:
                item["current_value"] = round(live_val_map[st], 2)

    return {
        "status": "success",
        "scenario_id": profile.scenario_id,
        "name": profile.name,
        "description": profile.description,
        "primary_sensors": [s.value for s in profile.primary_sensors],
        "supporting_sensors": [s.value for s in profile.supporting_sensors],
        "inactive_sensors": [s.value for s in profile.inactive_sensors],
        "sensor_weights": {k.value: v for k, v in profile.sensor_weights.items()},
        "hazard_weights": profile.hazard_weights,
        "sensor_matrix": matrix,
    }


# --------------------------------------------------------------------------- #
# Admin / Org Registry Endpoints (Persistent in SQLite, Unscoped)
# --------------------------------------------------------------------------- #

@app.get("/disaster-scenarios")
@app.get("/admin/disaster-scenarios")
def get_disaster_scenarios_master():
    """Canonical single-source-of-truth master list of all 19 disaster scenarios."""
    return {"scenarios": get_all_scenarios()}


@app.post("/admin/personnel/add")
def admin_add_personnel(req: AddPersonnelRequest):
    person_id = f"P{uuid.uuid4().hex[:6].upper()}"
    db.add_personnel(
        person_id=person_id, full_name=req.full_name, role=req.role, dob=req.dob,
        gender=req.gender, phone=req.phone, email=req.email, address=req.address,
        status=req.status, badge_id=req.badge_id, scenarios=req.scenarios,
    )
    return {"person_id": person_id, "created": True, "scenarios": req.scenarios}


@app.get("/admin/personnel")
def admin_list_personnel():
    return {"personnel": db.list_personnel()}


@app.get("/admin/personnel/{person_id}")
def admin_get_personnel(person_id: str):
    p = db.get_personnel(person_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Personnel '{person_id}' not found")
    return {"personnel": p}


@app.patch("/admin/personnel/{person_id}/scenarios")
@app.post("/admin/personnel/{person_id}/scenarios")
def admin_update_personnel_scenarios(person_id: str, req: UpdatePersonnelScenariosRequest):
    updated = db.update_personnel_scenarios(person_id, req.scenarios)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Personnel '{person_id}' not found")
    # Also sync scenarios across all active running operations
    scenarios_list = db._parse_scenarios_json(db._format_scenarios_input(req.scenarios)[0])
    for op in operations.values():
        for members in op.team_members.values():
            for m in members:
                if m.personnel_id == person_id:
                    m.scenarios = list(scenarios_list)
    return {"person_id": person_id, "updated": True, "scenarios": scenarios_list}


@app.post("/admin/scenario/create")
def admin_create_scenario(req: CreateScenarioRequest):
    """Build a custom scenario and start it under a new isolated operation."""
    try:
        config = scenario_loader.build_custom_scenario(
            hazard_type=req.hazard_type,
            victim_count=req.victim_count,
            site_origin=GPSCoordinate(latitude=req.latitude, longitude=req.longitude, altitude_m=req.altitude_m),
            scenario_name=req.scenario_name,
            seed=req.seed,
        )
    except ScenarioConfigError as e:
        raise HTTPException(status_code=422, detail=str(e))

    op_id = req.operation_id.strip() if (req.operation_id and req.operation_id.strip()) else f"op-{uuid.uuid4().hex[:8]}"
    op = ScenarioState()
    op.start(
        seed=req.seed,
        enable_degradation=req.enable_degradation,
        custom_config=config,
    )
    operations[op_id] = op

    # Cache so this scenario can also be offered/started from the Dashboard's
    # "Start Scenario" picker (GET /scenarios, POST /scenario/start), gated
    # by its ledger status (Active/Inactive) - see list_scenarios() below.
    custom_scenario_configs[config.scenario_id] = config

    db.log_admin_scenario(
        scenario_ref_id=config.scenario_id, scenario_name=config.name,
        hazard_type=req.hazard_type, victim_count=req.victim_count,
        latitude=req.latitude, longitude=req.longitude,
        status="Active",
    )

    return {"created": True, "operation_id": op_id, **op.scenario_meta()}


@app.get("/admin/scenarios")
def admin_list_scenarios():
    return {"scenarios": db.list_admin_scenarios()}


class SetScenarioStatusRequest(BaseModel):
    status: str  # "Active" | "Inactive"


@app.post("/admin/scenarios/{scenario_ref_id}/status")
@app.patch("/admin/scenarios/{scenario_ref_id}/status")
@app.patch("/scenarios/{scenario_ref_id}/status")
def admin_set_scenario_status(scenario_ref_id: str, req: SetScenarioStatusRequest):
    """Toggle a scenario's ledger status. Inactive scenarios are hidden
    from the Dashboard's 'Start Scenario' picker (see list_scenarios())."""
    status = (req.status or "").strip().capitalize()
    if status not in ("Active", "Inactive"):
        raise HTTPException(status_code=422, detail="status must be 'Active' or 'Inactive'")

    updated = db.set_admin_scenario_status(scenario_ref_id, status)
    if not updated:
        # Check if it's a built-in scenario not yet seeded
        builtin_meta = {s["scenario_id"]: s for s in scenario_loader.available_scenarios()}
        if scenario_ref_id in builtin_meta:
            db.seed_builtin_scenarios()
            updated = db.set_admin_scenario_status(scenario_ref_id, status)
        if not updated:
            raise HTTPException(status_code=404, detail=f"No scenario in the ledger with id {scenario_ref_id!r}")

    return {"scenario_ref_id": scenario_ref_id, "id": scenario_ref_id, "status": status, "updated": True}


@app.post("/admin/teams/create")
def admin_create_team(req: CreateAdminTeamRequest):
    team_ref_id = f"T{uuid.uuid4().hex[:6].upper()}"
    db.create_admin_team(team_ref_id=team_ref_id, team_name=req.team_name,
                          team_type=req.team_type, description=req.description)
    for m in req.members:
        db.add_team_member(team_ref_id=team_ref_id, person_id=m.person_id, role_on_team=m.role_on_team)

    # Dynamically register team in all active running operations!
    for op in operations.values():
        if op.running and op.config:
            op.register_team_from_db(team_ref_id)

    return {"team_ref_id": team_ref_id, "created": True}


@app.get("/admin/teams")
def admin_list_teams():
    return {"teams": db.list_admin_teams()}


# --------------------------------------------------------------------------- #
# Operation-Scoped and Root Live Scenario Endpoints
# --------------------------------------------------------------------------- #

@app.post("/admin/victims/add")
@app.post("/operations/{operation_id}/admin/victims/add")
def admin_add_victim(req: AddVictimRequest, operation_id: Optional[str] = None):
    op = _get_operation(operation_id, not_running_status=400)
    if not op.running or op.simulator is None or op.config is None:
        raise HTTPException(status_code=400, detail="No scenario is running in this operation.")

    template = ADMIN_PRIORITY_TEMPLATES.get(req.status.upper())
    if template is None:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of {list(ADMIN_PRIORITY_TEMPLATES.keys())}, got {req.status!r}",
        )

    victim_id = req.victim_id.strip() if req.victim_id and req.victim_id.strip() else None
    if not victim_id:
        idx = len(op.config.victims) + 1
        while f"V{idx}" in op.simulator.nodes:
            idx += 1
        victim_id = f"V{idx}"

    if victim_id in op.simulator.nodes:
        raise HTTPException(status_code=409, detail=f"Victim id '{victim_id}' already exists in this operation")

    burial_depth = float(req.burial_depth_m) if req.burial_depth_m is not None else float(template["burial_depth_m"])

    note_parts = []
    if template.get("notes"):
        note_parts.append(template["notes"])
    if req.notes and req.notes != template.get("notes"):
        note_parts.append(req.notes)
    if req.injury_notes:
        note_parts.append(f"Injuries: {req.injury_notes}")
    if req.consciousness:
        note_parts.append(f"Consciousness: {req.consciousness}")
    if req.mobility:
        note_parts.append(f"Mobility: {req.mobility}")
    if req.age is not None:
        note_parts.append(f"Age: {req.age}")
    if req.gender:
        note_parts.append(f"Gender: {req.gender}")
    formatted_notes = " | ".join(note_parts) if note_parts else template["notes"]

    victim = VictimProfile(
        victim_id=victim_id,
        label=req.label,
        status=template["status"],
        location=GPSCoordinate(latitude=req.latitude, longitude=req.longitude, altitude_m=req.altitude_m),
        burial_depth_m=burial_depth,
        signature_range=template["signature_range"],
        notes=formatted_notes,
        age=req.age,
        gender=req.gender,
        consciousness=req.consciousness,
        mobility=req.mobility,
        injury_notes=req.injury_notes,
    )

    try:
            op.simulator.add_victim(victim)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if victim not in op.config.victims:
        op.config.victims.append(victim)

    op.config.hazards[victim.victim_id] = HazardContext(burial_depth_m=burial_depth)

    if op.session_id:
        db.log_rescue_status_event(
            session_id=op.session_id,
            event_type="victim_added",
            victim_id=victim.victim_id,
            notes=f"🆕 New victim {victim.victim_id} ({victim.label}) registered with status {req.status.upper()}.",
        )
        db.update_session_victim_count(op.session_id, len(op.config.victims))

    op.custom_operational_events.append({
        "id": f"reg_victim:{op.session_id}:{victim.victim_id}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "time": datetime.now(timezone.utc).isoformat(),
        "severity": "CRITICAL" if req.status.upper() == "HIGH" else ("WARNING" if req.status.upper() == "MEDIUM" else "INFO"),
        "type": "Victim Detected",
        "message": f"🆕 New victim {victim.victim_id} ({victim.label}) registered in operation",
        "source": "Triage Entry",
        "target": "Commander",
        "victim_id": victim.victim_id,
        "action_type": "view_victim",
        "action_label": "View Victim",
        "action_url": f"victims.html?victim_id={victim.victim_id}",
        "category": "system",
    })

    return {
        "added": True,
        "victim_id": victim.victim_id,
        "status": req.status.upper(),
        "victim_count": len(op.config.victims),
        "victim": victim.to_dict(),
    }


@app.post("/admin/team-members/add-unassigned")
@app.post("/operations/{operation_id}/admin/team-members/add-unassigned")
def admin_add_unassigned_member(req: AddUnassignedMemberRequest, operation_id: Optional[str] = None):
    op = _get_operation(operation_id, not_running_status=400)
    if not op.running or op.config is None:
        raise HTTPException(status_code=400, detail="No scenario is running in this operation.")

    member_id = f"UN-{req.person_id}" if not req.person_id.startswith("UN-") else req.person_id

    existing_members = [m for members in op.team_members.values() for m in members]
    if any(m.member_id == member_id or (m.personnel_id and m.personnel_id == req.person_id) for m in existing_members):
        raise HTTPException(status_code=409, detail=f"Team member '{member_id}' or personnel '{req.person_id}' is already registered in this operation.")

    p_scenarios = req.scenarios
    if not p_scenarios and req.person_id:
        p_db = db.get_personnel(req.person_id)
        if p_db:
            p_scenarios = p_db.get("scenarios")
    if not p_scenarios:
        p_scenarios = ["earthquake", "building_collapse"]
    elif isinstance(p_scenarios, str):
        p_scenarios = db._parse_scenarios_json(p_scenarios)

    origin = op.config.site_origin
    member = TeamMember(
        member_id=member_id,
        callsign=f"{req.full_name} ({req.role or 'Staff'})",
        team_id="UNASSIGNED",
        location=GPSCoordinate(latitude=origin.latitude, longitude=origin.longitude, altitude_m=origin.altitude_m),
        full_name=req.full_name,
        role=req.role or "Rescuer",
        status=MemberStatus.HOLD,
        assigned_victim_id=None,
        assigned_at=None,
        personnel_id=req.person_id,
        scenarios=list(p_scenarios),
    )

    op.team_members.setdefault("UNASSIGNED", []).append(member)

    if op.session_id:
        db.log_rescue_status_event(
            session_id=op.session_id,
            event_type="member_registered",
            team_id="UNASSIGNED",
            notes=f"🆕 New team member registered: {member.full_name} (unassigned pool).",
        )

    op.custom_operational_events.append({
        "id": f"reg_member:{op.session_id}:{member.member_id}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "time": datetime.now(timezone.utc).isoformat(),
        "severity": "INFO",
        "type": "Personnel Registered",
        "message": f"🆕 New team member registered: {member.full_name} (unassigned)",
        "source": "Roster Management",
        "target": "Commander",
        "member_id": member.member_id,
        "callsign": member.callsign,
        "team_id": "UNASSIGNED",
        "action_type": "view_team",
        "action_label": "View Team",
        "action_url": "commander.html",
        "category": "dispatch",
    })

    return {
        "added": True,
        "operation_id": _op_id(op, operation_id),
        "member": member.to_dict(),
    }


@app.post("/commander/team/assign-member")
@app.post("/operations/{operation_id}/commander/team/assign-member")
def commander_assign_member_to_team(req: AssignTeamMemberRequest, operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)

    target_team = next((t for t in op.rescue_teams if t.team_id == req.target_team_id), None)
    if target_team is None:
        raise HTTPException(status_code=404, detail=f"Unknown team '{req.target_team_id}'")

    found_member: Optional[TeamMember] = None
    old_team_id: Optional[str] = None
    for tid, members in list(op.team_members.items()):
        for m in members:
            if m.member_id == req.member_id:
                found_member = m
                old_team_id = tid
                break
        if found_member:
            break

    if found_member is None:
        raise HTTPException(status_code=404, detail=f"Unknown team member '{req.member_id}'")

    if old_team_id != req.target_team_id:
        if old_team_id in op.team_members and found_member in op.team_members[old_team_id]:
            op.team_members[old_team_id].remove(found_member)
        op.team_members.setdefault(req.target_team_id, []).append(found_member)

    found_member.team_id = req.target_team_id
    if req.role:
        found_member.role = req.role
    found_member.callsign = f"{target_team.team_name} - {found_member.full_name or found_member.member_id}"
    found_member.last_updated = datetime.now(timezone.utc).isoformat()
    target_team.members = max(target_team.members, len(op.team_members[req.target_team_id]))

    if op.session_id:
        db.log_rescue_status_event(
            session_id=op.session_id,
            event_type="member_reassigned",
            team_id=req.target_team_id,
            notes=f"Member {found_member.full_name or found_member.member_id} assigned to team {target_team.team_name}.",
        )

    return {
        "assigned": True,
        "operation_id": _op_id(op, operation_id),
        "team_id": req.target_team_id,
        "member": found_member.to_dict(),
    }


@app.post("/admin/teams/{team_id}/roster")
@app.post("/operations/{operation_id}/admin/teams/{team_id}/roster")
def admin_resize_roster(team_id: str, req: ResizeRosterRequest, operation_id: Optional[str] = None):
    op = _get_operation(operation_id, not_running_status=400)
    if not op.running:
        raise HTTPException(status_code=400, detail="No scenario is running in this operation.")
    try:
        team = op.resize_team_roster(team_id, req.member_count)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "team": team.to_dict(),
        "tracked_members": [m.to_dict() for m in op.team_members.get(team_id, [])],
    }


@app.get("/victims")
@app.get("/operations/{operation_id}/victims")
def get_victims(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    op.tick()

    fusion_results = op.fuse_current()
    readings_by_victim = op.current_readings_by_victim()
    battery_report = op.simulator.battery_report()
    power_report = op.simulator.power_report()
    imu_report = op.simulator.imu_report()

    def _nearest_member_distance_m(victim_location) -> Optional[float]:
        all_members = [m for members in op.team_members.values() for m in members]
        if not all_members:
            return None
        return min(haversine_distance_m(victim_location, m.location) for m in all_members)

    victims_payload = []
    for v in op.config.victims:
        vid = v.victim_id
        latest_by_sensor = {}
        readings = readings_by_victim.get(vid, [])
        for r in readings[::-1]:
            key = r.sensor_type.value
            if key not in latest_by_sensor:
                latest_by_sensor[key] = {
                    "value": r.value,
                    "unit": r.unit,
                    "confidence": r.confidence,
                    "noisy": r.noisy,
                    "timestamp": r.timestamp,
                }
        fusion = fusion_results[vid]
        location = readings[-1].location if readings else v.location
        nearest_dist = _nearest_member_distance_m(location)
        victims_payload.append({
            "victim_id": vid,
            "location": {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "altitude_m": location.altitude_m,
            },
            "nearest_team_member_distance_m": round(nearest_dist, 1) if nearest_dist is not None else None,
            "sensors": latest_by_sensor,
            "sensor_node_online": len(readings) > 0,
            "battery_pct": battery_report.get(vid, 100.0),
            "charging": power_report.get(vid, {}).get("charging", False),
            "kit_disturbed": imu_report.get(vid, {}).get("kit_disturbed", False),
            "fusion": fusion.to_dict(),
        })

    return {
        "operation_id": _op_id(op, operation_id),
        "scenario": op.scenario_meta(),
        "victims": victims_payload,
    }


@app.get("/battery")
@app.get("/operations/{operation_id}/battery")
def get_battery(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    report = op.simulator.battery_report()
    return {
        "operation_id": _op_id(op, operation_id),
        "scenario": op.scenario_meta(),
        "battery": [
            {"victim_id": vid, "battery_pct": pct, "low_battery": pct < LOW_BATTERY_WARNING_PCT}
            for vid, pct in report.items()
        ],
    }


@app.get("/rain")
@app.get("/operations/{operation_id}/rain")
def get_rain(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    report = op.simulator.rain_report()
    return {"operation_id": _op_id(op, operation_id), "scenario": op.scenario_meta(), **report}


@app.get("/soil")
@app.get("/operations/{operation_id}/soil")
def get_soil(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    report = op.simulator.soil_report()
    return {"operation_id": _op_id(op, operation_id), "scenario": op.scenario_meta(), **report}


@app.get("/seismic")
@app.get("/operations/{operation_id}/seismic")
def get_seismic(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    report = op.simulator.seismic_report()
    return {"operation_id": _op_id(op, operation_id), "scenario": op.scenario_meta(), **report}


@app.get("/tilt")
@app.get("/operations/{operation_id}/tilt")
def get_tilt(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    report = op.simulator.tilt_report()
    return {"operation_id": _op_id(op, operation_id), "scenario": op.scenario_meta(), **report}


@app.get("/fusion-config")
@app.get("/operations/{operation_id}/fusion-config")
def get_fusion_config(operation_id: Optional[str] = None):
    import fusion_engine as fe
    return {
        "confidence_weights": {
            "radar": fe.WEIGHT_RADAR, "thermal": fe.WEIGHT_THERMAL, "acoustic": fe.WEIGHT_ACOUSTIC,
            "co2": fe.WEIGHT_CO2, "camera": fe.WEIGHT_CAMERA,
            "uwb_bioradar": getattr(fe, "WEIGHT_UWB_LANDSLIDE", 0.40),
        },
        "triage_thresholds_pct": {
            "high": fe.HIGH_THRESHOLD_PCT, "tap_high_min": fe.TAP_HIGH_MIN_PCT,
            "medium": fe.MEDIUM_THRESHOLD_PCT, "low": fe.LOW_THRESHOLD_PCT,
        },
        "hazard_multiplier_cap": fe.HAZARD_MULTIPLIER_CAP,
    }


# --------------------------------------------------------------------------- #
# Subsurface UWB Bioradar Simulation Endpoints (RIDGEWATCH Landslide Module)
# --------------------------------------------------------------------------- #

class SubsurfaceConfigPayload(BaseModel):
    preset_id: Optional[Any] = None
    soil_type: Optional[str] = None
    soil_moisture_pct: Optional[float] = None
    clay_fraction: Optional[float] = None
    burial_depth_m: Optional[float] = None
    clutter_level: Optional[str] = None
    sensor_noise: Optional[str] = None
    survivor_mode: Optional[str] = None
    survivor_alive: Optional[bool] = None
    breathing_rate_rpm: Optional[float] = None
    heart_rate_bpm: Optional[float] = None
    micro_motion: Optional[bool] = None
    micro_motion_level: Optional[str] = None
    respiration_pattern: Optional[str] = None
    heartbeat_pattern: Optional[str] = None
    target_orientation: Optional[str] = None
    target_movement: Optional[str] = None
    obstacles: Optional[List[Dict[str, Any]]] = None
    enable_layer_interfaces: Optional[bool] = None
    enable_shadowing: Optional[bool] = None
    enable_ringing: Optional[bool] = None
    layered_profile: Optional[List[Dict[str, Any]]] = None
    step_time: Optional[float] = 0.5
    seed: Optional[int] = None


class SubsurfaceControlPayload(BaseModel):
    action: str  # "start", "pause", "resume", "reset", "set_preset"
    preset_id: Optional[Any] = None


class SubsurfaceReadingPayload(BaseModel):
    device_id: Optional[str] = "DEV-UWB-RADAR-01"
    victim_id: Optional[str] = "VICTIM-UWB-01"
    session_id: Optional[str] = "SUBSURFACE_SIM_SESSION"
    value: Optional[float] = 85.0
    unit: Optional[str] = "%"
    confidence: Optional[float] = 0.90
    estimated_depth_m: Optional[float] = 1.0
    ground_truth_depth_m: Optional[float] = None
    respiration_rpm: Optional[float] = None
    heart_rate_bpm: Optional[float] = None
    soil_type: Optional[str] = "wet_soil"
    moisture_pct: Optional[float] = 50.0
    snr_db: Optional[float] = 15.0
    latitude: Optional[float] = 32.2435
    longitude: Optional[float] = 77.1895


@app.get("/api/subsurface/presets")
@app.get("/subsurface/presets")
def get_subsurface_presets():
    """Return all predefined simulation presets."""
    try:
        import subsurface_dsp as sdsp
    except ImportError:
        import backend.subsurface_dsp as sdsp
    presets_data = {}
    for k, p in sdsp.SubsurfaceSimulator.PRESETS.items():
        presets_data[k] = {
            "id": k,
            "name": p["name"],
            "description": p["description"],
            "soil_type": p["soil_type"].value if hasattr(p["soil_type"], "value") else str(p["soil_type"]),
            "soil_moisture_pct": p["soil_moisture_pct"],
            "clay_fraction": p.get("clay_fraction", 0.20),
            "burial_depth_m": p["burial_depth_m"],
            "clutter_level": p["clutter_level"],
            "sensor_noise": p["sensor_noise"],
            "survivor_mode": p["survivor_mode"],
            "survivor_alive": p["survivor_alive"],
            "breathing_rate_rpm": p["breathing_rate_rpm"],
            "heart_rate_bpm": p["heart_rate_bpm"],
            "respiration_pattern": p.get("respiration_pattern", "normal"),
            "micro_motion_level": p.get("micro_motion_level", "medium"),
            "layered_profile": p.get("layered_profile", None),
        }
    return {
        "success": True,
        "disclaimer": "SIMULATION MODE — SOFTWARE-SIMULATED UWB BIORADAR (0–6.0m) — 5m Simulation Target / No Physical Hardware Validation",
        "simulation_label": "SIMULATION MODE — SOFTWARE-SIMULATED UWB BIORADAR (0–6.0m)",
        "presets": presets_data,
    }


@app.get("/api/subsurface/status")
@app.get("/subsurface/status")
def get_subsurface_status():
    """Return current subsurface simulator state, active config, and latest telemetry."""
    try:
        import subsurface_dsp as sdsp
    except ImportError:
        import backend.subsurface_dsp as sdsp
    sim = sdsp.subsurface_simulator
    telemetry = sim.last_telemetry or sim.run_simulation_cycle()
    return {
        "success": True,
        "simulation_mode": True,
        "is_simulated": True,
        "hardware_connected": False,
        "disclaimer": "SIMULATION MODE — SOFTWARE-SIMULATED UWB BIORADAR (0–6.0m) — 5m Simulation Target / No Physical Hardware Validation",
        "simulation_label": "SIMULATION MODE — SOFTWARE-SIMULATED UWB BIORADAR (0–6.0m)",
        "config": sim.config.to_dict(),
        "telemetry": telemetry.to_dict(),
    }


@app.post("/api/subsurface/simulate")
@app.post("/subsurface/simulate")
def post_subsurface_simulate(payload: Optional[SubsurfaceConfigPayload] = None):
    """Execute one simulation cycle with optional configuration updates."""
    try:
        import subsurface_dsp as sdsp
    except ImportError:
        import backend.subsurface_dsp as sdsp
    sim = sdsp.subsurface_simulator
    if payload:
        if payload.preset_id:
            sim.set_preset(payload.preset_id)
        updates = payload.dict(exclude_unset=True) if hasattr(payload, "dict") else payload.model_dump(exclude_unset=True)
        if updates:
            sim.update_config(**updates)

    telemetry = sim.run_simulation_cycle()
    return {
        "success": True,
        "simulation_mode": True,
        "is_simulated": True,
        "disclaimer": "SIMULATION MODE — SOFTWARE-SIMULATED UWB BIORADAR (0–6.0m) — 5m Simulation Target / No Physical Hardware Validation",
        "simulation_label": "SIMULATION MODE — SOFTWARE-SIMULATED UWB BIORADAR (0–6.0m)",
        "config": sim.config.to_dict(),
        "telemetry": telemetry.to_dict(),
    }


@app.post("/api/subsurface/config")
@app.post("/subsurface/config")
def post_subsurface_config(payload: SubsurfaceConfigPayload):
    """Update subsurface simulation configuration."""
    try:
        import subsurface_dsp as sdsp
    except ImportError:
        import backend.subsurface_dsp as sdsp
    sim = sdsp.subsurface_simulator
    if payload.preset_id:
        sim.set_preset(payload.preset_id)
    updates = payload.dict(exclude_unset=True) if hasattr(payload, "dict") else payload.model_dump(exclude_unset=True)
    if updates:
        sim.update_config(**updates)
    telemetry = sim.run_simulation_cycle()
    return {
        "success": True,
        "status": "CONFIG_UPDATED",
        "disclaimer": "SIMULATION MODE — SOFTWARE-SIMULATED UWB BIORADAR (0–6.0m) — 5m Simulation Target / No Physical Hardware Validation",
        "simulation_label": "SIMULATION MODE — SOFTWARE-SIMULATED UWB BIORADAR (0–6.0m)",
        "config": sim.config.to_dict(),
        "telemetry": telemetry.to_dict(),
    }


@app.post("/api/subsurface/control")
@app.post("/subsurface/control")
def post_subsurface_control(payload: SubsurfaceControlPayload):
    """Control simulation state: start, pause, resume, reset, set_preset."""
    try:
        import subsurface_dsp as sdsp
    except ImportError:
        import backend.subsurface_dsp as sdsp
    sim = sdsp.subsurface_simulator
    action = payload.action.lower().strip()
    if action in ("start", "resume"):
        sim.start()
    elif action == "pause":
        sim.pause()
    elif action == "reset":
        sim.reset()
    elif action == "set_preset":
        if payload.preset_id is None:
            raise HTTPException(status_code=400, detail="preset_id required for set_preset action")
        ok = sim.set_preset(payload.preset_id)
        if not ok:
            raise HTTPException(status_code=400, detail=f"Unknown preset: {payload.preset_id}")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown control action: '{payload.action}'")

    telemetry = sim.run_simulation_cycle()
    return {
        "success": True,
        "status": action.upper(),
        "is_running": sim.is_running,
        "disclaimer": "SIMULATION MODE — NO PHYSICAL UWB HARDWARE",
        "simulation_label": "SIMULATION MODE — NO PHYSICAL UWB HARDWARE",
        "config": sim.config.to_dict(),
        "telemetry": telemetry.to_dict(),
    }


@app.post("/api/sensor/subsurface-reading")
def post_subsurface_sensor_reading(payload: SubsurfaceReadingPayload):
    """
    Ingest a subsurface UWB bioradar reading into the telemetry registry.
    Strictly differentiates ground truth vs estimated metrics.
    """
    import models as m
    import db

    loc = m.GPSCoordinate(
        latitude=payload.latitude or 32.2435,
        longitude=payload.longitude or 77.1895,
    )
    conf_val = payload.confidence if payload.confidence is not None else 0.90
    reading_val = payload.value if payload.value is not None else (conf_val * 100.0)
    reading = m.SensorReading(
        sensor_type=m.SensorType.UWB_BIORADAR,
        value=reading_val,
        unit=payload.unit or "%",
        location=loc,
        victim_id=payload.victim_id or "VICTIM-UWB-01",
        device_id=payload.device_id or "DEV-UWB-RADAR-01",
        confidence=conf_val,
        status=m.SensorHealthStatus.ONLINE,
        raw_data={
            "is_simulated": True,
            "simulation_label": "SIMULATION MODE — NO PHYSICAL UWB HARDWARE",
            "estimated_depth_m": payload.estimated_depth_m,
            "ground_truth_depth_m": payload.ground_truth_depth_m,
        },
    )

    try:
        with db._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sessions
                    (session_id, started_at, enable_degradation, victim_count, scenario_id, scenario_name)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.session_id or "SUBSURFACE_SIM_SESSION",
                    datetime.now(timezone.utc).isoformat(),
                    0,
                    1,
                    "landslide",
                    "Landslide Subsurface Simulation",
                ),
            )
            conn.execute(
                """
                INSERT INTO sensor_readings
                    (session_id, cycle, victim_id, sensor_type, value, unit,
                     sensor_confidence, noisy, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.session_id or "SUBSURFACE_SIM_SESSION",
                    1,
                    reading.victim_id or "SITE",
                    reading.sensor_type.value if hasattr(reading.sensor_type, "value") else str(reading.sensor_type),
                    reading.value,
                    reading.unit,
                    reading.confidence,
                    0,
                    reading.timestamp,
                ),
            )
    except Exception as ex:
        logger.warning(f"Could not persist subsurface reading to db: {ex}")

    return {
        "success": True,
        "status": "INGESTED",
        "device_id": payload.device_id or "DEV-UWB-RADAR-01",
        "is_simulated": True,
        "estimated_depth_m": payload.estimated_depth_m,
        "ground_truth_depth_m": payload.ground_truth_depth_m,
        "confidence": conf_val,
        "reading": reading.to_dict(),
        "disclaimer": "SIMULATION MODE — NO PHYSICAL UWB HARDWARE",
        "simulation_label": "SIMULATION MODE — NO PHYSICAL UWB HARDWARE",
    }


@app.get("/environment")
@app.get("/operations/{operation_id}/environment")
def get_environment(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    report = {
        **op.simulator.temperature_report(),
        **op.simulator.humidity_report(),
    }
    return {"operation_id": _op_id(op, operation_id), "scenario": op.scenario_meta(), **report}


@app.get("/power")
@app.get("/operations/{operation_id}/power")
def get_power(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    report = op.simulator.power_report()
    return {
        "operation_id": _op_id(op, operation_id),
        "scenario": op.scenario_meta(),
        "daylight": op.simulator.is_daylight(),
        "power": [
            {"victim_id": vid, **info}
            for vid, info in report.items()
        ],
    }


@app.get("/queue")
@app.get("/operations/{operation_id}/queue")
def get_queue(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    op.tick()

    fusion_results = op.fuse_current()
    ranked = rank_victims(fusion_results.values())
    new_alerts = op._dispatch_alerts(ranked)

    queue_payload = [
        {
            "rank": i + 1,
            "victim_id": r.victim_id,
            "triage_class": r.triage_class.value,
            "confidence_pct": round(r.confidence_pct, 2),
            "sps": round(r.sps, 2),
            "hazard_multiplier": round(r.hazard_multiplier, 3),
            "tapping_detected": r.tapping_detected,
            "location": {
                "latitude": r.location.latitude,
                "longitude": r.location.longitude,
                "altitude_m": r.location.altitude_m,
            } if r.location else None,
            "notes": r.notes,
        }
        for i, r in enumerate(ranked)
    ]

    return {
        "operation_id": _op_id(op, operation_id),
        "scenario": op.scenario_meta(),
        "queue": queue_payload,
        "new_alerts": [a.to_dict() for a in new_alerts],
    }


@app.get("/commander/overview")
@app.get("/operations/{operation_id}/commander/overview")
def commander_overview(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    op.tick()
    newly_arrived = op.advance_team_members()

    for m in newly_arrived:
        if op.session_id:
            db.log_rescue_status_event(
                session_id=op.session_id, event_type="member_arrived",
                team_id=m.team_id, victim_id=m.assigned_victim_id,
                notes=f"{m.callsign} reached {m.assigned_victim_id}.",
            )

    fusion_results = op.fuse_current()
    ranked = rank_victims(fusion_results.values())

    victims_payload = [
        {
            "victim_id": r.victim_id,
            "triage_class": r.triage_class.value,
            "confidence_pct": round(r.confidence_pct, 2),
            "sps": round(r.sps, 2),
            "location": {
                "latitude": r.location.latitude,
                "longitude": r.location.longitude,
                "altitude_m": r.location.altitude_m,
            } if r.location else None,
        }
        for r in ranked
    ]

    # Ensure Alpha Member 1 authoritative state is synchronized with latest real GPS telemetry
    has_a1_gps = (ALPHA_M001_LATEST_GPS.get("latitude") is not None and ALPHA_M001_LATEST_GPS.get("longitude") is not None and ALPHA_M001_LATEST_GPS.get("location_source") == "PHONE_GPS")
    for team_id, members in op.team_members.items():
        for m in members:
            if m.member_id == "ALPHA-M001" and has_a1_gps and (m.location_source == "PHONE_GPS" or ALPHA_M001_LATEST_GPS.get("location_source") == "PHONE_GPS"):
                m.location = GPSCoordinate(
                    latitude=ALPHA_M001_LATEST_GPS["latitude"],
                    longitude=ALPHA_M001_LATEST_GPS["longitude"],
                    altitude_m=ALPHA_M001_LATEST_GPS.get("altitude_m") if ALPHA_M001_LATEST_GPS.get("altitude_m") is not None else m.location.altitude_m,
                )
                m.location_source = "PHONE_GPS"
                if ALPHA_M001_LATEST_GPS.get("accuracy_m") is not None:
                    m.accuracy_m = ALPHA_M001_LATEST_GPS["accuracy_m"]
                if ALPHA_M001_LATEST_GPS.get("speed_mps") is not None:
                    m.speed_mps = ALPHA_M001_LATEST_GPS["speed_mps"]
                if ALPHA_M001_LATEST_GPS.get("heading_deg") is not None:
                    m.heading_deg = ALPHA_M001_LATEST_GPS["heading_deg"]
                if ALPHA_M001_LATEST_GPS.get("gps_timestamp") is not None:
                    m.gps_timestamp = ALPHA_M001_LATEST_GPS["gps_timestamp"]
                if ALPHA_M001_LATEST_GPS.get("gps_status") is not None:
                    m.gps_status = ALPHA_M001_LATEST_GPS["gps_status"]
                if ALPHA_M001_LATEST_GPS.get("navigation_status") is not None:
                    m.navigation_status = ALPHA_M001_LATEST_GPS["navigation_status"]
                if ALPHA_M001_LATEST_GPS.get("target_bearing_deg") is not None:
                    m.target_bearing_deg = ALPHA_M001_LATEST_GPS["target_bearing_deg"]
                if ALPHA_M001_LATEST_GPS.get("heading_difference_deg") is not None:
                    m.heading_difference_deg = ALPHA_M001_LATEST_GPS["heading_difference_deg"]
                if ALPHA_M001_LATEST_GPS.get("direction_delta_deg") is not None:
                    m.direction_delta_deg = ALPHA_M001_LATEST_GPS["direction_delta_deg"]
                if ALPHA_M001_LATEST_GPS.get("distance_to_target_m") is not None:
                    m.distance_to_target_m = ALPHA_M001_LATEST_GPS["distance_to_target_m"]
                if ALPHA_M001_LATEST_GPS.get("distance_trend") is not None:
                    m.distance_trend = ALPHA_M001_LATEST_GPS["distance_trend"]
                if ALPHA_M001_LATEST_GPS.get("direction_guidance") is not None:
                    m.direction_guidance = ALPHA_M001_LATEST_GPS["direction_guidance"]
                if ALPHA_M001_LATEST_GPS.get("arrived_at") is not None:
                    m.arrived_at = ALPHA_M001_LATEST_GPS["arrived_at"]
                if ALPHA_M001_LATEST_GPS.get("active_command_id") is not None:
                    m.active_command_id = ALPHA_M001_LATEST_GPS["active_command_id"]

    # Ensure active mission command ID is populated from DB for active members
    active_cmd_a1 = db.get_active_command_for_member("ALPHA-M001")
    if active_cmd_a1:
        for members in op.team_members.values():
            for m in members:
                if m.member_id == "ALPHA-M001":
                    m.active_command_id = active_cmd_a1.get("command_id")
                    if not m.assigned_victim_id:
                        m.assigned_victim_id = active_cmd_a1.get("victim_id")

    members_payload = [
        m.to_dict()
        for team_id, members in op.team_members.items()
        for m in members
    ]

    active_scenario_key = normalize_scenario_key(op.config.scenario_id) if (op and op.config and op.config.scenario_id) else None
    if active_scenario_key:
        all_jobs = db.list_commander_jobs(scenario_id=active_scenario_key)
    else:
        all_jobs = db.list_commander_jobs()
    all_assignments = db.list_job_assignments()
    assessment_dict = op.latest_assessment.to_dict() if op.latest_assessment else {}
    active_alerts = db.list_active_alerts(session_id=op.session_id, status="ACTIVE")
    env_report = op.simulator.environmental_full_report() if op.simulator else {}

    return {
        "operation_id": _op_id(op, operation_id),
        "scenario": op.scenario_meta(),
        "victims": victims_payload,
        "team_members": members_payload,
        "newly_arrived": [m.to_dict() for m in newly_arrived],
        "jobs": all_jobs,
        "assignments": all_assignments,
        "disaster_assessment": assessment_dict,
        "active_alerts": active_alerts,
        "environmental": env_report,
    }


# --------------------------------------------------------------------------- #
# Scenario-Based Commander Jobs & Matching Endpoints
# --------------------------------------------------------------------------- #

@app.post("/commander/jobs/create")
@app.post("/operations/{operation_id}/commander/jobs/create")
def commander_create_job(req: CreateCommanderJobRequest, operation_id: Optional[str] = None):
    if not req.job_name or not req.job_name.strip():
        raise HTTPException(status_code=422, detail="job_name is required")
    if not req.scenario_id or not req.scenario_id.strip():
        raise HTTPException(status_code=422, detail="scenario_id is required")

    scenario_meta = get_scenario_by_id(req.scenario_id)
    scenario_name = scenario_meta["name"] if scenario_meta else req.scenario_id.title().replace("_", " ")

    job_id = f"JOB-{uuid.uuid4().hex[:6].upper()}"
    job = db.create_commander_job(
        job_id=job_id,
        job_name=req.job_name.strip(),
        scenario_id=normalize_scenario_key(req.scenario_id),
        scenario_name=scenario_name,
        location=req.location,
        latitude=req.latitude,
        longitude=req.longitude,
        priority=(req.priority or "HIGH").upper(),
        description=req.description,
        victim_id=req.victim_id,
        created_by="Commander",
    )
    return {"created": True, "job_id": job_id, "job": job}


@app.get("/commander/jobs")
@app.get("/operations/{operation_id}/commander/jobs")
def commander_list_jobs(
    scenario_id: Optional[str] = None,
    status: Optional[str] = None,
    operation_id: Optional[str] = None,
):
    norm_scenario = normalize_scenario_key(scenario_id) if scenario_id else None
    return {"jobs": db.list_commander_jobs(scenario_id=norm_scenario, status=status)}


@app.get("/commander/jobs/{job_id}")
@app.get("/operations/{operation_id}/commander/jobs/{job_id}")
def commander_get_job(job_id: str, operation_id: Optional[str] = None):
    job = db.get_commander_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {"job": job}


@app.get("/commander/eligible-staff")
@app.get("/operations/{operation_id}/commander/eligible-staff")
@app.get("/commander/jobs/{job_id}/eligible-staff")
@app.get("/operations/{operation_id}/commander/jobs/{job_id}/eligible-staff")
def commander_eligible_staff(
    job_id: Optional[str] = None,
    scenario_id: Optional[str] = None,
    operation_id: Optional[str] = None,
):
    target_scenario = scenario_id
    if job_id:
        job = db.get_commander_job(job_id)
        if job:
            target_scenario = job["scenario_id"]

    if not target_scenario:
        op = _get_operation_optional(operation_id)
        if op and op.config:
            target_scenario = op.config.scenario_id or op.config.name
        else:
            target_scenario = "earthquake"

    norm_target_scenario = normalize_scenario_key(target_scenario)

    all_personnel = db.list_personnel()
    personnel_by_id = {p["person_id"]: p for p in all_personnel}

    op = _get_operation_optional(operation_id)
    member_by_p_id = {}
    standalone_live_members = []
    if op and op.running:
        for tid, members in op.team_members.items():
            for m in members:
                if m.personnel_id:
                    member_by_p_id[m.personnel_id] = m
                else:
                    standalone_live_members.append(m)

    eligible = []
    ineligible = []

    # 1. Process all personnel from registry
    for p in all_personnel:
        p_id = p["person_id"]
        scenarios = p.get("scenarios", [])
        is_active = p.get("status", "Active") == "Active"
        is_match = is_staff_eligible_for_scenario(scenarios, norm_target_scenario)
        live_m = member_by_p_id.get(p_id)

        staff_entry = {
            "member_id": live_m.member_id if live_m else p_id,
            "personnel_id": p_id,
            "callsign": live_m.callsign if live_m else p["full_name"],
            "full_name": p["full_name"],
            "team_id": live_m.team_id if live_m else "UNASSIGNED",
            "role": (live_m.role if live_m else p.get("role")) or "Rescuer",
            "status": live_m.status.value if live_m else "hold",
            "phone": p.get("phone"),
            "email": p.get("email"),
            "scenarios": scenarios,
            "is_active": is_active,
            "scenario_match": is_match,
        }

        if not is_active:
            staff_entry["reason"] = "Staff member is Inactive"
            ineligible.append(staff_entry)
        elif not is_match:
            staff_entry["reason"] = f"Not trained for scenario '{target_scenario}'"
            ineligible.append(staff_entry)
        else:
            eligible.append(staff_entry)

    # 2. Process standalone live team members (e.g. simulated team members without a personnel_id)
    for m in standalone_live_members:
        scenarios = m.scenarios or ["earthquake", "avalanche", "flood", "building_collapse"]
        is_match = is_staff_eligible_for_scenario(scenarios, norm_target_scenario)
        staff_entry = {
            "member_id": m.member_id,
            "personnel_id": None,
            "callsign": m.callsign,
            "full_name": m.full_name,
            "team_id": m.team_id,
            "role": m.role,
            "status": m.status.value,
            "scenarios": scenarios,
            "is_active": True,
            "scenario_match": is_match,
        }
        if not is_match:
            staff_entry["reason"] = f"Not trained for scenario '{target_scenario}'"
            ineligible.append(staff_entry)
        else:
            eligible.append(staff_entry)

    return {
        "scenario_id": norm_target_scenario,
        "eligible": eligible,
        "ineligible": ineligible,
        "eligible_count": len(eligible),
        "ineligible_count": len(ineligible),
    }


@app.post("/commander/jobs/assign")
@app.post("/operations/{operation_id}/commander/jobs/assign")
def commander_assign_job(req: AssignCommanderJobRequest, operation_id: Optional[str] = None):
    job = db.get_commander_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{req.job_id}' not found")

    op = _get_operation_optional(operation_id)
    member = None
    if op and op.running:
        member = next(
            (m for members in op.team_members.values() for m in members if m.member_id == req.member_id or m.personnel_id == req.member_id),
            None,
        )

    p_rec = None
    if member and member.personnel_id:
        p_rec = db.get_personnel(member.personnel_id)
    elif not member:
        p_rec = db.get_personnel(req.member_id)
        if not p_rec:
            contact = db.resolve_member_contact_info(req.member_id)
            if contact and contact.get("personnel_id"):
                p_rec = db.get_personnel(contact["personnel_id"])

    if not member and not p_rec:
        raise HTTPException(status_code=404, detail=f"Unknown staff member '{req.member_id}'")

    is_active = (p_rec.get("status") == "Active") if p_rec else True
    if not is_active:
        raise HTTPException(status_code=400, detail="Staff member is inactive and cannot be assigned.")

    staff_scenarios = member.scenarios if (member and member.scenarios) else (p_rec.get("scenarios") if p_rec else [])
    if not staff_scenarios and p_rec:
        staff_scenarios = p_rec.get("scenarios", [])

    # Strict server-side scenario compatibility validation
    if not is_staff_eligible_for_scenario(staff_scenarios, job["scenario_id"]):
        raise HTTPException(
            status_code=400,
            detail="Staff is not eligible for this disaster scenario.",
        )

    assignment_id = f"ASN-{uuid.uuid4().hex[:6].upper()}"
    person_id_from_rec = p_rec.get("person_id", req.member_id) if isinstance(p_rec, dict) else req.member_id
    member_id_val = member.member_id if member else req.member_id
    personnel_id_val = member.personnel_id if (member and member.personnel_id) else person_id_from_rec
    team_id_val = member.team_id if member else ("ALPHA" if "ALPHA" in req.member_id.upper() else "BRAVO" if "BRAVO" in req.member_id.upper() else "COMMAND")

    assignment = db.create_job_assignment(
        assignment_id=assignment_id,
        job_id=req.job_id,
        member_id=member_id_val,
        personnel_id=personnel_id_val,
        team_id=team_id_val,
        scenario_id=job["scenario_id"],
        assigned_by="Commander",
        status="ASSIGNED",
        result_notes=req.notes,
    )

    if member:
        member.assigned_job_id = req.job_id
        if member.status == MemberStatus.HOLD:
            member.status = MemberStatus.EN_ROUTE
            member.assigned_at = datetime.now(timezone.utc).isoformat()

    if op and op.session_id:
        db.log_rescue_status_event(
            session_id=op.session_id,
            event_type="job_assigned",
            team_id=team_id_val,
            notes=f"Commander assigned {member.callsign if member else personnel_id_val} to Job {req.job_id} ({job['job_name']}).",
        )

    # Isolated Multi-Channel Notification Dispatch (SMSGate SMS)
    try:
        try:
            from notification_dispatch import dispatch_job_assignment_notifications
        except ImportError:
            from backend.notification_dispatch import dispatch_job_assignment_notifications

        dispatch_job_assignment_notifications(
            assignment_id=assignment_id,
            job_id=req.job_id,
            job_name=job.get("job_name", req.job_id),
            team_id=team_id_val,
            member_id=member_id_val,
            scenario_id=job.get("scenario_id", ""),
            location=job.get("location", ""),
            priority=job.get("priority", "HIGH"),
            notes=req.notes,
            instructions=job.get("description") or req.notes,
        )
    except Exception as notif_ex:
        logger.warning(f"Work assignment SMS notification dispatch non-blocking exception: {notif_ex}")

    return {
        "assigned": True,
        "status": "ASSIGNED",
        "assignment_id": assignment_id,
        "assignment": assignment,
        "job": job,
        "member": member.to_dict() if member else None,
    }


@app.get("/staff/{member_id}/jobs")
@app.get("/operations/{operation_id}/staff/{member_id}/jobs")
def staff_list_jobs(member_id: str, operation_id: Optional[str] = None):
    assignments = db.list_job_assignments(member_id=member_id)
    return {
        "member_id": member_id,
        "assignments": assignments,
        "active_count": len([a for a in assignments if a["status"] not in ("COMPLETED", "FAILED")]),
    }


@app.post("/staff/jobs/{assignment_id}/status")
@app.post("/operations/{operation_id}/staff/jobs/{assignment_id}/status")
def staff_update_job_status(
    assignment_id: str,
    req: UpdateStaffJobStatusRequest,
    operation_id: Optional[str] = None,
):
    status_val = req.status.upper().strip()
    if status_val not in ("ASSIGNED", "ACCEPTED", "IN_PROGRESS", "COMPLETED", "FAILED"):
        raise HTTPException(status_code=422, detail=f"Invalid assignment status '{req.status}'")

    assignment = db.get_job_assignment(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail=f"Assignment '{assignment_id}' not found")

    if status_val == "ACCEPTED":
        result = accept_rescue_assignment(
            command_or_assignment_id=assignment_id,
            acceptance_source="APK",
            operation_id=operation_id,
        )
        if not result.get("success") and not result.get("already_accepted"):
            raise HTTPException(status_code=400, detail=result.get("error", "Acceptance failed"))
        if req.progress_pct is not None or req.result_notes is not None:
            db.update_job_assignment_status(
                assignment_id=assignment_id,
                status=status_val,
                progress_pct=req.progress_pct,
                result_notes=req.result_notes,
            )
        updated_assignment = db.get_job_assignment(assignment_id)
        return {"updated": True, "assignment": updated_assignment, "result": result}

    updated = db.update_job_assignment_status(
        assignment_id=assignment_id,
        status=status_val,
        progress_pct=req.progress_pct,
        result_notes=req.result_notes,
    )

    op = _get_operation_optional(operation_id)
    if op and op.running:
        member = next(
            (m for members in op.team_members.values() for m in members if m.member_id == assignment["member_id"] or m.personnel_id == assignment["personnel_id"]),
            None,
        )
        if member:
            if status_val in ("ACCEPTED", "IN_PROGRESS"):
                member.status = MemberStatus.EN_ROUTE
            elif status_val == "COMPLETED":
                member.status = MemberStatus.ARRIVED
            elif status_val == "FAILED":
                member.status = MemberStatus.HOLD

        if op.session_id:
            db.log_rescue_status_event(
                session_id=op.session_id,
                event_type="job_status_updated",
                team_id=assignment["team_id"],
                notes=f"Staff assignment {assignment_id} updated to {status_val} (Progress: {req.progress_pct}%). {req.result_notes or ''}",
            )

    updated_assignment = db.get_job_assignment(assignment_id)
    return {"updated": True, "assignment": updated_assignment}


@app.get("/commander/assignments")
@app.get("/operations/{operation_id}/commander/assignments")
def commander_list_assignments(operation_id: Optional[str] = None):
    return {"assignments": db.list_job_assignments()}


@app.get("/commander/nearest/{member_id}")
@app.get("/operations/{operation_id}/commander/nearest/{member_id}")
def commander_nearest_victims(member_id: str, operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)

    member = next(
        (m for members in op.team_members.values() for m in members if m.member_id == member_id),
        None,
    )
    if member is None:
        raise HTTPException(status_code=404, detail=f"Unknown team member '{member_id}'")

    fusion_results = op.fuse_current()
    ranked = rank_victims(fusion_results.values())

    candidates = []
    for r in ranked:
        if r.location is None:
            continue
        distance_m = haversine_distance_m(member.location, r.location)
        candidates.append({
            "victim_id": r.victim_id,
            "triage_class": r.triage_class.value,
            "confidence_pct": round(r.confidence_pct, 2),
            "sps": round(r.sps, 2),
            "distance_m": round(distance_m, 1),
            "distance_label": f"{distance_m / 1000:.2f} km" if distance_m >= 1000 else f"{distance_m:.0f} m",
        })

    candidates.sort(key=lambda c: c["distance_m"])

    return {
        "operation_id": _op_id(op, operation_id),
        "member": member.to_dict(),
        "suggestions": candidates[:NEAREST_SUGGESTION_COUNT],
    }


@app.post("/commander/assign")
@app.post("/operations/{operation_id}/commander/assign")
def commander_assign(req: AssignMemberRequest, operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    if op is None or not op.running:
        try:
            op = _get_operation(operation_id)
            op.start(scenario_id="himalaya_avalanche", seed=42)
        except Exception:
            _require_running(op)

    member = next(
        (m for members in op.team_members.values() for m in members if m.member_id == req.member_id),
        None,
    )
    if member is None:
        raise HTTPException(status_code=404, detail=f"Unknown team member '{req.member_id}'")
    if not any(v.victim_id == req.victim_id for v in op.config.victims):
        raise HTTPException(status_code=404, detail=f"Unknown victim '{req.victim_id}'")

    # Validate scenario compatibility against current operation scenario
    op_scenario = (op.config.scenario_id or op.config.name) if op.config else "earthquake"
    p_rec = db.get_personnel(member.personnel_id) if member.personnel_id else None
    if p_rec and p_rec.get("status") != "Active":
        raise HTTPException(status_code=400, detail="Staff member is inactive and cannot be assigned.")

    staff_scenarios = member.scenarios if member.scenarios else (p_rec.get("scenarios") if p_rec else [])
    if not is_staff_eligible_for_scenario(staff_scenarios, op_scenario):
        raise HTTPException(status_code=400, detail="Staff is not eligible for this disaster scenario.")

    # Stage 7 Lifecycle Hardening: Idempotent assignment protection
    existing_cmd = db.get_active_command_for_member(member.member_id)
    if existing_cmd and existing_cmd.get("victim_id") == req.victim_id and existing_cmd.get("status") not in ("COMPLETED", "RESCUED", "CANCELLED"):
        logger.info(f"Idempotent assignment: Member {member.member_id} already assigned to {req.victim_id} under active command {existing_cmd.get('command_id')}")
        member.active_command_id = existing_cmd.get("command_id")
        member.assigned_victim_id = req.victim_id
        return member.to_dict()

    member.status = MemberStatus.EN_ROUTE
    member.assigned_victim_id = req.victim_id
    member.assigned_at = datetime.now(timezone.utc).isoformat()
    if member.member_id == "ALPHA-M001":
        member.location_source = "PHONE_GPS"
        member.gps_status = "WAITING_FOR_PERMISSION" if not ALPHA_M001_LATEST_GPS.get("latitude") else ALPHA_M001_LATEST_GPS.get("gps_status", "TRACKING")
        reset_alpha_m001_mission_navigation_state(new_command_id=None, new_victim_id=req.victim_id, preserve_hardware_fix=True)
        ALPHA_M001_LATEST_GPS["location_source"] = "PHONE_GPS"
        ALPHA_M001_LATEST_GPS["navigation_status"] = "ON_TRACK"
        ALPHA_M001_NAV_STATE["navigation_status"] = "ON_TRACK"

    if op.session_id:
        db.log_rescue_status_event(
            session_id=op.session_id, event_type="member_assigned",
            team_id=member.team_id, victim_id=req.victim_id,
            notes=f"CMD leader assigned {member.callsign} to {req.victim_id}.",
        )

    # Non-blocking Wearable Command Dispatch with Explicit Member-to-Watch Resolution
    try:
        target_victim = next((v for v in op.config.victims if v.victim_id == req.victim_id), None)
        dest_lat = target_victim.location.latitude if target_victim else 0.0
        dest_lon = target_victim.location.longitude if target_victim else 0.0
        dest_alt = target_victim.location.altitude_m if target_victim else 0.0
        dest_label = target_victim.label if target_victim else req.victim_id

        # Resolve member's registered watch hardware
        target_dev_id, hw_meta = global_wearable_gateway.resolve_watch_for_member(member.member_id, member.team_id)

        # Create permanent rescue command in database
        cmd_id = f"CMD-{uuid.uuid4().hex[:8].upper()}"
        member.active_command_id = cmd_id
        if member.member_id == "ALPHA-M001":
            ALPHA_M001_LATEST_GPS["active_command_id"] = cmd_id
            ALPHA_M001_NAV_STATE["active_command_id"] = cmd_id
        db.create_rescue_command(
            command_id=cmd_id,
            team_id=member.team_id,
            scenario_id=op_scenario,
            member_id=member.member_id,
            victim_id=req.victim_id,
            destination_latitude=dest_lat,
            destination_longitude=dest_lon,
            destination_altitude_m=dest_alt,
            destination_label=dest_label,
            priority="HIGH",
            command_type="GO",
            command_text=f"Proceed to rescue {dest_label}",
            target_device_id=target_dev_id,
            location_source="PHONE_GPS",
        )
        
        # Persist alert in active_alerts_ledger for UI alert visibility
        db.upsert_active_alert(
            alert_key=f"CMD_{cmd_id}",
            session_id=op.session_id if (op and op.session_id) else "GLOBAL",
            hazard_type="RESCUE_DISPATCH",
            alert_title=f"🚨 RESCUE MISSION: {member.callsign} ➔ {dest_label}",
            severity="HIGH",
            confidence_pct=100.0,
            evidence_summary=f"Commander dispatched {member.callsign} ({member.member_id}) to rescue {dest_label}.",
        )

        # Parallel Real-Time Physical Watch Dispatch
        global_wearable_gateway.dispatch_alert_to_watch({
            "alert_id": f"ALT-{cmd_id}",
            "command_id": cmd_id,
            "operation_id": op_scenario,
            "team_id": member.team_id,
            "member_id": member.member_id,
            "scenario_id": op_scenario,
            "victim_id": req.victim_id,
            "target_id": req.victim_id,
            "latitude": dest_lat,
            "longitude": dest_lon,
            "altitude_m": dest_alt,
            "location": dest_label,
            "location_label": dest_label,
            "priority": "HIGH",
            "command_type": "GO",
            "command_text": f"Proceed to rescue {dest_label}",
            "title": "🚨 RIDGEWATCH — GO",
            "body": f"Proceed to rescue {dest_label}",
            "watch_device_id": target_dev_id,
            "watch_mac": hw_meta.get("mac_address", "CB:4E:FD:EE:7F:1B"),
            "watch_name": hw_meta.get("bluetooth_name", "CALLPLUS_7F1B"),
        })

        # Notification Dispatch (SMSGate SMS) from the SAME Rescue Command
        try:
            try:
                from notification_dispatch import dispatch_rescue_command_notifications
            except ImportError:
                from backend.notification_dispatch import dispatch_rescue_command_notifications
            sps_val = getattr(target_victim, "sps", 88.5) if target_victim else 88.5
            dispatch_rescue_command_notifications(
                command_id=cmd_id,
                team_id=member.team_id,
                member_id=member.member_id,
                victim_id=req.victim_id,
                destination_label=dest_label,
                destination_latitude=dest_lat,
                destination_longitude=dest_lon,
                priority="HIGH",
                sps=float(sps_val or 88.5),
                distance_m=62.0,
                command_text=f"Proceed to rescue {dest_label}",
                mission_id=f"MSN-{cmd_id}",
            )
        except Exception as notif_ex:
            logger.warning(f"Multi-channel notification dispatch non-blocking exception: {notif_ex}")
    except Exception as ex:
        logger.warning(f"Wearable dispatch notification non-blocking exception: {ex}")

    return member.to_dict()


@app.get("/teams")
@app.get("/api/teams")
@app.get("/api/v1/teams")
@app.get("/teams/list")
@app.get("/operations/{operation_id}/teams")
@app.get("/operations/{operation_id}/teams/list")
def list_teams_endpoint(operation_id: Optional[str] = None):
    op = _get_operation_optional(operation_id)
    if op and op.running and op.team_members:
        teams_list = []
        for team_id, members in op.team_members.items():
            team_name = team_id
            if team_id == "ALPHA":
                team_name = "Rescue Team Alpha"
            elif team_id == "BRAVO":
                team_name = "Rescue Team Bravo"
            elif team_id == "CHARLIE":
                team_name = "Rescue Team Charlie"
            else:
                team_name = f"Rescue Team {team_id}"
            m_dicts = []
            for m in members:
                d = m.to_dict()
                d["watch_device_id"] = "DEV-WEARABLE-CALLPLUS"
                d["watch_mac"] = "CB:4E:FD:EE:7F:1B"
                d["watch_model"] = "Wave Call Plus"
                m_dicts.append(d)
            teams_list.append({
                "team_id": team_id,
                "team_name": team_name,
                "name": team_name,
                "members": m_dicts,
            })
        return {
            "operation_id": _op_id(op, operation_id),
            "teams": teams_list,
            "team_members": [m.to_dict() for members in op.team_members.values() for m in members],
        }

    # Standby fallback: load real teams and roster from SQLite database
    db_teams = db.list_admin_teams()
    teams_list = []
    all_members = []
    if db_teams:
        for t in db_teams:
            t_ref = t.get("team_ref_id") or t.get("team_id") or "ALPHA"
            t_name = t.get("team_name") or f"Rescue Team {t_ref}"
            p_members = t.get("members") if t.get("members") is not None else db.list_team_roster_members(t_ref)
            m_list = []
            for idx, p in enumerate(p_members):
                if isinstance(p, dict):
                    p_full_name = p.get("full_name", f"Rescuer {idx+1}")
                    p_role = p.get("role_on_team", "Rescuer")
                    p_person_id = p.get("person_id")
                elif isinstance(p, str):
                    p_full_name = p
                    p_role = "Rescuer"
                    p_person_id = p
                else:
                    p_full_name = getattr(p, "full_name", f"Rescuer {idx+1}")
                    p_role = getattr(p, "role_on_team", "Rescuer")
                    p_person_id = getattr(p, "person_id", None)
                m_dict = {
                    "member_id": f"{t_ref}-M{idx+1:03d}",
                    "callsign": f"{t_name} - {p_full_name}",
                    "full_name": p_full_name,
                    "team_id": t_ref,
                    "role": p_role,
                    "personnel_id": p_person_id,
                    "status": "hold",
                    "watch_device_id": "DEV-WEARABLE-CALLPLUS",
                    "watch_mac": "CB:4E:FD:EE:7F:1B",
                    "watch_model": "Wave Call Plus",
                    "location": {"latitude": 32.3739, "longitude": 77.2491, "altitude_m": 3950},
                }
                m_list.append(m_dict)
                all_members.append(m_dict)
            if not m_list:
                for idx in range(2):
                    m_dict = {
                        "member_id": f"{t_ref}-M{idx+1:03d}",
                        "callsign": f"{t_name} #{idx+1}",
                        "full_name": f"{t_name} Rescuer {idx+1}",
                        "team_id": t_ref,
                        "role": "Leader" if idx == 0 else "Rescuer",
                        "status": "hold",
                        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
                        "watch_mac": "CB:4E:FD:EE:7F:1B",
                        "watch_model": "Wave Call Plus",
                        "location": {"latitude": 32.3739, "longitude": 77.2491, "altitude_m": 3950},
                    }
                    m_list.append(m_dict)
                    all_members.append(m_dict)
            teams_list.append({
                "team_id": t_ref,
                "team_name": t_name,
                "name": t_name,
                "members": m_list,
            })

    if not teams_list:
        default_defs = [
            ("ALPHA", "Rescue Team Alpha"),
            ("BRAVO", "Rescue Team Bravo"),
            ("CHARLIE", "Rescue Team Charlie"),
        ]
        for t_ref, t_name in default_defs:
            m_list = [
                {
                    "member_id": f"{t_ref}-M001",
                    "callsign": f"{t_name} #1",
                    "full_name": f"{t_name} Leader",
                    "team_id": t_ref,
                    "role": "Leader",
                    "status": "hold",
                    "watch_device_id": "DEV-WEARABLE-CALLPLUS",
                    "watch_mac": "CB:4E:FD:EE:7F:1B",
                    "watch_model": "Wave Call Plus",
                    "location": {"latitude": 32.3739, "longitude": 77.2491, "altitude_m": 3950},
                },
                {
                    "member_id": f"{t_ref}-M002",
                    "callsign": f"{t_name} #2",
                    "full_name": f"{t_name} Rescuer",
                    "team_id": t_ref,
                    "role": "Rescuer",
                    "status": "hold",
                    "watch_device_id": "DEV-WEARABLE-CALLPLUS",
                    "watch_mac": "CB:4E:FD:EE:7F:1B",
                    "watch_model": "Wave Call Plus",
                    "location": {"latitude": 32.3739, "longitude": 77.2491, "altitude_m": 3950},
                },
            ]
            teams_list.append({
                "team_id": t_ref,
                "team_name": t_name,
                "name": t_name,
                "members": m_list,
            })
            all_members.extend(m_list)

    return {
        "operation_id": _op_id(op, operation_id) if op else "standby",
        "teams": teams_list,
        "team_members": all_members,
    }


@app.get("/members")
@app.get("/api/members")
@app.get("/api/v1/members")
@app.get("/api/teams/{team_id}/members")
@app.get("/teams/{team_id}/members")
def list_members_endpoint(team_id: Optional[str] = None, operation_id: Optional[str] = None):
    teams_res = list_teams_endpoint(operation_id=operation_id)
    raw_members = teams_res.get("team_members", []) if isinstance(teams_res, dict) else []
    all_members = []
    for idx, m in enumerate(raw_members):
        if isinstance(m, dict):
            all_members.append(m)
        elif isinstance(m, str):
            t_ref = m.split("-")[0] if "-" in m else "ALPHA"
            all_members.append({
                "member_id": m,
                "callsign": f"Rescuer {m}",
                "full_name": f"Rescuer {m}",
                "team_id": t_ref,
                "role": "Rescuer",
                "status": "hold",
                "watch_device_id": "DEV-WEARABLE-CALLPLUS",
                "watch_mac": "CB:4E:FD:EE:7F:1B",
                "watch_model": "Wave Call Plus",
                "location": {"latitude": 32.3739, "longitude": 77.2491, "altitude_m": 3950},
            })
        elif hasattr(m, "to_dict") and callable(m.to_dict):
            all_members.append(m.to_dict())
        else:
            all_members.append({
                "member_id": getattr(m, "member_id", f"M-{idx+1:03d}"),
                "callsign": getattr(m, "callsign", "Rescuer"),
                "full_name": getattr(m, "full_name", "Rescuer"),
                "team_id": getattr(m, "team_id", getattr(m, "team_ref_id", "ALPHA")),
                "role": getattr(m, "role", "Rescuer"),
                "status": getattr(m, "status", "hold"),
                "watch_device_id": "DEV-WEARABLE-CALLPLUS",
                "watch_mac": "CB:4E:FD:EE:7F:1B",
                "watch_model": "Wave Call Plus",
                "location": getattr(m, "location", {"latitude": 32.3739, "longitude": 77.2491, "altitude_m": 3950}),
            })

    if team_id:
        filtered = [
            m for m in all_members
            if m.get("team_id") == team_id
            or m.get("team_ref_id") == team_id
            or (isinstance(m.get("member_id"), str) and m.get("member_id").startswith(f"{team_id}-"))
        ]
        return {"status": "success", "team_id": team_id, "members": filtered, "total": len(filtered)}
    return {"status": "success", "members": all_members, "total": len(all_members)}


@app.get("/watch")
@app.get("/watch/")
@app.get("/operations/{operation_id}/watch")
@app.get("/operations/{operation_id}/watch/")
def watch_default_view(operation_id: Optional[str] = None):
    op = _get_operation_optional(operation_id)
    if not op or not op.running:
        return {
            "member_id": "ALPHA-M001",
            "callsign": "Rescuer Alpha-1",
            "status": "hold",
            "message": "Awaiting CMD leader assignment.",
        }
    active_m = None
    for members in op.team_members.values():
        for m in members:
            if m.status != MemberStatus.HOLD:
                active_m = m
                break
        if active_m:
            break
    if not active_m:
        active_m = next((m for members in op.team_members.values() for m in members), None)
    if active_m:
        return watch_view(active_m.member_id, operation_id)
    return {
        "member_id": "ALPHA-M001",
        "callsign": "Rescuer Alpha-1",
        "status": "hold",
        "message": "Awaiting CMD leader assignment.",
    }


@app.get("/watch/{member_id}")
@app.get("/operations/{operation_id}/watch/{member_id}")
def watch_view(member_id: str, operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)

    if member_id in ("null", "undefined", ""):
        first_m = next((m for members in op.team_members.values() for m in members), None)
        if not first_m:
            return {
                "member_id": "ALPHA-M001",
                "callsign": "Rescuer",
                "status": "hold",
                "message": "Awaiting CMD leader assignment.",
            }
        member = first_m
    else:
        member = next(
            (m for members in op.team_members.values() for m in members if m.member_id == member_id),
            None,
        )
        if member is None:
            raise HTTPException(status_code=404, detail=f"Unknown watch/member id '{member_id}'")

    if member.status == MemberStatus.HOLD or not member.assigned_victim_id:
        return {
            "member_id": member.member_id,
            "callsign": member.callsign,
            "status": "hold",
            "message": "Awaiting CMD leader assignment.",
        }

    victim = next((v for v in op.config.victims if v.victim_id == member.assigned_victim_id), None)
    if victim is None:
        return {
            "member_id": member.member_id,
            "callsign": member.callsign,
            "status": member.status.value,
            "message": "Assigned target is no longer available.",
        }

    distance_m = haversine_distance_m(member.location, victim.location)
    bearing_deg = _bearing_deg(member.location, victim.location)

    # Check if rescuer has arrived at victim location (within threshold)
    if distance_m <= MEMBER_ARRIVAL_THRESHOLD_M and member.status == MemberStatus.EN_ROUTE:
        member.status = MemberStatus.ARRIVED
    return {
        "member_id": member.member_id,
        "callsign": member.callsign,
        "status": member.status.value,
        "assigned_victim_id": member.assigned_victim_id,
        "distance_m": round(distance_m, 1),
        "distance_label": f"{distance_m / 1000:.2f} km" if distance_m >= 1000 else f"{distance_m:.0f} m",
        "bearing_deg": round(bearing_deg, 1),
        "compass_label": _compass_label(bearing_deg),
    }


@app.get("/alerts")
@app.get("/operations/{operation_id}/alerts")
def get_alerts(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    op_events = op.get_operational_events()
    return {
        "operation_id": _op_id(op, operation_id),
        "scenario": op.scenario_meta(),
        "alerts": [a.to_dict() for a in op.alert_dispatcher.history()],
        "events": op_events["events"],
        "summary": op_events["summary"],
        "operation_status": op_events["operation_status"],
        "recent_activities": op_events["recent_activities"],
    }


@app.get("/analytics/summary")
@app.get("/operations/{operation_id}/analytics/summary")
def analytics_summary(operation_id: Optional[str] = None, scenario_id: Optional[str] = None, since: Optional[str] = None):
    sessions = db.list_sessions()
    summary = []
    for s in sessions:
        if scenario_id and s.get("scenario_id") != scenario_id:
            continue
        if since and s.get("started_at") and s.get("started_at") < since:
            continue

        counts = db.session_counts(s["session_id"])
        raw_rescued = db.count_rescued_events(s["session_id"])
        v_count = max(0, s.get("victim_count", 0))
        rescued_count = min(v_count, max(0, raw_rescued))

        summary.append({
            "session_id": s["session_id"],
            "started_at": s["started_at"],
            "scenario_id": s.get("scenario_id") or "unknown",
            "scenario_name": s.get("scenario_name") or s.get("scenario_id") or "—",
            "victim_count": v_count,
            "rescued_count": rescued_count,
            "alert_count": counts.get("network_alerts", 0),
        })
    summary.sort(key=lambda r: r["started_at"])

    total_rescued = sum(r["rescued_count"] for r in summary)
    total_victims = sum(r["victim_count"] for r in summary)

    return {
        "sessions": summary,
        "totals": {
            "session_count": len(summary),
            "total_rescued": total_rescued,
            "total_victims": total_victims,
            "overall_rescue_rate_pct": round((total_rescued / total_victims) * 100, 1) if total_victims else 0.0,
        },
    }


@app.get("/rescue-team/status")
@app.get("/operations/{operation_id}/rescue-team/status")
def get_rescue_team_status(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)

    fusion_results = op.fuse_current()
    ranked = rank_victims(fusion_results.values())
    _auto_dispatch(op, ranked)
    op.dispatch_agent.load_queue(ranked)

    return {
        "operation_id": _op_id(op, operation_id),
        "scenario": op.scenario_meta(),
        "teams": [t.to_dict() for t in op.rescue_teams],
        "dispatch_sim": op.dispatch_agent.status_dict(),
    }


@app.get("/rescue-team/member-arrivals")
@app.get("/operations/{operation_id}/rescue-team/member-arrivals")
def rescue_team_member_arrivals(since: Optional[str] = None, operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    arrivals = op.recent_member_arrivals
    if since:
        arrivals = [a for a in arrivals if a["arrived_at"] > since]
    return {"operation_id": _op_id(op, operation_id), "arrivals": arrivals}


@app.get("/rescue-team/members-status")
@app.get("/operations/{operation_id}/rescue-team/members-status")
def rescue_team_members_status(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    all_members = [m for members in op.team_members.values() for m in members]
    return {
        "operation_id": _op_id(op, operation_id),
        "members": [m.to_dict() for m in all_members],
        "recent_arrivals": op.recent_member_arrivals[-5:],
    }


@app.post("/rescue-team/advance")
@app.post("/operations/{operation_id}/rescue-team/advance")
def advance_rescue_team(req: RescueAdvanceRequest = RescueAdvanceRequest(), operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)

    if req.steps < 1:
        raise HTTPException(status_code=400, detail="steps must be >= 1")

    fusion_results = op.fuse_current()
    ranked = rank_victims(fusion_results.values())
    op.dispatch_agent.load_queue(ranked)

    arrivals = []
    for _ in range(req.steps):
        entry = op.dispatch_agent.advance(seconds=req.seconds)
        if entry is not None:
            arrivals.append(entry.to_dict())
            if op.session_id:
                db.log_rescue_status_event(
                    session_id=op.session_id,
                    event_type="victim_reached",
                    team_id=op.dispatch_agent.team_id,
                    victim_id=entry.victim_id,
                    arrival_order=entry.order,
                    travel_seconds=entry.travel_seconds,
                    timestamp=entry.reached_at,
                    notes=f"Dispatch agent reached {entry.victim_id} (arrival #{entry.order}).",
                )
        if op.dispatch_agent.is_complete():
            break

    return {
        "operation_id": _op_id(op, operation_id),
        "scenario": op.scenario_meta(),
        "arrivals": arrivals,
        "dispatch_sim": op.dispatch_agent.status_dict(),
    }


@app.post("/rescue-team/set-target")
@app.post("/operations/{operation_id}/rescue-team/set-target")
def rescue_team_set_target(req: SetTargetRequest, operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    ok = op.dispatch_agent.set_target(req.victim_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Victim '{req.victim_id}' not in queue or already reached")
    return op.dispatch_agent.status_dict()


@app.post("/rescue-team/clear-target")
@app.post("/operations/{operation_id}/rescue-team/clear-target")
def rescue_team_clear_target(operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    op.dispatch_agent.clear_override()
    return op.dispatch_agent.status_dict()


@app.post("/rescue-team/move")
@app.post("/operations/{operation_id}/rescue-team/move")
def rescue_team_move(req: ManualMoveRequest, operation_id: Optional[str] = None):
    op = _get_operation(operation_id)
    _require_running(op)
    op.dispatch_agent.move_manual(req.bearing_deg, req.distance_m)
    return op.dispatch_agent.status_dict()


@app.get("/sessions")
def get_sessions():
    sessions = db.list_sessions()
    for s in sessions:
        s["counts"] = db.session_counts(s["session_id"])
    latest_sess = list(operations.values())[-1].session_id if operations else None
    return {
        "current_session_id": latest_sess,
        "operations": {op_id: op.session_id for op_id, op in operations.items()},
        "sessions": sessions,
    }


@app.get("/sessions/{session_id}/export.csv")
def export_session(session_id: str):
    known_ids = {s["session_id"] for s in db.list_sessions()}
    if session_id not in known_ids:
        raise HTTPException(status_code=404, detail=f"Unknown session_id: {session_id}")

    csv_text = db.export_session_csv(session_id)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{session_id}_log.csv"'
        },
    )


# --------------------------------------------------------------------------- #
# Sensor Modules & Disaster Scenario Intelligence Pipeline Endpoints
# --------------------------------------------------------------------------- #

@app.get("/sensors/current")
@app.get("/operations/{operation_id}/sensors/current")
def get_sensors_current(operation_id: Optional[str] = None):
    """Retrieve current readings across all channels with quality and status."""
    op = _get_operation(operation_id)
    _require_running(op)
    victim_readings = []
    for vid, buf in op.history.items():
        if buf:
            for r in buf:
                victim_readings.append(r.to_dict() if hasattr(r, "to_dict") else r.__dict__)
    env_report = op.simulator.environmental_full_report() if op.simulator else {}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "readings": victim_readings,
        "environmental": env_report,
        "victim_count": len(op.config.victims) if op.config else 0,
    }


@app.get("/sensors/history")
@app.get("/operations/{operation_id}/sensors/history")
def get_sensors_history(
    operation_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    sensor_type: Optional[str] = None,
    limit: int = 100,
):
    """Query time-series sensor history from the database."""
    op = _get_operation(operation_id)
    session_id = op.session_id if op.session_id else None
    if not session_id:
        return {"history": [], "count": 0}
    rows = db.get_sensor_history(session_id, victim_id=victim_id, sensor_type=sensor_type, limit=limit)
    return {"history": rows, "count": len(rows), "session_id": session_id}


@app.get("/sensors/health")
@app.get("/operations/{operation_id}/sensors/health")
def get_sensors_health(operation_id: Optional[str] = None):
    """Retrieve operational health, signal quality, and error states for all sensors."""
    op = _get_operation(operation_id)
    _require_running(op)
    health_list = op.simulator.get_sensor_health_report() if op.simulator else []
    online = sum(1 for h in health_list if h.status.value == "ONLINE")
    degraded = sum(1 for h in health_list if h.status.value == "DEGRADED")
    offline = sum(1 for h in health_list if h.status.value in ("OFFLINE", "ERROR"))
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "health_records": [h.to_dict() for h in health_list],
        "overall_health": "CRITICAL_FAULTS" if offline > 0 else ("DEGRADED" if degraded > 0 else "OPTIMAL"),
        "online_count": online,
        "degraded_count": degraded,
        "offline_count": offline,
        "total_channels": len(health_list),
    }


@app.get("/sensors/evidence")
@app.get("/operations/{operation_id}/sensors/evidence")
def get_sensors_evidence(operation_id: Optional[str] = None):
    """Retrieve semantic sensor evidence tokens for active disaster inference."""
    op = _get_operation(operation_id)
    _require_running(op)
    if op.latest_assessment and op.latest_assessment.active_evidence:
        ev_list = [e.to_dict() for e in op.latest_assessment.active_evidence]
    else:
        ev_list = []
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "evidence": ev_list,
        "count": len(ev_list),
    }


@app.get("/sensors/environmental")
@app.get("/operations/{operation_id}/sensors/environmental")
def get_sensors_environmental(operation_id: Optional[str] = None):
    """Retrieve site-wide environmental readings (rain, soil, seismic, tilt, gas, smoke, baro, temp, humidity)."""
    op = _get_operation(operation_id)
    _require_running(op)
    env_report = op.simulator.environmental_full_report() if op.simulator else {}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "environmental": env_report,
    }


@app.get("/sensors/imu/3axis")
@app.get("/operations/{operation_id}/sensors/imu/3axis")
def get_sensors_imu_3axis(operation_id: Optional[str] = None):
    """Retrieve 3-axis IMU acceleration, tilt angle, impact, and sustained vibration metrics."""
    op = _get_operation(operation_id)
    _require_running(op)
    imu_3axis = op.simulator.imu_3axis_report() if op.simulator else {}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "imu_3axis_by_victim": imu_3axis,
    }


@app.get("/scenario/assessment")
@app.get("/operations/{operation_id}/scenario/assessment")
def get_scenario_assessment(operation_id: Optional[str] = None):
    """Retrieve full AI disaster scenario assessment, cascading risks, risk level, and recommendations."""
    op = _get_operation(operation_id)
    _require_running(op)
    if not op.latest_assessment:
        op.tick()
    assess_dict = op.latest_assessment.to_dict() if op.latest_assessment else {}
    rec_actions = [assess_dict["recommended_action"]] if assess_dict.get("recommended_action") else []
    for s in assess_dict.get("secondary_scenarios", []):
        if s.get("recommended_action") and s["recommended_action"] not in rec_actions:
            rec_actions.append(s["recommended_action"])
    return {
        "operation_id": _op_id(op, operation_id),
        "session_id": op.session_id,
        "cycle": op.cycle_count,
        "assessment": assess_dict,
        "overall_risk": assess_dict.get("overall_risk", "LOW"),
        "confidence_pct": assess_dict.get("confidence_pct", 0.0),
        "active_evidence": assess_dict.get("active_evidence", []),
        "recommended_actions": rec_actions,
        "cascading_disasters": assess_dict.get("secondary_scenarios", []),
    }


@app.get("/alerts/active")
@app.get("/operations/{operation_id}/alerts/active")
def get_active_alerts(operation_id: Optional[str] = None):
    """List all currently active alerts from the active alert ledger."""
    op = _get_operation(operation_id)
    session_id = op.session_id if op.session_id else None
    alerts = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    return {
        "operation_id": _op_id(op, operation_id),
        "session_id": session_id,
        "alerts": alerts,
        "count": len(alerts),
    }


@app.get("/sensors/gas-smoke/current")
@app.get("/operations/{operation_id}/sensors/gas-smoke/current")
def get_sensors_gas_smoke_current(operation_id: Optional[str] = None):
    """Retrieve structured real-time gas concentration and smoke density telemetry."""
    op = _get_operation(operation_id)
    _require_running(op)
    gs_report = op.simulator.gas_smoke_report() if op.simulator else {}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "gas_smoke": gs_report,
    }


@app.get("/sensors/gas-smoke/history")
@app.get("/operations/{operation_id}/sensors/gas-smoke/history")
def get_sensors_gas_smoke_history(limit: int = 100, operation_id: Optional[str] = None):
    """Retrieve historical time series of gas and smoke readings."""
    op = _get_operation(operation_id)
    session_id = op.session_id if op.session_id else None
    history = db.get_gas_smoke_history(session_id=session_id, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id),
        "session_id": session_id,
        "history": history,
        "count": len(history),
    }


@app.get("/sensors/gas-smoke/health")
@app.get("/operations/{operation_id}/sensors/gas-smoke/health")
def get_sensors_gas_smoke_health(operation_id: Optional[str] = None):
    """Retrieve diagnostic health status for the gas and smoke detector probe."""
    op = _get_operation(operation_id)
    _require_running(op)
    health = op.simulator.gas_smoke_adapter.get_health() if op.simulator else None
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "health": health.to_dict() if health else {},
    }


@app.post("/sensors/gas-smoke/readings")
@app.post("/operations/{operation_id}/sensors/gas-smoke/readings")
def ingest_gas_smoke_reading(req: IngestGasSmokeReadingRequest, operation_id: Optional[str] = None):
    """External/Hardware IoT Ingestion Endpoint for Gas & Smoke readings."""
    analyzer = GasSmokeAnalyzer()
    loc = GPSCoordinate(latitude=req.latitude, longitude=req.longitude) if req.latitude and req.longitude else None

    # Validate input
    reading = GasSmokeReading(
        sensor_id=req.sensor_id or "GAS-SMOKE-SITE",
        device_id=req.device_id or "DEV-GAS-01",
        gas_type=GasType(req.gas_type) if req.gas_type in GasType._value2member_map_ else GasType.GENERIC_SMOKE,
        gas_concentration=req.gas_concentration,
        smoke_density_pct=req.smoke_density_pct,
        gas_level=analyzer.classify_gas(req.gas_concentration),
        smoke_level=analyzer.classify_smoke(req.smoke_density_pct),
        location=loc,
    )

    if not reading.validate():
        raise HTTPException(status_code=422, detail="Invalid gas/smoke reading: negative, out-of-range, or corrupted values rejected.")

    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else "external-ingest"
    db.log_gas_smoke_reading(reading, session_id=session_id)

    return {"logged": True, "reading": reading.to_dict()}


# --------------------------------------------------------------------------- #
# Barometric Pressure Dedicated Endpoints
# --------------------------------------------------------------------------- #

@app.get("/sensors/pressure/config")
@app.get("/operations/{operation_id}/sensors/pressure/config")
def get_sensors_pressure_config(operation_id: Optional[str] = None):
    """Retrieve centralized Barometric Pressure configuration and threshold parameters."""
    return {
        "config": {
            "min_pressure_hpa": PRESSURE_CONFIG.min_pressure_hpa,
            "max_pressure_hpa": PRESSURE_CONFIG.max_pressure_hpa,
            "nominal_baseline_hpa": PRESSURE_CONFIG.nominal_baseline_hpa,
            "falling_threshold_hpa_per_cycle": PRESSURE_CONFIG.falling_threshold_hpa_per_cycle,
            "rapid_falling_threshold_hpa_per_cycle": PRESSURE_CONFIG.rapid_falling_threshold_hpa_per_cycle,
            "rising_threshold_hpa_per_cycle": PRESSURE_CONFIG.rising_threshold_hpa_per_cycle,
            "rapid_rising_threshold_hpa_per_cycle": PRESSURE_CONFIG.rapid_rising_threshold_hpa_per_cycle,
            "anomaly_z_score_threshold": PRESSURE_CONFIG.anomaly_z_score_threshold,
            "anomaly_absolute_drop_hpa": PRESSURE_CONFIG.anomaly_absolute_drop_hpa,
            "critical_drop_threshold_hpa": PRESSURE_CONFIG.critical_drop_threshold_hpa,
            "history_window_size": PRESSURE_CONFIG.history_window_size,
            "sampling_interval_seconds": PRESSURE_CONFIG.sampling_interval_seconds,
            "rate_calculation_unit": PRESSURE_CONFIG.rate_calculation_unit,
            "severe_cyclone_threshold_hpa": PRESSURE_CONFIG.severe_cyclone_threshold_hpa,
            "critical_plunge_threshold_hpa": PRESSURE_CONFIG.critical_plunge_threshold_hpa,
        }
    }


@app.get("/sensors/pressure/current")
@app.get("/sensors/pressure/latest")
@app.get("/operations/{operation_id}/sensors/pressure/current")
@app.get("/operations/{operation_id}/sensors/pressure/latest")
def get_sensors_pressure_current(operation_id: Optional[str] = None):
    """Retrieve structured real-time Barometric Pressure telemetry and trend."""
    op = _get_operation(operation_id)
    _require_running(op)
    pressure_report = op.simulator.barometric_pressure_report() if op.simulator else {}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "pressure": pressure_report,
    }


@app.get("/sensors/pressure/history")
@app.get("/operations/{operation_id}/sensors/pressure/history")
def get_sensors_pressure_history(limit: int = 100, operation_id: Optional[str] = None):
    """Retrieve historical time series of Barometric Pressure readings."""
    op = _get_operation(operation_id)
    session_id = op.session_id if op.session_id else None
    history = db.get_barometric_history(session_id=session_id, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id),
        "session_id": session_id,
        "history": history,
        "count": len(history),
    }


@app.get("/sensors/pressure/health")
@app.get("/operations/{operation_id}/sensors/pressure/health")
def get_sensors_pressure_health(operation_id: Optional[str] = None):
    """Retrieve diagnostic health status for the Barometric Pressure sensor."""
    op = _get_operation(operation_id)
    _require_running(op)
    health = op.simulator.barometric_adapter.get_health() if op.simulator else None
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "health": health.to_dict() if health else {},
    }


@app.get("/sensors/pressure/trend")
@app.get("/operations/{operation_id}/sensors/pressure/trend")
def get_sensors_pressure_trend(operation_id: Optional[str] = None):
    """Retrieve time-series trend analysis, rate of change, and trajectory for Barometric Pressure."""
    op = _get_operation(operation_id)
    _require_running(op)
    curr = op.simulator.barometric_pressure_report() if op.simulator else {}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "pressure_hpa": curr.get("pressure_hpa"),
        "trend": curr.get("trend", "STABLE"),
        "rate_of_change": curr.get("rate_of_change", 0.0),
        "drop_severity": curr.get("drop_severity", "NORMAL"),
        "unit": "hPa",
    }


@app.get("/sensors/pressure/anomaly")
@app.get("/operations/{operation_id}/sensors/pressure/anomaly")
def get_sensors_pressure_anomaly(operation_id: Optional[str] = None):
    """Retrieve atmospheric anomaly scoring and critical drop assessments."""
    op = _get_operation(operation_id)
    _require_running(op)
    curr = op.simulator.barometric_pressure_report() if op.simulator else {}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "anomaly_level": curr.get("anomaly_level", "NORMAL"),
        "drop_severity": curr.get("drop_severity", "NORMAL"),
        "pressure_hpa": curr.get("pressure_hpa"),
        "confidence": curr.get("confidence", 0.95),
    }


@app.get("/sensors/pressure/status")
@app.get("/operations/{operation_id}/sensors/pressure/status")
def get_sensors_pressure_status(operation_id: Optional[str] = None):
    """Retrieve comprehensive sensor status, mode, and availability."""
    op = _get_operation(operation_id)
    _require_running(op)
    curr = op.simulator.barometric_pressure_report() if op.simulator else {}
    health = op.simulator.barometric_adapter.get_health() if op.simulator else None
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "status": curr.get("status", "ONLINE"),
        "available": curr.get("status") not in ("OFFLINE", "ERROR"),
        "mode": curr.get("metadata", {}).get("mode", "SIMULATED"),
        "battery_pct": health.battery_pct if health else 100.0,
        "signal_quality": health.signal_quality if health else 1.0,
    }


@app.post("/sensors/pressure/readings")
@app.post("/operations/{operation_id}/sensors/pressure/readings")
def ingest_barometric_pressure_reading(req: IngestBarometricPressureReadingRequest, operation_id: Optional[str] = None):
    """External/Hardware IoT Ingestion Endpoint for Barometric Pressure readings."""
    analyzer = BarometricPressureAnalyzer()
    loc = GPSCoordinate(latitude=req.latitude, longitude=req.longitude) if req.latitude and req.longitude else None

    # Validate and construct reading
    reading = BarometricPressureReading(
        sensor_id=req.sensor_id or "ENV-BARO-01",
        device_id=req.device_id or "DEV-BARO-01",
        pressure_hpa=req.pressure_hpa,
        unit=req.unit or "hPa",
        location=loc,
        confidence=req.confidence if req.confidence is not None else 0.95,
        status=SensorHealthStatus(req.status) if req.status in SensorHealthStatus._value2member_map_ else SensorHealthStatus.ONLINE,
    )

    if not reading.validate():
        raise HTTPException(status_code=422, detail="Invalid barometric pressure reading: out-of-range, NaN, or corrupted values rejected.")

    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else "external-ingest"
    db.log_barometric_reading(reading, session_id=session_id)

    return {"logged": True, "reading": reading.to_dict()}


class SetPressureProfileRequest(BaseModel):
    profile: str


@app.post("/sensors/pressure/profile")
@app.post("/operations/{operation_id}/sensors/pressure/profile")
def set_sensors_pressure_profile(req: SetPressureProfileRequest, operation_id: Optional[str] = None):
    """Switch active barometric pressure simulation profile (e.g. CYCLONE, RAPID_PRESSURE_DROP)."""
    op = _get_operation(operation_id)
    _require_running(op)
    if op.simulator and hasattr(op.simulator, "barometric_adapter"):
        op.simulator.barometric_adapter.set_scenario_profile(req.profile)
    return {"status": "ok", "profile": req.profile.upper()}


# --------------------------------------------------------------------------- #
# Soil Moisture, Tilt & Landslide Early Warning Endpoints
# --------------------------------------------------------------------------- #

@app.get("/sensors/soil-moisture/current")
@app.get("/operations/{operation_id}/sensors/soil-moisture/current")
def get_sensors_soil_moisture_current(node_id: Optional[str] = None, operation_id: Optional[str] = None):
    """Retrieve the latest real-time Soil Moisture reading and trend analysis."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.soil_moisture_report(node_id=node_id) if op.simulator else {}
    health = op.simulator.landslide_adapter.get_soil_health(node_id=node_id) if op.simulator else None
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "reading": rep,
        "health": health.to_dict() if health else {},
    }


@app.get("/sensors/soil-moisture/history")
@app.get("/operations/{operation_id}/sensors/soil-moisture/history")
def get_sensors_soil_moisture_history(node_id: Optional[str] = None, limit: int = 50, operation_id: Optional[str] = None):
    """Retrieve historical Soil Moisture telemetry records."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    history = db.get_landslide_history(session_id=session_id, node_id=node_id, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "node_id": node_id or "ALL",
        "history": [
            {
                "id": h.get("id"),
                "reading_id": h.get("reading_id"),
                "node_id": h.get("node_id"),
                "soil_moisture_pct": h.get("soil_moisture_pct"),
                "moisture_trend": h.get("moisture_trend"),
                "moisture_rate": h.get("moisture_rate"),
                "status": h.get("status"),
                "confidence": h.get("confidence"),
                "quality": h.get("quality"),
                "timestamp": h.get("timestamp"),
            }
            for h in history
        ],
        "count": len(history),
    }


@app.get("/sensors/tilt/current")
@app.get("/operations/{operation_id}/sensors/tilt/current")
def get_sensors_tilt_current(node_id: Optional[str] = None, operation_id: Optional[str] = None):
    """Retrieve the latest real-time Inclinometer Tilt reading and rate of change."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.tilt_report(node_id=node_id) if op.simulator else {}
    health = op.simulator.landslide_adapter.get_tilt_health(node_id=node_id) if op.simulator else None
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "reading": rep,
        "health": health.to_dict() if health else {},
    }


@app.get("/sensors/tilt/history")
@app.get("/operations/{operation_id}/sensors/tilt/history")
def get_sensors_tilt_history(node_id: Optional[str] = None, limit: int = 50, operation_id: Optional[str] = None):
    """Retrieve historical Inclinometer Tilt telemetry records."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    history = db.get_landslide_history(session_id=session_id, node_id=node_id, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "node_id": node_id or "ALL",
        "history": [
            {
                "id": h.get("id"),
                "reading_id": h.get("reading_id"),
                "node_id": h.get("node_id"),
                "tilt_angle_deg": h.get("tilt_angle_deg"),
                "tilt_rate": h.get("tilt_rate"),
                "tilt_trend": h.get("tilt_trend"),
                "status": h.get("status"),
                "confidence": h.get("confidence"),
                "quality": h.get("quality"),
                "timestamp": h.get("timestamp"),
            }
            for h in history
        ],
        "count": len(history),
    }


@app.get("/hazards/landslide/current")
@app.get("/operations/{operation_id}/hazards/landslide/current")
def get_hazards_landslide_current(node_id: Optional[str] = None, operation_id: Optional[str] = None):
    """Retrieve comprehensive Landslide Hazard risk assessment, score, and factors."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.landslide_hazard_report(node_id=node_id) if op.simulator else {}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "assessment": rep,
    }


@app.get("/hazards/landslide/nodes")
@app.get("/operations/{operation_id}/hazards/landslide/nodes")
def get_hazards_landslide_nodes(operation_id: Optional[str] = None):
    """Retrieve telemetry and hazard assessments across all slope monitoring nodes."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.landslide_nodes_report() if op.simulator else {}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        **rep,
    }


@app.get("/hazards/landslide/risk")
@app.get("/operations/{operation_id}/hazards/landslide/risk")
def get_hazards_landslide_risk(node_id: Optional[str] = None, operation_id: Optional[str] = None):
    """Retrieve detailed explainable subscore breakdown for Landslide Risk score computation."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.landslide_hazard_report(node_id=node_id) if op.simulator else {}
    m = float(rep.get("soil_moisture_pct", 38.0))
    t = float(rep.get("tilt_angle_deg", 0.5))
    analyzer = LandslideRiskAnalyzer()
    analysis = analyzer.analyze(
        soil_moisture_pct=m,
        tilt_angle_deg=t,
        status=SensorHealthStatus(rep.get("status", "ONLINE")) if rep.get("status") in SensorHealthStatus._value2member_map_ else SensorHealthStatus.ONLINE,
        rainfall_mm_hr=float(op.simulator._rain_mm_hr) if op.simulator else 0.0,
        vibration_mm_s=float(op.simulator._vibration_mm_s) if op.simulator else 0.0,
        node_id=rep.get("node_id", "SLOPE-NODE-01"),
    )
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "risk_score": rep.get("landslide_risk_score", 10.0),
        "risk_level": rep.get("risk_level", "LOW"),
        "event_state": rep.get("event_state", "NORMAL"),
        "contributing_factors": rep.get("contributing_factors", []),
        "recommended_action": rep.get("recommended_action", "Routine slope monitoring active."),
        "score_breakdown": {
            "moisture_subscore": analysis.get("moisture_subscore", 0.0),
            "moisture_trend_bonus": analysis.get("moisture_trend_bonus", 0.0),
            "tilt_subscore": analysis.get("tilt_subscore", 0.0),
            "tilt_trend_bonus": analysis.get("tilt_trend_bonus", 0.0),
            "persistence_score": analysis.get("persistence_score", 0.0),
            "weights": {
                "moisture": LANDSLIDE_CONFIG.weight_moisture,
                "moisture_trend": LANDSLIDE_CONFIG.weight_moisture_trend,
                "tilt": LANDSLIDE_CONFIG.weight_tilt,
                "tilt_trend": LANDSLIDE_CONFIG.weight_tilt_trend,
                "persistence": LANDSLIDE_CONFIG.weight_persistence,
            },
        },
    }


@app.get("/hazards/landslide/history")
@app.get("/operations/{operation_id}/hazards/landslide/history")
def get_hazards_landslide_history(node_id: Optional[str] = None, limit: int = 100, operation_id: Optional[str] = None):
    """Retrieve historical Landslide Risk records from the audit ledger."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    history = db.get_landslide_history(session_id=session_id, node_id=node_id, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "node_id": node_id or "ALL",
        "history": history,
        "count": len(history),
    }


@app.post("/hazards/landslide/profile")
@app.post("/operations/{operation_id}/hazards/landslide/profile")
def set_hazards_landslide_profile(req: SetLandslideProfileRequest, operation_id: Optional[str] = None):
    """Switch active Landslide simulation profile (NORMAL, WET_SOIL, EARLY_LANDSLIDE, CRITICAL_LANDSLIDE, etc.)."""
    op = _get_operation(operation_id)
    _require_running(op)
    if op.simulator and hasattr(op.simulator, "landslide_adapter"):
        op.simulator.landslide_adapter.set_scenario_profile(req.profile)
    return {"status": "ok", "profile": req.profile.upper()}


@app.post("/sensors/soil-moisture/readings")
@app.post("/operations/{operation_id}/sensors/soil-moisture/readings")
def ingest_soil_moisture_reading(req: IngestSoilMoistureReadingRequest, operation_id: Optional[str] = None):
    """Hardware / IoT Ingestion Endpoint for Soil Moisture readings."""
    loc = GPSCoordinate(latitude=req.latitude, longitude=req.longitude) if (req.latitude is not None and req.longitude is not None) else None
    reading = SoilMoistureReading(
        sensor_id=req.sensor_id or "SLOPE-SOIL-01",
        node_id=req.node_id or "SLOPE-NODE-01",
        device_id=req.device_id or "DEV-SOIL-01",
        soil_moisture_pct=req.soil_moisture_pct,
        unit=req.unit or "%",
        location=loc,
        status=SensorHealthStatus(req.status) if req.status in SensorHealthStatus._value2member_map_ else SensorHealthStatus.ONLINE,
        confidence=req.confidence if req.confidence is not None else 0.95,
    )
    if not reading.validate():
        raise HTTPException(status_code=422, detail="Invalid soil moisture reading: out-of-bounds (0-100%), NaN, or corrupted values rejected.")
    
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else "external-ingest"
    db.log_landslide_reading(reading, session_id=session_id)
    if op and op.simulator and hasattr(op.simulator, "landslide_adapter"):
        op.simulator.landslide_adapter.set_node_moisture(reading.node_id, reading.soil_moisture_pct)

    return {"logged": True, "reading": reading.to_dict()}


@app.post("/sensors/tilt/readings")
@app.post("/operations/{operation_id}/sensors/tilt/readings")
def ingest_tilt_reading(req: IngestTiltReadingRequest, operation_id: Optional[str] = None):
    """Hardware / IoT Ingestion Endpoint for Inclinometer Tilt readings."""
    loc = GPSCoordinate(latitude=req.latitude, longitude=req.longitude) if (req.latitude is not None and req.longitude is not None) else None
    reading = TiltReading(
        sensor_id=req.sensor_id or "SLOPE-TILT-01",
        node_id=req.node_id or "SLOPE-NODE-01",
        device_id=req.device_id or "DEV-TILT-01",
        tilt_x=req.tilt_x or 0.0,
        tilt_y=req.tilt_y or 0.0,
        tilt_z=req.tilt_z or 1.0,
        tilt_angle_deg=req.tilt_angle_deg,
        unit=req.unit or "deg",
        location=loc,
        status=SensorHealthStatus(req.status) if req.status in SensorHealthStatus._value2member_map_ else SensorHealthStatus.ONLINE,
        confidence=req.confidence if req.confidence is not None else 0.95,
    )
    if not reading.validate():
        raise HTTPException(status_code=422, detail="Invalid tilt reading: out-of-bounds (0-90°), NaN, or corrupted values rejected.")
    
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else "external-ingest"
    db.log_landslide_reading(reading, session_id=session_id)
    if op and op.simulator and hasattr(op.simulator, "landslide_adapter"):
        op.simulator.landslide_adapter.set_node_tilt(reading.node_id, reading.tilt_angle_deg)

    return {"logged": True, "reading": reading.to_dict()}


@app.post("/alerts/{alert_key}/resolve")
@app.post("/operations/{operation_id}/alerts/{alert_key}/resolve")
def resolve_alert(alert_key: str, operation_id: Optional[str] = None):
    """Manually resolve an active alert in the ledger."""
    ok = db.resolve_active_alert(alert_key)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_key}' not found in active alerts ledger.")
    return {"alert_key": alert_key, "status": "RESOLVED", "resolved": True}


# --------------------------------------------------------------------------- #
# Optical Camera Endpoints
# --------------------------------------------------------------------------- #

@app.get("/sensors/camera/current")
@app.get("/operations/{operation_id}/sensors/camera/current")
def get_sensors_camera_current(
    camera_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    operation_id: Optional[str] = None,
):
    """Get the current live telemetry for an optical camera channel."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.camera_report(victim_id=victim_id, camera_id=camera_id) if op.simulator else {}
    session_id = op.session_id if (op and op.session_id) else "default"
    
    # Audit log to DB
    reading_obj = CameraReading(
        camera_id=rep.get("camera_id", "CAM-001"),
        device_id=rep.get("device_id", "DEV-CAM-01"),
        victim_id=rep.get("victim_id"),
        detection_state=CameraDetectionState(rep.get("detection_state", "NO_DETECTION")),
        detection_type=rep.get("detection_type", "none"),
        classification=CameraClassification(rep.get("classification", "UNKNOWN")),
        classification_confidence=rep.get("classification_confidence", 0.0),
        person_count=rep.get("person_count", 0),
        confidence=rep.get("confidence", 0.0),
        visibility=rep.get("visibility", 1.0),
        occlusion=rep.get("occlusion", 0.0),
        image_quality=rep.get("image_quality", 1.0),
        motion_detected=rep.get("motion_detected", False),
        smoke_present=rep.get("smoke_present", False),
        fire_visible=rep.get("fire_visible", False),
        debris_present=rep.get("debris_present", False),
        orientation=rep.get("orientation", "0° NADIR"),
        field_of_view_deg=rep.get("field_of_view_deg", 85.0),
        range_m=rep.get("range_m", 30.0),
        status=CameraHealthStatus(rep.get("status", "ONLINE")),
        health_score=rep.get("health_score", 100.0),
    )
    db.log_camera_reading(reading_obj, session_id=session_id)
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "camera": rep,
    }


@app.get("/sensors/camera/history")
@app.get("/operations/{operation_id}/sensors/camera/history")
def get_sensors_camera_history(
    camera_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    limit: int = 100,
    operation_id: Optional[str] = None,
):
    """Retrieve historical Optical Camera telemetry from the audit ledger."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    history = db.get_camera_history(session_id=session_id, camera_id=camera_id, victim_id=victim_id, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "history": history,
        "count": len(history),
    }


@app.get("/sensors/cameras")
@app.get("/operations/{operation_id}/sensors/cameras")
@app.get("/sensors/camera/all")
@app.get("/operations/{operation_id}/sensors/camera/all")
def get_sensors_cameras_all(operation_id: Optional[str] = None):
    """Retrieve all active optical camera telemetry channels."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.cameras_all_report() if op.simulator else {"camera_count": 0, "cameras": {}}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "cameras": rep.get("cameras", {}),
        "camera_count": rep.get("camera_count", 0),
        "profile": rep.get("profile", "AUTO"),
    }


@app.get("/analytics/camera")
@app.get("/operations/{operation_id}/analytics/camera")
def get_camera_analytics(operation_id: Optional[str] = None):
    """Retrieve statistical aggregations and historical analytics for Optical Cameras."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    analytics = db.get_camera_analytics(session_id=session_id)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "analytics": analytics,
    }


@app.post("/sensors/camera/simulate")
@app.post("/operations/{operation_id}/sensors/camera/simulate")
def simulate_camera_profile(req: SimulateCameraRequest, operation_id: Optional[str] = None):
    """Set simulation profile for optical cameras."""
    op = _get_operation(operation_id)
    _require_running(op)
    if op.simulator and hasattr(op.simulator, "camera_adapter"):
        op.simulator.camera_adapter.set_scenario_profile(req.profile or "NORMAL")
    return {"status": "ok", "profile": (req.profile or "NORMAL").upper()}


@app.post("/sensors/camera/readings")
@app.post("/operations/{operation_id}/sensors/camera/readings")
def ingest_camera_reading(req: IngestCameraReadingRequest, operation_id: Optional[str] = None):
    """Hardware / IoT Ingestion Endpoint for Optical Camera telemetry."""
    loc = GPSCoordinate(latitude=req.latitude, longitude=req.longitude, altitude_m=req.altitude_m) if (req.latitude is not None and req.longitude is not None) else None
    det_st = CameraDetectionState(req.detection_state) if req.detection_state in CameraDetectionState._value2member_map_ else CameraDetectionState.PERSON_DETECTED
    cl_st = CameraClassification(req.classification) if req.classification in CameraClassification._value2member_map_ else CameraClassification.HUMAN
    h_st = CameraHealthStatus(req.status) if req.status in CameraHealthStatus._value2member_map_ else CameraHealthStatus.ONLINE

    reading = CameraReading(
        camera_id=req.camera_id or "CAM-001",
        device_id=req.device_id or "DEV-CAM-01",
        victim_id=req.victim_id,
        location=loc,
        detection_state=det_st,
        classification=cl_st,
        person_count=req.person_count if req.person_count is not None else 1,
        confidence=req.confidence,
        visibility=req.visibility if req.visibility is not None else 1.0,
        occlusion=req.occlusion if req.occlusion is not None else 0.0,
        motion_detected=req.motion_detected or False,
        smoke_present=req.smoke_present or False,
        fire_visible=req.fire_visible or False,
        debris_present=req.debris_present or False,
        status=h_st,
    )
    if not reading.validate():
        raise HTTPException(status_code=422, detail="Invalid optical camera reading: out-of-bounds, NaN, or corrupted values rejected.")
    
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else "external-ingest"
    db.log_camera_reading(reading, session_id=session_id)
    return {"logged": True, "reading": reading.to_dict()}


# --------------------------------------------------------------------------- #
# Thermal Infrared Camera Endpoints
# --------------------------------------------------------------------------- #

@app.get("/sensors/thermal/current")
@app.get("/operations/{operation_id}/sensors/thermal/current")
def get_sensors_thermal_current(
    camera_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    operation_id: Optional[str] = None,
):
    """Get the current live telemetry for a thermal infrared camera channel."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.thermal_report(victim_id=victim_id, camera_id=camera_id) if op.simulator else {}
    session_id = op.session_id if (op and op.session_id) else "default"

    # Audit log to DB
    reading_obj = ThermalCameraReading(
        camera_id=rep.get("camera_id", "THERMAL-001"),
        device_id=rep.get("device_id", "DEV-THM-01"),
        victim_id=rep.get("victim_id"),
        detection_type=ThermalDetectionType(rep.get("detection_type", "NO_HEAT")),
        classification=ThermalClassification(rep.get("classification", "NO_SIGNATURE")),
        classification_confidence=rep.get("classification_confidence", 0.0),
        heat_signature_detected=rep.get("heat_signature_detected", False),
        human_signature=rep.get("human_signature", False),
        heat_signature_count=rep.get("heat_signature_count", 0),
        thermal_confidence=rep.get("thermal_confidence", 0.0),
        estimated_temperature=rep.get("estimated_temperature", 20.0),
        background_temperature=rep.get("background_temperature", 18.0),
        temperature_delta=rep.get("temperature_delta", 2.0),
        thermal_visibility=rep.get("thermal_visibility", 1.0),
        thermal_contrast=rep.get("thermal_contrast", 1.0),
        occlusion=rep.get("occlusion", 0.0),
        fire_hotspot=rep.get("fire_hotspot", False),
        hot_debris=rep.get("hot_debris", False),
        orientation=rep.get("orientation", "0° NADIR"),
        field_of_view_deg=rep.get("field_of_view_deg", 60.0),
        range_m=rep.get("range_m", 40.0),
        status=ThermalHealthStatus(rep.get("status", "ONLINE")),
        health_score=rep.get("health_score", 100.0),
    )
    db.log_thermal_reading(reading_obj, session_id=session_id)
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "thermal": rep,
    }


@app.get("/sensors/thermal/history")
@app.get("/operations/{operation_id}/sensors/thermal/history")
def get_sensors_thermal_history(
    camera_id: Optional[str] = None,
    victim_id: Optional[str] = None,
    limit: int = 100,
    operation_id: Optional[str] = None,
):
    """Retrieve historical Thermal Camera telemetry from the audit ledger."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    history = db.get_thermal_history(session_id=session_id, camera_id=camera_id, victim_id=victim_id, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "history": history,
        "count": len(history),
    }


@app.get("/sensors/thermal")
@app.get("/operations/{operation_id}/sensors/thermal")
@app.get("/sensors/thermal/all")
@app.get("/operations/{operation_id}/sensors/thermal/all")
def get_sensors_thermal_all(operation_id: Optional[str] = None):
    """Retrieve all active thermal infrared camera channels."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.thermal_all_report() if op.simulator else {"thermal_count": 0, "thermal_cameras": {}}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "thermal_cameras": rep.get("thermal_cameras", {}),
        "thermal_count": rep.get("thermal_count", 0),
        "profile": rep.get("profile", "AUTO"),
    }


@app.get("/analytics/thermal")
@app.get("/operations/{operation_id}/analytics/thermal")
def get_thermal_analytics(operation_id: Optional[str] = None):
    """Retrieve statistical aggregations and historical analytics for Thermal Cameras."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    analytics = db.get_thermal_analytics(session_id=session_id)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "analytics": analytics,
    }


@app.post("/sensors/thermal/simulate")
@app.post("/operations/{operation_id}/sensors/thermal/simulate")
def simulate_thermal_profile(req: SimulateThermalRequest, operation_id: Optional[str] = None):
    """Set simulation profile for thermal infrared cameras."""
    op = _get_operation(operation_id)
    _require_running(op)
    if op.simulator and hasattr(op.simulator, "thermal_adapter"):
        op.simulator.thermal_adapter.set_scenario_profile(req.profile or "HUMAN_HEAT")
    return {"status": "ok", "profile": (req.profile or "HUMAN_HEAT").upper()}


@app.post("/sensors/thermal/readings")
@app.post("/operations/{operation_id}/sensors/thermal/readings")
def ingest_thermal_reading(req: IngestThermalReadingRequest, operation_id: Optional[str] = None):
    """Hardware / IoT Ingestion Endpoint for Thermal Camera telemetry."""
    loc = GPSCoordinate(latitude=req.latitude, longitude=req.longitude, altitude_m=req.altitude_m) if (req.latitude is not None and req.longitude is not None) else None
    det_tp = ThermalDetectionType(req.detection_type) if req.detection_type in ThermalDetectionType._value2member_map_ else ThermalDetectionType.HUMAN_HEAT_SIGNATURE
    cl_tp = ThermalClassification(req.classification) if req.classification in ThermalClassification._value2member_map_ else ThermalClassification.HUMAN_HEAT_SIGNATURE
    h_tp = ThermalHealthStatus(req.status) if req.status in ThermalHealthStatus._value2member_map_ else ThermalHealthStatus.ONLINE

    reading = ThermalCameraReading(
        camera_id=req.camera_id or "THERMAL-001",
        device_id=req.device_id or "DEV-THM-01",
        victim_id=req.victim_id,
        location=loc,
        detection_type=det_tp,
        classification=cl_tp,
        estimated_temperature=req.estimated_temperature,
        background_temperature=req.background_temperature if req.background_temperature is not None else 18.0,
        temperature_delta=abs(req.estimated_temperature - (req.background_temperature or 18.0)),
        thermal_confidence=req.thermal_confidence if req.thermal_confidence is not None else 0.90,
        thermal_visibility=req.thermal_visibility if req.thermal_visibility is not None else 1.0,
        fire_hotspot=req.fire_hotspot or False,
        hot_debris=req.hot_debris or False,
        status=h_tp,
    )
    if not reading.validate():
        raise HTTPException(status_code=422, detail="Invalid thermal camera reading: out-of-bounds, NaN, or corrupted values rejected.")
    
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else "external-ingest"
    db.log_thermal_reading(reading, session_id=session_id)
    return {"logged": True, "reading": reading.to_dict()}


# --------------------------------------------------------------------------- #
# Cross-Modal Correlation & Analytics Endpoints
# --------------------------------------------------------------------------- #

@app.get("/sensors/camera-thermal/correlation")
@app.get("/operations/{operation_id}/sensors/camera-thermal/correlation")
@app.get("/sensors/camera-thermal/correlation/{victim_id}")
@app.get("/operations/{operation_id}/sensors/camera-thermal/correlation/{victim_id}")
def get_camera_thermal_correlation(victim_id: str = "V1", operation_id: Optional[str] = None):
    """Retrieve explainable Optical + Thermal cross-modal correlation analysis for a victim."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.camera_thermal_correlation_report(victim_id=victim_id) if op.simulator else {}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "victim_id": victim_id,
        "correlation": rep,
    }


@app.get("/analytics/camera-thermal")
@app.get("/operations/{operation_id}/analytics/camera-thermal")
def get_camera_thermal_analytics(operation_id: Optional[str] = None):
    """Retrieve statistical and audit analytics for optical and thermal cameras."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    analytics = db.get_camera_thermal_analytics(session_id=session_id)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "analytics": analytics,
    }


# --------------------------------------------------------------------------- #
# Dedicated Rainfall / Precipitation Endpoints
# --------------------------------------------------------------------------- #

@app.get("/sensors/rainfall/current")
@app.get("/operations/{operation_id}/sensors/rainfall/current")
def get_sensors_rainfall_current(operation_id: Optional[str] = None):
    """Retrieve current Rainfall / Precipitation telemetry and meteorological classification."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.rainfall_report() if op.simulator else {}
    session_id = op.session_id if (op and op.session_id) else None
    if rep:
        db.log_rainfall_reading(rep, session_id=session_id or "default", cycle=op.cycle_count)
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "rainfall": rep,
    }


@app.get("/sensors/rainfall/history")
@app.get("/operations/{operation_id}/sensors/rainfall/history")
def get_sensors_rainfall_history(
    sensor_id: Optional[str] = None,
    limit: int = 100,
    operation_id: Optional[str] = None,
):
    """Retrieve historical Rainfall telemetry from the audit ledger."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    history = db.get_rainfall_history(session_id=session_id, sensor_id=sensor_id, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "history": history,
        "count": len(history),
    }


@app.post("/sensors/rainfall/simulate")
@app.post("/operations/{operation_id}/sensors/rainfall/simulate")
def simulate_rainfall_profile(req: SimulateRainfallRequest, operation_id: Optional[str] = None):
    """Set simulation weather profile for the Rainfall sensor."""
    op = _get_operation(operation_id)
    _require_running(op)
    if op.simulator and hasattr(op.simulator, "rainfall_adapter"):
        op.simulator.rainfall_adapter.set_simulation_profile(req.profile or "HEAVY")
        if req.rainfall_rate_mm_h is not None:
            op.simulator.rainfall_adapter._rainfall_rate_mm_h = max(0.0, req.rainfall_rate_mm_h)
            op.simulator._rain_mm_hr = max(0.0, req.rainfall_rate_mm_h)
        if req.cumulative_rainfall_mm is not None:
            op.simulator.rainfall_adapter._cumulative_rainfall_mm = max(0.0, req.cumulative_rainfall_mm)
            op.simulator._accumulated_rain_mm = max(0.0, req.cumulative_rainfall_mm)
    return {"status": "ok", "profile": (req.profile or "HEAVY").upper()}


@app.post("/sensors/rainfall/readings")
@app.post("/operations/{operation_id}/sensors/rainfall/readings")
def ingest_rainfall_reading(req: IngestRainfallReadingRequest, operation_id: Optional[str] = None):
    """Hardware / IoT Ingestion Endpoint for Rainfall sensor telemetry."""
    loc = GPSCoordinate(latitude=req.latitude, longitude=req.longitude, altitude_m=req.altitude_m) if (req.latitude is not None and req.longitude is not None) else None
    cls_tp = RainfallClassification(req.classification) if req.classification in RainfallClassification._value2member_map_ else RainfallClassification.NO_RAIN
    sev_tp = RiskLevel(req.severity) if req.severity in RiskLevel._value2member_map_ else RiskLevel.LOW
    tr_tp = RainfallTrend(req.trend) if req.trend in RainfallTrend._value2member_map_ else RainfallTrend.STABLE
    h_tp = SensorHealthStatus(req.status) if req.status in SensorHealthStatus._value2member_map_ else SensorHealthStatus.ONLINE

    reading = RainfallReading(
        sensor_id=req.sensor_id or "ENV-RAIN-01",
        device_id=req.device_id or "DEV-RAIN-01",
        rainfall_rate_mm_h=req.rainfall_rate_mm_h,
        rainfall_mm_hr=req.rainfall_rate_mm_h,
        cumulative_rainfall_mm=req.cumulative_rainfall_mm or 0.0,
        unit=req.unit or "mm/h",
        rate_of_change=req.rate_of_change or 0.0,
        trend=tr_tp,
        classification=cls_tp,
        severity=sev_tp,
        location=loc,
        status=h_tp,
        confidence=req.confidence if req.confidence is not None else 0.98,
        quality=req.quality if req.quality is not None else 0.98,
    )
    if not reading.validate():
        raise HTTPException(status_code=422, detail="Invalid rainfall reading: negative, out-of-bounds, NaN, or corrupted values rejected.")
    
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else "external-ingest"
    db.log_rainfall_reading(reading, session_id=session_id)
    return {"logged": True, "reading": reading.to_dict()}


@app.get("/analytics/rainfall")
@app.get("/operations/{operation_id}/analytics/rainfall")
def get_rainfall_analytics(operation_id: Optional[str] = None):
    """Retrieve statistical and audit analytics for Rainfall / Precipitation."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    analytics = db.get_rainfall_analytics(session_id=session_id)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "analytics": analytics,
    }


# --------------------------------------------------------------------------- #
# Dedicated Ambient Temperature Endpoints
# --------------------------------------------------------------------------- #

@app.get("/sensors/temperature/current")
@app.get("/operations/{operation_id}/sensors/temperature/current")
def get_sensors_temperature_current(operation_id: Optional[str] = None):
    """Retrieve current ambient Temperature telemetry and trend analysis."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.temperature_report() if op.simulator else {}
    session_id = op.session_id if (op and op.session_id) else None
    if rep:
        db.log_temperature_reading(rep, session_id=session_id or "default", cycle=op.cycle_count)
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "temperature": rep,
    }


@app.get("/sensors/temperature/history")
@app.get("/operations/{operation_id}/sensors/temperature/history")
def get_sensors_temperature_history(
    sensor_id: Optional[str] = None,
    limit: int = 100,
    operation_id: Optional[str] = None,
):
    """Retrieve historical Temperature telemetry from the audit ledger."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    history = db.get_temperature_history(session_id=session_id, sensor_id=sensor_id, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "history": history,
        "count": len(history),
    }


@app.get("/sensors/temperature/health")
@app.get("/operations/{operation_id}/sensors/temperature/health")
def get_sensors_temperature_health(operation_id: Optional[str] = None):
    """Retrieve diagnostic health status for the temperature probe."""
    op = _get_operation(operation_id)
    _require_running(op)
    health = None
    if op.simulator and hasattr(op.simulator, "temperature_adapter"):
        health = op.simulator.temperature_adapter.get_health().to_dict()
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "health": health,
    }


@app.get("/sensors/temperature/trend")
@app.get("/operations/{operation_id}/sensors/temperature/trend")
def get_sensors_temperature_trend(operation_id: Optional[str] = None):
    """Retrieve rate-of-change and trend classification for ambient temperature."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.temperature_report() if op.simulator else {}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "trend": rep.get("trend", "STABLE"),
        "rate_of_change": rep.get("rate_of_change", 0.0),
        "temperature_c": rep.get("temperature_c", 15.0),
    }


@app.post("/sensors/temperature/simulate")
@app.post("/operations/{operation_id}/sensors/temperature/simulate")
def simulate_temperature_profile(req: SimulateTemperatureRequest, operation_id: Optional[str] = None):
    """Set simulation thermal profile for the Temperature sensor."""
    op = _get_operation(operation_id)
    _require_running(op)
    if op.simulator and hasattr(op.simulator, "temperature_adapter"):
        op.simulator.temperature_adapter.set_simulation_profile(req.profile or "NORMAL")
        if req.temperature_c is not None:
            op.simulator.temperature_adapter._temperature_c = req.temperature_c
            op.simulator._ambient_temp_c = req.temperature_c
    return {"status": "ok", "profile": (req.profile or "NORMAL").upper()}


@app.post("/sensors/temperature/readings")
@app.post("/operations/{operation_id}/sensors/temperature/readings")
def ingest_temperature_reading(req: IngestTemperatureReadingRequest, operation_id: Optional[str] = None):
    """Hardware / IoT Ingestion Endpoint for Temperature sensor telemetry."""
    loc = GPSCoordinate(latitude=req.latitude, longitude=req.longitude, altitude_m=req.altitude_m) if (req.latitude is not None and req.longitude is not None) else None
    tr_tp = TemperatureTrend(req.trend) if req.trend in TemperatureTrend._value2member_map_ else TemperatureTrend.STABLE
    h_tp = SensorHealthStatus(req.status) if req.status in SensorHealthStatus._value2member_map_ else SensorHealthStatus.ONLINE

    reading = TemperatureReading(
        sensor_id=req.sensor_id or "ENV-TEMP-01",
        device_id=req.device_id or "DEV-TEMP-01",
        temperature_c=req.temperature_c,
        ambient_temp_c=req.ambient_temp_c if req.ambient_temp_c is not None else req.temperature_c,
        unit=req.unit or "°C",
        rate_of_change=req.rate_of_change or 0.0,
        trend=tr_tp,
        location=loc,
        status=h_tp,
        confidence=req.confidence if req.confidence is not None else 0.98,
        quality=req.quality if req.quality is not None else 0.98,
    )
    if not reading.validate():
        raise HTTPException(status_code=422, detail="Invalid temperature reading: out-of-bounds, NaN, or corrupted values rejected.")

    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else "external-ingest"
    db.log_temperature_reading(reading, session_id=session_id)
    return {"logged": True, "reading": reading.to_dict()}


@app.get("/analytics/temperature")
@app.get("/operations/{operation_id}/analytics/temperature")
def get_temperature_analytics(operation_id: Optional[str] = None):
    """Retrieve statistical and audit analytics for ambient temperature."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    analytics = db.get_temperature_analytics(session_id=session_id)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "analytics": analytics,
    }


# --------------------------------------------------------------------------- #
# Dedicated Atmospheric Humidity Endpoints
# --------------------------------------------------------------------------- #

@app.get("/sensors/humidity/current")
@app.get("/operations/{operation_id}/sensors/humidity/current")
def get_sensors_humidity_current(operation_id: Optional[str] = None):
    """Retrieve current atmospheric Relative Humidity telemetry and trend analysis."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.humidity_report() if op.simulator else {}
    session_id = op.session_id if (op and op.session_id) else None
    if rep:
        db.log_humidity_reading(rep, session_id=session_id or "default", cycle=op.cycle_count)
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "humidity": rep,
    }


@app.get("/sensors/humidity/history")
@app.get("/operations/{operation_id}/sensors/humidity/history")
def get_sensors_humidity_history(
    sensor_id: Optional[str] = None,
    limit: int = 100,
    operation_id: Optional[str] = None,
):
    """Retrieve historical Relative Humidity telemetry from the audit ledger."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    history = db.get_humidity_history(session_id=session_id, sensor_id=sensor_id, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "history": history,
        "count": len(history),
    }


@app.get("/sensors/humidity/health")
@app.get("/operations/{operation_id}/sensors/humidity/health")
def get_sensors_humidity_health(operation_id: Optional[str] = None):
    """Retrieve diagnostic health status for the hygrometer probe."""
    op = _get_operation(operation_id)
    _require_running(op)
    health = None
    if op.simulator and hasattr(op.simulator, "humidity_adapter"):
        health = op.simulator.humidity_adapter.get_health().to_dict()
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "health": health,
    }


@app.get("/sensors/humidity/trend")
@app.get("/operations/{operation_id}/sensors/humidity/trend")
def get_sensors_humidity_trend(operation_id: Optional[str] = None):
    """Retrieve rate-of-change and trend classification for relative humidity."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.humidity_report() if op.simulator else {}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "trend": rep.get("trend", "STABLE"),
        "rate_of_change": rep.get("rate_of_change", 0.0),
        "humidity_pct": rep.get("humidity_pct", 50.0),
    }


@app.post("/sensors/humidity/simulate")
@app.post("/operations/{operation_id}/sensors/humidity/simulate")
def simulate_humidity_profile(req: SimulateHumidityRequest, operation_id: Optional[str] = None):
    """Set simulation atmospheric moisture profile for the Humidity sensor."""
    op = _get_operation(operation_id)
    _require_running(op)
    if op.simulator and hasattr(op.simulator, "humidity_adapter"):
        op.simulator.humidity_adapter.set_simulation_profile(req.profile or "NORMAL")
        if req.humidity_pct is not None:
            op.simulator.humidity_adapter._humidity_pct = req.humidity_pct
            op.simulator._humidity_pct = req.humidity_pct
    return {"status": "ok", "profile": (req.profile or "NORMAL").upper()}


@app.post("/sensors/humidity/readings")
@app.post("/operations/{operation_id}/sensors/humidity/readings")
def ingest_humidity_reading(req: IngestHumidityReadingRequest, operation_id: Optional[str] = None):
    """Hardware / IoT Ingestion Endpoint for Relative Humidity sensor telemetry."""
    loc = GPSCoordinate(latitude=req.latitude, longitude=req.longitude, altitude_m=req.altitude_m) if (req.latitude is not None and req.longitude is not None) else None
    tr_tp = HumidityTrend(req.trend) if req.trend in HumidityTrend._value2member_map_ else HumidityTrend.STABLE
    h_tp = SensorHealthStatus(req.status) if req.status in SensorHealthStatus._value2member_map_ else SensorHealthStatus.ONLINE

    reading = HumidityReading(
        sensor_id=req.sensor_id or "ENV-HUMID-01",
        device_id=req.device_id or "DEV-HUMID-01",
        humidity_pct=req.humidity_pct,
        unit=req.unit or "%",
        rate_of_change=req.rate_of_change or 0.0,
        trend=tr_tp,
        location=loc,
        status=h_tp,
        confidence=req.confidence if req.confidence is not None else 0.98,
        quality=req.quality if req.quality is not None else 0.98,
    )
    if not reading.validate():
        raise HTTPException(status_code=422, detail="Invalid humidity reading: negative, >100%, NaN, or corrupted values rejected.")

    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else "external-ingest"
    db.log_humidity_reading(reading, session_id=session_id)
    return {"logged": True, "reading": reading.to_dict()}


@app.get("/analytics/humidity")
@app.get("/operations/{operation_id}/analytics/humidity")
def get_humidity_analytics(operation_id: Optional[str] = None):
    """Retrieve statistical and audit analytics for atmospheric relative humidity."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    analytics = db.get_humidity_analytics(session_id=session_id)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "analytics": analytics,
    }


# --------------------------------------------------------------------------- #
# Dedicated Water-Level & Flood Telemetry Endpoints
# --------------------------------------------------------------------------- #

@app.get("/sensors/water-level/current")
@app.get("/operations/{operation_id}/sensors/water-level/current")
def get_sensors_water_level_current(operation_id: Optional[str] = None):
    """Retrieve current Water-Level & Flow velocity telemetry and trend analysis."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.water_level_report() if op.simulator else {}
    session_id = op.session_id if (op and op.session_id) else None
    if rep:
        db.log_water_level_reading(rep, session_id=session_id or "default", cycle=op.cycle_count)
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "water_level": rep,
    }


@app.get("/sensors/water-level/history")
@app.get("/operations/{operation_id}/sensors/water-level/history")
def get_sensors_water_level_history(
    sensor_id: Optional[str] = None,
    limit: int = 100,
    operation_id: Optional[str] = None,
):
    """Retrieve historical Water-Level telemetry from the audit ledger."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    history = db.get_water_level_history(session_id=session_id, sensor_id=sensor_id, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "history": history,
        "count": len(history),
    }


@app.get("/sensors/water-level/health")
@app.get("/operations/{operation_id}/sensors/water-level/health")
def get_sensors_water_level_health(operation_id: Optional[str] = None):
    """Retrieve diagnostic health status for the hydrostatic level sensor probe."""
    op = _get_operation(operation_id)
    _require_running(op)
    health = None
    if op.simulator and hasattr(op.simulator, "water_level_adapter"):
        health = op.simulator.water_level_adapter.get_health().to_dict()
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "health": health,
    }


@app.get("/sensors/water-level/trend")
@app.get("/operations/{operation_id}/sensors/water-level/trend")
def get_sensors_water_level_trend(operation_id: Optional[str] = None):
    """Retrieve rate-of-change and trend classification for water level."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.water_level_report() if op.simulator else {}
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "trend": rep.get("trend", "STABLE"),
        "rate_of_change": rep.get("rate_of_change", 0.0),
        "water_level_cm": rep.get("water_level_cm", 0.0),
        "water_flow_mps": rep.get("water_flow_mps", 0.0),
    }


@app.get("/sensors/non-contact-pressure/current")
@app.get("/operations/{operation_id}/sensors/non-contact-pressure/current")
def get_sensors_non_contact_pressure_current(operation_id: Optional[str] = None):
    """Retrieve current non-contact radar/ultrasonic flood-water level & hydrostatic pressure estimation."""
    op = _get_operation_optional(operation_id)
    rep = op.simulator.non_contact_pressure_report() if (op and op.simulator) else None
    if rep is None:
        rep = NonContactPressureEngine().get_latest_report()
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "cycle": op.cycle_count if op else 0,
        "non_contact_pressure": rep,
    }


@app.post("/sensors/water-level/simulate")
@app.post("/operations/{operation_id}/sensors/water-level/simulate")
def simulate_water_level_profile(req: SimulateWaterLevelRequest, operation_id: Optional[str] = None):
    """Set simulation hydrological profile for the Water-Level sensor."""
    op = _get_operation(operation_id)
    _require_running(op)
    if op.simulator and hasattr(op.simulator, "water_level_adapter"):
        op.simulator.water_level_adapter.set_simulation_profile(req.profile or "NORMAL")
        if req.water_level_cm is not None:
            op.simulator.water_level_adapter._water_level_cm = max(0.0, req.water_level_cm)
        if req.water_flow_mps is not None:
            op.simulator.water_level_adapter._water_flow_mps = max(0.0, req.water_flow_mps)
    return {"status": "ok", "profile": (req.profile or "NORMAL").upper()}


@app.post("/sensors/water-level/readings")
@app.post("/operations/{operation_id}/sensors/water-level/readings")
def ingest_water_level_reading(req: IngestWaterLevelReadingRequest, operation_id: Optional[str] = None):
    """Hardware / IoT Ingestion Endpoint for Water-Level sensor telemetry."""
    loc = GPSCoordinate(latitude=req.latitude, longitude=req.longitude, altitude_m=req.altitude_m) if (req.latitude is not None and req.longitude is not None) else None
    tr_tp = WaterTrend(req.trend) if req.trend in WaterTrend._value2member_map_ else WaterTrend.STABLE
    cl_tp = WaterLevelClassification(req.classification) if req.classification in WaterLevelClassification._value2member_map_ else WaterLevelClassification.NORMAL
    sev_tp = RiskLevel(req.severity) if req.severity in RiskLevel._value2member_map_ else RiskLevel.LOW
    h_tp = SensorHealthStatus(req.status) if req.status in SensorHealthStatus._value2member_map_ else SensorHealthStatus.ONLINE

    reading = WaterLevelReading(
        sensor_id=req.sensor_id or "ENV-WATER-01",
        device_id=req.device_id or "DEV-WATER-01",
        water_level_cm=req.water_level_cm,
        water_flow_mps=req.water_flow_mps or 0.0,
        unit=req.unit or "cm",
        rate_of_change=req.rate_of_change or 0.0,
        trend=tr_tp,
        classification=cl_tp,
        severity=sev_tp,
        location=loc,
        status=h_tp,
        confidence=req.confidence if req.confidence is not None else 0.98,
        quality=req.quality if req.quality is not None else 0.98,
    )
    if not reading.validate():
        raise HTTPException(status_code=422, detail="Invalid water level reading: negative, out-of-bounds, NaN, or corrupted values rejected.")

    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else "external-ingest"
    db.log_water_level_reading(reading, session_id=session_id)
    return {"logged": True, "reading": reading.to_dict()}


@app.get("/analytics/water-level")
@app.get("/operations/{operation_id}/analytics/water-level")
def get_water_level_analytics(operation_id: Optional[str] = None):
    """Retrieve statistical and audit analytics for water level and flood dynamics."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    analytics = db.get_water_level_analytics(session_id=session_id)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "analytics": analytics,
    }


# --------------------------------------------------------------------------- #
# Dedicated GPS & Geospatial Intelligence Endpoints
# --------------------------------------------------------------------------- #

@app.get("/sensors/gps/current")
@app.get("/operations/{operation_id}/sensors/gps/current")
def get_sensors_gps_current(operation_id: Optional[str] = None):
    """Retrieve current GPS telemetry, coordinates, accuracy, satellites, and kinematic movement."""
    op = _get_operation(operation_id)
    _require_running(op)
    rep = op.simulator.gps_report() if op.simulator else {}
    session_id = op.session_id if (op and op.session_id) else None
    if rep:
        db.log_gps_reading(rep, session_id=session_id or "default", cycle=op.cycle_count)
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "gps": rep,
    }


@app.get("/sensors/gps/history")
@app.get("/operations/{operation_id}/sensors/gps/history")
def get_sensors_gps_history(
    sensor_id: Optional[str] = None,
    limit: int = 100,
    operation_id: Optional[str] = None,
):
    """Retrieve historical GPS telemetry log from the audit ledger."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    history = db.get_gps_history(session_id=session_id, sensor_id=sensor_id, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "history": history,
        "count": len(history),
    }


@app.get("/sensors/gps/health")
@app.get("/operations/{operation_id}/sensors/gps/health")
def get_sensors_gps_health(operation_id: Optional[str] = None):
    """Retrieve diagnostic health status for the GNSS/GPS receiver."""
    op = _get_operation(operation_id)
    _require_running(op)
    health = None
    if op.simulator and hasattr(op.simulator, "gps_adapter"):
        health = op.simulator.gps_adapter.get_health().to_dict()
    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "health": health,
    }


@app.get("/sensors/gps/trail")
@app.get("/operations/{operation_id}/sensors/gps/trail")
def get_sensors_gps_trail(
    limit: int = 100,
    operation_id: Optional[str] = None,
):
    """Retrieve GPS breadcrumb trail coordinates for mapping and route tracking."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    trail = db.get_gps_trail(session_id=session_id, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "trail": trail,
        "count": len(trail),
    }


@app.post("/sensors/gps/simulate")
@app.post("/operations/{operation_id}/sensors/gps/simulate")
def simulate_gps_profile(req: SimulateGPSRequest, operation_id: Optional[str] = None):
    """Set simulation movement/degradation profile for the GPS sensor."""
    op = _get_operation(operation_id)
    _require_running(op)
    if op.simulator and hasattr(op.simulator, "gps_adapter"):
        op.simulator.gps_adapter.set_simulation_profile(req.profile or "STATIONARY")
        if req.latitude is not None and req.longitude is not None:
            op.simulator.gps_adapter.set_location(req.latitude, req.longitude, req.altitude_m)
        if req.accuracy_m is not None:
            op.simulator.gps_adapter.accuracy_m = req.accuracy_m
        if req.speed_mps is not None:
            op.simulator.gps_adapter.speed_mps = req.speed_mps
        if req.heading_deg is not None:
            op.simulator.gps_adapter.heading_deg = req.heading_deg
        if req.satellites is not None:
            op.simulator.gps_adapter.satellites = req.satellites
    return {"status": "ok", "profile": (req.profile or "STATIONARY").upper()}


@app.post("/sensors/gps/readings")
@app.post("/operations/{operation_id}/sensors/gps/readings")
def ingest_gps_reading(req: IngestGPSReadingRequest, operation_id: Optional[str] = None):
    """Hardware / IoT Ingestion Endpoint for GPS telemetry."""
    mov_tp = GPSMovementState(req.movement_state) if req.movement_state in GPSMovementState._value2member_map_ else GPSMovementState.STATIONARY
    h_tp = SensorHealthStatus(req.status) if req.status in SensorHealthStatus._value2member_map_ else SensorHealthStatus.ONLINE

    reading = GPSReading(
        sensor_id=req.sensor_id or "DEV-GPS-01",
        device_id=req.device_id or "RESCUE-KIT-01",
        sensor_type=SensorType.GPS,
        latitude=req.latitude,
        longitude=req.longitude,
        altitude_m=req.altitude_m if req.altitude_m is not None else 3950.0,
        accuracy_m=req.accuracy_m if req.accuracy_m is not None else 2.5,
        speed_mps=req.speed_mps if req.speed_mps is not None else 0.0,
        heading_deg=req.heading_deg if req.heading_deg is not None else 0.0,
        satellites=req.satellites if req.satellites is not None else 12,
        movement_state=mov_tp,
        is_valid_fix=req.is_valid_fix if req.is_valid_fix is not None else True,
        status=h_tp,
        confidence=req.confidence if req.confidence is not None else 0.98,
        quality=req.quality if req.quality is not None else 0.98,
        entity_type=req.entity_type or "DEVICE",
        entity_id=req.entity_id,
    )
    if not reading.validate():
        raise HTTPException(status_code=422, detail="Invalid GPS reading: latitude/longitude out of range, negative accuracy, or corrupted values rejected.")

    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else "external-ingest"
    db.log_gps_reading(reading, session_id=session_id)
    return {"logged": True, "reading": reading.to_dict()}


@app.get("/analytics/gps")
@app.get("/operations/{operation_id}/analytics/gps")
def get_gps_analytics(operation_id: Optional[str] = None):
    """Retrieve statistical and kinematic analytics for GPS positioning and kinematics."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    analytics = db.get_gps_analytics(session_id=session_id)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "analytics": analytics,
    }


@app.get("/geospatial/distance")
@app.get("/operations/{operation_id}/geospatial/distance")
def calculate_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    operation_id: Optional[str] = None,
):
    """Calculate geodesic Haversine distance in meters and kilometers between two coordinate pairs."""
    c1 = GPSCoordinate(latitude=lat1, longitude=lon1)
    c2 = GPSCoordinate(latitude=lat2, longitude=lon2)
    dist_m = calculate_geospatial_distance(c1, c2)
    return {
        "distance_m": round(dist_m, 2),
        "distance_km": round(dist_m / 1000.0, 3),
        "point1": {"latitude": lat1, "longitude": lon1},
        "point2": {"latitude": lat2, "longitude": lon2},
    }


@app.get("/geospatial/nearest-team")
@app.get("/operations/{operation_id}/geospatial/nearest-team")
def get_nearest_team(
    target_lat: float,
    target_lon: float,
    operation_id: Optional[str] = None,
):
    """Find the nearest available rescue team to a given target coordinate."""
    op = _get_operation(operation_id)
    _require_running(op)
    target = GPSCoordinate(latitude=target_lat, longitude=target_lon)
    teams = {t.team_id: t.location for t in op.rescue_teams}
    team_id, dist_m = find_nearest_rescue_team(target, teams)
    team_info = next((t for t in op.rescue_teams if t.team_id == team_id), None) if team_id else None
    return {
        "target": {"latitude": target_lat, "longitude": target_lon},
        "nearest_team_id": team_id,
        "team_name": team_info.team_name if team_info else None,
        "distance_m": round(dist_m, 2),
        "distance_km": round(dist_m / 1000.0, 3),
        "team_location": team_info.location.to_dict() if (team_info and team_info.location) else None,
    }


@app.get("/geospatial/nearest-survivor")
@app.get("/operations/{operation_id}/geospatial/nearest-survivor")
def get_nearest_survivor(
    ref_lat: float,
    ref_lon: float,
    operation_id: Optional[str] = None,
):
    """Find the nearest survivor to a given reference coordinate."""
    op = _get_operation(operation_id)
    _require_running(op)
    ref = GPSCoordinate(latitude=ref_lat, longitude=ref_lon)
    survivors = {v.victim_id: v.location for v in op.config.victims} if op.config else {}
    vid, dist_m = find_nearest_survivor(ref, survivors)
    return {
        "reference": {"latitude": ref_lat, "longitude": ref_lon},
        "nearest_victim_id": vid,
        "distance_m": round(dist_m, 2),
        "distance_km": round(dist_m / 1000.0, 3),
    }


@app.get("/geospatial/entities")
@app.get("/operations/{operation_id}/geospatial/entities")
def get_geospatial_entities(operation_id: Optional[str] = None):
    """Retrieve all geospatial entities in the operation: site origin, device GPS, survivors, rescue teams, tracked members."""
    op = _get_operation(operation_id)
    _require_running(op)
    site_origin = op.config.site_origin.to_dict() if (op.config and op.config.site_origin) else None
    device_gps = op.simulator.gps_report() if op.simulator else {}

    victims = []
    if op.config:
        for v in op.config.victims:
            victims.append({
                "victim_id": v.victim_id,
                "label": getattr(v, "label", getattr(v, "full_name", v.victim_id)),
                "location": v.location.to_dict() if v.location else None,
                "status": v.status.value if hasattr(v.status, "value") else str(getattr(v, "status", "UNKNOWN")),
            })

    teams = []
    for t in op.rescue_teams:
        teams.append({
            "team_id": t.team_id,
            "team_name": t.team_name,
            "location": t.location.to_dict() if t.location else None,
            "availability": t.availability.value if hasattr(t.availability, "value") else str(t.availability),
            "members_count": t.members,
        })

    members = []
    for tid, m_list in op.team_members.items():
        for m in m_list:
            members.append({
                "member_id": m.member_id,
                "callsign": m.callsign,
                "team_id": m.team_id,
                "status": m.status.value if hasattr(m.status, "value") else str(m.status),
                "location": m.location.to_dict() if m.location else None,
                "assigned_victim_id": m.assigned_victim_id,
            })

    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "site_origin": site_origin,
        "device_gps": device_gps,
        "victims": victims,
        "teams": teams,
        "members": members,
    }


# =========================================================================== #
# SENSOR REJECTIONS & UNIFIED TELEMETRY APIS
# =========================================================================== #

@app.get("/sensors/rejections")
@app.get("/operations/{operation_id}/sensors/rejections")
def get_sensor_rejections(
    sensor_type: Optional[str] = None,
    limit: int = 100,
    operation_id: Optional[str] = None,
):
    """Retrieve quarantine ledger of corrupted or out-of-range sensor readings."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    rejections = db.get_rejected_readings(session_id=session_id, sensor_type=sensor_type, limit=limit)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "rejections": rejections,
        "count": len(rejections),
    }


@app.get("/analytics/rejections")
@app.get("/operations/{operation_id}/analytics/rejections")
def get_rejection_analytics(operation_id: Optional[str] = None):
    """Retrieve statistical aggregations of sensor rejections."""
    op = _get_operation_optional(operation_id)
    session_id = op.session_id if (op and op.session_id) else None
    analytics = db.get_rejection_analytics(session_id=session_id)
    return {
        "operation_id": _op_id(op, operation_id) if op else "default",
        "session_id": session_id,
        "analytics": analytics,
    }


@app.get("/telemetry/cycle/latest")
@app.get("/operations/{operation_id}/telemetry/cycle/latest")
def get_latest_cycle_telemetry(operation_id: Optional[str] = None):
    """Retrieve unified multi-sensor telemetry snapshot across all channels for current cycle."""
    op = _get_operation(operation_id)
    _require_running(op)

    survivor_readings = [r.to_dict() for buf in op.history.values() for r in list(buf)[-1:]]
    environmental_report = op.simulator.environmental_full_report() if op.simulator else {}
    camera_report = op.simulator.cameras_all_report() if op.simulator else {}
    thermal_report = op.simulator.thermal_all_report() if op.simulator else {}
    gps_report = op.simulator.gps_report() if op.simulator else {}
    health_report = [h.to_dict() for h in op.simulator.get_sensor_health_report()] if op.simulator else []

    return {
        "operation_id": _op_id(op, operation_id),
        "cycle": op.cycle_count,
        "session_id": op.session_id,
        "survivor_sensors": survivor_readings,
        "environmental_sensors": environmental_report,
        "camera_sensors": camera_report,
        "thermal_sensors": thermal_report,
        "gps": gps_report,
        "sensor_health": health_report,
    }


# --------------------------------------------------------------------------- #
# Hardware Architecture & Digital Twin Registry Endpoints
# --------------------------------------------------------------------------- #

@app.get("/hardware/inventory")
@app.get("/api/hardware/inventory")
@app.get("/operations/{operation_id}/hardware/inventory")
def get_hardware_inventory_endpoint(operation_id: Optional[str] = None):
    """Retrieve complete hardware equipment inventory including simulated and physical models."""
    inventory = hardware_registry.get_hardware_inventory()
    op = _get_operation_optional(operation_id)
    scenario_id = op.config.scenario_id if (op and op.config) else None

    return {
        "status": "success",
        "total_equipment": len(inventory),
        "active_scenario_id": scenario_id,
        "inventory": inventory,
    }


@app.get("/hardware/inventory/{device_id}")
@app.get("/api/hardware/inventory/{device_id}")
def get_hardware_device_endpoint(device_id: str):
    """Retrieve specific hardware asset details by device ID."""
    dev = hardware_registry.get_hardware_by_id(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found in hardware registry")
    return {"status": "success", "device": dev}


@app.get("/hardware/topology")
@app.get("/api/hardware/topology")
@app.get("/operations/{operation_id}/hardware/topology")
def get_hardware_topology_endpoint(operation_id: Optional[str] = None):
    """Retrieve interconnect, wiring, and bus topology connecting hardware to controllers."""
    topology = hardware_registry.get_hardware_topology()
    return {
        "status": "success",
        "total_connections": len(topology),
        "topology": topology,
    }


@app.get("/hardware/summary")
@app.get("/api/hardware/summary")
@app.get("/operations/{operation_id}/hardware/summary")
def get_hardware_summary_endpoint(operation_id: Optional[str] = None):
    """Retrieve dynamic hardware summary counts and active scenario state."""
    op = _get_operation_optional(operation_id)
    scenario_id = op.config.scenario_id if (op and op.config) else None
    summary = hardware_registry.get_hardware_summary(scenario_id)
    return {
        "status": "success",
        **summary,
    }
# --------------------------------------------------------------------------- #
# Isolated Real Wearable IoT & Android Companion Bridge Endpoints
# --------------------------------------------------------------------------- #

class AssignWearableRequest(BaseModel):
    team_id: str
    device_id: str


class UpdateWearableStatusRequest(BaseModel):
    status: str
    delivery_error: Optional[str] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None


class BridgeSyncRequest(BaseModel):
    session_id: str
    team_id: str
    device_name: Optional[str] = "Android Companion Bridge"
    member_id: Optional[str] = None
    bluetooth_state: Optional[str] = "ENABLED"
    watch_connected: Optional[bool] = False
    watch_device_id: Optional[str] = None
    watch_mac: Optional[str] = None
    watch_model: Optional[str] = None
    gps_available: Optional[bool] = True
    location_source: Optional[str] = "PHONE_GPS"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None
    accuracy_m: Optional[float] = None
    speed_mps: Optional[float] = None
    heading_deg: Optional[float] = None
    timestamp: Optional[str] = None
    gps_status: Optional[str] = None
    status: Optional[str] = "ONLINE"
    notes: Optional[str] = None


class WearableTelemetryRequest(BaseModel):
    device_id: str
    latitude: float
    longitude: float
    altitude_m: Optional[float] = None
    accuracy_m: Optional[float] = None
    speed_mps: Optional[float] = None
    battery_pct: Optional[float] = None
    heart_rate_bpm: Optional[float] = None
    step_count: Optional[int] = None
    team_id: Optional[str] = None
    session_id: Optional[str] = None


class SetWearableModeRequest(BaseModel):
    mode: str  # "SIMULATION" or "REAL_HARDWARE"


@app.get("/api/wearable/mode")
def get_wearable_mode_endpoint():
    return {
        "status": "success",
        "mode": global_wearable_gateway.get_mode(),
        "available_modes": ["SIMULATION", "REAL_HARDWARE"],
    }


@app.post("/api/wearable/mode")
def set_wearable_mode_endpoint(req: SetWearableModeRequest):
    new_mode = global_wearable_gateway.set_mode(req.mode)
    return {
        "status": "success",
        "mode": new_mode,
        "message": f"Operational mode set to {new_mode}.",
    }
@app.get("/api/wearable/devices")
def list_wearable_devices_endpoint(team_id: Optional[str] = None):
    devices = db.list_wearable_devices(team_id=team_id)
    return {"status": "success", "total": len(devices), "devices": devices}


@app.get("/api/wearable/devices/{device_id}")
def get_wearable_device_endpoint(device_id: str):
    device = db.get_wearable_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Wearable device '{device_id}' not found")
    return {"status": "success", "device": device}


@app.post("/api/wearable/assign")
def assign_wearable_endpoint(req: AssignWearableRequest):
    if "T800" in req.device_id.upper():
        raise HTTPException(
            status_code=400,
            detail="Device T800Ultra is unsupported and obsolete. System uses Wave Call Plus (CALLPLUS_7F1B) only.",
        )
    global_wearable_gateway.bind_team_to_device(req.team_id, req.device_id)
    db.assign_wearable_device_to_team(req.device_id, req.team_id)
    device = db.get_wearable_device(req.device_id)
    return {
        "status": "success",
        "assigned": {"team_id": req.team_id, "device_id": req.device_id},
        "device": device,
    }


@app.post("/api/wearable/diagnostics/{device_id}")
def run_wearable_diagnostics_endpoint(device_id: str):
    if "T800" in device_id.upper():
        raise HTTPException(
            status_code=400,
            detail="Device T800Ultra is unsupported and obsolete. System uses Wave Call Plus (CALLPLUS_7F1B) only.",
        )
    device = db.get_wearable_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
    diag = global_wearable_gateway.run_hardware_diagnostics(device_id)
    return {"status": "success", "device_id": device_id, "diagnostics": diag}


@app.get("/api/wearable/capabilities")
def get_wearable_capabilities_endpoint(device_id: str = "DEV-WEARABLE-CALLPLUS"):
    dev_clean = (device_id or "").strip()
    if dev_clean not in ("DEV-WEARABLE-CALLPLUS", "CALLPLUS_7F1B"):
        raise HTTPException(
            status_code=400,
            detail=f"Device '{device_id}' is unsupported. System uses Wave Call Plus (DEV-WEARABLE-CALLPLUS / CALLPLUS_7F1B) only.",
        )
    adapter = global_wearable_gateway.get_adapter_for_device(dev_clean)
    capabilities = adapter.discover_services(dev_clean)
    return {"status": "success", "device_id": dev_clean, "capabilities": capabilities}


@app.get("/api/wearable/connection/state")
def get_wearable_connection_state_endpoint():
    manager = global_wearable_gateway.wave_call_plus_adapter.connection_manager
    return {
        "status": "success",
        "device_id": "DEV-WEARABLE-CALLPLUS",
        "bluetooth_name": manager.ALLOWED_BLUETOOTH_NAME,
        "mac_address": manager.ALLOWED_MAC,
        "connection_state": manager.get_state(),
        "backend_session": manager.get_state(),
        "physical_ble": "CONNECTED" if manager.is_connected() else "DISCONNECTED",
        "is_connected": manager.is_connected(),
        "last_seen": manager.last_seen,
        "last_error": manager.last_error,
    }


@app.get("/api/wearable/devices")
@app.get("/api/devices")
def list_wearable_devices_endpoint(team_id: Optional[str] = None):
    devs = db.list_wearable_devices(team_id=team_id)
    conn_mgr = global_wearable_gateway.wave_call_plus_adapter.connection_manager

    for d in devs:
        if conn_mgr.is_connected():
            d["connection_status"] = "CONNECTED"
            d["physical_ble"] = "CONNECTED"
        elif conn_mgr.get_state() == "CONNECTING":
            d["connection_status"] = "CONNECTING"
            d["physical_ble"] = "CONNECTING"
        else:
            d["connection_status"] = "DISCONNECTED"
            d["physical_ble"] = "DISCONNECTED"

    return {"status": "success", "total": len(devs), "devices": devs}


@app.get("/api/wearable/devices/{device_id}")
def get_wearable_device_endpoint(device_id: str):
    dev = db.get_wearable_device(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
    return {"status": "success", "device": dev}


class WearableConnectPayload(BaseModel):
    event: Optional[str] = "BLE_GATT_CONNECTED"
    wearable_id: Optional[str] = "DEV-WEARABLE-CALLPLUS"
    device_name: Optional[str] = "CALLPLUS_7F1B"
    physical_connected: Optional[bool] = None
    mac_address: Optional[str] = None


@app.post("/api/wearable/connect")
@app.post("/api/bridge/connect")
def connect_wearable_endpoint(
    req: Optional[WearableConnectPayload] = None,
    mac_address: Optional[str] = None,
    physical_connected: Optional[bool] = None,
):
    manager = global_wearable_gateway.wave_call_plus_adapter.connection_manager
    target_mac = (req.mac_address if req else None) or mac_address
    target_dev = (req.wearable_id if req else None) or "DEV-WEARABLE-CALLPLUS"
    target_name = (req.device_name if req else None) or "CALLPLUS_7F1B"
    is_phys = True if (req is None and physical_connected is None) else ((req.physical_connected if req and req.physical_connected is not None else True) if physical_connected is None else physical_connected)

    if req and req.event == "BLE_CONNECT_REQUESTED":
        is_phys = False

    ok, msg = manager.connect(target_dev, mac_address=target_mac, bluetooth_name=target_name, physical_confirmed=is_phys)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    db.update_wearable_device_status("DEV-WEARABLE-CALLPLUS", status=manager.get_state())
    return {
        "status": "success" if is_phys else "pending",
        "message": msg,
        "state": manager.get_state(),
        "backend_session": manager.get_state(),
        "physical_ble": "CONNECTED" if manager.is_connected() else ("CONNECTING" if manager.get_state() == "CONNECTING" else "DISCONNECTED"),
    }


@app.post("/api/wearable/disconnect")
@app.post("/api/bridge/disconnect")
def disconnect_wearable_endpoint():
    manager = global_wearable_gateway.wave_call_plus_adapter.connection_manager
    ok, msg = manager.disconnect()
    db.update_wearable_device_status("DEV-WEARABLE-CALLPLUS", status="DISCONNECTED")
    return {
        "status": "success",
        "message": msg,
        "state": manager.get_state(),
        "backend_session": "DISCONNECTED",
        "physical_ble": "DISCONNECTED",
    }


@app.post("/api/wearable/reconnect")
@app.post("/api/bridge/reconnect")
def reconnect_wearable_endpoint(
    req: Optional[WearableConnectPayload] = None,
    physical_connected: Optional[bool] = None,
):
    manager = global_wearable_gateway.wave_call_plus_adapter.connection_manager
    is_phys = (req.physical_connected if req and req.physical_connected is not None else False) if physical_connected is None else physical_connected

    if req and req.event == "BLE_GATT_CONNECTED":
        is_phys = True

    ok, msg = manager.reconnect(physical_confirmed=is_phys)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    db.update_wearable_device_status("DEV-WEARABLE-CALLPLUS", status=manager.get_state())
    return {
        "status": "success" if is_phys else "pending",
        "message": msg,
        "state": manager.get_state(),
        "backend_session": manager.get_state(),
        "physical_ble": "CONNECTED" if manager.is_connected() else ("RECONNECTING" if manager.get_state() == "RECONNECTING" else "DISCONNECTED"),
    }
@app.get("/api/wearable/commands/active")
def get_active_wearable_command_endpoint(
    team_id: Optional[str] = None,
    device_id: Optional[str] = None,
    member_id: Optional[str] = None,
):
    if device_id and "T800" in device_id.upper():
        raise HTTPException(
            status_code=400,
            detail="Device T800Ultra is unsupported and obsolete. System uses Wave Call Plus (CALLPLUS_7F1B) only.",
        )
    cmd = global_wearable_gateway.get_active_command_for_team_or_device(
        team_id=team_id, device_id=device_id if not member_id else None, member_id=member_id
    )
    if not cmd:
        # Check DB for active commands matching filters
        active_statuses = [
            "ASSIGNED", "PENDING", "SENT_TO_BRIDGE", "PHONE_NOTIFICATION_POSTED",
            "DELIVERED", "GO", "ACCEPTED", "EN_ROUTE", "ARRIVED"
        ]
        cmds = db.list_rescue_commands(
            team_id=team_id,
            member_id=member_id,
            target_device_id=device_id if not member_id else None,
            limit=5
        )
        for c in cmds:
            if c.get("status") in active_statuses:
                cmd = c
                break

    # Discover system-wide latest active command for cross-dashboard synchronization
    latest_cmd = global_wearable_gateway.get_active_command_for_team_or_device()
    if not latest_cmd:
        all_recent = db.list_rescue_commands(limit=5)
        for c in all_recent:
            if c.get("status") in [
                "ASSIGNED", "PENDING", "SENT_TO_BRIDGE", "PHONE_NOTIFICATION_POSTED",
                "DELIVERED", "GO", "ACCEPTED", "EN_ROUTE", "ARRIVED"
            ]:
                latest_cmd = c
                break

    return {
        "status": "success",
        "has_active_command": bool(cmd),
        "command": cmd,
        "latest_assigned_member_id": latest_cmd.get("member_id") if latest_cmd else None,
        "latest_assigned_command_id": latest_cmd.get("command_id") if latest_cmd else None,
        "latest_assigned_team_id": latest_cmd.get("team_id") if latest_cmd else None,
        "message": "Active rescue assignment retrieved." if cmd else "No active command for target device.",
    }


@app.get("/api/wearable/commands")
def list_wearable_commands_endpoint(
    team_id: Optional[str] = None,
    device_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
):
    cmds = db.list_rescue_commands(team_id=team_id, target_device_id=device_id, status=status, limit=limit)
    return {"status": "success", "total": len(cmds), "commands": cmds}


@app.get("/api/wearable/alerts/active")
def get_active_wearable_alerts_endpoint(
    session_id: Optional[str] = None,
    team_id: Optional[str] = None,
    member_id: Optional[str] = None,
):
    """
    Returns active rescue alerts with real-time watch delivery states.
    Guarantees alert persistence regardless of watch delivery or ACK state.
    """
    ledger_alerts = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    active_cmd = global_wearable_gateway.get_active_command_for_team_or_device(team_id=team_id, member_id=member_id)
    return {
        "status": "success",
        "total_active_alerts": len(ledger_alerts),
        "alerts": ledger_alerts,
        "active_watch_command": active_cmd,
        "watch_delivery_channel": {
            "device_name": "Wave Call Plus",
            "bluetooth_name": "CALLPLUS_7F1B",
            "is_connected": global_wearable_gateway.wave_call_plus_adapter.connection_manager.is_connected(),
            "state": global_wearable_gateway.wave_call_plus_adapter.connection_manager.get_state(),
        }
    }


class WearableTestAlertRequest(BaseModel):
    command_id: Optional[str] = None
    team_id: Optional[str] = "ALPHA"
    member_id: Optional[str] = "ALPHA-M001"
    victim_id: Optional[str] = "SURVIVOR-TEST-01"
    location: Optional[str] = "Sector Alpha-1"
    priority: Optional[str] = "HIGH"
    command_type: Optional[str] = "GO"
    command_text: Optional[str] = "Proceed to rescue SURVIVOR-TEST-01 (LIVE HARDWARE TEST)"
    title: Optional[str] = "🚨 RIDGEWATCH — GO (TEST ALERT)"
    body: Optional[str] = "Live Hardware Test: Proceed to rescue SURVIVOR-TEST-01."
    watch_device_id: Optional[str] = "DEV-WEARABLE-CALLPLUS"


@app.post("/api/wearable/commands/test_alert")
def create_wearable_test_alert_endpoint(req: WearableTestAlertRequest):
    """
    Registers and persists a test rescue alert through the backend HAL and SQLite tables.
    """
    cmd_id = req.command_id or f"CMD-TEST-{uuid.uuid4().hex[:5].upper()}"
    team_id = req.team_id or "ALPHA"
    member_id = req.member_id or "ALPHA-M001"
    victim_id = req.victim_id or "SURVIVOR-TEST-01"
    priority = req.priority or "HIGH"

    alert_obj = {
        "alert_id": f"ALT-{cmd_id}",
        "command_id": cmd_id,
        "team_id": team_id,
        "member_id": member_id,
        "victim_id": victim_id,
        "target_id": victim_id,
        "location": req.location or "Sector Alpha-1",
        "location_label": req.location or "Sector Alpha-1",
        "priority": priority,
        "command_type": req.command_type or "GO",
        "command_text": req.command_text or f"Proceed to rescue {victim_id} (LIVE TEST)",
        "title": req.title or "🚨 RIDGEWATCH — GO (TEST ALERT)",
        "body": req.body or f"Live Hardware Test: Proceed to rescue {victim_id}.",
        "watch_device_id": req.watch_device_id or "DEV-WEARABLE-CALLPLUS",
    }

    res = global_wearable_gateway.dispatch_alert_to_watch(alert_obj)
    try:
        db.create_rescue_command(
            command_id=cmd_id,
            team_id=team_id,
            member_id=member_id,
            victim_id=victim_id,
            command_type=alert_obj.get("command_type", "GO"),
            command_text=alert_obj.get("body", ""),
            destination_label=alert_obj.get("location", ""),
            priority=priority,
        )
    except Exception as ex:
        logger.warning(f"Could not persist test alert command: {ex}")
    return {
        "status": "success",
        "command_id": cmd_id,
        "alert": alert_obj,
        "dispatch_result": res,
    }


@app.post("/api/wearable/commands/{command_id}/ack")
def ack_wearable_command_endpoint(
    command_id: str,
    device_id: Optional[str] = None,
    member_id: Optional[str] = None,
    source: Optional[str] = "RESCUER_CONFIRMATION",
):
    res = global_wearable_gateway.acknowledge_command(
        command_id, device_id=device_id, member_id=member_id, source=source
    )
    if res.get("status") == "error":
        reason = res.get("reason", "VALIDATION_FAILED")
        status_code = 400 if reason in ("WRONG_WEARABLE", "WRONG_MEMBER") else (404 if reason == "WRONG_COMMAND" else 409)
        raise HTTPException(status_code=status_code, detail=f"Confirmation rejected: {reason}")

    cmd = db.get_rescue_command(command_id) or global_wearable_gateway.active_commands.get(command_id)
    session_id = (cmd.get("operation_id") or cmd.get("session_id") or "GLOBAL") if cmd else "GLOBAL"
    team_id = cmd.get("team_id", "ALPHA") if cmd else "ALPHA"
    victim_id = cmd.get("victim_id") if cmd else None
    try:
        db.log_rescue_status_event(
            session_id=session_id,
            event_type="watch_ack_received",
            team_id=team_id,
            victim_id=victim_id,
            notes=f"Physical Wave Call Plus (CALLPLUS_7F1B) acknowledged rescue alert {command_id}.",
        )
    except Exception:
        pass
    return {"status": "success", "command_id": command_id, "result": res}


def accept_rescue_assignment(
    command_or_assignment_id: str,
    sender_phone: Optional[str] = None,
    member_id: Optional[str] = None,
    acceptance_source: str = "APK",
    operation_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified Acceptance Service for Two-Way Rescue and Job Acceptance (APK + SMS).
    
    Guarantees:
    1. Validates command or job assignment exists.
    2. Validates rescuer identity and E.164 phone authorization.
    3. Handles duplicate acceptance safely (returns ALREADY_ACCEPTED without duplicate ACK/GPS reset).
    4. Rejects terminal/arrived states.
    5. Sets authoritative backend state to ACCEPTED / USER_ACCEPTED with acceptance_source and accepted_at.
    6. Synchronizes with in-memory running operations and triggers PHONE_GPS readiness for ALPHA-M001.
    7. Dispatches non-blocking confirmation SMS if accepted via SMS.
    """
    try:
        from notification_dispatch import (
            normalize_phone_number_e164,
            resolve_recipient_mobile,
            send_acceptance_confirmation_sms,
        )
    except ImportError:
        from backend.notification_dispatch import (
            normalize_phone_number_e164,
            resolve_recipient_mobile,
            send_acceptance_confirmation_sms,
        )

    raw_id = str(command_or_assignment_id).strip()
    clean_id = raw_id
    if clean_id.startswith("NOTIF-"):
        clean_id = clean_id[6:]
    elif clean_id.startswith("ALT-"):
        clean_id = clean_id[4:]

    item_type, item = db.get_rescue_command_or_job(clean_id, db_path=db_path)
    if not item:
        item_type, item = db.get_rescue_command_or_job(raw_id, db_path=db_path)
    if not item and not clean_id.startswith("CMD-"):
        item_type, item = db.get_rescue_command_or_job(f"CMD-{clean_id}", db_path=db_path)

    if not item:
        # Check global wearable gateway fallback
        gw_cmd = (
            global_wearable_gateway.active_commands.get(raw_id)
            or global_wearable_gateway.active_commands.get(clean_id)
            or global_wearable_gateway.active_commands.get(f"CMD-{clean_id}")
            or global_wearable_gateway.active_commands.get(f"ALT-{clean_id}")
        )
        if gw_cmd:
            item_type = "RESCUE_COMMAND"
            item = gw_cmd

    if not item:
        if clean_id.startswith("CMD-TEST-") or clean_id.startswith("TEST-") or clean_id.startswith("ACCEPT-") or raw_id.startswith("ALT-"):
            now_iso = datetime.now(timezone.utc).isoformat()
            db.upsert_notification({
                "alert_id": clean_id,
                "team_id": "ALPHA",
                "member_id": member_id or "ALPHA-M001",
                "title": "Emergency Alert",
                "message": f"Rescue Command: GO (Test Alert)",
                "status": "USER_ACCEPTED",
                "watch_delivery_status": "DELIVERED",
                "watch_ack_status": "ACCEPTED",
                "acceptance_source": acceptance_source,
                "accepted_at": now_iso,
            }, db_path=db_path)
            return {
                "success": True,
                "status": "ACCEPTED",
                "source": acceptance_source,
                "command_id": clean_id,
                "member_id": member_id or "ALPHA-M001",
                "message": f"Test alert {clean_id} accepted successfully.",
            }
        return {
            "success": False,
            "status": "NOT_FOUND",
            "error": f"Command or assignment '{command_or_assignment_id}' not found.",
        }

    now_iso = datetime.now(timezone.utc).isoformat()

    if item_type == "RESCUE_COMMAND":
        assigned_member = item.get("member_id") or "ALPHA-M001"
        assigned_team = item.get("team_id") or "ALPHA"
        assigned_victim = item.get("victim_id")
        current_status = str(item.get("status") or "ASSIGNED").upper()

        # Rescuer Identity / Member ID validation if provided
        if member_id and member_id.strip().upper() != assigned_member.upper():
            return {
                "success": False,
                "status": "MEMBER_MISMATCH",
                "error": f"Member '{member_id}' is not assigned to command '{clean_id}' (Assigned: '{assigned_member}').",
            }

        # Sender Phone Verification if provided (e.g. from SMS)
        if sender_phone:
            clean_sender = normalize_phone_number_e164(sender_phone)
            contact = resolve_recipient_mobile(assigned_member, team_id=assigned_team, db_path=db_path)
            expected_phone = contact.get("phone_normalized")
            cmd_phone = normalize_phone_number_e164(item.get("phone_number"))

            if not clean_sender:
                return {
                    "success": False,
                    "status": "INVALID_SENDER_PHONE",
                    "error": f"Invalid sender phone number '{sender_phone}'.",
                }
            if clean_sender != expected_phone and clean_sender != cmd_phone:
                logger.warning(
                    f"[ACCEPTANCE_SECURITY] Unauthorized SMS sender '{clean_sender}' attempted to accept command '{clean_id}' for '{assigned_member}' (Expected: '{expected_phone}')."
                )
                return {
                    "success": False,
                    "status": "UNAUTHORIZED_SENDER",
                    "error": f"Phone number '{clean_sender}' is not authorized to accept commands for '{assigned_member}'.",
                }

        # Duplicate acceptance protection
        if current_status in ("ACCEPTED", "USER_ACCEPTED", "EN_ROUTE", "GO"):
            return {
                "success": True,
                "status": "ALREADY_ACCEPTED",
                "already_accepted": True,
                "command_id": clean_id,
                "member_id": assigned_member,
                "source": item.get("acceptance_source") or acceptance_source,
                "message": f"Command {clean_id} is already accepted.",
            }

        # Terminal state protection
        if current_status in ("COMPLETED", "RESCUED", "CANCELLED", "ARRIVED"):
            return {
                "success": False,
                "status": "REJECTED",
                "error": f"Command {clean_id} is in terminal or arrived state '{current_status}' and cannot be re-accepted.",
            }

        # Transition authoritative state
        actual_cmd_id = item.get("command_id") or clean_id
        db.update_rescue_command_status(
            actual_cmd_id,
            status="USER_ACCEPTED",
            watch_delivery_status="PHONE_NOTIFICATION_POSTED",
            acceptance_source=acceptance_source,
            accepted_at=now_iso,
            db_path=db_path,
        )
        if actual_cmd_id != clean_id:
            db.update_rescue_command_status(
                clean_id,
                status="USER_ACCEPTED",
                watch_delivery_status="PHONE_NOTIFICATION_POSTED",
                acceptance_source=acceptance_source,
                accepted_at=now_iso,
                db_path=db_path,
            )
        global_wearable_gateway.update_command_status(actual_cmd_id, "USER_ACCEPTED")
        global_wearable_gateway.update_command_status(clean_id, "USER_ACCEPTED")
        global_wearable_gateway.update_command_status(raw_id, "USER_ACCEPTED")

        # Update linked notification
        db.update_notification_status(
            actual_cmd_id,
            watch_delivery_status="DELIVERED",
            watch_ack_status="ACCEPTED",
            status="USER_ACCEPTED",
            db_path=db_path,
        )
        db.update_notification_status(
            clean_id,
            watch_delivery_status="DELIVERED",
            watch_ack_status="ACCEPTED",
            status="USER_ACCEPTED",
            db_path=db_path,
        )
        db.update_notification_status(
            raw_id,
            watch_delivery_status="DELIVERED",
            watch_ack_status="ACCEPTED",
            status="USER_ACCEPTED",
            db_path=db_path,
        )

        # Reflect in running operations
        for op in operations.values():
            if not op or not hasattr(op, "team_members"):
                continue
            for t_id, members in op.team_members.items():
                if t_id in (assigned_team, "ALPHA"):
                    for m in members:
                        if m.member_id == assigned_member:
                            m.status = MemberStatus.EN_ROUTE
                            m.assigned_victim_id = assigned_victim
                            m.active_command_id = clean_id
                            m.assigned_at = now_iso
                            if assigned_member == "ALPHA-M001":
                                m.location_source = "PHONE_GPS"
                                m.gps_status = "WAITING_FOR_PERMISSION" if not ALPHA_M001_LATEST_GPS.get("latitude") else ALPHA_M001_LATEST_GPS.get("gps_status", "TRACKING")
                                reset_alpha_m001_mission_navigation_state(new_command_id=clean_id, new_victim_id=assigned_victim, preserve_hardware_fix=True)
                                ALPHA_M001_LATEST_GPS["active_command_id"] = clean_id
                                ALPHA_M001_LATEST_GPS["location_source"] = "PHONE_GPS"
                                ALPHA_M001_LATEST_GPS["navigation_status"] = "ON_TRACK"
                                ALPHA_M001_NAV_STATE["active_command_id"] = clean_id
                                ALPHA_M001_NAV_STATE["navigation_status"] = "ON_TRACK"

        # Log rescue status event
        db.log_rescue_status_event(
            session_id="GLOBAL",
            event_type="member_accepted",
            team_id=assigned_team,
            victim_id=assigned_victim,
            notes=f"Rescuer {assigned_member} manually accepted rescue command {clean_id} via {acceptance_source}.",
            db_path=db_path,
        )

        # Dispatch confirmation SMS if accepted via SMS
        if acceptance_source.upper() == "SMS":
            send_acceptance_confirmation_sms(
                phone_normalized=sender_phone or item.get("phone_number") or "+918098897666",
                command_id=clean_id,
                member_id=assigned_member,
                db_path=db_path,
            )

        logger.info(f"[ACCEPTANCE] Rescue command {clean_id} successfully accepted via {acceptance_source} by {assigned_member}")
        return {
            "success": True,
            "status": "ACCEPTED",
            "source": acceptance_source,
            "command_id": clean_id,
            "member_id": assigned_member,
            "team_id": assigned_team,
            "victim_id": assigned_victim,
            "accepted_at": now_iso,
            "message": f"Rescue mission {clean_id} accepted successfully via {acceptance_source}.",
        }

    elif item_type == "JOB_ASSIGNMENT":
        assigned_member = item.get("member_id") or "ALPHA-M001"
        assigned_team = item.get("team_id") or "ALPHA"
        current_status = str(item.get("status") or "ASSIGNED").upper()

        # Rescuer Identity / Member ID validation if provided
        if member_id and member_id.strip().upper() != assigned_member.upper():
            return {
                "success": False,
                "status": "MEMBER_MISMATCH",
                "error": f"Member '{member_id}' is not assigned to job '{clean_id}' (Assigned: '{assigned_member}').",
            }

        # Sender Phone Verification if provided
        if sender_phone:
            clean_sender = normalize_phone_number_e164(sender_phone)
            contact = resolve_recipient_mobile(assigned_member, team_id=assigned_team, db_path=db_path)
            expected_phone = contact.get("phone_normalized")
            if not clean_sender or clean_sender != expected_phone:
                logger.warning(
                    f"[ACCEPTANCE_SECURITY] Unauthorized SMS sender '{clean_sender}' attempted to accept job '{clean_id}' for '{assigned_member}'."
                )
                return {
                    "success": False,
                    "status": "UNAUTHORIZED_SENDER",
                    "error": f"Phone number '{clean_sender}' is not authorized to accept jobs for '{assigned_member}'.",
                }

        # Duplicate acceptance protection
        if current_status in ("ACCEPTED", "IN_PROGRESS"):
            return {
                "success": True,
                "status": "ALREADY_ACCEPTED",
                "already_accepted": True,
                "assignment_id": clean_id,
                "member_id": assigned_member,
                "source": item.get("acceptance_source") or acceptance_source,
                "message": f"Job assignment {clean_id} is already accepted.",
            }

        # Terminal state protection
        if current_status in ("COMPLETED", "FAILED", "CANCELLED"):
            return {
                "success": False,
                "status": "REJECTED",
                "error": f"Job assignment {clean_id} is in terminal state '{current_status}' and cannot be re-accepted.",
            }

        # Transition authoritative state
        db.update_job_assignment_status(
            clean_id,
            status="ACCEPTED",
            progress_pct=0,
            result_notes=f"Accepted by field rescuer via {acceptance_source}",
            acceptance_source=acceptance_source,
            accepted_at=now_iso,
            db_path=db_path,
        )

        # Reflect in running operations
        for op in operations.values():
            if not op or not hasattr(op, "team_members"):
                continue
            for t_id, members in op.team_members.items():
                if t_id in (assigned_team, "ALPHA"):
                    for m in members:
                        if m.member_id == assigned_member:
                            m.status = MemberStatus.EN_ROUTE
                            m.assigned_job_id = clean_id
                            m.assigned_at = now_iso
                            if assigned_member == "ALPHA-M001":
                                m.location_source = "PHONE_GPS"

        # Log event
        db.log_rescue_status_event(
            session_id="GLOBAL",
            event_type="job_accepted",
            team_id=assigned_team,
            notes=f"Staff {assigned_member} manually accepted work assignment {clean_id} via {acceptance_source}.",
            db_path=db_path,
        )

        # Dispatch confirmation SMS if accepted via SMS
        if acceptance_source.upper() == "SMS":
            send_acceptance_confirmation_sms(
                phone_normalized=sender_phone or "+918098897666",
                command_id=clean_id,
                member_id=assigned_member,
                db_path=db_path,
            )

        logger.info(f"[ACCEPTANCE] Job assignment {clean_id} successfully accepted via {acceptance_source} by {assigned_member}")
        return {
            "success": True,
            "status": "ACCEPTED",
            "source": acceptance_source,
            "assignment_id": clean_id,
            "member_id": assigned_member,
            "team_id": assigned_team,
            "accepted_at": now_iso,
            "message": f"Job assignment {clean_id} accepted successfully via {acceptance_source}.",
        }

    return {
        "success": False,
        "status": "UNKNOWN_TYPE",
        "error": f"Unknown item type for '{command_or_assignment_id}'.",
    }


@app.post("/api/wearable/commands/{command_id}/status")
def update_wearable_command_status_endpoint(
    command_id: str,
    req: UpdateWearableStatusRequest,
    operation_id: Optional[str] = None,
):
    status_upper = req.status.upper().strip()
    if status_upper in ("ACCEPTED", "USER_ACCEPTED"):
        result = accept_rescue_assignment(
            command_or_assignment_id=command_id,
            acceptance_source="APK",
            operation_id=operation_id,
        )
        if not result.get("success") and not result.get("already_accepted"):
            raise HTTPException(status_code=400, detail=result.get("error", "Acceptance failed"))
        cmd = db.get_rescue_command(command_id) or global_wearable_gateway.active_commands.get(command_id)
        return {"status": "success", "command_id": command_id, "command": cmd, "result": result}

    cmd = db.get_rescue_command(command_id)
    if not cmd:
        cmd = global_wearable_gateway.active_commands.get(command_id)

    updated = db.update_rescue_command_status(
        command_id=command_id,
        status=req.status,
        delivery_error=req.delivery_error,
    )
    global_wearable_gateway.update_command_status(command_id, req.status, error=req.delivery_error)

    # Reflect in running operation if applicable
    op = _get_operation_optional(operation_id)
    if op and op.running and cmd and cmd.get("team_id") in op.team_members:
        team_id = cmd["team_id"]
        cmd_member = cmd.get("member_id")
        for m in op.team_members[team_id]:
            if cmd_member and m.member_id != cmd_member:
                continue
            if status_upper in ("ARRIVED", "RESCUE_STARTED"):
                m.status = MemberStatus.ARRIVED
            elif status_upper in ("RESCUED", "COMPLETED"):
                m.status = MemberStatus.HOLD
                m.assigned_victim_id = None

            if req.last_latitude is not None and req.last_longitude is not None:
                m.location = GPSCoordinate(
                    latitude=req.last_latitude,
                    longitude=req.last_longitude,
                    altitude_m=m.location.altitude_m,
                )

        if op.session_id:
            db.log_rescue_status_event(
                session_id=op.session_id,
                event_type=f"wearable_status_{req.status.lower()}",
                team_id=team_id,
                victim_id=cmd.get("victim_id"),
                notes=f"Wearable command {command_id} reported {req.status}. {req.delivery_error or ''}",
            )

    return {"status": "success", "command_id": command_id, "command": updated or cmd}


@app.get("/notifications")
@app.get("/api/notifications")
@app.get("/api/wearable/notifications")
def get_notifications_endpoint(
    team_id: Optional[str] = None,
    limit: int = 50,
):
    """
    Returns stored multi-channel notification records for the dedicated Notification module.
    """
    notifs = db.list_notifications(team_id=team_id, limit=limit)
    return {
        "status": "success",
        "total": len(notifs),
        "notifications": notifs,
    }


@app.get("/notifications/{notification_id}")
@app.get("/api/notifications/{notification_id}")
def get_single_notification_endpoint(notification_id: str):
    """
    Returns complete details for a single notification record.
    """
    notif = db.get_notification(notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail=f"Notification '{notification_id}' not found.")
    return {
        "status": "success",
        "notification": notif,
    }


@app.post("/api/wearable/notifications/{notification_id}/accept")
def accept_wearable_notification_endpoint(notification_id: str):
    """
    Records a user acceptance action on an emergency notification via Unified Acceptance Service.
    """
    result = accept_rescue_assignment(
        command_or_assignment_id=notification_id,
        acceptance_source="APK",
    )
    if not result.get("success") and not result.get("already_accepted"):
        raise HTTPException(status_code=404 if result.get("status") == "NOT_FOUND" else 400, detail=result.get("error", "Acceptance failed."))

    return {
        "status": "success",
        "notification_id": notification_id,
        "state": "USER_ACCEPTED",
        "result": result,
    }


@app.post("/api/sms/inbound")
@app.post("/api/sms/webhook")
@app.post("/api/smsgate/inbound")
@app.post("/api/v1/sms/inbound")
@app.post("/api/sms/accept")
async def inbound_sms_webhook_endpoint(
    req: Optional[InboundSmsWebhookRequest] = None,
    from_param: Optional[str] = None,
    phone_number: Optional[str] = None,
    message: Optional[str] = None,
    text: Optional[str] = None,
):
    """
    Inbound SMS Webhook endpoint for SMSGate Local Server / Android SMS Gateways.
    Receives incoming SMS messages, strictly parses 'ACCEPT <COMMAND_ID>',
    verifies sender authorization, and triggers authoritative mission acceptance.
    """
    raw_message = None
    raw_sender = None

    if req:
        # Check standard top-level fields
        raw_message = req.message or req.text or req.message_body
        raw_sender = req.phoneNumber or req.phone_number or req.sender
        # Check nested SMSGate payload if present
        if not raw_message and req.payload and isinstance(req.payload, dict):
            raw_message = req.payload.get("message") or req.payload.get("text") or req.payload.get("message_body")
            raw_sender = req.payload.get("phoneNumber") or req.payload.get("phone_number") or req.payload.get("sender") or req.payload.get("from")

    # Fallback to direct query parameters
    if not raw_message:
        raw_message = message or text
    if not raw_sender:
        raw_sender = phone_number or from_param

    if not raw_message:
        raise HTTPException(
            status_code=400,
            detail="Missing SMS message text. Provide 'message', 'text', or 'payload.message'."
        )

    # 1. Parse SMS Command strictly
    try:
        from notification_dispatch import parse_sms_acceptance_command
    except ImportError:
        from backend.notification_dispatch import parse_sms_acceptance_command

    cmd_id = parse_sms_acceptance_command(raw_message)
    if not cmd_id:
        logger.info(f"[SMS_INBOUND] Rejected non-acceptance SMS message: '{raw_message[:60]}'")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid acceptance format. To accept a rescue mission, reply: ACCEPT <COMMAND_ID>"
        )

    # 2. Invoke Unified Acceptance Service
    result = accept_rescue_assignment(
        command_or_assignment_id=cmd_id,
        sender_phone=raw_sender,
        acceptance_source="SMS",
    )

    if not result.get("success"):
        status_code = 403 if result.get("status") == "UNAUTHORIZED_SENDER" else 400
        if result.get("status") == "NOT_FOUND":
            status_code = 404
        raise HTTPException(status_code=status_code, detail=result.get("error", "Acceptance failed"))

    return {
        "status": "success",
        "result": result,
    }


@app.post("/api/sms/inbox/poll")
@app.post("/api/smsgate/inbox/poll")
async def manual_smsgate_inbox_poll_endpoint():
    """Triggers an immediate on-demand poll of SMSGate /inbox."""
    try:
        from notification_dispatch import poll_smsgate_inbound_messages
    except ImportError:
        from backend.notification_dispatch import poll_smsgate_inbound_messages
    results = await poll_smsgate_inbound_messages()
    return {
        "status": "success",
        "processed_count": len(results),
        "results": results,
    }


@app.get("/api/wearable/commands/current_state")
@app.get("/api/wearable/commands/{command_id}/live_state")
def get_wearable_command_live_state_endpoint(
    command_id: Optional[str] = None,
    team_id: Optional[str] = None,
    member_id: Optional[str] = None,
):
    """Returns real-time backend state for active rescue command and hardware connection."""
    if command_id:
        gw_cmd = global_wearable_gateway.active_commands.get(command_id)
        db_cmd = db.get_rescue_command(command_id)
        if gw_cmd and db_cmd:
            cmd = {**db_cmd, **gw_cmd}
        else:
            cmd = gw_cmd or db_cmd
    else:
        cmd = None
        if member_id:
            cmd = db.get_active_command_for_member(member_id)
        if not cmd:
            cmd = global_wearable_gateway.get_active_command_for_team_or_device(team_id=team_id, member_id=member_id)
        if not cmd and (team_id or member_id):
            db_cmds = db.list_rescue_commands(team_id=team_id, member_id=member_id, limit=1)
            cmd = db_cmds[0] if db_cmds else None

    conn_state = global_wearable_gateway.wave_call_plus_adapter.connection_state
    is_connected = conn_state == "CONNECTED"
    last_seen = global_wearable_gateway.wave_call_plus_adapter.last_seen

    if not cmd:
        return {
            "status": "success",
            "has_command": False,
            "command_id": None,
            "command": None,
            "team_id": team_id,
            "member_id": member_id,
            "watch_device_id": "DEV-WEARABLE-CALLPLUS",
            "device_name": "CALLPLUS_7F1B",
            "watch_connected": is_connected,
            "gatt_ready": is_connected,
            "command_sent": False,
            "watch_acknowledged": False,
            "ack_timestamp": None,
            "command_status": "STANDBY",
            "watch_delivery_status": "WATCH_DELIVERY_UNCONFIRMED",
            "last_seen": last_seen,
            "error": None,
        }

    status = cmd.get("status", "ASSIGNED")
    watch_del_st = cmd.get("watch_delivery_status", "WATCH_DELIVERY_UNCONFIRMED")
    is_bridge_delivered = status in ("SENT_TO_BRIDGE", "BRIDGE_RECEIVED", "COMMAND_SENT", "WAITING_FOR_WATCH_ACK", "PHONE_NOTIFICATION_POSTED", "WATCH_ACKNOWLEDGED", "USER_ACCEPTED", "ACCEPTED") or cmd.get("bridge_sent_at") is not None
    is_phone_notif = status == "PHONE_NOTIFICATION_POSTED" or cmd.get("phone_notification_posted_at") is not None
    is_sent = status in ("COMMAND_SENT", "WAITING_FOR_WATCH_ACK", "WATCH_ACKNOWLEDGED", "ACKNOWLEDGED", "DELIVERED", "COMPLETED", "RESCUED", "ARRIVED") or watch_del_st == "COMMAND_SENT"
    is_acked = status in ("WATCH_ACKNOWLEDGED", "ACKNOWLEDGED") or watch_del_st == "WATCH_ACKNOWLEDGED"
    is_rescuer_confirmed = bool(cmd.get("rescuer_confirmed") or status in ("USER_ACCEPTED", "ACCEPTED") or cmd.get("ack_source") == "RESCUER_CONFIRMATION")
    is_hardware_acked = bool(cmd.get("hardware_ack_received") or cmd.get("ack_source") in ("PHYSICAL_WATCH", "HARDWARE_ACK") or (is_acked and cmd.get("ack_source") != "RESCUER_CONFIRMATION"))

    return {
        "status": "success",
        "has_command": True,
        "command_id": cmd.get("command_id"),
        "command": cmd.get("command_type", "GO"),
        "team_id": cmd.get("team_id"),
        "member_id": cmd.get("member_id"),
        "victim_id": cmd.get("victim_id"),
        "watch_device_id": cmd.get("target_device_id", "DEV-WEARABLE-CALLPLUS"),
        "device_name": "CALLPLUS_7F1B",
        "watch_connected": is_connected,
        "gatt_ready": is_connected,
        "bridge_delivered": is_bridge_delivered,
        "command_sent": is_sent,
        "phone_notification_posted": is_phone_notif,
        "watch_acknowledged": is_acked,
        "rescuer_confirmed": is_rescuer_confirmed,
        "rescuer_confirmation_status": "RESCUER_CONFIRMED" if is_rescuer_confirmed else "PENDING",
        "rescuer_confirmed_at": cmd.get("rescuer_confirmed_at") or (cmd.get("acknowledged_at") if cmd.get("ack_source") == "RESCUER_CONFIRMATION" else None),
        "hardware_ack_received": is_hardware_acked,
        "ack_source": cmd.get("ack_source"),
        "bridge_sent_at": cmd.get("bridge_sent_at"),
        "phone_notification_posted_at": cmd.get("phone_notification_posted_at"),
        "delivered_at": cmd.get("delivered_at"),
        "ack_timestamp": cmd.get("acknowledged_at"),
        "command_status": status,
        "watch_delivery_status": watch_del_st,
        "last_seen": last_seen,
        "error": cmd.get("delivery_error"),
    }


@app.get("/api/rescue/commands/{command_id}")
def get_rescue_command_endpoint(command_id: str):
    """Retrieve detailed lifecycle status of a specific rescue command."""
    cmd = db.get_rescue_command(command_id)
    if not cmd:
        cmd = global_wearable_gateway.active_commands.get(command_id)
    if not cmd:
        raise HTTPException(status_code=404, detail=f"Rescue command '{command_id}' not found")

    return {
        "status": "success",
        "command_id": cmd.get("command_id", command_id),
        "command_type": cmd.get("command_type", "GO"),
        "team_id": cmd.get("team_id"),
        "member_id": cmd.get("member_id"),
        "victim_id": cmd.get("victim_id"),
        "target_id": cmd.get("victim_id"),
        "watch_id": cmd.get("target_device_id", "DEV-WEARABLE-CALLPLUS"),
        "target_device_id": cmd.get("target_device_id", "DEV-WEARABLE-CALLPLUS"),
        "status": cmd.get("status", "ASSIGNED"),
        "bridge_status": cmd.get("phone_bridge_status", "SENT_TO_BRIDGE" if cmd.get("status") in ["SENT_TO_BRIDGE", "PHONE_NOTIFICATION_POSTED", "DELIVERED"] else "PENDING"),
        "watch_status": cmd.get("watch_delivery_status", "WATCH_DELIVERY_UNCONFIRMED"),
        "created_at": cmd.get("created_at"),
        "updated_at": cmd.get("updated_at") or cmd.get("created_at"),
        "phone_notification_posted_at": cmd.get("phone_notification_posted_at"),
        "delivered_at": cmd.get("delivered_at"),
        "acknowledged_at": cmd.get("acknowledged_at"),
    }


@app.post("/api/wearable/bridge/heartbeat")
@app.post("/api/bridge/sync")
@app.post("/api/bridge/heartbeat")
@app.post("/api/wearable/heartbeat")
@app.post("/api/heartbeat")
@app.post("/heartbeat")
def bridge_heartbeat_endpoint(req: BridgeSyncRequest):
    logger.info(f"[BRIDGE_RECEIVED] session={req.session_id} team={req.team_id} member={req.member_id or 'ALL'} bluetooth={req.bluetooth_state}")
    if req.watch_device_id and "T800" in req.watch_device_id.upper():
        raise HTTPException(
            status_code=400,
            detail="Device T800Ultra is unsupported and obsolete. System uses Wave Call Plus (CALLPLUS_7F1B) only.",
        )
    if req.watch_mac and "70:20:33" in req.watch_mac:
        raise HTTPException(
            status_code=400,
            detail="MAC address belongs to obsolete T800Ultra. System uses Wave Call Plus (CB:4E:FD:EE:7F:1B) only.",
        )

    # Stage 7 Validation: Strict coordinate, numeric, and timestamp checks
    if req.latitude is not None or req.longitude is not None:
        if not validate_gps_coordinates(req.latitude, req.longitude):
            raise HTTPException(
                status_code=400,
                detail="INVALID_GPS_COORDINATES: Latitude must be in [-90, 90] and longitude in [-180, 180], no NaN or Inf allowed.",
            )

    if req.accuracy_m is not None:
        try:
            acc_f = float(req.accuracy_m)
            if math.isnan(acc_f) or math.isinf(acc_f) or acc_f < 0:
                raise HTTPException(status_code=400, detail="INVALID_GPS_ACCURACY: Accuracy must be non-negative and finite.")
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="INVALID_GPS_ACCURACY: Accuracy must be a numeric value.")

    if req.speed_mps is not None:
        try:
            spd_f = float(req.speed_mps)
            if math.isnan(spd_f) or math.isinf(spd_f) or spd_f < 0:
                raise HTTPException(status_code=400, detail="INVALID_GPS_SPEED: Speed must be non-negative and finite.")
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="INVALID_GPS_SPEED: Speed must be a numeric value.")

    if req.heading_deg is not None:
        try:
            hdg_f = float(req.heading_deg)
            if math.isnan(hdg_f) or math.isinf(hdg_f) or hdg_f < 0 or hdg_f > 360:
                raise HTTPException(status_code=400, detail="INVALID_GPS_HEADING: Heading must be within 0-360 degrees.")
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="INVALID_GPS_HEADING: Heading must be a numeric value.")

    now_utc = datetime.now(timezone.utc)
    incoming_dt = None
    if req.timestamp:
        try:
            incoming_dt = datetime.fromisoformat(req.timestamp.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="INVALID_TIMESTAMP: Malformed ISO 8601 timestamp.")
        if (incoming_dt - now_utc).total_seconds() > 3600:
            raise HTTPException(status_code=400, detail="INVALID_TIMESTAMP: Future timestamp exceeds allowed tolerance.")
    else:
        incoming_dt = now_utc

    # Stage 7 Telemetry Ordering & Duplicate Protection
    is_duplicate = False
    is_out_of_order = False
    if req.member_id == "ALPHA-M001":
        last_gps_dt = ALPHA_M001_LATEST_GPS.get("latest_gps_dt")
        if last_gps_dt is not None and incoming_dt is not None:
            if incoming_dt < last_gps_dt:
                is_out_of_order = True
                logger.info(f"[TELEMETRY_ORDERING] Out-of-order GPS sample: incoming {incoming_dt} < latest {last_gps_dt}. Ignoring update.")
            elif incoming_dt == last_gps_dt:
                is_duplicate = True
                logger.info(f"[TELEMETRY_ORDERING] Duplicate GPS sample timestamp {incoming_dt}. Ignoring duplicate.")

    watch_dev_id = "DEV-WEARABLE-CALLPLUS"

    # Bind member to device if member_id is provided
    if req.member_id:
        global_wearable_gateway.bind_member_to_device(req.member_id, watch_dev_id)

    # Sync real BLE connection state
    conn_mgr = global_wearable_gateway.wave_call_plus_adapter.connection_manager
    if req.watch_connected:
        conn_mgr.connect(watch_dev_id, mac_address=req.watch_mac or "CB:4E:FD:EE:7F:1B")
        db.update_wearable_device_status(watch_dev_id, status="CONNECTED")
    else:
        conn_mgr.disconnect(watch_dev_id)
        db.update_wearable_device_status(watch_dev_id, status="DISCONNECTED")

    session = db.register_or_update_bridge_session(
        session_id=req.session_id,
        team_id=req.team_id,
        device_name=req.device_name or "Android Companion Bridge",
        member_id=req.member_id,
        bluetooth_state=req.bluetooth_state or "ENABLED",
        watch_connected=bool(req.watch_connected),
        watch_device_id=watch_dev_id,
        watch_mac=req.watch_mac or "CB:4E:FD:EE:7F:1B",
        watch_model=req.watch_model or "Wave Call Plus",
        gps_available=bool(req.gps_available),
        location_source=req.location_source or "PHONE_GPS",
        latitude=req.latitude,
        longitude=req.longitude,
        altitude_m=req.altitude_m,
        accuracy_m=req.accuracy_m,
        speed_mps=req.speed_mps,
        heading_deg=req.heading_deg,
        gps_timestamp=req.timestamp,
        status=req.status or "ONLINE",
        notes=req.notes,
    )

    if req.latitude is not None and req.longitude is not None and not is_out_of_order and not is_duplicate:
        db.log_wearable_telemetry(
            device_id=watch_dev_id,
            latitude=req.latitude,
            longitude=req.longitude,
            altitude_m=req.altitude_m,
            accuracy_m=req.accuracy_m,
            speed_mps=req.speed_mps,
            heading_deg=req.heading_deg,
            team_id=req.team_id,
            session_id=req.session_id,
        )

    # Ingest Real GPS for Alpha Member 1 into authoritative cache and in-memory operations
    if req.member_id == "ALPHA-M001":
        effective_status = req.gps_status or ("TRACKING" if req.latitude is not None and req.longitude is not None and req.gps_available else "GPS_UNAVAILABLE")
        if incoming_dt:
            age = (now_utc - incoming_dt).total_seconds()
            if age > GPS_STALE_THRESHOLD_SECONDS:
                effective_status = "STALE"

        if effective_status == "STALE":
            ALPHA_M001_NAV_STATE["navigation_status"] = "STALE"
            ALPHA_M001_LATEST_GPS["navigation_status"] = "STALE"
            ALPHA_M001_LATEST_GPS["gps_status"] = "STALE"
        elif effective_status == "GPS_UNAVAILABLE" or not req.gps_available:
            ALPHA_M001_NAV_STATE["navigation_status"] = "GPS_UNAVAILABLE"
            ALPHA_M001_LATEST_GPS["navigation_status"] = "GPS_UNAVAILABLE"
            ALPHA_M001_LATEST_GPS["gps_status"] = effective_status

        if not is_out_of_order and not is_duplicate:
            if incoming_dt is not None:
                ALPHA_M001_LATEST_GPS["latest_gps_dt"] = incoming_dt

            if req.latitude is not None and req.longitude is not None and req.gps_available and effective_status != "GPS_UNAVAILABLE":
                ALPHA_M001_LATEST_GPS.update({
                    "latitude": req.latitude,
                    "longitude": req.longitude,
                    "altitude_m": req.altitude_m,
                    "accuracy_m": req.accuracy_m,
                    "speed_mps": req.speed_mps,
                    "heading_deg": req.heading_deg,
                    "gps_timestamp": req.timestamp or now_utc.isoformat(),
                    "gps_status": effective_status,
                    "location_source": req.location_source or "PHONE_GPS",
                })
                if effective_status == "STALE":
                    ALPHA_M001_LATEST_GPS["navigation_status"] = "STALE"
            elif req.gps_status:
                ALPHA_M001_LATEST_GPS["gps_status"] = req.gps_status
                if req.gps_status in ("STALE", "GPS_UNAVAILABLE"):
                    ALPHA_M001_LATEST_GPS["navigation_status"] = req.gps_status

            for op in operations.values():
                if not op or not hasattr(op, "team_members"):
                    continue
                for t_id, members in op.team_members.items():
                    if t_id in (req.team_id, "ALPHA"):
                        for m in members:
                            if m.member_id == req.member_id:
                                if req.latitude is not None and req.longitude is not None and req.gps_available and effective_status != "GPS_UNAVAILABLE":
                                    m.location = GPSCoordinate(
                                        latitude=req.latitude,
                                        longitude=req.longitude,
                                        altitude_m=req.altitude_m if req.altitude_m is not None else m.location.altitude_m,
                                    )
                                    m.location_source = req.location_source or "PHONE_GPS"
                                    m.accuracy_m = req.accuracy_m
                                    m.speed_mps = req.speed_mps
                                    m.heading_deg = req.heading_deg
                                    m.gps_timestamp = req.timestamp or now_utc.isoformat()
                                    m.last_updated = now_utc.isoformat()
                                    m.gps_status = effective_status
                                    if effective_status == "STALE":
                                        m.navigation_status = "STALE"
                                elif req.gps_status:
                                    m.gps_status = req.gps_status
                                    if req.gps_status in ("STALE", "GPS_UNAVAILABLE"):
                                        m.navigation_status = req.gps_status

    active_cmd = None
    if req.member_id:
        active_cmd = db.get_active_command_for_member(req.member_id)
    if not active_cmd:
        active_cmd = global_wearable_gateway.get_active_command_for_team_or_device(
            team_id=req.team_id, device_id=watch_dev_id if not req.member_id else None, member_id=req.member_id
        )
    if not active_cmd and req.member_id:
        db_cmds = db.list_rescue_commands(member_id=req.member_id, limit=1)
        if db_cmds:
            active_cmd = db_cmds[0]

    target_coord = None
    victim_id = None

    # Stage 4 & 6 Navigation & Guidance Evaluation for Alpha Member 1
    # ONLY evaluate if fresh sample, GPS tracking active, and coordinates present
    if (
        req.member_id == "ALPHA-M001"
        and not is_out_of_order
        and not is_duplicate
        and req.latitude is not None
        and req.longitude is not None
        and req.gps_available
        and effective_status == "TRACKING"
    ):
        assigned_member = None
        assigned_op = None
        assigned_victim = None
        for op in operations.values():
            if not op or not hasattr(op, "team_members"):
                continue
            for t_id, members in op.team_members.items():
                if t_id in (req.team_id, "ALPHA"):
                    for m in members:
                        if m.member_id == req.member_id:
                            assigned_member = m
                            assigned_op = op
                            if active_cmd:
                                m.active_command_id = active_cmd.get("command_id")
                            if m.assigned_victim_id and op.config and op.config.victims:
                                assigned_victim = next((v for v in op.config.victims if v.victim_id == m.assigned_victim_id), None)
                            break

        target_coord = None
        victim_id = "Survivor"
        if assigned_victim and assigned_victim.location:
            target_coord = assigned_victim.location
            victim_id = assigned_victim.victim_id
        elif active_cmd and active_cmd.get("destination_latitude") is not None and active_cmd.get("destination_longitude") is not None:
            d_lat = active_cmd.get("destination_latitude")
            d_lon = active_cmd.get("destination_longitude")
            if d_lat != 0.0 or d_lon != 0.0:
                target_coord = GPSCoordinate(latitude=d_lat, longitude=d_lon)
                victim_id = active_cmd.get("victim_id") or "Survivor"

        # Check if mission is already COMPLETED
        is_already_completed = bool(active_cmd and active_cmd.get("status") in ("COMPLETED", "RESCUED", "CANCELLED"))
        if is_already_completed:
            nav_status = "COMPLETED"
            ALPHA_M001_NAV_STATE.update({
                "navigation_status": "COMPLETED",
                "distance_trend": "STABLE",
                "direction_guidance": "Mission completed",
                "consecutive_wrong_samples": 0,
            })
            ALPHA_M001_LATEST_GPS.update({
                "navigation_status": "COMPLETED",
                "distance_trend": "STABLE",
                "direction_guidance": "Mission completed",
            })
            if assigned_member:
                assigned_member.status = MemberStatus.HOLD
                assigned_member.navigation_status = "COMPLETED"
                assigned_member.direction_guidance = "Mission completed"
        else:
            rescuer_coord = GPSCoordinate(latitude=req.latitude, longitude=req.longitude, altitude_m=req.altitude_m)
            movement_heading = None
            if req.heading_deg is not None and 0.0 <= req.heading_deg <= 360.0:
                movement_heading = req.heading_deg
            elif ALPHA_M001_NAV_STATE.get("previous_coord") is not None:
                prev = ALPHA_M001_NAV_STATE["previous_coord"]
                disp_m = haversine_distance_m(prev, rescuer_coord)
                if disp_m >= 1.5:
                    movement_heading = _bearing_deg(prev, rescuer_coord)

            ALPHA_M001_NAV_STATE["previous_coord"] = rescuer_coord
            ALPHA_M001_NAV_STATE["previous_coord_time"] = time.time()

            if movement_heading is not None:
                ALPHA_M001_NAV_STATE["heading_deg"] = round(movement_heading, 1)
                ALPHA_M001_LATEST_GPS["heading_deg"] = round(movement_heading, 1)
                if assigned_member:
                    assigned_member.heading_deg = round(movement_heading, 1)

            if target_coord is not None:
                dist_m = haversine_distance_m(rescuer_coord, target_coord)
                target_bearing = _bearing_deg(rescuer_coord, target_coord)

                # 1. Arrival Detection (<= 15.0 meters) and Idempotency
                is_already_arrived = bool(ALPHA_M001_NAV_STATE.get("is_arrived")) or (ALPHA_M001_NAV_STATE.get("navigation_status") == "ARRIVED") or (active_cmd and active_cmd.get("status") == "ARRIVED")
                if is_already_arrived or dist_m <= GPS_ARRIVAL_DISTANCE_METERS:
                    now_iso = ALPHA_M001_NAV_STATE.get("arrived_at") or datetime.now(timezone.utc).isoformat()
                    ALPHA_M001_NAV_STATE.update({
                        "navigation_status": "ARRIVED",
                        "target_bearing_deg": round(target_bearing, 1),
                        "heading_difference_deg": None,
                        "direction_delta_deg": None,
                        "distance_to_target_m": round(dist_m, 1),
                        "distance_trend": "STABLE",
                        "previous_distance_m": dist_m,
                        "direction_guidance": "Arrived at survivor location",
                        "arrived_at": now_iso,
                        "consecutive_wrong_samples": 0,
                        "is_arrived": True,
                    })
                    ALPHA_M001_LATEST_GPS.update({
                        "navigation_status": "ARRIVED",
                        "target_bearing_deg": round(target_bearing, 1),
                        "heading_difference_deg": None,
                        "direction_delta_deg": None,
                        "distance_to_target_m": round(dist_m, 1),
                        "distance_trend": "STABLE",
                        "direction_guidance": "Arrived at survivor location",
                        "arrived_at": now_iso,
                        "is_arrived": True,
                    })
                    if assigned_member:
                        assigned_member.status = MemberStatus.ARRIVED
                        assigned_member.navigation_status = "ARRIVED"
                        assigned_member.target_bearing_deg = round(target_bearing, 1)
                        assigned_member.heading_difference_deg = None
                        assigned_member.direction_delta_deg = None
                        assigned_member.distance_to_target_m = round(dist_m, 1)
                        assigned_member.distance_trend = "STABLE"
                        assigned_member.direction_guidance = "Arrived at survivor location"
                        assigned_member.arrived_at = now_iso
                        assigned_member.last_updated = now_iso
                    if active_cmd:
                        active_cmd["status"] = "ARRIVED"
                        cmd_id = active_cmd.get("command_id")
                        db.update_rescue_command_status(cmd_id, status="ARRIVED")
                        db.update_rescue_command_navigation(
                            cmd_id,
                            navigation_status="ARRIVED",
                            target_bearing_deg=round(target_bearing, 1),
                            distance_to_target_m=round(dist_m, 1),
                            distance_trend="STABLE",
                            direction_guidance="Arrived at survivor location",
                            arrived_at=now_iso,
                        )
                    if not is_already_arrived:
                        if assigned_op and assigned_op.session_id:
                            db.log_rescue_status_event(
                                session_id=assigned_op.session_id,
                                event_type="member_arrived",
                                team_id=req.team_id or "ALPHA",
                                victim_id=victim_id,
                                notes=f"Alpha Member 1 reached {victim_id} via Real Phone GPS.",
                            )
                else:
                    # 2. En Route Navigation Evaluation
                    prev_dist = ALPHA_M001_NAV_STATE.get("previous_distance_m")
                    distance_trend = calculate_distance_trend(dist_m, prev_dist, DISTANCE_TREND_HYSTERESIS_METERS)
                    ALPHA_M001_NAV_STATE["previous_distance_m"] = dist_m

                    speed = req.speed_mps if req.speed_mps is not None else 0.0
                    acc = req.accuracy_m if req.accuracy_m is not None else 10.0
                    delta = None

                    if speed < GPS_MIN_SPEED_FOR_DIRECTION_MPS:
                        # Stationary: speed is below the direction-analysis threshold (0.5 m/s)
                        nav_status = "STATIONARY"
                        guidance_str = "Stationary - head toward survivor"
                        delta = None
                    elif movement_heading is not None and acc <= 150.0:
                        delta = calculate_angular_difference(movement_heading, target_bearing)
                        if delta > DIRECTION_TOLERANCE_DEGREES:
                            ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] = ALPHA_M001_NAV_STATE.get("consecutive_wrong_samples", 0) + 1
                            if ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] >= DIRECTION_CONFIRMATION_SAMPLES:
                                nav_status = "WRONG_DIRECTION"
                                guidance_str, _ = calculate_direction_guidance(movement_heading, target_bearing)
                                now_time = time.time()
                                if now_time - ALPHA_M001_NAV_STATE.get("last_direction_alert_time", 0.0) >= DIRECTION_ALERT_COOLDOWN_SECONDS:
                                    cmd_id = active_cmd.get("command_id") if active_cmd else f"CMD-{req.member_id}"
                                    send_direction_guidance_sms(
                                        member_id=req.member_id,
                                        team_id=req.team_id or "ALPHA",
                                        command_id=cmd_id,
                                        victim_id=victim_id,
                                        heading_deg=movement_heading,
                                        target_bearing_deg=target_bearing,
                                        guidance=guidance_str,
                                        distance_m=dist_m,
                                    )
                                    ALPHA_M001_NAV_STATE["last_direction_alert_time"] = now_time
                                    now_iso = datetime.now(timezone.utc).isoformat()
                                    if active_cmd:
                                        db.update_rescue_command_navigation(
                                            active_cmd["command_id"],
                                            navigation_status="WRONG_DIRECTION",
                                            target_bearing_deg=round(target_bearing, 1),
                                            direction_delta_deg=round(delta, 1),
                                            heading_difference_deg=round(delta, 1),
                                            distance_to_target_m=round(dist_m, 1),
                                            distance_trend=distance_trend,
                                            direction_guidance=guidance_str,
                                            direction_alert_last_sent_at=now_iso,
                                        )
                            else:
                                # Not yet confirmed (samples 1 or 2): remain ON_TRACK, no wrong-direction alert
                                nav_status = "ON_TRACK"
                                guidance_str, _ = calculate_direction_guidance(movement_heading, target_bearing)
                        else:
                            ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] = 0
                            nav_status = "ON_TRACK"
                            guidance_str = "Continue straight toward survivor"
                            if active_cmd:
                                db.update_rescue_command_navigation(
                                    active_cmd["command_id"],
                                    navigation_status="ON_TRACK",
                                    target_bearing_deg=round(target_bearing, 1),
                                    direction_delta_deg=round(delta, 1),
                                    heading_difference_deg=round(delta, 1),
                                    distance_to_target_m=round(dist_m, 1),
                                    distance_trend=distance_trend,
                                    direction_guidance=guidance_str,
                                )
                    else:
                        nav_status = ALPHA_M001_NAV_STATE.get("navigation_status") or "ON_TRACK"
                        guidance_str = ALPHA_M001_NAV_STATE.get("direction_guidance") or "Continue straight toward survivor"
                        delta = ALPHA_M001_NAV_STATE.get("heading_difference_deg") or ALPHA_M001_NAV_STATE.get("direction_delta_deg")

                    heading_diff_deg = round(delta, 1) if delta is not None else None
                    ALPHA_M001_NAV_STATE.update({
                        "navigation_status": nav_status,
                        "target_bearing_deg": round(target_bearing, 1),
                        "heading_difference_deg": heading_diff_deg,
                        "direction_delta_deg": heading_diff_deg,
                        "distance_to_target_m": round(dist_m, 1),
                        "distance_trend": distance_trend,
                        "direction_guidance": guidance_str,
                    })
                    ALPHA_M001_LATEST_GPS.update({
                        "navigation_status": nav_status,
                        "target_bearing_deg": round(target_bearing, 1),
                        "heading_difference_deg": heading_diff_deg,
                        "direction_delta_deg": heading_diff_deg,
                        "distance_to_target_m": round(dist_m, 1),
                        "distance_trend": distance_trend,
                        "direction_guidance": guidance_str,
                    })
                    if assigned_member:
                        assigned_member.navigation_status = nav_status
                        assigned_member.target_bearing_deg = round(target_bearing, 1)
                        assigned_member.heading_difference_deg = heading_diff_deg
                        assigned_member.direction_delta_deg = heading_diff_deg
                        assigned_member.distance_to_target_m = round(dist_m, 1)
                        assigned_member.distance_trend = distance_trend
                        assigned_member.direction_guidance = guidance_str

    if active_cmd:
        if active_cmd.get("status") in ["ASSIGNED", "PENDING"]:
            active_cmd["status"] = "SENT_TO_BRIDGE"
            active_cmd["phone_bridge_status"] = "SENT_TO_BRIDGE"
            active_cmd["watch_delivery_status"] = "WATCH_DELIVERY_UNCONFIRMED"
            db.update_rescue_command_status(
                active_cmd["command_id"],
                status="SENT_TO_BRIDGE",
                watch_delivery_status="WATCH_DELIVERY_UNCONFIRMED",
            )
            global_wearable_gateway.update_command_status(active_cmd["command_id"], "SENT_TO_BRIDGE")

        if "notification_payload" not in active_cmd:
            active_cmd["notification_payload"] = {
                "title": "🚨 RIDGEWATCH — GO",
                "body": "Rescue assignment received. Proceed to the assigned rescue operation.",
                "priority": active_cmd.get("priority", "HIGH"),
                "command_type": "GO",
                "command_id": active_cmd.get("command_id"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    pending_commands = [active_cmd] if active_cmd else db.list_rescue_commands(
        team_id=req.team_id, member_id=req.member_id, status="ASSIGNED", limit=5
    )

    active_job = None
    if req.member_id:
        active_job = db.get_active_job_assignment_for_member(req.member_id)
        if active_job:
            if "title" not in active_job or not active_job["title"]:
                active_job["title"] = active_job.get("job_name") or active_job.get("job_id") or "Work Assignment"
            if "sector" not in active_job or not active_job["sector"]:
                active_job["sector"] = active_job.get("job_location") or active_job.get("location") or ""
            if "priority" not in active_job or not active_job["priority"]:
                active_job["priority"] = active_job.get("job_priority") or "HIGH"
            if "description" not in active_job or not active_job["description"]:
                active_job["description"] = active_job.get("job_description") or ""
            if "job_type" not in active_job or not active_job["job_type"]:
                active_job["job_type"] = "GENERAL"

    return {
        "status": "success",
        "session": session,
        "active_command": active_cmd,
        "active_job_assignment": active_job,
        "pending_commands": pending_commands,
        "navigation": {
            "navigation_status": ALPHA_M001_NAV_STATE.get("navigation_status"),
            "target_bearing_deg": ALPHA_M001_NAV_STATE.get("target_bearing_deg"),
            "heading_difference_deg": ALPHA_M001_NAV_STATE.get("heading_difference_deg"),
            "direction_delta_deg": ALPHA_M001_NAV_STATE.get("direction_delta_deg"),
            "distance_to_target_m": ALPHA_M001_NAV_STATE.get("distance_to_target_m"),
            "distance_trend": ALPHA_M001_NAV_STATE.get("distance_trend"),
            "direction_guidance": ALPHA_M001_NAV_STATE.get("direction_guidance"),
            "arrived_at": ALPHA_M001_NAV_STATE.get("arrived_at"),
            "is_arrived": ALPHA_M001_NAV_STATE.get("navigation_status") == "ARRIVED" or bool(ALPHA_M001_NAV_STATE.get("is_arrived")),
            "victim_id": victim_id if target_coord is not None else None,
        } if req.member_id == "ALPHA-M001" else None,
    }


@app.get("/api/wearable/bridge/heartbeat")
@app.get("/api/bridge/sync")
@app.get("/api/bridge/heartbeat")
@app.get("/api/wearable/heartbeat")
@app.get("/api/heartbeat")
@app.get("/heartbeat")
def bridge_heartbeat_get_endpoint(
    team_id: Optional[str] = None,
    member_id: Optional[str] = None,
    session_id: Optional[str] = None,
):
    active_cmd = global_wearable_gateway.get_active_command_for_team_or_device(
        team_id=team_id, member_id=member_id
    )
    return {
        "status": "success",
        "message": "Heartbeat active",
        "active_command": active_cmd,
    }


@app.get("/api/wearable/bridge/status")
@app.get("/api/bridge/status")
@app.get("/api/bridge/sessions")
def get_bridge_status_endpoint(team_id: Optional[str] = None):
    sessions = db.list_bridge_sessions(team_id=team_id)
    online_count = sum(1 for s in sessions if s.get("status") == "ONLINE")
    watches_connected = sum(1 for s in sessions if s.get("watch_connected"))
    return {
        "status": "success",
        "total_sessions": len(sessions),
        "online_bridges": online_count,
        "watches_connected": watches_connected,
        "sessions": sessions,
    }


@app.post("/api/wearable/telemetry")
def log_wearable_telemetry_endpoint(req: WearableTelemetryRequest):
    # Phase 5 & 6: Strict Device & Range Validation
    dev_upper = req.device_id.upper()
    if "T800" in dev_upper or (dev_upper not in ("DEV-WEARABLE-CALLPLUS", "CALLPLUS_7F1B", "CB:4E:FD:EE:7F:1B")):
        raise HTTPException(status_code=400, detail=f"TELEMETRY_REJECTED_DEVICE_MISMATCH: Unauthorized wearable device '{req.device_id}'.")

    if req.battery_pct is not None and (req.battery_pct < 0 or req.battery_pct > 100):
        raise HTTPException(status_code=400, detail=f"TELEMETRY_REJECTED_OUT_OF_RANGE: Battery percentage {req.battery_pct}% is out of valid range (0-100%).")

    if req.heart_rate_bpm is not None and (req.heart_rate_bpm < 30 or req.heart_rate_bpm > 240):
        raise HTTPException(status_code=400, detail=f"TELEMETRY_REJECTED_OUT_OF_RANGE: Heart rate {req.heart_rate_bpm} bpm is out of valid range (30-240 bpm).")

    telemetry_id = db.log_wearable_telemetry(
        device_id=req.device_id,
        latitude=req.latitude,
        longitude=req.longitude,
        altitude_m=req.altitude_m,
        accuracy_m=req.accuracy_m,
        speed_mps=req.speed_mps,
        battery_pct=req.battery_pct,
        heart_rate_bpm=req.heart_rate_bpm,
        step_count=req.step_count,
        team_id=req.team_id,
        session_id=req.session_id,
    )
    return {
        "status": "success",
        "telemetry_id": telemetry_id,
        "device_id": req.device_id,
        "battery_pct": req.battery_pct,
        "heart_rate_bpm": req.heart_rate_bpm,
    }


@app.get("/api/wearable/telemetry/latest/{team_id}")
def get_latest_team_telemetry_endpoint(team_id: str):
    latest = db.get_latest_team_wearable_location(team_id)
    return {"status": "success", "team_id": team_id, "location": latest}


# --------------------------------------------------------------------------- #
# Feature #15: Tactical Road Network & Dynamic Detour Routing Endpoints
# --------------------------------------------------------------------------- #

@app.get("/api/dispatch/route/{command_id}")
@app.get("/dispatch/route/{command_id}")
def get_dispatch_route_endpoint(
    command_id: str,
    tilt_deg: Optional[float] = None,
    water_level_cm: Optional[float] = None,
    water_flow_mps: Optional[float] = None,
    landslide_risk_score: Optional[float] = None,
    vibration_mm_s: Optional[float] = None,
    gas_ppm: Optional[float] = None,
    smoke_pct: Optional[float] = None,
    debris_present: Optional[bool] = None,
):
    """
    Read-only dynamic hazard-aware detour route calculation for an active rescue command.
    Consumes live ALPHA_M001 real GPS and active sensor hazard telemetry without mutating state.
    """
    cmd = db.get_rescue_command(command_id)
    if not cmd:
        # Check active gateway commands
        cmd = getattr(global_wearable_gateway, "active_commands", {}).get(command_id)

    if not cmd:
        raise HTTPException(status_code=404, detail=f"Rescue command '{command_id}' not found.")

    team_id = cmd.get("team_id") or "ALPHA"
    member_id = cmd.get("member_id") or "ALPHA-M001"
    victim_id = cmd.get("victim_id")

    # 1. Determine Start Coordinate (Live Rescuer Position)
    start_lat = None
    start_lon = None
    start_alt = 3950.0

    if (
        (member_id == "ALPHA-M001" or team_id in ("ALPHA", "RESCUE-1"))
        and ALPHA_M001_LATEST_GPS.get("latitude") is not None
        and ALPHA_M001_LATEST_GPS.get("longitude") is not None
    ):
        start_lat = ALPHA_M001_LATEST_GPS["latitude"]
        start_lon = ALPHA_M001_LATEST_GPS["longitude"]
        start_alt = ALPHA_M001_LATEST_GPS.get("altitude_m", 3950.0)
    else:
        # Check wearable telemetry
        loc = db.get_latest_team_wearable_location(team_id)
        if loc and loc.get("latitude") is not None and loc.get("longitude") is not None:
            start_lat = loc["latitude"]
            start_lon = loc["longitude"]
            start_alt = loc.get("altitude_m", 3950.0)

    # If still not found, check active operation member location or site origin
    if start_lat is None or start_lon is None:
        if operations:
            latest_op = list(operations.values())[-1]
            members = latest_op.team_members.get(team_id, [])
            for m in members:
                if m.member_id == member_id or not start_lat:
                    start_lat = m.location.latitude
                    start_lon = m.location.longitude
                    start_alt = m.location.altitude_m
                    break
            if start_lat is None and latest_op.config and latest_op.config.site_origin:
                start_lat = latest_op.config.site_origin.latitude
                start_lon = latest_op.config.site_origin.longitude
                start_alt = latest_op.config.site_origin.altitude_m
        if start_lat is None or start_lon is None:
            start_lat = HIMALAYA_SITE_ORIGIN.latitude
            start_lon = HIMALAYA_SITE_ORIGIN.longitude
            start_alt = HIMALAYA_SITE_ORIGIN.altitude_m

    start_coord = GPSCoordinate(latitude=start_lat, longitude=start_lon, altitude_m=start_alt)

    # 2. Determine Target Coordinate (Victim Location)
    dest_lat = cmd.get("destination_latitude") or cmd.get("latitude")
    dest_lon = cmd.get("destination_longitude") or cmd.get("longitude")
    dest_alt = cmd.get("destination_altitude_m") or cmd.get("altitude_m", 3950.0)

    if (dest_lat is None or dest_lon is None or (dest_lat == 0.0 and dest_lon == 0.0)) and victim_id:
        if operations:
            latest_op = list(operations.values())[-1]
            if latest_op.config and latest_op.config.victims:
                for v in latest_op.config.victims:
                    if v.victim_id == victim_id:
                        dest_lat = v.location.latitude
                        dest_lon = v.location.longitude
                        dest_alt = v.location.altitude_m
                        break

    if dest_lat is None or dest_lon is None or (dest_lat == 0.0 and dest_lon == 0.0):
        # Default offset if victim has no coordinate
        dest_lat = start_lat + 0.00045
        dest_lon = start_lon + 0.00060

    target_coord = GPSCoordinate(latitude=dest_lat, longitude=dest_lon, altitude_m=dest_alt)

    # 3. Gather Live Hazard State from active simulator or query overrides
    hazard_state: Dict[str, Any] = {}
    if operations:
        latest_op = list(operations.values())[-1]
        if latest_op.simulator:
            water_rep = latest_op.simulator.water_report()
            flow_rep = latest_op.simulator.water_flow_report()
            tilt_rep = latest_op.simulator.tilt_report()
            seismic_rep = latest_op.simulator.seismic_report()
            soil_rep = latest_op.simulator.soil_report()
            rain_rep = latest_op.simulator.rain_report()

            # Max water level
            max_water = max([float(v) for v in water_rep.values()] or [0.0]) if isinstance(water_rep, dict) else 0.0
            max_flow = max([float(v) for v in flow_rep.values()] or [0.0]) if isinstance(flow_rep, dict) else 0.0

            hazard_state["water_level_cm"] = max_water
            hazard_state["water_flow_mps"] = max_flow
            hazard_state["tilt_deg"] = float(tilt_rep.get("tilt_deg", 0.0))
            hazard_state["vibration_mm_s"] = float(seismic_rep.get("vibration_mm_s", 0.0))
            hazard_state["aftershock_active"] = bool(seismic_rep.get("aftershock_active", False))
            hazard_state["soil_moisture_pct"] = float(soil_rep.get("soil_moisture_pct", 0.0))
            hazard_state["rainfall_rate_mm_h"] = float(rain_rep.get("rainfall_rate_mm_h", rain_rep.get("rainfall_mm_hr", 0.0)))

    # Apply explicit request overrides if provided
    if tilt_deg is not None:
        hazard_state["tilt_deg"] = tilt_deg
    if water_level_cm is not None:
        hazard_state["water_level_cm"] = water_level_cm
    if water_flow_mps is not None:
        hazard_state["water_flow_mps"] = water_flow_mps
    if landslide_risk_score is not None:
        hazard_state["landslide_risk_score"] = landslide_risk_score
    if vibration_mm_s is not None:
        hazard_state["vibration_mm_s"] = vibration_mm_s
    if gas_ppm is not None:
        hazard_state["gas_ppm"] = gas_ppm
    if smoke_pct is not None:
        hazard_state["smoke_pct"] = smoke_pct
    if debris_present is not None:
        hazard_state["debris_present"] = debris_present

    route_res = global_road_network.calculate_route(
        start_coord=start_coord,
        target_coord=target_coord,
        hazard_state=hazard_state,
        command_id=command_id,
        team_id=team_id,
        victim_id=victim_id,
    )
    return route_res.to_dict()


@app.get("/api/dispatch/route")
@app.get("/dispatch/route")
def calculate_custom_route_endpoint(
    start_lat: float,
    start_lon: float,
    target_lat: float,
    target_lon: float,
    start_alt_m: Optional[float] = 3950.0,
    target_alt_m: Optional[float] = 3950.0,
    tilt_deg: Optional[float] = None,
    water_level_cm: Optional[float] = None,
    water_flow_mps: Optional[float] = None,
    landslide_risk_score: Optional[float] = None,
    vibration_mm_s: Optional[float] = None,
    gas_ppm: Optional[float] = None,
    smoke_pct: Optional[float] = None,
    debris_present: Optional[bool] = None,
    command_id: Optional[str] = None,
    team_id: Optional[str] = None,
    victim_id: Optional[str] = None,
):
    """
    Read-only dynamic route calculation between arbitrary GPS coordinates and hazard parameters.
    """
    start_coord = GPSCoordinate(latitude=start_lat, longitude=start_lon, altitude_m=start_alt_m)
    target_coord = GPSCoordinate(latitude=target_lat, longitude=target_lon, altitude_m=target_alt_m)

    hazard_state: Dict[str, Any] = {}
    if tilt_deg is not None:
        hazard_state["tilt_deg"] = tilt_deg
    if water_level_cm is not None:
        hazard_state["water_level_cm"] = water_level_cm
    if water_flow_mps is not None:
        hazard_state["water_flow_mps"] = water_flow_mps
    if landslide_risk_score is not None:
        hazard_state["landslide_risk_score"] = landslide_risk_score
    if vibration_mm_s is not None:
        hazard_state["vibration_mm_s"] = vibration_mm_s
    if gas_ppm is not None:
        hazard_state["gas_ppm"] = gas_ppm
    if smoke_pct is not None:
        hazard_state["smoke_pct"] = smoke_pct
    if debris_present is not None:
        hazard_state["debris_present"] = debris_present

    route_res = global_road_network.calculate_route(
        start_coord=start_coord,
        target_coord=target_coord,
        hazard_state=hazard_state,
        command_id=command_id,
        team_id=team_id,
        victim_id=victim_id,
    )
    return route_res.to_dict()


# --------------------------------------------------------------------------- #
# Flash-Flood Early Warning, Non-Contact Pressure & Evacuation Endpoints
# --------------------------------------------------------------------------- #

@app.get("/hydrostatic-pressure/estimate")
@app.get("/api/v1/hydrostatic-pressure/estimate")
@app.get("/operations/{operation_id}/hydrostatic-pressure/estimate")
def estimate_hydrostatic_pressure_endpoint(
    measured_distance_m: Optional[float] = None,
    sensor_mount_height_m: float = 6.0,
    water_depth_m: Optional[float] = None,
    fluid_density_kg_m3: float = 1000.0,
    sensor_id: str = "DEV-WATER-NC01",
    is_live_sensor: bool = False,
    operation_id: Optional[str] = None,
):
    """
    Direct endpoint calculating non-contact hydrostatic water pressure:
    P = rho * g * h
    Where h = sensor_mount_height_m - measured_distance_m (or direct water_depth_m).
    Derived strictly from surface distance measurements without submerged contact.
    """
    engine = get_non_contact_pressure_engine(sensor_mount_height_m=sensor_mount_height_m)
    now_iso = datetime.now(timezone.utc).isoformat()

    reading = NonContactSensorReading(
        sensor_id=sensor_id,
        device_id="DEV-WATER-NC01",
        sensor_mount_height_m=sensor_mount_height_m,
        measured_surface_distance_m=measured_distance_m,
        water_depth_m=water_depth_m,
        timestamp=now_iso,
        is_live_sensor=is_live_sensor,
        data_source_mode="PRODUCTION_LIVE" if is_live_sensor else "SIMULATED_TESTING",
    )

    estimate = engine.estimate_pressure(reading)
    return estimate.to_dict()


@app.get("/flood-intelligence/current")
@app.get("/api/v1/flood-intelligence/current")
@app.get("/operations/{operation_id}/flood-intelligence/current")
def get_current_flood_intelligence(
    operation_id: Optional[str] = None,
    is_live_sensor: bool = False,
):
    """
    Returns real-time flash-flood intelligence, multi-sensor hazard fusion,
    hydrostatic pressure estimation, risk classification, and swiftwater rescue flags.
    """
    op = _get_operation_optional(operation_id)
    flood_engine = get_flood_intelligence_engine()
    landslide_engine = get_landslide_detector()
    debris_engine = get_debris_flow_detector()
    health_monitor = get_sensor_health_monitor()

    # Gather readings from simulator if running
    measured_distance = 4.8  # Default 1.2m depth under 6.0m mount
    water_depth = 1.2
    flow_vel = 0.5
    rain_rate = 12.0
    soil_m = 45.0
    tilt_deg = 2.5
    rumble_db = 28.0
    upstream_surge = False

    if op and op.running and op.simulator:
        sim = op.simulator
        if hasattr(sim, "non_contact_pressure_report"):
            try:
                water_rep = sim.non_contact_pressure_report()
            except Exception:
                water_rep = {}
            if isinstance(water_rep, dict):
                measured_distance = water_rep.get("measured_surface_distance_m")
                water_depth = water_rep.get("water_depth_m")
                flow_vel = water_rep.get("water_flow_mps")
            if water_depth is None:
                w_map = sim.water_report() if hasattr(sim, "water_report") else {}
                water_depth = (max(w_map.values(), default=120.0) / 100.0) if w_map else 1.2
            if flow_vel is None:
                f_map = sim.water_flow_report() if hasattr(sim, "water_flow_report") else {}
                flow_vel = max(f_map.values(), default=0.5) if f_map else 0.5
            if measured_distance is None:
                measured_distance = max(0.1, 6.0 - water_depth)
        else:
            w_map = sim.water_report() if hasattr(sim, "water_report") else {}
            f_map = sim.water_flow_report() if hasattr(sim, "water_flow_report") else {}
            water_depth = (max(w_map.values(), default=120.0) / 100.0) if w_map else 1.2
            flow_vel = max(f_map.values(), default=0.5) if f_map else 0.5
            measured_distance = max(0.1, 6.0 - water_depth)

        rain_rep = sim.rain_report() if hasattr(sim, "rain_report") else {}
        rain_rate = rain_rep.get("rainfall_rate_mmh") or rain_rep.get("rainfall_mm_hr", 12.0)

        soil_rep = sim.soil_report() if hasattr(sim, "soil_report") else {}
        soil_m = soil_rep.get("soil_moisture_pct", 45.0)

        tilt_rep = sim.tilt_report() if hasattr(sim, "tilt_report") else {}
        tilt_deg = tilt_rep.get("tilt_deg", 2.5)

        seismic_rep = sim.seismic_report() if hasattr(sim, "seismic_report") else {}
        rumble_db = min(100.0, 20.0 + seismic_rep.get("vibration_mm_s", 1.0) * 8.0)

        # Audit health
        health_monitor.record_heartbeat("DEV-WATER-NC01", value=water_depth, battery_volts=3.9, rssi_dbm=-68)
        health_monitor.record_heartbeat("DEV-RAIN-01", value=rain_rate, battery_volts=4.1, rssi_dbm=-62)
        health_monitor.record_heartbeat("DEV-SOIL-FDR01", value=soil_m, battery_volts=3.7, rssi_dbm=-75)
        health_monitor.record_heartbeat("DEV-TILT-MPU01", value=tilt_deg, battery_volts=3.8, rssi_dbm=-70)
        health_monitor.record_heartbeat("DEV-GEO-RMB01", value=rumble_db, battery_volts=3.9, rssi_dbm=-66)

    # Detect Landslide & Debris Flow hazards
    ls_res = landslide_engine.detect_landslide(
        soil_moisture_pct=soil_m,
        tilt_angle_deg=tilt_deg,
        cumulative_rainfall_mm=rain_rate * 2.0,
    )
    df_res = debris_engine.detect_debris_flow(
        water_flow_velocity_mps=flow_vel,
        water_depth_m=water_depth,
        acoustic_rumble_db=rumble_db,
    )

    # Process flood risk
    report = flood_engine.process_cycle(
        measured_surface_distance_m=measured_distance,
        water_depth_m=water_depth,
        rainfall_rate_mmh=rain_rate,
        flow_velocity_mps=flow_vel,
        upstream_surge_active=upstream_surge or df_res.debris_flow_detected,
        soil_moisture_pct=soil_m,
        slope_tilt_deg=tilt_deg,
        acoustic_rumble_db=rumble_db,
        is_live_sensor=is_live_sensor,
    )

    # Persist assessment to DB if session exists
    if op and op.session_id and report.current_assessment:
        ca = report.current_assessment
        try:
            db.log_flood_risk_assessment(
                session_id=op.session_id,
                assessment_id=ca.assessment_id,
                water_depth_m=ca.water_depth_m,
                measured_distance_m=ca.measured_distance_m,
                rise_rate_mps=ca.rise_rate_mps,
                estimated_pressure_kpa=ca.hydrostatic_pressure_kpa,
                rainfall_intensity_mmh=ca.rainfall_intensity_mmh,
                risk_score=ca.risk_score,
                risk_level=ca.risk_level.value,
                warning_issued=ca.warning_issued,
                evacuation_recommended=ca.evacuation_recommended,
                time_to_inundation_minutes=ca.time_to_inundation_minutes,
                reading_quality=ca.reading_quality,
            )
        except Exception:
            pass

    return report.to_dict()


@app.get("/flood-intelligence/early-warning")
@app.get("/api/v1/flood-intelligence/early-warning")
@app.get("/operations/{operation_id}/flood-intelligence/early-warning")
def get_flood_early_warning(
    operation_id: Optional[str] = None,
):
    """
    Returns proactive early-warning metrics: surge acceleration, time-to-inundation,
    debris damming probability, and active life-safety alert status.
    """
    flood_engine = get_flood_intelligence_engine()
    rep = flood_engine.get_latest_report()
    ca = rep.current_assessment

    status = "NORMAL"
    warning_title = "Flood Conditions Normal"
    warning_body = "River stage and surface distance are within safe nominal ranges."

    if ca.risk_level == FloodRiskLevel.CRITICAL:
        status = "CRITICAL_WARNING"
        warning_title = "🚨 CRITICAL FLASH-FLOOD SURGE ALERT"
        warning_body = f"Rapid inundation detected ({ca.water_depth_m:.2f}m depth, +{ca.rise_rate_mps*60:.2f} m/min). Immediate high-ground evacuation mandatory!"
    elif ca.risk_level == FloodRiskLevel.WARNING:
        status = "FLOOD_WARNING"
        warning_title = "⚠️ FLASH-FLOOD WARNING"
        warning_body = f"Water level surging rapidly ({ca.water_depth_m:.2f}m depth, +{ca.rise_rate_mps*60:.2f} m/min). Prepare for immediate evacuation."
    elif ca.risk_level == FloodRiskLevel.WATCH:
        status = "FLOOD_WATCH"
        warning_title = "ℹ️ FLOOD WATCH ACTIVE"
        warning_body = "Elevated water level and upstream precipitation observed. Monitor gorge gauges."

    return {
        "early_warning_status": status,
        "warning_title": warning_title,
        "warning_body": warning_body,
        "risk_level": ca.risk_level.value,
        "risk_score": ca.risk_score,
        "water_depth_m": round(ca.water_depth_m, 2),
        "rise_rate_mps": round(ca.rise_rate_mps, 4),
        "rise_rate_m_per_minute": round(ca.rise_rate_mps * 60.0, 2),
        "rate_acceleration_mps2": round(ca.rate_acceleration_mps2, 6),
        "time_to_inundation_minutes": (
            round(ca.time_to_inundation_minutes, 1)
            if ca.time_to_inundation_minutes is not None
            else None
        ),
        "upstream_surge_active": ca.upstream_surge_active,
        "debris_damming_risk": ca.debris_damming_risk,
        "evacuation_recommended": ca.evacuation_recommended,
        "swiftwater_rescue_flag": ca.swiftwater_rescue_flag,
        "warning_issued": ca.warning_issued,
        "evaluated_at": ca.assessment_timestamp,
    }


@app.post("/flood-intelligence/evaluate")
@app.post("/api/v1/flood-intelligence/evaluate")
@app.post("/operations/{operation_id}/flood-intelligence/evaluate")
def evaluate_flood_intelligence_endpoint(req: EvaluateFloodRequest, operation_id: Optional[str] = None):
    """
    Accepts arbitrary sensor telemetry or field probe inputs to evaluate flood risk.
    """
    flood_engine = get_flood_intelligence_engine()
    report = flood_engine.process_cycle(
        measured_surface_distance_m=req.measured_surface_distance_m,
        water_depth_m=req.water_depth_m,
        sensor_mount_height_m=req.sensor_mount_height_m or 6.0,
        rainfall_rate_mmh=req.rainfall_rate_mmh or 0.0,
        flow_velocity_mps=req.flow_velocity_mps or 0.0,
        upstream_surge_active=req.upstream_surge_active or False,
        soil_moisture_pct=req.soil_moisture_pct or 40.0,
        slope_tilt_deg=req.slope_tilt_deg or 0.0,
        acoustic_rumble_db=req.acoustic_rumble_db or 30.0,
        is_live_sensor=req.is_live_sensor or False,
    )
    return report.to_dict()


@app.get("/evacuation/recommendations")
@app.get("/api/v1/evacuation/recommendations")
@app.get("/operations/{operation_id}/evacuation/recommendations")
def get_evacuation_recommendations(operation_id: Optional[str] = None):
    """
    Returns real-time dynamic evacuation recommendations, danger zones,
    safe high-ground assembly points, transit times, and safety margins.
    """
    flood_engine = get_flood_intelligence_engine()
    evac_engine = get_evacuation_engine()
    ls_engine = get_landslide_detector()
    df_engine = get_debris_flow_detector()

    rep = flood_engine.get_latest_report()
    ls_active = ls_engine.get_latest_result().landslide_detected
    df_active = df_engine.get_latest_result().debris_flow_detected

    recs = evac_engine.evaluate_evacuation_plan(
        flood_report=rep,
        landslide_active=ls_active,
        debris_flow_active=df_active,
    )

    # Persist to database
    for r in recs:
        try:
            db.log_evacuation_recommendation(
                recommendation_id=r.recommendation_id,
                zone_id=r.zone_id,
                zone_name=r.zone_name,
                assembly_point_id=r.recommended_assembly_point.point_id,
                assembly_point_name=r.recommended_assembly_point.name,
                urgency=r.urgency,
                route_confidence=r.route_safety_confidence.value,
                transit_minutes=r.estimated_transit_minutes,
                safety_margin_minutes=r.safety_margin_minutes,
                avoided_hazards=r.avoided_hazards,
                instructions=r.tactical_instructions,
            )
        except Exception:
            pass

    return {
        "total_zones": len(recs),
        "immediate_evacuation_count": sum(1 for r in recs if r.urgency == "IMMEDIATE_EVACUATION"),
        "high_priority_count": sum(1 for r in recs if r.urgency == "HIGH_PRIORITY_EVACUATION"),
        "assembly_points": [p.to_dict() for p in evac_engine.assembly_points],
        "recommendations": [r.to_dict() for r in recs],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/evacuation/plan")
@app.post("/api/v1/evacuation/plan")
@app.post("/operations/{operation_id}/evacuation/plan")
def plan_custom_evacuation(operation_id: Optional[str] = None):
    """Recomputes and returns fresh evacuation routes across all zones."""
    return get_evacuation_recommendations(operation_id=operation_id)


@app.get("/sensors/health/summary")
@app.get("/api/v1/sensors/health/summary")
@app.get("/operations/{operation_id}/sensors/health/summary")
def get_sensor_health_summary(operation_id: Optional[str] = None):
    """
    Returns sensor fleet health index, battery levels, signal quality,
    freshness, and diagnostics breakdown.
    """
    monitor = get_sensor_health_monitor()
    return monitor.get_fleet_summary()


@app.get("/communication/status")
@app.get("/api/v1/communication/status")
@app.get("/operations/{operation_id}/communication/status")
def get_communication_status(operation_id: Optional[str] = None):
    """
    Returns operational status of Internet, GSM SMS, LoRa Mesh, and Offline App Sync channels.
    """
    try:
        try:
            from communication import get_communication_router
        except ImportError:
            from backend.communication import get_communication_router
        router = get_communication_router()
        status_data = router.get_status()
    except Exception:
        status_data = {"health": {}, "queue_depth": 0}

    # Backward compatibility for legacy callers expecting bearer_status
    manager = get_communication_manager()
    status_data["bearer_status"] = manager.get_bearer_status()
    status_data["recent_messages"] = manager.list_messages(limit=25)
    return status_data


@app.post("/communication/send")
@app.post("/api/v1/communication/send")
@app.post("/operations/{operation_id}/communication/send")
def send_emergency_alert_endpoint(req: SendEmergencyAlertRequest, operation_id: Optional[str] = None):
    """
    Dispatches or queues an emergency alert with automatic multi-bearer fallback.
    """
    manager = get_communication_manager()
    prio = MessagePriority.WARNING
    if req.priority:
        try:
            prio = MessagePriority(req.priority.upper())
        except Exception:
            prio = MessagePriority.WARNING

    msg = manager.queue_message(
        recipient=req.recipient or "BROADCAST",
        payload=req.payload,
        priority=prio,
        idempotency_key=req.idempotency_key,
    )
    return msg.to_dict()


# --------------------------------------------------------------------------- #
# SMSGate Inbound Polling Lifecycle Handlers
# --------------------------------------------------------------------------- #

async def _smsgate_inbound_polling_loop():
    """Background task continuously polling SMSGate /inbox on a cancellable interval."""
    logger.info("[SMSGATE-INBOUND] Starting background SMSGate /inbox polling worker...")
    while True:
        try:
            try:
                from notification_dispatch import poll_smsgate_inbound_messages
            except ImportError:
                from backend.notification_dispatch import poll_smsgate_inbound_messages
            await poll_smsgate_inbound_messages()
        except asyncio.CancelledError:
            logger.info("[SMSGATE-INBOUND] Background polling worker cancelled.")
            break
        except Exception as poll_ex:
            logger.warning(f"[SMSGATE-INBOUND] Background polling iteration error: {poll_ex}")

        poll_interval = float(os.getenv("SMSGATE_INBOUND_POLL_SECONDS", "3.0"))
        try:
            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            break


# --------------------------------------------------------------------------- #
# Multi-Channel Emergency Communication Observability Endpoints
# --------------------------------------------------------------------------- #

class CommunicationDispatchPayload(BaseModel):
    recipient: str
    payload: str
    priority: str = "HIGH"
    alert_id: Optional[str] = None
    rescue_command_id: Optional[str] = None
    mission_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    sps: Optional[float] = None
    preferred_channel: Optional[str] = None


class CommunicationAckPayload(BaseModel):
    message_id: str
    rescuer_id: Optional[str] = None


@app.get("/api/v1/communication/deliveries")
@app.get("/communication/deliveries")
def list_communication_deliveries_endpoint(limit: int = 50):
    """Retrieves recent multi-channel emergency communication ledger records."""
    try:
        return db.list_communication_deliveries(limit=limit)
    except Exception as ex:
        logger.warning(f"Error listing communication deliveries: {ex}")
        return []


@app.post("/api/v1/communication/ack")
@app.post("/communication/ack")
def acknowledge_communication_endpoint(req: CommunicationAckPayload):
    """Records two-way delivery confirmation for an emergency message."""
    try:
        try:
            from communication import get_communication_router
        except ImportError:
            from backend.communication import get_communication_router
        router = get_communication_router()
        success = router.acknowledge_message(req.message_id, rescuer_id=req.rescuer_id)
        return {"success": success, "message_id": req.message_id, "status": "ACKNOWLEDGED"}
    except Exception as ex:
        logger.warning(f"Error acknowledging communication message: {ex}")
        return {"success": False, "error": str(ex)}


@app.post("/api/v1/communication/dispatch")
@app.post("/communication/dispatch")
def manual_communication_dispatch_endpoint(req: CommunicationDispatchPayload):
    """Dispatches emergency message across resilient failover layer."""
    try:
        try:
            from communication import get_communication_router, MessagePriority, ChannelType
        except ImportError:
            from backend.communication import get_communication_router, MessagePriority, ChannelType
        router = get_communication_router()
        prio_enum = getattr(MessagePriority, req.priority.upper(), MessagePriority.HIGH)
        pref_channel = getattr(ChannelType, req.preferred_channel.upper(), None) if req.preferred_channel else None
        
        msg = router.dispatch_alert(
            recipient=req.recipient,
            payload=req.payload,
            priority=prio_enum,
            alert_id=req.alert_id,
            rescue_command_id=req.rescue_command_id,
            mission_id=req.mission_id,
            latitude=req.latitude,
            longitude=req.longitude,
            sps=req.sps,
            preferred_channel=pref_channel,
        )
        return msg.to_dict()
    except Exception as ex:
        logger.warning(f"Error executing manual communication dispatch: {ex}")
        raise HTTPException(status_code=500, detail=str(ex))


# -------------------------------------------------------------------------
# Offline Communication Subsystem Endpoints
# -------------------------------------------------------------------------

class OfflineEnqueuePayload(BaseModel):
    message_type: str = "SURVIVOR_DETECTED"
    payload: Dict[str, Any] = {}
    priority: str = "HIGH"
    alert_id: Optional[str] = None
    destination_device_id: str = "GATEWAY-01"
    source_device_id: Optional[str] = None


class OfflineSimulatorSendPayload(BaseModel):
    source_id: str = "NODE-01"
    destination_id: str = "GATEWAY-01"
    message_type: str = "SURVIVOR_DETECTED"
    payload: Dict[str, Any] = {}
    simulated_distance_m: Optional[float] = None
    priority: str = "HIGH"


@app.get("/api/offline/status")
@app.get("/offline/status")
def get_offline_status():
    """Returns the operational health and metrics of the local edge offline communication system."""
    try:
        try:
            from local_edge_backend import get_local_edge_backend
        except ImportError:
            from backend.local_edge_backend import get_local_edge_backend
        edge = get_local_edge_backend()
        return edge.get_health_status()
    except Exception as ex:
        logger.error(f"Error fetching offline status: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(ex))


@app.get("/api/offline/queue")
@app.get("/offline/queue")
def get_offline_queue(status: Optional[str] = None, limit: int = 50):
    """Returns local offline message queue entries and status breakdown."""
    try:
        try:
            from local_edge_backend import get_local_edge_backend
            from offline_models import MessageStatus
        except ImportError:
            from backend.local_edge_backend import get_local_edge_backend
            from backend.offline_models import MessageStatus
        edge = get_local_edge_backend()
        status_enum = None
        if status:
            try:
                status_enum = MessageStatus(status.upper())
            except Exception:
                status_enum = None
        messages = edge.queue.get_messages(status=status_enum, limit=limit)
        stats = edge.queue.get_queue_stats()
        return {
            "queue_stats": stats,
            "count": len(messages),
            "messages": [m.to_dict() for m in messages],
        }
    except Exception as ex:
        logger.error(f"Error fetching offline queue: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(ex))


@app.post("/api/offline/enqueue")
@app.post("/offline/enqueue")
def enqueue_offline_alert(req: OfflineEnqueuePayload):
    """Enqueues an emergency alert into the local edge offline pipeline."""
    try:
        try:
            from local_edge_backend import get_local_edge_backend
        except ImportError:
            from backend.local_edge_backend import get_local_edge_backend
        edge = get_local_edge_backend()
        result = edge.ingest_emergency_alert(
            message_type=req.message_type,
            payload=req.payload,
            priority=req.priority,
            alert_id=req.alert_id,
            destination_device_id=req.destination_device_id,
            source_device_id=req.source_device_id,
        )
        return result
    except Exception as ex:
        logger.error(f"Error enqueueing offline alert: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(ex))


@app.post("/api/offline/sync")
@app.post("/offline/sync")
def trigger_offline_sync():
    """Manually triggers synchronization of pending offline messages with central cloud / external dispatch."""
    try:
        try:
            from local_edge_backend import get_local_edge_backend
        except ImportError:
            from backend.local_edge_backend import get_local_edge_backend
        edge = get_local_edge_backend()
        result = edge.trigger_sync()
        return result
    except Exception as ex:
        logger.error(f"Error triggering offline sync: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(ex))


@app.post("/api/offline/simulator/send")
@app.post("/offline/simulator/send")
def simulator_send_packet(req: OfflineSimulatorSendPayload):
    """Simulates sending a LoRa packet across nodes with configurable distance propagation modeling."""
    try:
        try:
            from local_edge_backend import get_local_edge_backend
            from offline_models import LoRaPacket, MessageType
        except ImportError:
            from backend.local_edge_backend import get_local_edge_backend
        import json
        edge = get_local_edge_backend()
        
        # Build simulated packet
        packet = LoRaPacket(
            source_id=req.source_id,
            destination_id=req.destination_id,
            message_type=req.message_type,
            payload_raw=json.dumps(req.payload) if isinstance(req.payload, dict) else str(req.payload),
        )
        
        # Send via LoRa gateway in simulator mode
        tx_res = edge.gateway.send_packet(
            packet=packet,
            target_node_id=req.destination_id,
            simulated_distance_m=req.simulated_distance_m,
        )
        
        # If destination is gateway or local edge, also deliver to edge receiver
        if req.destination_id in ("GATEWAY-01", edge.node_id, "BROADCAST") and tx_res.get("success"):
            edge.gateway.receive_packet(packet)
            
        return {
            "success": tx_res.get("success", False),
            "packet": packet.to_dict(),
            "tx_result": tx_res,
            "mode": edge.gateway.mode,
        }
    except Exception as ex:
        logger.error(f"Error simulating packet send: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(ex))


@app.get("/api/offline/nodes")
@app.get("/offline/nodes")
def get_offline_nodes():
    """Returns registered LoRa mesh nodes and topology."""
    try:
        try:
            from local_edge_backend import get_local_edge_backend
        except ImportError:
            from backend.local_edge_backend import get_local_edge_backend
        edge = get_local_edge_backend()
        nodes = edge.gateway.get_registered_nodes()
        routes = edge.router.get_routing_table()
        return {
            "nodes": nodes,
            "count": len(nodes),
            "routing_table": routes,
            "gateway_id": edge.node_id,
            "lora_mode": edge.gateway.mode,
        }
    except Exception as ex:
        logger.error(f"Error fetching offline nodes: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(ex))


@app.on_event("startup")
async def on_startup_handler():
    """FastAPI startup lifecycle handler."""
    enabled_val = os.getenv("SMSGATE_ENABLED", "false").lower().strip()
    inbound_enabled = os.getenv("SMSGATE_INBOUND_ENABLED", "true").lower().strip()
    if enabled_val in ("true", "1", "yes", "on") and inbound_enabled in ("true", "1", "yes", "on"):
        if "PYTEST_CURRENT_TEST" not in os.environ:
            app.state.smsgate_poll_task = asyncio.create_task(_smsgate_inbound_polling_loop())


@app.on_event("shutdown")
async def on_shutdown_handler():
    """FastAPI shutdown lifecycle handler."""
    if hasattr(app.state, "smsgate_poll_task"):
        app.state.smsgate_poll_task.cancel()
        try:
            await app.state.smsgate_poll_task
        except (asyncio.CancelledError, Exception):
            pass


if __name__ == "__main__":
    import uvicorn
    import os
    import sys

    # On Windows, auto-free stale port 8000 process if previously left running
    if sys.platform == "win32":
        try:
            import subprocess
            out = subprocess.check_output(
                'powershell -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"',
                shell=True,
                text=True,
            ).strip()
            if out:
                my_pid = os.getpid()
                for pid_str in out.split():
                    if pid_str.isdigit() and int(pid_str) != my_pid:
                        subprocess.run(f"powershell -Command \"Stop-Process -Id {pid_str} -Force -ErrorAction SilentlyContinue\"", shell=True)
        except Exception:
            pass

    dev_reload = os.environ.get("RIDGEWATCH_RELOAD", "true").lower() in ("true", "1", "yes")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=dev_reload)



