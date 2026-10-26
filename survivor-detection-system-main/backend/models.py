"""
models.py
----------
Core data classes for the AI-Based Multi-Sensor Survivor Detection &
Rescue Prioritization System.

These models are shared by sensor_simulator.py (produces SensorReading
objects), fusion_engine.py (consumes readings, produces DetectionResult
objects), api.py (serializes all of the above over REST), and db.py
(persists everything to SQLite for the evaluation/testing section).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
import uuid


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #

class SensorType(str, Enum):
    THERMAL_IMAGING = "thermal_imaging"          # deg C, body-heat signature
    PIR_MOTION = "pir_motion"                    # 0.0-1.0 motion intensity
    ACOUSTIC = "acoustic"                        # dB, breathing/sound/tapping
    CO2 = "co2"                                  # ppm, exhaled CO2 concentration
    HEART_RATE_RADAR = "heart_rate_radar"        # bpm, doppler radar vital signs
    RGB_CAMERA = "rgb_camera"                    # 0.0-1.0 visual detection confidence
    WATER_LEVEL = "water_level"                  # cm, rising flood water depth at victim location
    WATER_FLOW = "water_flow"                    # m/s, current velocity/flow speed at victim location
    IMU_TILT = "imu_tilt"                        # degrees, kit tilt from vertical
    IMU_VIBRATION = "imu_vibration"              # g-force, kit vibration / seismic acceleration
    GAS_CONCENTRATION = "gas_concentration"      # ppm, toxic / combustible gas concentration
    SMOKE_DENSITY = "smoke_density"              # %, optical smoke obscuration / particulate
    BAROMETRIC_PRESSURE = "barometric_pressure"  # hPa / mbar, atmospheric barometric pressure
    RAINFALL_INTENSITY = "rainfall_intensity"    # mm/hr, precipitation rate
    SOIL_MOISTURE = "soil_moisture"              # %, volumetric soil water content / saturation
    TEMPERATURE = "temperature"                  # deg C, ambient air temperature
    HUMIDITY = "humidity"                        # %, relative atmospheric humidity
    GPS = "gps"                                  # GNSS geospatial coordinate, fix, and movement tracking
    UWB_BIORADAR = "uwb_bioradar"                # %, subsurface bioradar life-sign confidence / signal strength


class SensorHealthStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"
    CALIBRATION = "CALIBRATION"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GasType(str, Enum):
    GENERIC_SMOKE = "GENERIC_SMOKE"
    CO = "CO"
    CO2 = "CO2"
    VOC = "VOC"
    TOXIC_GAS = "TOXIC_GAS"
    INDUSTRIAL_GAS = "INDUSTRIAL_GAS"
    CHLORINE = "CHLORINE"
    NATURAL_GAS = "NATURAL_GAS"


class GasConcentrationLevel(str, Enum):
    NORMAL = "NORMAL"          # 0-30 simulation range
    ELEVATED = "ELEVATED"      # 31-60 simulation range
    HIGH = "HIGH"              # 61-80 simulation range
    CRITICAL = "CRITICAL"      # 81-100+ simulation range


class SmokeLevel(str, Enum):
    NO_SMOKE = "NO_SMOKE"      # 0%
    LOW = "LOW"                # 1-25%
    MODERATE = "MODERATE"      # 26-50%
    HIGH = "HIGH"              # 51-75%
    CRITICAL = "CRITICAL"      # 76-100%


class PressureTrend(str, Enum):
    STABLE = "STABLE"
    RISING = "RISING"
    FALLING = "FALLING"
    RAPIDLY_FALLING = "RAPIDLY_FALLING"
    RAPIDLY_RISING = "RAPIDLY_RISING"
    UNKNOWN = "UNKNOWN"


class PressureDropSeverity(str, Enum):
    NORMAL = "NORMAL"
    SIGNIFICANT_DROP = "SIGNIFICANT_DROP"
    RAPID_DROP = "RAPID_DROP"
    CRITICAL_DROP = "CRITICAL_DROP"


class PressureAnomalyLevel(str, Enum):
    NORMAL = "NORMAL"
    ABNORMAL = "ABNORMAL"
    CRITICAL = "CRITICAL"


class MoistureTrend(str, Enum):
    STABLE = "STABLE"
    RISING = "RISING"
    RAPIDLY_RISING = "RAPIDLY_RISING"
    FALLING = "FALLING"
    RAPIDLY_FALLING = "RAPIDLY_FALLING"
    UNKNOWN = "UNKNOWN"


class TiltTrend(str, Enum):
    STABLE = "STABLE"
    RISING = "RISING"
    RAPIDLY_RISING = "RAPIDLY_RISING"
    FALLING = "FALLING"
    RAPIDLY_FALLING = "RAPIDLY_FALLING"
    UNKNOWN = "UNKNOWN"


class LandslideRiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class LandslideEventState(str, Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    ELEVATED = "ELEVATED"
    HIGH_RISK = "HIGH_RISK"
    CRITICAL = "CRITICAL"
    RECOVERY = "RECOVERY"


@dataclass(frozen=True)
class LandslideConfig:
    """
    Centralized configurable simulation and decision-support thresholds for
    Soil Moisture + Tilt multi-sensor fusion, trend analysis, and Landslide Risk scoring.
    Note: These are decision-support and simulation parameters, not universal scientific constants.
    """
    min_moisture_pct: float = 0.0
    max_moisture_pct: float = 100.0
    nominal_baseline_moisture_pct: float = 38.0
    moisture_elevated_threshold_pct: float = 50.0
    moisture_high_threshold_pct: float = 70.0
    moisture_critical_threshold_pct: float = 80.0
    moisture_rising_rate_threshold: float = 1.5
    moisture_rapid_rising_rate_threshold: float = 3.5

    min_tilt_deg: float = 0.0
    max_tilt_deg: float = 90.0
    nominal_baseline_tilt_deg: float = 0.5
    tilt_elevated_threshold_deg: float = 1.5
    tilt_high_threshold_deg: float = 3.0
    tilt_critical_threshold_deg: float = 4.5
    tilt_rising_rate_threshold: float = 0.3
    tilt_rapid_rising_rate_threshold: float = 0.8

    weight_moisture: float = 0.25
    weight_moisture_trend: float = 0.15
    weight_tilt: float = 0.25
    weight_tilt_trend: float = 0.25
    weight_persistence: float = 0.10

    risk_low_max: float = 24.0
    risk_moderate_max: float = 49.0
    risk_high_max: float = 74.0
    risk_critical_min: float = 75.0

    history_window_size: int = 60
    persistence_cycles_required: int = 2
    recovery_cycles_required: int = 2
    sampling_interval_seconds: float = 4.0


LANDSLIDE_CONFIG = LandslideConfig()


@dataclass(frozen=True)
class PressureConfig:
    """
    Centralized configurable application and simulation thresholds for
    Barometric Pressure processing, trend analysis, rate of change, and anomaly detection.
    Note: These are configurable application/simulation thresholds, not universal scientific disaster constants.
    """
    min_pressure_hpa: float = 850.0
    max_pressure_hpa: float = 1100.0
    nominal_baseline_hpa: float = 1013.25
    falling_threshold_hpa_per_cycle: float = 2.0
    rapid_falling_threshold_hpa_per_cycle: float = 4.0
    rising_threshold_hpa_per_cycle: float = 2.0
    rapid_rising_threshold_hpa_per_cycle: float = 4.0
    anomaly_z_score_threshold: float = 2.0
    anomaly_absolute_drop_hpa: float = 8.0
    critical_drop_threshold_hpa: float = 16.0
    history_window_size: int = 60
    sampling_interval_seconds: float = 4.0
    rate_calculation_unit: str = "cycle"
    severe_cyclone_threshold_hpa: float = 990.0
    critical_plunge_threshold_hpa: float = 975.0


PRESSURE_CONFIG = PressureConfig()


class RainfallClassification(str, Enum):
    NO_RAIN = "NO_RAIN"
    LIGHT = "LIGHT"
    MODERATE = "MODERATE"
    HEAVY = "HEAVY"
    VERY_HEAVY = "VERY_HEAVY"
    EXTREME = "EXTREME"


class RainfallTrend(str, Enum):
    STABLE = "STABLE"
    INCREASING = "INCREASING"
    RAPIDLY_INCREASING = "RAPIDLY_INCREASING"
    DECREASING = "DECREASING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RainfallConfig:
    """
    Centralized configurable simulation, classification, and decision-support thresholds
    for Rainfall / Precipitation Rate (mm/h) and Cumulative Precipitation (mm).
    """
    min_rainfall_rate_mm_h: float = 0.0
    max_rainfall_rate_mm_h: float = 500.0   # physical sensor ceiling for spike protection
    no_rain_threshold: float = 0.0
    light_threshold_mm_h: float = 5.0
    moderate_threshold_mm_h: float = 20.0
    heavy_threshold_mm_h: float = 50.0
    very_heavy_threshold_mm_h: float = 100.0
    extreme_threshold_mm_h: float = 100.0
    flash_flood_trigger_mm_h: float = 30.0
    landslide_trigger_mm_h: float = 25.0
    critical_accumulation_mm: float = 100.0
    weight_rainfall: float = 0.15
    sampling_interval_seconds: float = 4.0


RAINFALL_CONFIG = RainfallConfig()


class TemperatureTrend(str, Enum):
    STABLE = "STABLE"
    RISING = "RISING"
    RAPIDLY_RISING = "RAPIDLY_RISING"
    FALLING = "FALLING"
    RAPIDLY_FALLING = "RAPIDLY_FALLING"
    UNKNOWN = "UNKNOWN"


class HumidityTrend(str, Enum):
    STABLE = "STABLE"
    RISING = "RISING"
    RAPIDLY_RISING = "RAPIDLY_RISING"
    FALLING = "FALLING"
    RAPIDLY_FALLING = "RAPIDLY_FALLING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TemperatureConfig:
    """
    Centralized configurable simulation, classification, and decision-support thresholds
    for Ambient Air Temperature (°C).
    """
    min_temp_c: float = -100.0
    max_temp_c: float = 150.0
    nominal_baseline_c: float = 15.0
    freezing_threshold_c: float = 0.0
    heatwave_warning_c: float = 40.0
    heatwave_critical_c: float = 45.0
    fire_indication_c: float = 50.0
    rising_rate_threshold_c_per_cycle: float = 1.0
    rapid_rising_rate_threshold_c_per_cycle: float = 2.5
    history_window_size: int = 60
    sampling_interval_seconds: float = 4.0


TEMPERATURE_CONFIG = TemperatureConfig()


@dataclass(frozen=True)
class HumidityConfig:
    """
    Centralized configurable simulation, classification, and decision-support thresholds
    for Atmospheric Relative Humidity (%).
    """
    min_humidity_pct: float = 0.0
    max_humidity_pct: float = 100.0
    nominal_baseline_pct: float = 50.0
    low_arid_threshold_pct: float = 25.0
    high_humidity_threshold_pct: float = 80.0
    saturated_threshold_pct: float = 90.0
    rising_rate_threshold_pct_per_cycle: float = 2.0
    rapid_rising_rate_threshold_pct_per_cycle: float = 5.0
    history_window_size: int = 60
    sampling_interval_seconds: float = 4.0


HUMIDITY_CONFIG = HumidityConfig()


class WaterTrend(str, Enum):
    STABLE = "STABLE"
    RISING = "RISING"
    RAPIDLY_RISING = "RAPIDLY_RISING"
    FALLING = "FALLING"
    RAPIDLY_FALLING = "RAPIDLY_FALLING"
    UNKNOWN = "UNKNOWN"


class WaterLevelClassification(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class WaterLevelConfig:
    """
    Centralized configurable simulation, classification, rate thresholds,
    and decision-support boundaries for Water-Level & Flow monitoring.
    """
    min_water_level_cm: float = 0.0
    max_water_level_cm: float = 2000.0   # 20m max physical flood probe range
    min_flow_velocity_mps: float = 0.0
    max_flow_velocity_mps: float = 25.0
    nominal_baseline_cm: float = 0.0
    warning_threshold_cm: float = 30.0
    high_threshold_cm: float = 60.0
    critical_threshold_cm: float = 100.0
    rapid_rising_rate_cm_per_cycle: float = 10.0
    dam_break_rising_rate_cm_per_cycle: float = 25.0
    tsunami_rising_rate_cm_per_cycle: float = 30.0
    high_flow_velocity_threshold_mps: float = 1.5
    extreme_flow_velocity_threshold_mps: float = 3.5
    history_window_size: int = 60
    sampling_interval_seconds: float = 4.0


WATER_LEVEL_CONFIG = WaterLevelConfig()


class GPSMovementState(str, Enum):
    STATIONARY = "STATIONARY"
    MOVING = "MOVING"
    RAPID_MOVEMENT = "RAPID_MOVEMENT"
    SIGNAL_LOSS = "SIGNAL_LOSS"
    JUMP_ANOMALY = "JUMP_ANOMALY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class GPSConfig:
    """
    Centralized configurable simulation, kinematic tracking, anomaly detection,
    and decision-support thresholds for GPS / GNSS receivers.
    """
    min_latitude: float = -90.0
    max_latitude: float = 90.0
    min_longitude: float = -180.0
    max_longitude: float = 180.0
    default_accuracy_m: float = 2.5
    degraded_accuracy_m: float = 15.0
    critical_accuracy_m: float = 30.0
    default_satellites: int = 12
    min_satellites_online: int = 4
    min_satellites_degraded: int = 3
    stationary_speed_threshold_mps: float = 0.2
    walking_speed_ref_mps: float = 1.4
    rapid_speed_threshold_mps: float = 10.0
    max_speed_mps: float = 50.0
    jump_distance_threshold_m: float = 1000.0   # Max realistic single-step displacement
    stale_timeout_seconds: float = 10.0
    history_window_size: int = 100
    sampling_interval_seconds: float = 1.0


GPS_CONFIG = GPSConfig()


class VictimStatus(str, Enum):
    SAFE = "safe"
    MINOR_INJURY = "minor_injury"
    CRITICAL = "critical"
    DECEASED = "deceased"
    UNKNOWN = "unknown"          # default until fusion engine classifies


class TriagePriority(str, Enum):
    """START-triage-inspired priority bands used to order the rescue queue."""
    P1_IMMEDIATE = "P1_immediate"     # critical, viable, rescue first
    P2_DELAYED = "P2_delayed"         # minor injury / stable, safe to wait
    P3_MINIMAL = "P3_minimal"         # ambulatory / safe, self-evacuating
    P4_DECEASED = "P4_deceased"       # no vital signs detected, lowest priority
    UNCLASSIFIED = "unclassified"     # not enough sensor data yet


class TeamAvailability(str, Enum):
    AVAILABLE = "available"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    OFF_DUTY = "off_duty"


# --------------------------------------------------------------------------- #
# GPS Coordinate Model
# --------------------------------------------------------------------------- #

@dataclass
class GPSCoordinate:
    latitude: float
    longitude: float
    altitude_m: Optional[float] = None  # useful for avalanche burial depth context

    def as_tuple(self) -> tuple:
        return (self.latitude, self.longitude)

    def to_dict(self) -> dict:
        return {
            "latitude": round(float(self.latitude), 6) if isinstance(self.latitude, (int, float)) else self.latitude,
            "longitude": round(float(self.longitude), 6) if isinstance(self.longitude, (int, float)) else self.longitude,
            "altitude_m": round(float(self.altitude_m), 1) if isinstance(self.altitude_m, (int, float)) else self.altitude_m,
        }

    def as_dict(self) -> dict:
        return self.to_dict()

    def validate(self) -> bool:
        """Validate latitude in [-90, 90] and longitude in [-180, 180], reject NaN/Inf."""
        import math
        if not isinstance(self.latitude, (int, float)) or not isinstance(self.longitude, (int, float)):
            return False
        if math.isnan(self.latitude) or math.isinf(self.latitude) or math.isnan(self.longitude) or math.isinf(self.longitude):
            return False
        if self.latitude < -90.0 or self.latitude > 90.0 or self.longitude < -180.0 or self.longitude > 180.0:
            return False
        if self.altitude_m is not None:
            if not isinstance(self.altitude_m, (int, float)) or math.isnan(self.altitude_m) or math.isinf(self.altitude_m):
                return False
        return True

    def haversine_distance_to(self, other: "GPSCoordinate") -> float:
        """Great-circle distance in meters to another GPS coordinate."""
        import math
        earth_r = 6371000.0
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        h = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
        return 2.0 * earth_r * math.asin(min(1.0, math.sqrt(h)))


# --------------------------------------------------------------------------- #
# Sensor Health & Trend Data Classes
# --------------------------------------------------------------------------- #

@dataclass
class SensorHealth:
    sensor_id: str
    sensor_type: SensorType
    status: SensorHealthStatus
    battery_pct: float = 100.0
    signal_quality: float = 1.0
    error_message: Optional[str] = None
    last_heartbeat: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sensor_type"] = self.sensor_type.value if hasattr(self.sensor_type, "value") else str(self.sensor_type)
        d["status"] = self.status.value if hasattr(self.status, "value") else str(self.status)
        return d


@dataclass
class SensorTrend:
    sensor_type: SensorType
    current_value: float
    previous_value: float = 0.0
    rate_of_change_per_cycle: float = 0.0
    trend_direction: str = "STABLE"                   # "RISING", "FALLING", "STABLE", "SPIKE", "DROP"
    is_spike: bool = False
    is_sustained_abnormal: bool = False
    anomaly_score: float = 0.0             # 0.0 - 1.0
    history_samples: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sensor_type"] = self.sensor_type.value if hasattr(self.sensor_type, "value") else str(self.sensor_type)
        return d


@dataclass
class SensorEvidence:
    sensor_type: SensorType
    evidence_label: str                    # e.g. "SEISMIC_TREMOR_DETECTED", "EXTREME_THERMAL_SIGNATURE"
    observed_value: float
    threshold_triggered: str
    confidence: float                      # 0.0 - 1.0
    description: str = ""
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    location: Optional[GPSCoordinate] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    victim_id: Optional[str] = None
    raw_metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sensor_type"] = self.sensor_type.value if hasattr(self.sensor_type, "value") else str(self.sensor_type)
        d["location"] = self.location.as_tuple() if self.location else None
        return d


@dataclass
class ScenarioInferenceResult:
    scenario_id: str
    scenario_name: str
    confidence_pct: float                  # 0.0 - 100.0 (Confidence Score)
    risk_level: RiskLevel
    primary_evidence: list[str] = field(default_factory=list)
    secondary_hazards: list[str] = field(default_factory=list)
    survivor_detected: bool = False
    survivor_count: int = 0
    recommended_action: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sensor_health_summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["risk_level"] = self.risk_level.value if hasattr(self.risk_level, "value") else str(self.risk_level)
        return d


@dataclass
class DisasterAssessment:
    primary_scenario: ScenarioInferenceResult
    secondary_scenarios: list[ScenarioInferenceResult] = field(default_factory=list)
    overall_risk: RiskLevel = RiskLevel.MEDIUM
    confidence_pct: float = 0.0
    survivor_status: str = "SEARCHING"     # "DETECTED_ACTIVE_SURVIVORS", "SEARCHING", etc.
    active_evidence: list[SensorEvidence] = field(default_factory=list)
    sensor_health_matrix: dict = field(default_factory=dict)
    recommended_action: str = ""
    assessed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    cycle: int = 0

    def to_dict(self) -> dict:
        return {
            "primary_scenario": self.primary_scenario.to_dict() if self.primary_scenario else None,
            "secondary_scenarios": [s.to_dict() for s in self.secondary_scenarios],
            "overall_risk": self.overall_risk.value if hasattr(self.overall_risk, "value") else str(self.overall_risk),
            "confidence_pct": round(self.confidence_pct, 1),
            "survivor_status": self.survivor_status,
            "active_evidence": [e.to_dict() if hasattr(e, "to_dict") else e for e in self.active_evidence],
            "sensor_health_matrix": self.sensor_health_matrix,
            "recommended_action": self.recommended_action,
            "assessed_at": self.assessed_at,
            "cycle": self.cycle,
        }


# --------------------------------------------------------------------------- #
# Sensor Reading
# --------------------------------------------------------------------------- #

@dataclass
class SensorReading:
    """A single reading emitted by one simulated sensor for one victim location or environmental node."""
    sensor_type: SensorType
    value: float
    unit: str
    location: GPSCoordinate
    victim_id: Optional[str] = None          # ground-truth link, simulator-only
    device_id: Optional[str] = None          # hardware node identifier
    reading_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    confidence: float = 1.0                  # sensor self-reported signal quality (0-1)
    quality: float = 1.0                     # reliability score (0-1)
    status: SensorHealthStatus = SensorHealthStatus.ONLINE
    noisy: bool = False                      # flag if simulator injected noise/dropout
    raw_data: dict = field(default_factory=dict)

    def validate(self) -> bool:
        """Enforce strict physical boundaries and data type integrity."""
        valid, _ = SensorValidator.validate_reading(self)
        return valid

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sensor_type"] = self.sensor_type.value if hasattr(self.sensor_type, "value") else str(self.sensor_type)
        d["status"] = self.status.value if hasattr(self.status, "value") else str(self.status)
        return d


@dataclass
class RejectedSensorReading:
    """Carries diagnostic information about a sensor reading that failed physical validation."""
    rejection_id: str = field(default_factory=lambda: f"REJ-{uuid.uuid4().hex[:8]}")
    session_id: Optional[str] = None
    cycle: int = 0
    sensor_type: str = "unknown"
    sensor_id: Optional[str] = None
    device_id: Optional[str] = None
    victim_id: Optional[str] = None
    attempted_value: Optional[float] = None
    unit: Optional[str] = None
    rejection_reason: str = "Unknown validation failure"
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rejection_id": self.rejection_id,
            "session_id": self.session_id,
            "cycle": self.cycle,
            "sensor_type": self.sensor_type,
            "sensor_id": self.sensor_id,
            "device_id": self.device_id,
            "victim_id": self.victim_id,
            "attempted_value": self.attempted_value,
            "unit": self.unit,
            "rejection_reason": self.rejection_reason,
            "raw_payload": self.raw_payload,
            "timestamp": self.timestamp,
        }


class SensorValidator:
    """
    Unified validation gate enforcing physical boundary limits, data type integrity,
    and sanity rules across all survivor, environmental, visual, and navigation modalities.
    """

    # Physical valid ranges per sensor modality: (min_value, max_value, requires_non_negative)
    SENSOR_BOUNDS = {
        SensorType.HEART_RATE_RADAR: (0.0, 250.0, True),
        SensorType.PIR_MOTION: (0.0, 1.0, True),
        SensorType.ACOUSTIC: (0.0, 160.0, True),
        SensorType.CO2: (0.0, 50000.0, True),
        SensorType.THERMAL_IMAGING: (-50.0, 300.0, False),
        SensorType.RGB_CAMERA: (0.0, 1.0, True),
        SensorType.WATER_LEVEL: (0.0, 5000.0, True),
        SensorType.WATER_FLOW: (0.0, 50.0, True),
        SensorType.IMU_TILT: (0.0, 180.0, True),
        SensorType.IMU_VIBRATION: (0.0, 100.0, True),
        SensorType.GAS_CONCENTRATION: (0.0, 50000.0, True),
        SensorType.SMOKE_DENSITY: (0.0, 100.0, True),
        SensorType.BAROMETRIC_PRESSURE: (500.0, 1200.0, True),
        SensorType.RAINFALL_INTENSITY: (0.0, 1000.0, True),
        SensorType.SOIL_MOISTURE: (0.0, 100.0, True),
        SensorType.TEMPERATURE: (-100.0, 150.0, False),
        SensorType.HUMIDITY: (0.0, 100.0, True),
        SensorType.GPS: (0.0, 64.0, True),   # GPS value is locked satellites
        SensorType.UWB_BIORADAR: (0.0, 100.0, True),  # % confidence or reflection energy
    }

    @classmethod
    def validate_reading(cls, reading: Any) -> tuple[bool, Optional[str]]:
        """
        Validate any SensorReading or typed telemetry dataclass.
        Returns (is_valid: bool, error_reason: Optional[str]).
        """
        import math

        if reading is None:
            return False, "Null reading object"

        # If reading has custom validate() method (e.g. GPSReading, CameraReading, etc.)
        if hasattr(reading, "validate") and callable(reading.validate) and not isinstance(reading, SensorReading):
            try:
                if not reading.validate():
                    return False, f"Dataclass validation failed for {type(reading).__name__}"
            except Exception as ex:
                return False, f"Validation exception: {str(ex)}"

        if isinstance(reading, SensorReading):
            st = reading.sensor_type
            if isinstance(st, str):
                try:
                    st = SensorType(st)
                except ValueError:
                    return False, f"Unrecognized sensor_type '{reading.sensor_type}'"

            val = reading.value
            if val is None or not isinstance(val, (int, float)):
                return False, f"Value must be a numeric float, got {type(val).__name__ if val is not None else 'None'}"

            if math.isnan(val) or math.isinf(val):
                return False, "Value cannot be NaN or Infinite"

            bounds = cls.SENSOR_BOUNDS.get(st)
            if bounds:
                min_v, max_v, non_neg = bounds
                if non_neg and val < 0.0:
                    return False, f"Value {val} violates non-negative requirement for {st.value}"
                if val < min_v or val > max_v:
                    return False, f"Value {val} out of physical range [{min_v}, {max_v}] for {st.value}"

            if reading.confidence is not None:
                if not isinstance(reading.confidence, (int, float)) or math.isnan(reading.confidence) or reading.confidence < 0.0 or reading.confidence > 1.0:
                    return False, f"Confidence {reading.confidence} out of range [0.0, 1.0]"

            if reading.quality is not None:
                if not isinstance(reading.quality, (int, float)) or math.isnan(reading.quality) or reading.quality < 0.0 or reading.quality > 1.0:
                    return False, f"Quality {reading.quality} out of range [0.0, 1.0]"

            if reading.location is not None:
                if hasattr(reading.location, "validate") and not reading.location.validate():
                    return False, "Invalid location coordinates"

        return True, None


# --------------------------------------------------------------------------- #
# Gas & Smoke Dedicated Sensor Models & Hardware Interface
# --------------------------------------------------------------------------- #

@dataclass
class GasSmokeReading:
    """Dedicated structured reading from a gas/smoke telemetry module."""
    reading_id: str = field(default_factory=lambda: f"GSR-{uuid.uuid4().hex[:8]}")
    sensor_id: str = "GAS-SMOKE-SITE"
    device_id: str = "DEV-GAS-01"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    gas_type: GasType = GasType.GENERIC_SMOKE
    gas_concentration: float = 0.0          # simulated normalized ppm or index
    gas_unit: str = "ppm"
    gas_level: GasConcentrationLevel = GasConcentrationLevel.NORMAL
    smoke_density_pct: float = 0.0          # optical obscuration percentage 0-100%
    smoke_level: SmokeLevel = SmokeLevel.NO_SMOKE
    rate_of_change_gas: float = 0.0         # rate of change per cycle
    rate_of_change_smoke: float = 0.0       # rate of change per cycle
    location: Optional[GPSCoordinate] = None
    status: SensorHealthStatus = SensorHealthStatus.ONLINE
    confidence: float = 0.95                # 0.0 to 1.0 confidence score
    quality: float = 0.95                   # 0.0 to 1.0 signal quality
    raw_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        """Strict validation rejecting NaN, Infinity, negative values, and out-of-range corruptions."""
        import math
        if any(math.isnan(x) or math.isinf(x) for x in [self.gas_concentration, self.smoke_density_pct, self.rate_of_change_gas, self.rate_of_change_smoke]):
            return False
        if self.gas_concentration < 0.0 or self.smoke_density_pct < 0.0:
            return False
        if self.smoke_density_pct > 100.0:
            return False
        if self.confidence < 0.0 or self.confidence > 1.0 or self.quality < 0.0 or self.quality > 1.0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "sensor_id": self.sensor_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "gas_type": self.gas_type.value if hasattr(self.gas_type, "value") else str(self.gas_type),
            "gas_concentration": round(self.gas_concentration, 2),
            "gas_unit": self.gas_unit,
            "gas_level": self.gas_level.value if hasattr(self.gas_level, "value") else str(self.gas_level),
            "smoke_density_pct": round(self.smoke_density_pct, 2),
            "smoke_level": self.smoke_level.value if hasattr(self.smoke_level, "value") else str(self.smoke_level),
            "rate_of_change_gas": round(self.rate_of_change_gas, 3),
            "rate_of_change_smoke": round(self.rate_of_change_smoke, 3),
            "location": self.location.as_dict() if self.location and hasattr(self.location, "as_dict") else (self.location.to_dict() if self.location and hasattr(self.location, "to_dict") else None),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "confidence": round(self.confidence, 2),
            "quality": round(self.quality, 2),
            "raw_data": self.raw_data,
            "metadata": self.metadata,
        }


class GasSmokeSensorInterface(ABC):
    """
    Abstract Hardware / Simulator Interface for Gas & Smoke detection probes.
    Enables plug-and-play switching between simulation adapters and real IoT hardware.
    """
    @abstractmethod
    def read_sensor(self) -> GasSmokeReading:
        """Poll and return the latest validated GasSmokeReading."""
        pass

    @abstractmethod
    def get_health(self) -> SensorHealth:
        """Return diagnostic health record for the hardware/sim probe."""
        pass

    @abstractmethod
    def set_gas_type(self, gas_type: GasType) -> None:
        """Configure active gas detection target profile."""
        pass


# --------------------------------------------------------------------------- #
# Barometric Pressure Dedicated Sensor Models & Hardware Interface
# --------------------------------------------------------------------------- #

@dataclass
class BarometricPressureReading:
    """
    Dedicated structured reading from a Barometric Pressure telemetry module (BMP280/BME280 or simulation).
    Enforces normalized units (hPa), strict validation, and comprehensive anomaly/trend metadata.
    """
    reading_id: str = field(default_factory=lambda: f"BPR-{uuid.uuid4().hex[:8]}")
    sensor_id: str = "ENV-BARO-01"
    device_id: str = "DEV-BARO-01"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    pressure_hpa: float = 1013.25
    unit: str = "hPa"
    rate_of_change: float = 0.0          # hPa per cycle
    trend: PressureTrend = PressureTrend.STABLE
    drop_severity: PressureDropSeverity = PressureDropSeverity.NORMAL
    anomaly_level: PressureAnomalyLevel = PressureAnomalyLevel.NORMAL
    location: Optional[GPSCoordinate] = None
    status: SensorHealthStatus = SensorHealthStatus.ONLINE
    confidence: float = 0.95             # 0.0 - 1.0
    quality: float = 0.95                # 0.0 - 1.0
    raw_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        """
        Strict validation rejecting null, NaN, Infinity, negative/out-of-range values,
        invalid sensor ID, invalid timestamp, and malformed payload.
        Never converts invalid values to 0 hPa.
        """
        import math
        if not self.sensor_id or not isinstance(self.sensor_id, str) or not self.sensor_id.strip():
            return False
        if not self.timestamp or not isinstance(self.timestamp, str) or not self.timestamp.strip():
            return False
        if any(math.isnan(x) or math.isinf(x) for x in [self.pressure_hpa, self.rate_of_change, self.confidence, self.quality]):
            return False
        if self.pressure_hpa < PRESSURE_CONFIG.min_pressure_hpa or self.pressure_hpa > PRESSURE_CONFIG.max_pressure_hpa:
            return False
        if self.confidence < 0.0 or self.confidence > 1.0 or self.quality < 0.0 or self.quality > 1.0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "sensor_id": self.sensor_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "pressure_hpa": round(self.pressure_hpa, 2),
            "unit": self.unit,
            "rate_of_change": round(self.rate_of_change, 3),
            "trend": self.trend.value if hasattr(self.trend, "value") else str(self.trend),
            "drop_severity": self.drop_severity.value if hasattr(self.drop_severity, "value") else str(self.drop_severity),
            "anomaly_level": self.anomaly_level.value if hasattr(self.anomaly_level, "value") else str(self.anomaly_level),
            "location": self.location.as_tuple() if self.location and hasattr(self.location, "as_tuple") else (self.location.to_dict() if self.location and hasattr(self.location, "to_dict") else None),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "confidence": round(self.confidence, 2),
            "quality": round(self.quality, 2),
            "raw_data": self.raw_data,
            "metadata": self.metadata,
        }


class BarometricPressureInterface(ABC):
    """
    Abstract Hardware / Simulator Interface for Barometric Pressure sensors (BMP280, BME280, Simulation).
    Enables normalized data flow into the pressure processing pipeline regardless of hardware or sim source.
    """
    @abstractmethod
    def read_sensor(self) -> BarometricPressureReading:
        """Poll and return the latest validated BarometricPressureReading."""
        pass

    @abstractmethod
    def get_health(self) -> SensorHealth:
        """Return diagnostic health record for the sensor probe."""
        pass

    @abstractmethod
    def set_sampling_interval(self, seconds: float) -> None:
        """Configure sampling cadence."""
        pass


# --------------------------------------------------------------------------- #
# Dedicated Rainfall Sensor Models & Hardware Interface
# --------------------------------------------------------------------------- #

@dataclass
class RainfallReading:
    """
    Dedicated structured reading from a Rainfall / Precipitation telemetry module (Tipping Bucket, Optical, Sim).
    Enforces normalized rate (mm/h), cumulative accumulation (mm), strict bounds validation, and classification.
    """
    reading_id: str = field(default_factory=lambda: f"RNF-{uuid.uuid4().hex[:8]}")
    sensor_id: str = "ENV-RAIN-01"
    device_id: str = "DEV-RAIN-01"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rainfall_rate_mm_h: float = 0.0
    rainfall_mm_hr: float = 0.0          # backwards-compatible alias
    cumulative_rainfall_mm: float = 0.0  # total precipitation accumulated over active mission
    unit: str = "mm/h"
    rate_of_change: float = 0.0          # mm/h delta per cycle
    trend: RainfallTrend = RainfallTrend.STABLE
    classification: RainfallClassification = RainfallClassification.NO_RAIN
    severity: RiskLevel = RiskLevel.LOW
    location: Optional[GPSCoordinate] = None
    status: SensorHealthStatus = SensorHealthStatus.ONLINE
    confidence: float = 0.98             # 0.0 - 1.0
    quality: float = 0.98                # 0.0 - 1.0
    raw_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Synchronize rainfall_rate_mm_h and rainfall_mm_hr
        if self.rainfall_rate_mm_h != 0.0 and self.rainfall_mm_hr == 0.0:
            self.rainfall_mm_hr = self.rainfall_rate_mm_h
        elif self.rainfall_mm_hr != 0.0 and self.rainfall_rate_mm_h == 0.0:
            self.rainfall_rate_mm_h = self.rainfall_mm_hr

        # Auto classify if default
        if self.classification == RainfallClassification.NO_RAIN and self.rainfall_rate_mm_h > 0.0:
            rate = self.rainfall_rate_mm_h
            if rate <= RAINFALL_CONFIG.light_threshold_mm_h:
                self.classification = RainfallClassification.LIGHT
                self.severity = RiskLevel.LOW
            elif rate <= RAINFALL_CONFIG.moderate_threshold_mm_h:
                self.classification = RainfallClassification.MODERATE
                self.severity = RiskLevel.MEDIUM
            elif rate <= RAINFALL_CONFIG.heavy_threshold_mm_h:
                self.classification = RainfallClassification.HEAVY
                self.severity = RiskLevel.HIGH
            elif rate <= RAINFALL_CONFIG.very_heavy_threshold_mm_h:
                self.classification = RainfallClassification.VERY_HEAVY
                self.severity = RiskLevel.HIGH
            else:
                self.classification = RainfallClassification.EXTREME
                self.severity = RiskLevel.CRITICAL

    def validate(self) -> bool:
        """
        Strict validation rejecting null, NaN, Infinity, negative values,
        out-of-range (>500 mm/h), invalid sensor ID, missing timestamp, and malformed types.
        """
        import math
        if not self.sensor_id or not isinstance(self.sensor_id, str) or not self.sensor_id.strip():
            return False
        if not self.timestamp or not isinstance(self.timestamp, str) or not self.timestamp.strip():
            return False
        floats_to_check = [
            self.rainfall_rate_mm_h, self.rainfall_mm_hr,
            self.cumulative_rainfall_mm, self.rate_of_change,
            self.confidence, self.quality
        ]
        if any(not isinstance(x, (int, float)) or math.isnan(x) or math.isinf(x) for x in floats_to_check):
            return False
        if self.rainfall_rate_mm_h < RAINFALL_CONFIG.min_rainfall_rate_mm_h or self.rainfall_rate_mm_h > RAINFALL_CONFIG.max_rainfall_rate_mm_h:
            return False
        if self.cumulative_rainfall_mm < 0.0:
            return False
        if self.confidence < 0.0 or self.confidence > 1.0 or self.quality < 0.0 or self.quality > 1.0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "sensor_id": self.sensor_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "rainfall_rate_mm_h": round(self.rainfall_rate_mm_h, 2),
            "rainfall_mm_hr": round(self.rainfall_mm_hr, 2),
            "cumulative_rainfall_mm": round(self.cumulative_rainfall_mm, 2),
            "unit": self.unit,
            "rate_of_change": round(self.rate_of_change, 3),
            "trend": self.trend.value if hasattr(self.trend, "value") else str(self.trend),
            "classification": self.classification.value if hasattr(self.classification, "value") else str(self.classification),
            "severity": self.severity.value if hasattr(self.severity, "value") else str(self.severity),
            "location": self.location.as_tuple() if self.location and hasattr(self.location, "as_tuple") else (self.location.to_dict() if self.location and hasattr(self.location, "to_dict") else None),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "confidence": round(self.confidence, 2),
            "quality": round(self.quality, 2),
            "raw_data": self.raw_data,
            "metadata": self.metadata,
        }


class RainfallSensorInterface(ABC):
    """
    Abstract Hardware / Simulator Interface for Rainfall & Precipitation monitoring sensors.
    Enables plug-and-play swapping between physical optical rain gauges, tipping buckets, and simulated weather models.
    """
    @abstractmethod
    def read_sensor(self) -> RainfallReading:
        """Poll and return the latest validated RainfallReading."""
        pass

    @abstractmethod
    def get_health(self) -> SensorHealth:
        """Return diagnostic health record for the rainfall sensor probe."""
        pass

    @abstractmethod
    def set_simulation_profile(self, profile_name: str) -> None:
        """Configure simulation weather profile (NO_RAIN, LIGHT, MODERATE, HEAVY, VERY_HEAVY, EXTREME)."""
        pass


# --------------------------------------------------------------------------- #
# Soil Moisture & Tilt Sensor Data Classes & Interfaces
# --------------------------------------------------------------------------- #

@dataclass
class SoilMoistureReading:
    """
    Structured volumetric Soil Moisture reading from FDR/capacitive probes or simulation.
    Enforces percentage bounds (0-100%), rate of change, trend classification, and metadata.
    """
    reading_id: str = field(default_factory=lambda: f"SMR-{uuid.uuid4().hex[:8]}")
    sensor_id: str = "SLOPE-SOIL-01"
    node_id: str = "SLOPE-NODE-01"
    device_id: str = "DEV-SOIL-01"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    soil_moisture_pct: float = 38.0
    unit: str = "%"
    rate_of_change: float = 0.0          # % per cycle
    trend: MoistureTrend = MoistureTrend.STABLE
    location: Optional[GPSCoordinate] = None
    scenario_id: Optional[str] = None
    status: SensorHealthStatus = SensorHealthStatus.ONLINE
    confidence: float = 0.95             # 0.0 - 1.0
    quality: float = 0.95                # 0.0 - 1.0
    raw_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        """Strict validation rejecting null, NaN, Inf, out-of-range, and empty identifiers."""
        import math
        if not self.sensor_id or not isinstance(self.sensor_id, str) or not self.sensor_id.strip():
            return False
        if not self.timestamp or not isinstance(self.timestamp, str) or not self.timestamp.strip():
            return False
        if any(math.isnan(x) or math.isinf(x) for x in [self.soil_moisture_pct, self.rate_of_change, self.confidence, self.quality]):
            return False
        if self.soil_moisture_pct < LANDSLIDE_CONFIG.min_moisture_pct or self.soil_moisture_pct > LANDSLIDE_CONFIG.max_moisture_pct:
            return False
        if self.confidence < 0.0 or self.confidence > 1.0 or self.quality < 0.0 or self.quality > 1.0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "sensor_id": self.sensor_id,
            "node_id": self.node_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "soil_moisture_pct": round(self.soil_moisture_pct, 2),
            "unit": self.unit,
            "rate_of_change": round(self.rate_of_change, 3),
            "trend": self.trend.value if hasattr(self.trend, "value") else str(self.trend),
            "location": self.location.as_tuple() if self.location and hasattr(self.location, "as_tuple") else (self.location.to_dict() if self.location and hasattr(self.location, "to_dict") else None),
            "scenario_id": self.scenario_id,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "confidence": round(self.confidence, 2),
            "quality": round(self.quality, 2),
            "raw_data": self.raw_data,
            "metadata": self.metadata,
        }


@dataclass
class TiltReading:
    """
    Structured 3-axis inclinometer / IMU Tilt reading.
    Tracks 3-axis gravity vector (x, y, z), resultant tilt angle in degrees, tilt rate, and trend.
    """
    reading_id: str = field(default_factory=lambda: f"TLT-{uuid.uuid4().hex[:8]}")
    sensor_id: str = "SLOPE-TILT-01"
    node_id: str = "SLOPE-NODE-01"
    device_id: str = "DEV-TILT-01"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tilt_x: float = 0.0
    tilt_y: float = 0.0
    tilt_z: float = 1.0
    tilt_angle_deg: float = 0.5
    tilt_rate: float = 0.0               # deg per cycle
    trend: TiltTrend = TiltTrend.STABLE
    unit: str = "deg"
    location: Optional[GPSCoordinate] = None
    scenario_id: Optional[str] = None
    status: SensorHealthStatus = SensorHealthStatus.ONLINE
    confidence: float = 0.95
    quality: float = 0.95
    raw_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        """Strict validation rejecting null, NaN, Inf, out-of-range, and empty identifiers."""
        import math
        if not self.sensor_id or not isinstance(self.sensor_id, str) or not self.sensor_id.strip():
            return False
        if not self.timestamp or not isinstance(self.timestamp, str) or not self.timestamp.strip():
            return False
        if any(math.isnan(x) or math.isinf(x) for x in [self.tilt_angle_deg, self.tilt_rate, self.confidence, self.quality, self.tilt_x, self.tilt_y, self.tilt_z]):
            return False
        if self.tilt_angle_deg < LANDSLIDE_CONFIG.min_tilt_deg or self.tilt_angle_deg > LANDSLIDE_CONFIG.max_tilt_deg:
            return False
        if self.confidence < 0.0 or self.confidence > 1.0 or self.quality < 0.0 or self.quality > 1.0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "sensor_id": self.sensor_id,
            "node_id": self.node_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "tilt_x": round(self.tilt_x, 3),
            "tilt_y": round(self.tilt_y, 3),
            "tilt_z": round(self.tilt_z, 3),
            "tilt_angle_deg": round(self.tilt_angle_deg, 2),
            "tilt_deg": round(self.tilt_angle_deg, 2),
            "tilt_rate": round(self.tilt_rate, 3),
            "trend": self.trend.value if hasattr(self.trend, "value") else str(self.trend),
            "unit": self.unit,
            "location": self.location.as_tuple() if self.location and hasattr(self.location, "as_tuple") else (self.location.to_dict() if self.location and hasattr(self.location, "to_dict") else None),
            "scenario_id": self.scenario_id,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "confidence": round(self.confidence, 2),
            "quality": round(self.quality, 2),
            "raw_data": self.raw_data,
            "metadata": self.metadata,
        }


@dataclass
class LandslideRiskAssessment:
    """
    Fused multi-sensor Landslide Risk Assessment.
    Combines Soil Moisture, Tilt Angle, rates of change, persistence, and compound context.
    """
    node_id: str = "SLOPE-NODE-01"
    location: Optional[GPSCoordinate] = None
    soil_moisture_pct: float = 38.0
    moisture_trend: MoistureTrend = MoistureTrend.STABLE
    moisture_rate: float = 0.0
    tilt_angle_deg: float = 0.5
    tilt_trend: TiltTrend = TiltTrend.STABLE
    tilt_rate: float = 0.0
    persistence_cycles: int = 0
    landslide_risk_score: float = 10.0   # 0.0 - 100.0
    risk_level: LandslideRiskLevel = LandslideRiskLevel.LOW
    confidence: float = 0.95             # 0.0 - 1.0
    event_state: LandslideEventState = LandslideEventState.NORMAL
    contributing_factors: List[str] = field(default_factory=list)
    recommended_action: str = "Routine slope monitoring active."
    status: SensorHealthStatus = SensorHealthStatus.ONLINE
    quality: float = 0.95
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate(self) -> bool:
        """Strict validation rejecting null, NaN, Inf, and out-of-range corruptions."""
        import math
        if not self.node_id or not isinstance(self.node_id, str) or not self.node_id.strip():
            return False
        if not self.timestamp or not isinstance(self.timestamp, str) or not self.timestamp.strip():
            return False
        floats_to_check = [
            self.soil_moisture_pct, self.moisture_rate, self.tilt_angle_deg,
            self.tilt_rate, self.landslide_risk_score, self.confidence, self.quality
        ]
        if any(math.isnan(x) or math.isinf(x) for x in floats_to_check):
            return False
        if self.soil_moisture_pct < 0.0 or self.soil_moisture_pct > 100.0:
            return False
        if self.tilt_angle_deg < 0.0 or self.tilt_angle_deg > 180.0:
            return False
        if self.landslide_risk_score < 0.0 or self.landslide_risk_score > 100.0:
            return False
        if self.confidence < 0.0 or self.confidence > 1.0 or self.quality < 0.0 or self.quality > 1.0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "location": self.location.as_tuple() if self.location and hasattr(self.location, "as_tuple") else (self.location.to_dict() if self.location and hasattr(self.location, "to_dict") else None),
            "soil_moisture_pct": round(self.soil_moisture_pct, 2),
            "moisture_trend": self.moisture_trend.value if hasattr(self.moisture_trend, "value") else str(self.moisture_trend),
            "moisture_rate": round(self.moisture_rate, 3),
            "tilt_angle_deg": round(self.tilt_angle_deg, 2),
            "tilt_trend": self.tilt_trend.value if hasattr(self.tilt_trend, "value") else str(self.tilt_trend),
            "tilt_rate": round(self.tilt_rate, 3),
            "persistence_cycles": self.persistence_cycles,
            "landslide_risk_score": round(self.landslide_risk_score, 1),
            "risk_score": round(self.landslide_risk_score, 1),
            "risk_level": self.risk_level.value if hasattr(self.risk_level, "value") else str(self.risk_level),
            "confidence": round(self.confidence, 2),
            "event_state": self.event_state.value if hasattr(self.event_state, "value") else str(self.event_state),
            "contributing_factors": list(self.contributing_factors),
            "recommended_action": self.recommended_action,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "quality": round(self.quality, 2),
            "timestamp": self.timestamp,
        }


class SoilMoistureSensorInterface(ABC):
    """Abstract Hardware / Simulator Interface for Soil Moisture sensors."""
    @abstractmethod
    def read_soil_moisture(self, node_id: Optional[str] = None) -> SoilMoistureReading:
        pass

    @abstractmethod
    def get_soil_health(self, node_id: Optional[str] = None) -> SensorHealth:
        pass


class TiltSensorInterface(ABC):
    """Abstract Hardware / Simulator Interface for Tilt / Inclinometer sensors."""
    @abstractmethod
    def read_tilt(self, node_id: Optional[str] = None) -> TiltReading:
        pass

    @abstractmethod
    def get_tilt_health(self, node_id: Optional[str] = None) -> SensorHealth:
        pass


# --------------------------------------------------------------------------- #
# Ambient Temperature & Humidity Dedicated Sensor Models & Interfaces
# --------------------------------------------------------------------------- #

@dataclass
class TemperatureReading:
    """
    Dedicated structured reading from an ambient Temperature sensor (thermistor, RTD, BME280/BMP280, or simulation).
    Enforces normalized units (°C), strict bounds validation, rate of change, trend tracking, and metadata.
    """
    reading_id: str = field(default_factory=lambda: f"TMP-{uuid.uuid4().hex[:8]}")
    sensor_id: str = "ENV-TEMP-01"
    device_id: str = "DEV-TEMP-01"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    temperature_c: float = 15.0
    ambient_temp_c: float = 15.0         # backwards-compatible alias
    unit: str = "°C"
    rate_of_change: float = 0.0          # °C per cycle
    trend: TemperatureTrend = TemperatureTrend.STABLE
    location: Optional[GPSCoordinate] = None
    status: SensorHealthStatus = SensorHealthStatus.ONLINE
    confidence: float = 0.98             # 0.0 - 1.0
    quality: float = 0.98                # 0.0 - 1.0
    raw_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.temperature_c != 15.0 and self.ambient_temp_c == 15.0:
            self.ambient_temp_c = self.temperature_c
        elif self.ambient_temp_c != 15.0 and self.temperature_c == 15.0:
            self.temperature_c = self.ambient_temp_c

    def validate(self) -> bool:
        """Strict validation rejecting null, empty IDs, NaN, Infinity, out-of-bounds, and non-numeric values."""
        import math
        if not self.sensor_id or not isinstance(self.sensor_id, str) or not self.sensor_id.strip():
            return False
        if not self.timestamp or not isinstance(self.timestamp, str) or not self.timestamp.strip():
            return False
        floats = [self.temperature_c, self.ambient_temp_c, self.rate_of_change, self.confidence, self.quality]
        if any(not isinstance(x, (int, float)) or math.isnan(x) or math.isinf(x) for x in floats):
            return False
        if self.temperature_c < TEMPERATURE_CONFIG.min_temp_c or self.temperature_c > TEMPERATURE_CONFIG.max_temp_c:
            return False
        if self.confidence < 0.0 or self.confidence > 1.0 or self.quality < 0.0 or self.quality > 1.0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "sensor_id": self.sensor_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "temperature_c": round(self.temperature_c, 2),
            "ambient_temp_c": round(self.ambient_temp_c, 2),
            "unit": self.unit,
            "rate_of_change": round(self.rate_of_change, 3),
            "trend": self.trend.value if hasattr(self.trend, "value") else str(self.trend),
            "location": self.location.as_tuple() if self.location and hasattr(self.location, "as_tuple") else (self.location.to_dict() if self.location and hasattr(self.location, "to_dict") else None),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "confidence": round(self.confidence, 2),
            "quality": round(self.quality, 2),
            "raw_data": self.raw_data,
            "metadata": self.metadata,
        }


class TemperatureSensorInterface(ABC):
    """Abstract Hardware / Simulator Interface for Ambient Temperature monitoring probes."""
    @abstractmethod
    def read_sensor(self) -> TemperatureReading:
        pass

    @abstractmethod
    def get_health(self) -> SensorHealth:
        pass

    @abstractmethod
    def set_simulation_profile(self, profile_name: str) -> None:
        pass


@dataclass
class HumidityReading:
    """
    Dedicated structured reading from an atmospheric Relative Humidity sensor (capacitive hygrometer, BME280, or sim).
    Enforces normalized percentage units (0-100%), strict bounds validation, rate of change, trend tracking, and metadata.
    """
    reading_id: str = field(default_factory=lambda: f"HUM-{uuid.uuid4().hex[:8]}")
    sensor_id: str = "ENV-HUMID-01"
    device_id: str = "DEV-HUMID-01"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    humidity_pct: float = 50.0
    unit: str = "%"
    rate_of_change: float = 0.0          # % per cycle
    trend: HumidityTrend = HumidityTrend.STABLE
    location: Optional[GPSCoordinate] = None
    status: SensorHealthStatus = SensorHealthStatus.ONLINE
    confidence: float = 0.98             # 0.0 - 1.0
    quality: float = 0.98                # 0.0 - 1.0
    raw_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        """Strict validation rejecting null, empty IDs, NaN, Infinity, negative values, >100%, and non-numeric values."""
        import math
        if not self.sensor_id or not isinstance(self.sensor_id, str) or not self.sensor_id.strip():
            return False
        if not self.timestamp or not isinstance(self.timestamp, str) or not self.timestamp.strip():
            return False
        floats = [self.humidity_pct, self.rate_of_change, self.confidence, self.quality]
        if any(not isinstance(x, (int, float)) or math.isnan(x) or math.isinf(x) for x in floats):
            return False
        if self.humidity_pct < HUMIDITY_CONFIG.min_humidity_pct or self.humidity_pct > HUMIDITY_CONFIG.max_humidity_pct:
            return False
        if self.confidence < 0.0 or self.confidence > 1.0 or self.quality < 0.0 or self.quality > 1.0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "sensor_id": self.sensor_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "humidity_pct": round(self.humidity_pct, 2),
            "unit": self.unit,
            "rate_of_change": round(self.rate_of_change, 3),
            "trend": self.trend.value if hasattr(self.trend, "value") else str(self.trend),
            "location": self.location.as_tuple() if self.location and hasattr(self.location, "as_tuple") else (self.location.to_dict() if self.location and hasattr(self.location, "to_dict") else None),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "confidence": round(self.confidence, 2),
            "quality": round(self.quality, 2),
            "raw_data": self.raw_data,
            "metadata": self.metadata,
        }


class HumiditySensorInterface(ABC):
    """Abstract Hardware / Simulator Interface for Relative Humidity monitoring probes."""
    @abstractmethod
    def read_sensor(self) -> HumidityReading:
        pass

    @abstractmethod
    def get_health(self) -> SensorHealth:
        pass

    @abstractmethod
    def set_simulation_profile(self, profile_name: str) -> None:
        pass


# --------------------------------------------------------------------------- #
# GPS / GNSS Dedicated Sensor Models & Hardware Interface
# --------------------------------------------------------------------------- #

@dataclass
class GPSReading:
    """
    Dedicated structured reading from a GNSS / GPS positioning receiver.
    Enforces geographic bounds validation, speed/heading/accuracy integrity,
    satellite fix verification, movement states, and metadata.
    """
    reading_id: str = field(default_factory=lambda: f"GPS-{uuid.uuid4().hex[:8]}")
    sensor_id: str = "DEV-GPS-01"
    device_id: str = "RESCUE-KIT-01"
    sensor_type: SensorType = SensorType.GPS
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    latitude: float = 32.3740
    longitude: float = 77.2490
    altitude_m: float = 3950.0
    accuracy_m: float = 2.5
    speed_mps: float = 0.0
    heading_deg: float = 0.0
    satellites: int = 12
    movement_state: GPSMovementState = GPSMovementState.STATIONARY
    is_valid_fix: bool = True
    fix_quality: str = "3D_FIX_PRECISION"
    status: SensorHealthStatus = SensorHealthStatus.ONLINE
    confidence: float = 0.98             # 0.0 - 1.0
    quality: float = 0.98                # 0.0 - 1.0
    entity_type: str = "DEVICE"          # "DEVICE" (rescuer/kit) or "SURVIVOR"
    entity_id: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Normalize heading to 0.0 - 360.0 degrees
        if isinstance(self.heading_deg, (int, float)):
            self.heading_deg = float(self.heading_deg % 360.0)

    def validate(self) -> bool:
        """Strict validation rejecting null, empty IDs, NaN, Infinity, out-of-range coordinates, negative speed/accuracy/sats."""
        import math
        if not self.sensor_id or not isinstance(self.sensor_id, str) or not self.sensor_id.strip():
            return False
        if not self.timestamp or not isinstance(self.timestamp, str) or not self.timestamp.strip():
            return False
        floats = [self.latitude, self.longitude, self.altitude_m, self.accuracy_m, self.speed_mps, self.heading_deg, self.confidence, self.quality]
        if any(not isinstance(x, (int, float)) or math.isnan(x) or math.isinf(x) for x in floats):
            return False
        if not isinstance(self.satellites, int) or self.satellites < 0:
            return False
        if self.latitude < GPS_CONFIG.min_latitude or self.latitude > GPS_CONFIG.max_latitude:
            return False
        if self.longitude < GPS_CONFIG.min_longitude or self.longitude > GPS_CONFIG.max_longitude:
            return False
        if self.accuracy_m < 0.0 or self.speed_mps < 0.0:
            return False
        if self.confidence < 0.0 or self.confidence > 1.0 or self.quality < 0.0 or self.quality > 1.0:
            return False
        return True

    def to_coordinate(self) -> GPSCoordinate:
        return GPSCoordinate(latitude=self.latitude, longitude=self.longitude, altitude_m=self.altitude_m)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "sensor_id": self.sensor_id,
            "device_id": self.device_id,
            "sensor_type": self.sensor_type.value if hasattr(self.sensor_type, "value") else str(self.sensor_type),
            "timestamp": self.timestamp,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "altitude_m": round(self.altitude_m, 1),
            "accuracy_m": round(self.accuracy_m, 2),
            "speed_mps": round(self.speed_mps, 2),
            "heading_deg": round(self.heading_deg, 1),
            "satellites": int(self.satellites),
            "movement_state": self.movement_state.value if hasattr(self.movement_state, "value") else str(self.movement_state),
            "is_valid_fix": bool(self.is_valid_fix),
            "fix_quality": self.fix_quality,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "confidence": round(self.confidence, 2),
            "quality": round(self.quality, 2),
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "raw_data": self.raw_data,
            "metadata": self.metadata,
        }


class GPSSensorInterface(ABC):
    """Abstract Hardware / Simulator Interface for GNSS / GPS location receiver probes."""
    @abstractmethod
    def read_sensor(self) -> GPSReading:
        pass

    @abstractmethod
    def get_health(self) -> SensorHealth:
        pass

    @abstractmethod
    def set_simulation_profile(self, profile_name: str) -> None:
        pass

    @abstractmethod
    def set_location(self, latitude: float, longitude: float, altitude_m: Optional[float] = None) -> None:
        pass


# --------------------------------------------------------------------------- #
# Water-Level & Flood Telemetry Dedicated Sensor Models & Interfaces
# --------------------------------------------------------------------------- #

@dataclass
class WaterLevelReading:
    """
    Dedicated structured reading from a Water-Level & Flow velocity sensor
    (Hydrostatic probe, ultrasonic level sensor, Doppler current meter, or simulation).
    Enforces normalized depth (cm), velocity (m/s), strict physical validation,
    rate of rise, trend classification, and operational metadata.
    """
    reading_id: str = field(default_factory=lambda: f"WTR-{uuid.uuid4().hex[:8]}")
    sensor_id: str = "ENV-WATER-01"
    device_id: str = "DEV-WATER-01"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    water_level_cm: float = 0.0
    water_flow_mps: float = 0.0
    unit: str = "cm"
    rate_of_change: float = 0.0          # cm delta per cycle
    trend: WaterTrend = WaterTrend.STABLE
    classification: WaterLevelClassification = WaterLevelClassification.NORMAL
    severity: RiskLevel = RiskLevel.LOW
    location: Optional[GPSCoordinate] = None
    status: SensorHealthStatus = SensorHealthStatus.ONLINE
    confidence: float = 0.98             # 0.0 - 1.0
    quality: float = 0.98                # 0.0 - 1.0
    raw_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Non-contact radar / ultrasonic hydrostatic pressure estimation fields
    sensor_type: str = "ultrasonic"
    measured_surface_distance_m: Optional[float] = None
    water_depth_m: Optional[float] = None
    estimated_pressure_pa: Optional[float] = None
    estimated_pressure_kpa: Optional[float] = None
    reading_timestamp: Optional[str] = None
    reading_quality: str = "EXCELLENT"
    pressure_source: str = "non_contact_sensor_estimation"

    def __post_init__(self):
        if self.water_depth_m is None and self.water_level_cm is not None:
            self.water_depth_m = round(max(0.0, self.water_level_cm / 100.0), 4)
        if self.estimated_pressure_pa is None and self.water_depth_m is not None and self.water_depth_m >= 0.0:
            self.estimated_pressure_pa = round(1000.0 * 9.80665 * self.water_depth_m, 3)
            self.estimated_pressure_kpa = round(self.estimated_pressure_pa / 1000.0, 5)
        if self.reading_timestamp is None:
            self.reading_timestamp = self.timestamp

        if self.classification == WaterLevelClassification.NORMAL and self.water_level_cm > 0.0:
            if self.water_level_cm >= WATER_LEVEL_CONFIG.critical_threshold_cm:
                self.classification = WaterLevelClassification.CRITICAL
                self.severity = RiskLevel.CRITICAL
            elif self.water_level_cm >= WATER_LEVEL_CONFIG.high_threshold_cm:
                self.classification = WaterLevelClassification.HIGH
                self.severity = RiskLevel.HIGH
            elif self.water_level_cm >= WATER_LEVEL_CONFIG.warning_threshold_cm:
                self.classification = WaterLevelClassification.WARNING
                self.severity = RiskLevel.MEDIUM

    def validate(self) -> bool:
        """Strict validation rejecting null, empty IDs, NaN, Infinity, negative values, and out-of-bounds corruptions."""
        import math
        if not self.sensor_id or not isinstance(self.sensor_id, str) or not self.sensor_id.strip():
            return False
        if not self.timestamp or not isinstance(self.timestamp, str) or not self.timestamp.strip():
            return False
        floats = [self.water_level_cm, self.water_flow_mps, self.rate_of_change, self.confidence, self.quality]
        if any(not isinstance(x, (int, float)) or math.isnan(x) or math.isinf(x) for x in floats):
            return False
        if self.water_level_cm < WATER_LEVEL_CONFIG.min_water_level_cm or self.water_level_cm > WATER_LEVEL_CONFIG.max_water_level_cm:
            return False
        if self.water_flow_mps < WATER_LEVEL_CONFIG.min_flow_velocity_mps or self.water_flow_mps > WATER_LEVEL_CONFIG.max_flow_velocity_mps:
            return False
        if self.confidence < 0.0 or self.confidence > 1.0 or self.quality < 0.0 or self.quality > 1.0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "sensor_id": self.sensor_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "water_level_cm": round(self.water_level_cm, 2),
            "water_flow_mps": round(self.water_flow_mps, 2),
            "unit": self.unit,
            "rate_of_change": round(self.rate_of_change, 3),
            "trend": self.trend.value if hasattr(self.trend, "value") else str(self.trend),
            "classification": self.classification.value if hasattr(self.classification, "value") else str(self.classification),
            "severity": self.severity.value if hasattr(self.severity, "value") else str(self.severity),
            "location": self.location.as_tuple() if self.location and hasattr(self.location, "as_tuple") else (self.location.to_dict() if self.location and hasattr(self.location, "to_dict") else None),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "confidence": round(self.confidence, 2),
            "quality": round(self.quality, 2),
            "sensor_type": self.sensor_type,
            "measured_surface_distance_m": self.measured_surface_distance_m,
            "water_depth_m": self.water_depth_m,
            "estimated_pressure_pa": self.estimated_pressure_pa,
            "estimated_pressure_kpa": self.estimated_pressure_kpa,
            "reading_timestamp": self.reading_timestamp,
            "reading_quality": self.reading_quality,
            "pressure_source": self.pressure_source,
            "raw_data": self.raw_data,
            "metadata": self.metadata,
        }


class WaterLevelSensorInterface(ABC):
    """Abstract Hardware / Simulator Interface for Water-Level & Flow monitoring probes."""
    @abstractmethod
    def read_sensor(self) -> WaterLevelReading:
        pass

    @abstractmethod
    def get_health(self) -> SensorHealth:
        pass

    @abstractmethod
    def set_simulation_profile(self, profile_name: str) -> None:
        pass



# --------------------------------------------------------------------------- #
# Optical Camera & Thermal Camera Data Classes & Interfaces
# --------------------------------------------------------------------------- #

class CameraDetectionState(str, Enum):
    NO_DETECTION = "NO_DETECTION"
    PERSON_DETECTED = "PERSON_DETECTED"
    MULTIPLE_PERSONS = "MULTIPLE_PERSONS"
    PARTIAL_PERSON = "PARTIAL_PERSON"
    OCCLUDED_PERSON = "OCCLUDED_PERSON"
    DEBRIS = "DEBRIS"
    SMOKE = "SMOKE"
    FIRE = "FIRE"
    UNKNOWN_OBJECT = "UNKNOWN_OBJECT"


class CameraClassification(str, Enum):
    HUMAN = "HUMAN"
    ANIMAL = "ANIMAL"
    VEHICLE = "VEHICLE"
    DEBRIS = "DEBRIS"
    UNKNOWN = "UNKNOWN"


class CameraHealthStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    LOW_VISIBILITY = "LOW_VISIBILITY"
    BLOCKED = "BLOCKED"
    NO_SIGNAL = "NO_SIGNAL"
    CALIBRATION_REQUIRED = "CALIBRATION_REQUIRED"


class ThermalDetectionType(str, Enum):
    NO_HEAT = "NO_HEAT"
    HUMAN_HEAT_SIGNATURE = "HUMAN_HEAT_SIGNATURE"
    MULTIPLE_HUMAN_HEAT = "MULTIPLE_HUMAN_HEAT"
    WEAK_HEAT_SIGNATURE = "WEAK_HEAT_SIGNATURE"
    STRONG_HUMAN_HEAT = "STRONG_HUMAN_HEAT"
    HOT_DEBRIS = "HOT_DEBRIS"
    FIRE_HOTSPOT = "FIRE_HOTSPOT"
    ENVIRONMENTAL_HEAT = "ENVIRONMENTAL_HEAT"
    THERMAL_OBSTRUCTION = "THERMAL_OBSTRUCTION"
    THERMAL_NOISE = "THERMAL_NOISE"


class ThermalClassification(str, Enum):
    HUMAN_HEAT_SIGNATURE = "HUMAN_HEAT_SIGNATURE"
    ANIMAL_HEAT_SIGNATURE = "ANIMAL_HEAT_SIGNATURE"
    FIRE_HOTSPOT = "FIRE_HOTSPOT"
    HOT_OBJECT = "HOT_OBJECT"
    UNKNOWN_HEAT_SOURCE = "UNKNOWN_HEAT_SOURCE"
    NO_SIGNATURE = "NO_SIGNATURE"


class ThermalHealthStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    THERMAL_NOISE = "THERMAL_NOISE"
    LOW_CONTRAST = "LOW_CONTRAST"
    OBSTRUCTED = "OBSTRUCTED"


class CameraCorrelationCase(str, Enum):
    CASE_1_STRONG_SURVIVOR = "CASE_1_STRONG_SURVIVOR"
    CASE_2_POSSIBLE_FALSE_POSITIVE = "CASE_2_POSSIBLE_FALSE_POSITIVE"
    CASE_3_HIDDEN_OBSCURED_SURVIVOR = "CASE_3_HIDDEN_OBSCURED_SURVIVOR"
    CASE_4_MULTI_SENSOR_CONFIRMED = "CASE_4_MULTI_SENSOR_CONFIRMED"
    CASE_4_QUAD_SENSOR_CORROBORATED = "CASE_4_QUAD_SENSOR_CORROBORATED"
    NO_EVIDENCE = "NO_EVIDENCE"


@dataclass(frozen=True)
class CameraConfig:
    """Configurable simulation and explainability thresholds for Camera & Thermal fusion."""
    weight_optical: float = 0.05
    weight_thermal: float = 0.25
    min_visibility_threshold: float = 0.15
    heavy_occlusion_threshold: float = 0.60
    person_confidence_floor: float = 0.20
    human_thermal_min_c: float = 28.0
    human_thermal_max_c: float = 38.0
    fire_hotspot_threshold_c: float = 45.0
    hot_debris_threshold_c: float = 40.0
    synergy_bonus_weight: float = 0.15
    synergy_bonus_case1: float = 0.05
    synergy_bonus_case4: float = 0.05
    case2_false_positive_discount: float = 0.50
    false_positive_penalty_weight: float = 0.40
    single_sensor_max_confidence: float = 0.35


CAMERA_CONFIG = CameraConfig()


@dataclass
class CameraReading:
    """
    Structured visual telemetry from a simulated optical / RGB camera probe.
    Enforces validation on confidence, visibility, occlusion, and detection states.
    """
    reading_id: str = field(default_factory=lambda: f"CAMR-{uuid.uuid4().hex[:8]}")
    sensor_type: str = "camera"
    camera_id: str = "CAM-001"
    device_id: str = "DEV-CAM-01"
    victim_id: Optional[str] = None
    location: Optional[GPSCoordinate] = None
    detection_state: CameraDetectionState = CameraDetectionState.NO_DETECTION
    detection_type: str = "none"
    classification: CameraClassification = CameraClassification.UNKNOWN
    classification_confidence: float = 0.0
    person_count: int = 0
    confidence: float = 0.0               # 0.0 - 1.0 visual confidence
    visibility: float = 1.0               # 0.0 - 1.0 optical visibility
    occlusion: float = 0.0                # 0.0 - 1.0 obstruction fraction
    image_quality: float = 1.0            # 0.0 - 1.0 signal/image quality
    motion_detected: bool = False
    smoke_present: bool = False
    fire_visible: bool = False
    debris_present: bool = False
    orientation: str = "0° NADIR"
    field_of_view_deg: float = 85.0
    range_m: float = 30.0
    status: CameraHealthStatus = CameraHealthStatus.ONLINE
    health_score: float = 100.0           # 0.0 - 100.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        """Strict validation rejecting null, NaN, Inf, out-of-range, and empty identifiers."""
        import math
        if not self.camera_id or not isinstance(self.camera_id, str) or not self.camera_id.strip():
            return False
        if not self.timestamp or not isinstance(self.timestamp, str) or not self.timestamp.strip():
            return False
        floats_to_check = [
            self.confidence, self.visibility, self.occlusion,
            self.image_quality, self.classification_confidence, self.health_score,
            self.field_of_view_deg, self.range_m
        ]
        if any(math.isnan(x) or math.isinf(x) for x in floats_to_check):
            return False
        if self.confidence < 0.0 or self.confidence > 1.0:
            return False
        if self.visibility < 0.0 or self.visibility > 1.0:
            return False
        if self.occlusion < 0.0 or self.occlusion > 1.0:
            return False
        if self.image_quality < 0.0 or self.image_quality > 1.0:
            return False
        if self.classification_confidence < 0.0 or self.classification_confidence > 1.0:
            return False
        if self.health_score < 0.0 or self.health_score > 100.0:
            return False
        if self.person_count < 0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "sensor_type": self.sensor_type,
            "camera_id": self.camera_id,
            "device_id": self.device_id,
            "victim_id": self.victim_id,
            "location": self.location.as_tuple() if self.location and hasattr(self.location, "as_tuple") else (self.location.to_dict() if self.location and hasattr(self.location, "to_dict") else None),
            "detection_state": self.detection_state.value if hasattr(self.detection_state, "value") else str(self.detection_state),
            "detection_type": self.detection_type,
            "classification": self.classification.value if hasattr(self.classification, "value") else str(self.classification),
            "classification_confidence": round(self.classification_confidence, 2),
            "person_count": self.person_count,
            "confidence": round(self.confidence, 2),
            "visibility": round(self.visibility, 2),
            "occlusion": round(self.occlusion, 2),
            "image_quality": round(self.image_quality, 2),
            "motion_detected": bool(self.motion_detected),
            "smoke_present": bool(self.smoke_present),
            "fire_visible": bool(self.fire_visible),
            "debris_present": bool(self.debris_present),
            "orientation": self.orientation,
            "field_of_view_deg": round(self.field_of_view_deg, 1),
            "range_m": round(self.range_m, 1),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "health_score": round(self.health_score, 1),
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "raw_data": self.raw_data,
        }


@dataclass
class ThermalCameraReading:
    """
    Structured thermal infrared telemetry from a simulated Long-Wave Infrared (LWIR) camera.
    Enforces validation on temperature deltas, thermal contrast, human signatures, and hotspots.
    """
    reading_id: str = field(default_factory=lambda: f"THMR-{uuid.uuid4().hex[:8]}")
    sensor_type: str = "thermal_camera"
    camera_id: str = "THERMAL-001"
    device_id: str = "DEV-THM-01"
    victim_id: Optional[str] = None
    location: Optional[GPSCoordinate] = None
    detection_type: ThermalDetectionType = ThermalDetectionType.NO_HEAT
    classification: ThermalClassification = ThermalClassification.NO_SIGNATURE
    classification_confidence: float = 0.0
    heat_signature_detected: bool = False
    human_signature: bool = False
    heat_signature_count: int = 0
    thermal_confidence: float = 0.0       # 0.0 - 1.0 confidence in heat signature
    estimated_temperature: float = 20.0   # °C detected target temperature
    background_temperature: float = 18.0  # °C ambient background reference
    temperature_delta: float = 2.0        # °C delta (target - ambient)
    thermal_visibility: float = 1.0       # 0.0 - 1.0 infrared transmission
    thermal_contrast: float = 1.0         # contrast ratio
    occlusion: float = 0.0                # 0.0 - 1.0 thermal blockage
    fire_hotspot: bool = False
    hot_debris: bool = False
    orientation: str = "0° NADIR"
    field_of_view_deg: float = 60.0
    range_m: float = 40.0
    status: ThermalHealthStatus = ThermalHealthStatus.ONLINE
    health_score: float = 100.0           # 0.0 - 100.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.estimated_temperature is not None and self.background_temperature is not None:
            self.temperature_delta = round(abs(self.estimated_temperature - self.background_temperature), 1)

    def validate(self) -> bool:
        """Strict validation rejecting null, NaN, Inf, out-of-range, and empty identifiers."""
        import math
        if not self.camera_id or not isinstance(self.camera_id, str) or not self.camera_id.strip():
            return False
        if not self.timestamp or not isinstance(self.timestamp, str) or not self.timestamp.strip():
            return False
        floats_to_check = [
            self.thermal_confidence, self.estimated_temperature,
            self.background_temperature, self.temperature_delta,
            self.thermal_visibility, self.thermal_contrast, self.occlusion,
            self.classification_confidence, self.health_score,
            self.field_of_view_deg, self.range_m
        ]
        if any(math.isnan(x) or math.isinf(x) for x in floats_to_check):
            return False
        if self.thermal_confidence < 0.0 or self.thermal_confidence > 1.0:
            return False
        if self.estimated_temperature < -100.0 or self.estimated_temperature > 500.0:
            return False
        if self.background_temperature < -100.0 or self.background_temperature > 500.0:
            return False
        if self.temperature_delta < 0.0:
            return False
        if self.thermal_visibility < 0.0 or self.thermal_visibility > 1.0:
            return False
        if self.occlusion < 0.0 or self.occlusion > 1.0:
            return False
        if self.classification_confidence < 0.0 or self.classification_confidence > 1.0:
            return False
        if self.health_score < 0.0 or self.health_score > 100.0:
            return False
        if self.heat_signature_count < 0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "sensor_type": self.sensor_type,
            "camera_id": self.camera_id,
            "device_id": self.device_id,
            "victim_id": self.victim_id,
            "location": self.location.as_tuple() if self.location and hasattr(self.location, "as_tuple") else (self.location.to_dict() if self.location and hasattr(self.location, "to_dict") else None),
            "detection_type": self.detection_type.value if hasattr(self.detection_type, "value") else str(self.detection_type),
            "classification": self.classification.value if hasattr(self.classification, "value") else str(self.classification),
            "classification_confidence": round(self.classification_confidence, 2),
            "heat_signature_detected": bool(self.heat_signature_detected),
            "human_signature": bool(self.human_signature),
            "heat_signature_count": self.heat_signature_count,
            "thermal_confidence": round(self.thermal_confidence, 2),
            "estimated_temperature": round(self.estimated_temperature, 1),
            "background_temperature": round(self.background_temperature, 1),
            "temperature_delta": round(self.temperature_delta, 1),
            "thermal_visibility": round(self.thermal_visibility, 2),
            "thermal_contrast": round(self.thermal_contrast, 2),
            "occlusion": round(self.occlusion, 2),
            "fire_hotspot": bool(self.fire_hotspot),
            "hot_debris": bool(self.hot_debris),
            "orientation": self.orientation,
            "field_of_view_deg": round(self.field_of_view_deg, 1),
            "range_m": round(self.range_m, 1),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "health_score": round(self.health_score, 1),
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "raw_data": self.raw_data,
        }


@dataclass
class CameraThermalCorrelation:
    """Cross-modal correlation analysis between Optical Camera and Thermal Infrared observations."""
    victim_id: str
    camera_id: str = "CAM-001"
    thermal_camera_id: str = "THERMAL-001"
    thermal_id: str = "THERMAL-001"
    camera_state: Optional[Any] = None
    thermal_detection: Optional[Any] = None
    camera_confidence: float = 0.0
    camera_occlusion: float = 0.0
    thermal_temperature: float = 20.0
    thermal_delta: float = 2.0
    correlation_case: CameraCorrelationCase = CameraCorrelationCase.NO_EVIDENCE
    combined_confidence: float = 0.0      # 0.0 - 1.0
    synergy_bonus: float = 0.0
    single_modality_clamped: bool = False
    explainable_summary: str = "No cross-modal sensor data available."
    evidence_tokens: List[str] = field(default_factory=list)
    penalties_applied: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "victim_id": self.victim_id,
            "camera_id": self.camera_id,
            "thermal_id": self.thermal_id,
            "thermal_camera_id": self.thermal_camera_id,
            "camera_state": self.camera_state.value if hasattr(self.camera_state, "value") else str(self.camera_state) if self.camera_state else "NO_DETECTION",
            "thermal_detection": self.thermal_detection.value if hasattr(self.thermal_detection, "value") else str(self.thermal_detection) if self.thermal_detection else "NO_HEAT",
            "camera_confidence": round(self.camera_confidence, 2),
            "camera_occlusion": round(self.camera_occlusion, 2),
            "thermal_temperature": round(self.thermal_temperature, 1),
            "thermal_delta": round(self.thermal_delta, 1),
            "correlation_case": self.correlation_case.value if hasattr(self.correlation_case, "value") else str(self.correlation_case),
            "combined_confidence": round(self.combined_confidence, 2),
            "synergy_bonus": round(self.synergy_bonus, 2),
            "single_modality_clamped": bool(self.single_modality_clamped),
            "explainable_summary": self.explainable_summary,
            "evidence_tokens": list(self.evidence_tokens),
            "penalties_applied": list(self.penalties_applied),
            "timestamp": self.timestamp,
        }


class CameraSensorInterface(ABC):
    """Abstract Hardware / Simulator Interface for Optical Camera modules."""
    @abstractmethod
    def read_camera(self, camera_id: Optional[str] = None, victim_id: Optional[str] = None) -> CameraReading:
        pass

    @abstractmethod
    def get_camera_health(self, camera_id: Optional[str] = None) -> SensorHealth:
        pass


class ThermalCameraSensorInterface(ABC):
    """Abstract Hardware / Simulator Interface for Thermal Infrared Camera modules."""
    @abstractmethod
    def read_thermal(self, camera_id: Optional[str] = None, victim_id: Optional[str] = None) -> ThermalCameraReading:
        pass

    @abstractmethod
    def get_thermal_health(self, camera_id: Optional[str] = None) -> SensorHealth:
        pass


# --------------------------------------------------------------------------- #
# Victim Profile
# --------------------------------------------------------------------------- #

@dataclass
class SensorSignatureRange:
    """Expected (min, max) sensor output for a victim in a given physiological state."""
    thermal_imaging_c: tuple       # deg C
    pir_motion: tuple              # 0.0-1.0
    acoustic_db: tuple             # dB
    co2_ppm: tuple                 # ppm above ambient (~400ppm baseline)
    heart_rate_radar_bpm: tuple    # bpm, 0 = no cardiac signal detected
    rgb_camera_conf: tuple         # 0.0-1.0
    water_level_cm: tuple = (0.0, 0.0)   # default (0,0) = "not a flood scenario / dry"
    water_flow_ms: tuple = (0.0, 0.0)    # default (0,0) = "not a flood scenario / no current"
    gas_concentration_ppm: tuple = (0.0, 0.0)  # default (0,0) = ambient
    smoke_density_pct: tuple = (0.0, 0.0)      # default (0,0) = clear air


@dataclass
class VictimProfile:
    victim_id: str
    label: str
    status: VictimStatus
    location: GPSCoordinate
    burial_depth_m: float
    signature_range: SensorSignatureRange
    notes: str = ""
    initial_water_level_cm: float = 0.0
    water_rising_rate_cm_per_cycle: float = 0.0
    initial_water_flow_ms: float = 0.0
    water_flow_volatility_ms: float = 0.3   # how choppy/turbulent the current is at this location
    age: Optional[int] = None
    gender: Optional[str] = None
    consciousness: Optional[str] = None
    mobility: Optional[str] = None
    injury_notes: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


# --------------------------------------------------------------------------- #
# Detection Result (fusion engine output)
# --------------------------------------------------------------------------- #

@dataclass
class DetectionResult:
    victim_id: str
    location: GPSCoordinate
    predicted_status: VictimStatus
    triage_priority: TriagePriority
    survival_confidence: float          # 0.0-1.0, fused probability victim is alive
    contributing_sensors: list          # list[SensorType.value]
    fusion_score_breakdown: dict        # per-sensor-type normalized sub-scores
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    stale: bool = False                 # true if no fresh readings within timeout window

    def to_dict(self) -> dict:
        d = asdict(self)
        d["predicted_status"] = self.predicted_status.value
        d["triage_priority"] = self.triage_priority.value
        return d


# --------------------------------------------------------------------------- #
# Rescue Team Status
# --------------------------------------------------------------------------- #

@dataclass
class RescueTeamStatus:
    team_id: str
    team_name: str
    location: GPSCoordinate
    availability: TeamAvailability
    assigned_victim_id: Optional[str] = None
    eta_minutes: Optional[float] = None
    members: int = 2
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["availability"] = self.availability.value
        return d


# --------------------------------------------------------------------------- #
# Team Roster — individually-tracked members (Step 20)
# --------------------------------------------------------------------------- #
# RescueTeamStatus.members is the *official roster count* for a team (up to
# 500 - report/stats figure). Live-GPS-tracking all 500 in a browser demo is
# impractical, so only a small tracked sample (TRACKED_MEMBER_SAMPLE_SIZE in
# api.py) gets an individual TeamMember record with its own position/status.

class MemberStatus(str, Enum):
    HOLD = "hold"           # awaiting CMD leader assignment (Step 21-23 safety gate)
    EN_ROUTE = "en_route"   # assigned + moving toward a victim
    ARRIVED = "arrived"     # reached the assigned victim's location
    RESCUED = "rescued"     # completed rescue of assigned survivor
    COMPLETED = "completed" # mission completed


@dataclass
class TeamMember:
    """
    One individually-tracked rescue-team member (the 'sample' subset out
    of a team's full roster count - see TRACKED_MEMBER_SAMPLE_SIZE in
    api.py). Has its own live location + assignment state, unlike
    RescueTeamStatus which is one aggregate record per whole team.
    """
    member_id: str
    callsign: str
    team_id: str
    location: GPSCoordinate
    full_name: str = ""            # Step 29: human-readable name for the roster table
    role: str = "Rescuer"          # Step 29: "Leader" | "Rescuer" - squad's 1st member is auto-Leader
    status: MemberStatus = MemberStatus.HOLD
    assigned_victim_id: Optional[str] = None
    assigned_job_id: Optional[str] = None
    assigned_at: Optional[str] = None
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    personnel_id: Optional[str] = None  # Link back to persistent DB personnel ledger
    scenarios: list[str] = field(default_factory=list)
    location_source: str = "SIMULATED"  # "SIMULATED" | "PHONE_GPS"
    accuracy_m: Optional[float] = None
    speed_mps: Optional[float] = None
    heading_deg: Optional[float] = None
    gps_timestamp: Optional[str] = None
    gps_status: str = "STANDBY"         # STANDBY | WAITING_FOR_PERMISSION | WAITING_FOR_GPS | TRACKING | STALE | GPS_UNAVAILABLE | PERMISSION_DENIED
    navigation_status: Optional[str] = None       # "ON_TRACK" | "WRONG_DIRECTION" | "ARRIVED" | None
    target_bearing_deg: Optional[float] = None
    direction_delta_deg: Optional[float] = None
    heading_difference_deg: Optional[float] = None
    distance_to_target_m: Optional[float] = None
    distance_trend: Optional[str] = None          # "APPROACHING" | "MOVING_AWAY" | "STABLE" | None
    direction_guidance: Optional[str] = None
    arrived_at: Optional[str] = None
    active_command_id: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


# --------------------------------------------------------------------------- #
# Himalaya Avalanche Scenario — 4 fixed victim profiles
# --------------------------------------------------------------------------- #
# Site: simulated avalanche debris field near Rohtang Pass approach,
# Himachal Pradesh, India (~3,950 m). Coordinates are spread ~30-70m apart
# across the debris cone, which is realistic for a search-grid sized site.

HIMALAYA_SITE_ORIGIN = GPSCoordinate(latitude=32.3739, longitude=77.2491, altitude_m=3950)

HIMALAYA_VICTIMS: list[VictimProfile] = [

    VictimProfile(
        victim_id="V1",
        label="Victim 1 - Deceased",
        status=VictimStatus.DECEASED,
        location=GPSCoordinate(latitude=32.37401, longitude=77.24898, altitude_m=3946),
        burial_depth_m=1.8,
        signature_range=SensorSignatureRange(
            thermal_imaging_c=(-5.0, 2.0),        # cooled to near-ambient snow temp
            pir_motion=(0.0, 0.02),               # no movement
            acoustic_db=(0.0, 5.0),               # no breathing/tapping sound
            co2_ppm=(400.0, 420.0),                # ambient, no exhalation
            heart_rate_radar_bpm=(0.0, 0.0),      # no cardiac doppler signal
            rgb_camera_conf=(0.0, 0.1),
        ),
        notes="No vital signs on any channel; thermal signature has decayed to ambient.",
    ),

    VictimProfile(
        victim_id="V2",
        label="Victim 2 - Critical",
        status=VictimStatus.CRITICAL,
        location=GPSCoordinate(latitude=32.37378, longitude=77.24935, altitude_m=3948),
        burial_depth_m=1.2,
        signature_range=SensorSignatureRange(
            thermal_imaging_c=(8.0, 15.0),         # weak but present body heat
            pir_motion=(0.01, 0.08),               # minimal, labored movement
            acoustic_db=(5.0, 15.0),               # faint/shallow breathing only
            co2_ppm=(600.0, 900.0),                # elevated in small air pocket
            heart_rate_radar_bpm=(35.0, 55.0),     # weak, low bpm - hypothermic/shock
            rgb_camera_conf=(0.1, 0.3),
        ),
        notes="Faint vitals consistent with hypothermia/shock. Highest rescue priority.",
    ),

    VictimProfile(
        victim_id="V3",
        label="Victim 3 - Minor Injury",
        status=VictimStatus.MINOR_INJURY,
        location=GPSCoordinate(latitude=32.37415, longitude=77.24960, altitude_m=3952),
        burial_depth_m=0.4,
        signature_range=SensorSignatureRange(
            thermal_imaging_c=(20.0, 30.0),        # near-normal body heat, close to surface
            pir_motion=(0.15, 0.45),               # conscious, moving/struggling
            acoustic_db=(25.0, 45.0),              # audible breathing, possible calls
            co2_ppm=(900.0, 1500.0),               # strong exhalation buildup
            heart_rate_radar_bpm=(80.0, 110.0),    # elevated from exertion/stress
            rgb_camera_conf=(0.4, 0.7),
        ),
        notes="Shallow burial, conscious and responsive; stable but needs extraction.",
    ),

    VictimProfile(
        victim_id="V4",
        label="Victim 4 - Safe",
        status=VictimStatus.SAFE,
        location=GPSCoordinate(latitude=32.37450, longitude=77.24870, altitude_m=3958),
        burial_depth_m=0.0,
        signature_range=SensorSignatureRange(
            thermal_imaging_c=(28.0, 34.0),        # normal surface body temp
            pir_motion=(0.5, 1.0),                 # freely moving/walking
            acoustic_db=(40.0, 70.0),              # normal speech volume
            co2_ppm=(1500.0, 2500.0),              # strong, unobstructed exhalation
            heart_rate_radar_bpm=(70.0, 100.0),    # normal active bpm
            rgb_camera_conf=(0.8, 1.0),            # clearly visible, unburied
        ),
        notes="Unburied, ambulatory survivor found on debris surface near the edge of the slide.",
    ),
]


# --------------------------------------------------------------------------- #
# Convenience lookup
# --------------------------------------------------------------------------- #

def get_victim_by_id(victim_id: str) -> Optional[VictimProfile]:
    return next((v for v in HIMALAYA_VICTIMS if v.victim_id == victim_id), None)


# --------------------------------------------------------------------------- #
# Admin-added victim templates (Step 12)
# --------------------------------------------------------------------------- #
# When an admin adds a person to a RUNNING scenario, they only supply
# victim_id/label/status(HIGH|MEDIUM|LOW)/location - not a full sensor
# signature. These templates translate that coarse admin intent into a
# SensorSignatureRange that reliably fuses into the matching TriageClass
# (see fusion_engine.py's HIGH/MEDIUM/LOW_THRESHOLD_PCT), so "admin says
# HIGH" and "fusion engine classifies HIGH" actually agree.
ADMIN_PRIORITY_TEMPLATES: dict = {
    "HIGH": {
        "status": VictimStatus.CRITICAL,
        "burial_depth_m": 1.2,
        "signature_range": SensorSignatureRange(
            thermal_imaging_c=(8.0, 15.0),
            pir_motion=(0.01, 0.08),
            acoustic_db=(5.0, 15.0),
            co2_ppm=(600.0, 900.0),
            heart_rate_radar_bpm=(35.0, 55.0),
            rgb_camera_conf=(0.1, 0.3),
        ),
        "notes": "Admin-added — HIGH priority (faint vitals, needs urgent extraction).",
    },
    "MEDIUM": {
        "status": VictimStatus.MINOR_INJURY,
        "burial_depth_m": 0.4,
        "signature_range": SensorSignatureRange(
            thermal_imaging_c=(20.0, 30.0),
            pir_motion=(0.15, 0.45),
            acoustic_db=(25.0, 45.0),
            co2_ppm=(900.0, 1500.0),
            heart_rate_radar_bpm=(80.0, 110.0),
            rgb_camera_conf=(0.4, 0.7),
        ),
        "notes": "Admin-added — MEDIUM priority (conscious, stable, needs extraction).",
    },
    "LOW": {
        "status": VictimStatus.UNKNOWN,
        "burial_depth_m": 2.0,
        "signature_range": SensorSignatureRange(
            thermal_imaging_c=(-2.0, 5.0),
            pir_motion=(0.0, 0.03),
            acoustic_db=(1.0, 8.0),
            co2_ppm=(420.0, 550.0),
            heart_rate_radar_bpm=(0.0, 20.0),   # below HR_NOISE_FLOOR_BPM (15) - reads mostly as noise
            rgb_camera_conf=(0.0, 0.1),
        ),
        "notes": "Admin-added — LOW priority (weak/unreliable signal, recommend re-scan).",
    },
}


# --------------------------------------------------------------------------- #
# Subsurface UWB Bioradar Simulation Models (RIDGEWATCH Landslide Module)
# --------------------------------------------------------------------------- #

class SubsurfaceSoilType(str, Enum):
    DRY_SOIL = "dry_soil"
    SANDY_SOIL = "sandy_soil"
    CLAY_SOIL = "clay_soil"
    WET_SOIL = "wet_soil"
    SATURATED_MUD = "saturated_mud"
    MIXED_DEBRIS_SOIL = "mixed_debris_soil"


class SignalQuality(str, Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    POOR = "POOR"
    UNRELIABLE = "UNRELIABLE"
    NO_DETECTION = "NO_DETECTION"


class TargetOrientation(str, Enum):
    FACING_SENSOR = "FACING_SENSOR"
    SIDEWAYS = "SIDEWAYS"
    AWAY_FROM_SENSOR = "AWAY_FROM_SENSOR"
    UNKNOWN = "UNKNOWN"


class TargetMovement(str, Enum):
    STATIONARY = "STATIONARY"
    MINOR_MOVEMENT = "MINOR_MOVEMENT"
    STRUGGLING = "STRUGGLING"
    IRREGULAR_MICRO_MOVEMENT = "IRREGULAR_MICRO_MOVEMENT"


class RespirationPattern(str, Enum):
    NORMAL = "NORMAL"              # 12-24 RPM steady
    SLOW = "SLOW"                  # 6-12 RPM
    FAST = "FAST"                  # 24-35 RPM
    IRREGULAR = "IRREGULAR"        # Variable rhythm
    VERY_WEAK = "VERY_WEAK"        # Extremely faint chest displacement
    INTERMITTENT = "INTERMITTENT"  # Periodic pauses / apnea


class HeartbeatPattern(str, Enum):
    NORMAL = "NORMAL"              # 60-80 BPM
    ELEVATED = "ELEVATED"          # 90-130 BPM
    WEAK = "WEAK"                  # 40-60 BPM
    INTERMITTENT = "INTERMITTENT"
    UNDETECTABLE = "UNDETECTABLE"  # Faded / below noise floor


class MicroMotionLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"
    NONE = "NONE"


class ObstacleType(str, Enum):
    ROCK = "ROCK"
    ROOT = "ROOT"
    METALLIC_DEBRIS = "METALLIC_DEBRIS"
    CONCRETE_FRAGMENT = "CONCRETE_FRAGMENT"
    PIPE = "PIPE"
    LAYER_BOUNDARY = "LAYER_BOUNDARY"
    SURFACE_REFLECTION = "SURFACE_REFLECTION"
    RANDOM_CLUTTER = "RANDOM_CLUTTER"
    VOID = "VOID"
    PERIODIC_VIBRATION = "PERIODIC_VIBRATION"


@dataclass
class SubsurfaceTargetState:
    """
    Subsurface target state maintaining strict isolation between
    Ground Truth (simulation only) and Estimated DSP outputs.
    """
    target_id: str
    is_human: bool = True
    is_alive: bool = True
    ground_truth_depth_m: float = 1.0  # GROUND TRUTH - SIMULATION ONLY
    estimated_depth_m: float = 1.0     # DSP ESTIMATED FROM SYNTHETIC RADAR SIGNAL
    depth_uncertainty_m: float = 0.1   # Estimated measurement uncertainty
    depth_confidence: float = 0.85
    respiration_rate_rpm: float = 16.0 # Extracted from slow-time spectrum
    heart_rate_bpm: float = 72.0       # Extracted from slow-time spectrum
    micro_motion_detected: bool = True
    survivor_confidence: float = 0.85  # 0.0 to 1.0
    snr_db: float = 18.0
    triage_class: str = "HIGH"
    signal_quality: str = "GOOD"
    target_type: str = "HUMAN_SURVIVOR"
    orientation: str = "FACING_SENSOR"
    is_shadowed: bool = False
    rcs_m2: float = 0.85

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "is_human": self.is_human,
            "is_alive": self.is_alive,
            "ground_truth_depth_m": round(self.ground_truth_depth_m, 2),
            "estimated_depth_m": round(self.estimated_depth_m, 2),
            "depth_uncertainty_m": round(self.depth_uncertainty_m, 2),
            "depth_confidence": round(self.depth_confidence, 3),
            "respiration_rate_rpm": round(self.respiration_rate_rpm, 1),
            "heart_rate_bpm": round(self.heart_rate_bpm, 1),
            "micro_motion_detected": self.micro_motion_detected,
            "survivor_confidence": round(self.survivor_confidence, 3),
            "snr_db": round(self.snr_db, 1),
            "triage_class": self.triage_class,
            "signal_quality": self.signal_quality,
            "target_type": self.target_type,
            "orientation": self.orientation,
            "is_shadowed": self.is_shadowed,
            "rcs_m2": round(self.rcs_m2, 2),
        }


@dataclass
class SubsurfaceSimulationConfig:
    """Configurable simulation parameters for subsurface radar environment."""
    scenario_id: str = "landslide"
    soil_type: SubsurfaceSoilType = SubsurfaceSoilType.WET_SOIL
    soil_moisture_pct: float = 55.0
    clay_fraction: float = 0.25
    soil_density_g_cm3: float = 1.6
    clutter_level: str = "medium"           # low, medium, high
    sensor_noise: str = "medium"            # low, medium, high
    survivor_mode: str = "one"              # none, one, multiple, challenge, metallic_obstacle
    survivor_alive: bool = True
    burial_depth_m: float = 1.5             # Ground truth burial depth for primary victim
    breathing_rate_rpm: float = 16.0
    heart_rate_bpm: float = 72.0
    micro_motion: bool = True
    micro_motion_level: str = "medium"      # high, medium, low, very_low, none
    respiration_pattern: str = "normal"     # normal, slow, fast, irregular, very_weak, intermittent
    heartbeat_pattern: str = "normal"       # normal, elevated, weak, intermittent, undetectable
    target_orientation: str = "facing_sensor" # facing_sensor, sideways, away_from_sensor, unknown
    target_movement: str = "stationary"     # stationary, minor_movement, struggling, irregular_micro_movement
    obstacles: Optional[List[Dict[str, Any]]] = None
    enable_layer_interfaces: bool = True
    enable_shadowing: bool = True
    enable_ringing: bool = True
    signal_strength_db: float = 20.0
    layered_profile: Optional[List[Dict[str, Any]]] = None
    preset_id: Optional[str] = None
    is_running: bool = True
    seed: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "soil_type": self.soil_type.value if isinstance(self.soil_type, SubsurfaceSoilType) else str(self.soil_type),
            "soil_moisture_pct": self.soil_moisture_pct,
            "clay_fraction": self.clay_fraction,
            "soil_density_g_cm3": self.soil_density_g_cm3,
            "clutter_level": self.clutter_level,
            "sensor_noise": self.sensor_noise,
            "survivor_mode": self.survivor_mode,
            "survivor_alive": self.survivor_alive,
            "burial_depth_m": self.burial_depth_m,
            "breathing_rate_rpm": self.breathing_rate_rpm,
            "heart_rate_bpm": self.heart_rate_bpm,
            "micro_motion": self.micro_motion,
            "micro_motion_level": self.micro_motion_level,
            "respiration_pattern": self.respiration_pattern,
            "heartbeat_pattern": self.heartbeat_pattern,
            "target_orientation": self.target_orientation,
            "target_movement": self.target_movement,
            "obstacles": self.obstacles,
            "enable_layer_interfaces": self.enable_layer_interfaces,
            "enable_shadowing": self.enable_shadowing,
            "enable_ringing": self.enable_ringing,
            "signal_strength_db": self.signal_strength_db,
            "layered_profile": self.layered_profile,
            "preset_id": self.preset_id,
            "is_running": self.is_running,
            "seed": self.seed,
        }


@dataclass
class SubsurfaceRadarTelemetry:
    """
    Subsurface UWB bioradar telemetry package.
    Clearly marked as SIMULATED data with no physical hardware claims.
    """
    device_id: str = "DEV-UWB-RADAR-01"
    is_simulated: bool = True
    simulation_label: str = "SIMULATION MODE — NO PHYSICAL UWB HARDWARE"
    status: str = "SCANNING"  # SCANNING, TARGET_DETECTED, NO_TARGET, OFFLINE
    signal_quality: str = "GOOD"  # EXCELLENT, GOOD, DEGRADED, POOR, UNRELIABLE, NO_DETECTION
    scenario_state: str = "LANDSLIDE_OCCURRED"
    soil_type: str = "wet_soil"
    soil_moisture_pct: float = 55.0
    estimated_permittivity: float = 18.5
    soil_model_status: str = "SIMULATED SOIL MODEL (0–6.0m)"
    max_depth_m: float = 6.0
    targets: list[SubsurfaceTargetState] = field(default_factory=list)
    primary_target: Optional[SubsurfaceTargetState] = None
    radargram_profile: list[dict[str, float]] = field(default_factory=list)
    respiration_waveform: list[float] = field(default_factory=list)
    cardiac_waveform: list[float] = field(default_factory=list)
    obstacles_detected: list[dict[str, Any]] = field(default_factory=list)
    layer_strata: list[dict[str, Any]] = field(default_factory=list)
    simulation_seed: int = 42
    snr_db: float = 16.5
    overall_confidence_pct: float = 85.0
    triage_class: str = "HIGH"
    sps_score: float = 145.0
    simulated_latitude: float = 32.2435
    simulated_longitude: float = 77.1895
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def survivor_confidence(self) -> float:
        return round(self.overall_confidence_pct / 100.0, 3)

    @property
    def burial_depth_m(self) -> float:
        return self.primary_target.ground_truth_depth_m if self.primary_target else 0.0

    @property
    def depth_uncertainty_m(self) -> float:
        return self.primary_target.depth_uncertainty_m if self.primary_target else 0.0

    @property
    def survivor_present(self) -> bool:
        return len(self.targets) > 0 and any(t.is_human and t.is_alive for t in self.targets)

    @property
    def all_targets(self) -> list[SubsurfaceTargetState]:
        return self.targets

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "is_simulated": self.is_simulated,
            "simulation_label": self.simulation_label,
            "status": self.status,
            "signal_quality": self.signal_quality,
            "scenario_state": self.scenario_state,
            "soil_type": self.soil_type,
            "soil_moisture_pct": self.soil_moisture_pct,
            "estimated_permittivity": round(self.estimated_permittivity, 2),
            "soil_model_status": self.soil_model_status,
            "max_depth_m": self.max_depth_m,
            "targets": [t.to_dict() for t in self.targets],
            "primary_target": self.primary_target.to_dict() if self.primary_target else None,
            "radargram_profile": self.radargram_profile,
            "respiration_waveform": self.respiration_waveform,
            "cardiac_waveform": self.cardiac_waveform,
            "obstacles_detected": self.obstacles_detected,
            "layer_strata": self.layer_strata,
            "simulation_seed": self.simulation_seed,
            "snr_db": round(self.snr_db, 1),
            "overall_confidence_pct": round(self.overall_confidence_pct, 1),
            "triage_class": self.triage_class,
            "sps_score": round(self.sps_score, 1),
            "simulated_location": {
                "latitude": self.simulated_latitude,
                "longitude": self.simulated_longitude,
                "is_simulated": True,
                "label": "SIMULATED LOCATION",
            },
            "timestamp": self.timestamp,
        }

    # quick self-test / demo when run directly: python models.py
    for v in HIMALAYA_VICTIMS:
        print(v.label, "->", v.status.value, "@", v.location.as_tuple())
