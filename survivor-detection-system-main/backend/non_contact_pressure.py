"""
backend/non_contact_pressure.py
---------------------------------
RIDGEWATCH Non-Contact Flood-Water Level & Hydrostatic Pressure Estimation Module.

PHYSICAL PRINCIPLE:
Hydrostatic pressure at depth h is defined by fluid statics:
    P = ρ · g · h

Where:
    - ρ (rho) = Fluid density (1000.0 kg/m³ for fresh water)
    - g = Acceleration due to gravity (9.80665 m/s²)
    - h = Actual water-column depth in metres relative to the pressure measurement datum.

NON-CONTACT SENSING GEOMETRY:
1. Downward-facing sensor (Airborne Ultrasonic Transceiver / 60-80 GHz FMCW Radar Level Gauge)
   is mounted at a fixed vertical distance `sensor_mount_height_m` above the measurement datum (z = 0).
2. Sensor measures time-of-flight to the air-water interface to determine `measured_surface_distance_m`.
3. Water-column depth:
       water_depth_m = max(0.0, (sensor_mount_height_m - pressure_datum_m) - measured_surface_distance_m)
4. Hydrostatic Pressure:
       pressure_pa  = ρ · g · water_depth_m
       pressure_kpa = pressure_pa / 1000.0

VALIDATION & SAFETY RULES:
- Reject negative distance (d < 0).
- Reject distance greater than configured maximum sensor range (d > sensor_max_range_m).
- Reject stale readings exceeding timeout window.
- Reject sudden impossible physical jumps (|Δd| / Δt > max_jump_rate_m_s).
- Reject null, NaN, Infinity, or missing sensor data.
- Never silently convert invalid values to zero pressure; flag status as UNAVAILABLE/INVALID.
"""

from __future__ import annotations

import os
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List, Union
from collections import deque


@dataclass
class NonContactPressureConfig:
    """
    Configuration parameters for non-contact ultrasonic / radar water pressure estimation.
    Supports environment variable overrides.
    """
    sensor_type: str = field(
        default_factory=lambda: os.getenv("NONCONTACT_SENSOR_TYPE", "ultrasonic").lower()
    )
    sensor_mount_height_m: float = field(
        default_factory=lambda: float(os.getenv("NONCONTACT_SENSOR_MOUNT_HEIGHT_M", "5.0"))
    )
    pressure_datum_m: float = field(
        default_factory=lambda: float(os.getenv("NONCONTACT_PRESSURE_DATUM_M", "0.0"))
    )
    sensor_max_range_m: float = field(
        default_factory=lambda: float(os.getenv("NONCONTACT_SENSOR_MAX_RANGE_M", "10.0"))
    )
    sensor_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("NONCONTACT_SENSOR_TIMEOUT_SECONDS", "30.0"))
    )
    water_density_kg_m3: float = field(
        default_factory=lambda: float(os.getenv("NONCONTACT_WATER_DENSITY_KG_M3", "1000.0"))
    )
    gravity_m_s2: float = field(
        default_factory=lambda: float(os.getenv("NONCONTACT_GRAVITY_M_S2", "9.80665"))
    )
    max_jump_rate_m_s: float = field(
        default_factory=lambda: float(os.getenv("NONCONTACT_MAX_RISE_RATE_M_PER_SECOND", os.getenv("NONCONTACT_MAX_JUMP_RATE_M_S", "3.0")))
    )
    maximum_allowed_rise_rate_m_per_second: float = field(
        default_factory=lambda: float(os.getenv("NONCONTACT_MAX_RISE_RATE_M_PER_SECOND", "0.5"))
    )
    min_range_m: float = 0.02  # Ultrasonic/Radar physical dead-band limit

    def validate(self) -> bool:
        """Validate config physical feasibility."""
        if self.sensor_mount_height_m <= 0.0:
            return False
        if self.sensor_max_range_m <= 0.0 or self.sensor_max_range_m < self.sensor_mount_height_m:
            return False
        if self.water_density_kg_m3 <= 0.0 or self.gravity_m_s2 <= 0.0:
            return False
        if self.sensor_timeout_seconds <= 0.0 or self.max_jump_rate_m_s <= 0.0:
            return False
        return True


@dataclass
class NonContactSensorReading:
    """Raw telemetry reading received from non-contact downward-ranging sensor."""
    reading_id: str = field(default_factory=lambda: f"NC-{uuid.uuid4().hex[:8]}")
    sensor_id: str = "ENV-WATER-NC01"
    device_id: str = "DEV-WATER-NC01"
    sensor_type: str = "ultrasonic"  # "ultrasonic", "radar", "lidar"
    sensor_mount_height_m: float = 6.0
    measured_surface_distance_m: Optional[float] = None
    water_depth_m: Optional[float] = None
    timestamp: Optional[str] = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    signal_quality: float = 1.0  # 0.0 - 1.0
    confidence: float = 1.0      # 0.0 - 1.0
    is_live_sensor: bool = False
    data_source_mode: str = "SIMULATED_TESTING"
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NonContactPressureEstimate:
    """
    Structured outcome of non-contact water level and hydrostatic pressure computation.
    """
    success: bool = True
    sensor_type: str = "ultrasonic"
    measured_surface_distance_m: Optional[float] = None
    sensor_mount_height_m: float = 5.0
    pressure_datum_m: float = 0.0
    water_depth_m: Optional[float] = None
    water_level_rise_rate_mps: Optional[float] = None
    water_level_rise_rate_cm_min: Optional[float] = None
    estimated_pressure_pa: Optional[float] = None
    estimated_pressure_kpa: Optional[float] = None
    reading_timestamp: Optional[str] = None
    reading_quality: str = "VALID"  # "VALID", "DEGRADED", "STALE", "INVALID", "SENSOR_OFFLINE", "CALIBRATION_REQUIRED"
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    status_message: str = "Nominal hydrostatic pressure estimation"
    pressure_source: str = "non_contact_sensor_estimation"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "sensor_type": self.sensor_type,
            "measured_surface_distance_m": self.measured_surface_distance_m,
            "sensor_mount_height_m": self.sensor_mount_height_m,
            "pressure_datum_m": self.pressure_datum_m,
            "water_depth_m": self.water_depth_m,
            "water_level_rise_rate_mps": self.water_level_rise_rate_mps,
            "water_level_rise_rate_cm_min": self.water_level_rise_rate_cm_min,
            "estimated_pressure_pa": self.estimated_pressure_pa,
            "estimated_pressure_kpa": self.estimated_pressure_kpa,
            "reading_timestamp": self.reading_timestamp,
            "reading_quality": self.reading_quality,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
            "status_message": self.status_message,
            "pressure_source": self.pressure_source,
            "metadata": self.metadata,
        }


def _parse_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO UTC timestamp safely."""
    if not ts_str:
        return None
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.fromisoformat(ts_str)
    except Exception:
        return None


def check_sensor_freshness(
    timestamp_str: Optional[str],
    timeout_seconds: float = 30.0,
    current_time: Optional[datetime] = None,
) -> Tuple[bool, float]:
    """
    Check if a sensor reading timestamp is within the acceptable freshness window.

    Returns:
        (is_fresh: bool, age_seconds: float)
    """
    if not timestamp_str:
        return False, float("inf")
    dt = _parse_timestamp(timestamp_str)
    if not dt:
        return False, float("inf")
    now = current_time or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_s = max(0.0, (now - dt).total_seconds())
    return (age_s <= timeout_seconds), age_s


def detect_impossible_jump(
    current_distance_m: float,
    previous_distance_m: Optional[float],
    delta_seconds: float = 1.0,
    max_allowed_rate_mps: float = 3.0,
) -> Tuple[bool, float]:
    """
    Detect impossible physical jumping in sensor surface distance.

    Returns:
        (is_impossible_jump: bool, calculated_rate_mps: float)
    """
    if previous_distance_m is None or math.isnan(previous_distance_m):
        return False, 0.0
    dt = max(0.05, delta_seconds)
    delta_d = abs(current_distance_m - previous_distance_m)
    rate_mps = delta_d / dt
    return (rate_mps > max_allowed_rate_mps), round(rate_mps, 3)


def calculate_water_level_rise_rate(
    current_depth_m: float,
    previous_depth_m: Optional[float],
    delta_seconds: float = 1.0,
) -> Tuple[float, float]:
    """
    Calculate rate of water level rise.

    Returns:
        (rate_m_per_second: float, rate_cm_per_minute: float)
    """
    if previous_depth_m is None or math.isnan(previous_depth_m):
        return 0.0, 0.0
    dt = max(0.05, delta_seconds)
    rate_mps = (current_depth_m - previous_depth_m) / dt
    rate_cm_min = rate_mps * 100.0 * 60.0
    return round(rate_mps, 4), round(rate_cm_min, 2)


def validate_sensor_reading(
    distance_m: Optional[float],
    config: NonContactPressureConfig,
    timestamp_str: Optional[str] = None,
    previous_reading: Optional[Dict[str, Any]] = None,
    current_time: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """
    Strict validation of downward-ranging non-contact sensor telemetry.

    Returns:
        (is_valid: bool, status_reason: str)
    """
    # 1. Check for None, NaN, Infinity or non-numeric
    if distance_m is None or not isinstance(distance_m, (int, float)):
        return False, "MISSING_DATA"
    if math.isnan(distance_m) or math.isinf(distance_m):
        return False, "INVALID_NUMERIC"

    # 2. Reject negative distance
    if distance_m < 0.0:
        return False, "NEGATIVE_DISTANCE_REJECTED"

    # 3. Reject distance exceeding configured max sensor range
    if distance_m > config.sensor_max_range_m:
        return False, "OUT_OF_RANGE_REJECTED"

    # 4. Check for stale reading if timestamp provided
    now = current_time or datetime.now(timezone.utc)
    if timestamp_str:
        is_fresh, age_s = check_sensor_freshness(timestamp_str, config.sensor_timeout_seconds, now)
        if not is_fresh:
            return False, "STALE_READING_REJECTED"

    # 5. Check for impossible sudden jump against previous reading
    if previous_reading and "measured_surface_distance_m" in previous_reading:
        prev_d = previous_reading.get("measured_surface_distance_m")
        prev_ts_str = previous_reading.get("reading_timestamp")
        if prev_d is not None and isinstance(prev_d, (int, float)) and not math.isnan(prev_d):
            prev_dt = _parse_timestamp(prev_ts_str)
            dt_s = 1.0  # default 1 second step if no prev timestamp
            if prev_dt and timestamp_str:
                curr_dt = _parse_timestamp(timestamp_str)
                if curr_dt and prev_dt:
                    raw_dt = abs((curr_dt - prev_dt).total_seconds())
                    dt_s = raw_dt if raw_dt >= 0.05 else 1.0

            is_jump, _ = detect_impossible_jump(distance_m, prev_d, dt_s, config.max_jump_rate_m_s)
            if is_jump:
                return False, "IMPOSSIBLE_JUMP_REJECTED"

    return True, "VALID"


def calculate_water_depth(
    surface_distance_m: float,
    mount_height_m: float,
    datum_m: float = 0.0,
) -> float:
    """
    Calculate water-column depth from non-contact surface distance.

    Formula:
        water_depth_m = max(0.0, (mount_height_m - datum_m) - surface_distance_m)
    """
    effective_zero = mount_height_m - datum_m
    depth = effective_zero - surface_distance_m
    return round(max(0.0, depth), 4)


def calculate_hydrostatic_pressure(
    water_depth_m: float,
    density_kg_m3: float = 1000.0,
    gravity_m_s2: float = 9.80665,
) -> Tuple[float, float]:
    """
    Calculate hydrostatic gauge pressure from water column depth.

    Formula:
        P_pa  = ρ · g · h
        P_kpa = P_pa / 1000.0

    Returns:
        (pressure_pa: float, pressure_kpa: float)
    """
    if water_depth_m <= 0.0:
        return 0.0, 0.0

    pa = density_kg_m3 * gravity_m_s2 * water_depth_m
    kpa = pa / 1000.0
    return round(pa, 3), round(kpa, 5)


def estimate_pressure_from_sensor(
    measured_surface_distance_m: Optional[float],
    config: Optional[NonContactPressureConfig] = None,
    timestamp_str: Optional[str] = None,
    signal_quality: float = 1.0,
    previous_reading: Optional[Dict[str, Any]] = None,
    current_time: Optional[datetime] = None,
) -> NonContactPressureEstimate:
    """
    Primary estimation routine: Validates non-contact sensor reading,
    computes water depth, calculates rise rate, and derives hydrostatic pressure.
    """
    cfg = config or NonContactPressureConfig()
    ts = timestamp_str or datetime.now(timezone.utc).isoformat()

    is_valid, reason = validate_sensor_reading(
        distance_m=measured_surface_distance_m,
        config=cfg,
        timestamp_str=ts,
        previous_reading=previous_reading,
        current_time=current_time,
    )

    if not is_valid:
        quality_map = {
            "NEGATIVE_DISTANCE_REJECTED": "INVALID",
            "OUT_OF_RANGE_REJECTED": "INVALID",
            "STALE_READING_REJECTED": "STALE",
            "IMPOSSIBLE_JUMP_REJECTED": "INVALID",
            "MISSING_DATA": "SENSOR_OFFLINE",
            "INVALID_NUMERIC": "INVALID",
        }
        status_msg_map = {
            "NEGATIVE_DISTANCE_REJECTED": f"Rejected negative distance ({measured_surface_distance_m} m)",
            "OUT_OF_RANGE_REJECTED": f"Distance {measured_surface_distance_m} m exceeds max range {cfg.sensor_max_range_m} m",
            "STALE_READING_REJECTED": f"Reading is stale (exceeds {cfg.sensor_timeout_seconds}s timeout)",
            "IMPOSSIBLE_JUMP_REJECTED": f"Sudden rate of change exceeds physical limit ({cfg.max_jump_rate_m_s} m/s)",
            "MISSING_DATA": "Sensor distance data is missing or null",
            "INVALID_NUMERIC": "Sensor distance contains invalid non-numeric/NaN/Inf values",
        }
        return NonContactPressureEstimate(
            success=False,
            sensor_type=cfg.sensor_type,
            measured_surface_distance_m=measured_surface_distance_m,
            sensor_mount_height_m=cfg.sensor_mount_height_m,
            pressure_datum_m=cfg.pressure_datum_m,
            water_depth_m=None,
            water_level_rise_rate_mps=None,
            water_level_rise_rate_cm_min=None,
            estimated_pressure_pa=None,
            estimated_pressure_kpa=None,
            reading_timestamp=ts,
            reading_quality=quality_map.get(reason, "INVALID"),
            is_valid=False,
            validation_errors=[reason],
            status_message=status_msg_map.get(reason, f"Sensor reading rejected: {reason}"),
            pressure_source="non_contact_sensor_estimation",
            metadata={"validation_error": reason, "raw_distance": measured_surface_distance_m},
        )

    # Valid distance -> Compute depth and pressure
    depth_m = calculate_water_depth(
        surface_distance_m=measured_surface_distance_m,  # type: ignore
        mount_height_m=cfg.sensor_mount_height_m,
        datum_m=cfg.pressure_datum_m,
    )

    prev_depth_m = previous_reading.get("water_depth_m") if previous_reading else None
    rise_mps, rise_cm_min = calculate_water_level_rise_rate(
        current_depth_m=depth_m,
        previous_depth_m=prev_depth_m,
        delta_seconds=1.0,
    )

    pa, kpa = calculate_hydrostatic_pressure(
        water_depth_m=depth_m,
        density_kg_m3=cfg.water_density_kg_m3,
        gravity_m_s2=cfg.gravity_m_s2,
    )

    quality_rating = "VALID"
    if measured_surface_distance_m is not None and measured_surface_distance_m > cfg.sensor_mount_height_m:
        quality_rating = "CALIBRATION_REQUIRED"
    elif signal_quality < 0.5:
        quality_rating = "DEGRADED"
    elif signal_quality < 0.8:
        quality_rating = "VALID"

    return NonContactPressureEstimate(
        success=True,
        sensor_type=cfg.sensor_type,
        measured_surface_distance_m=round(measured_surface_distance_m, 4),  # type: ignore
        sensor_mount_height_m=cfg.sensor_mount_height_m,
        pressure_datum_m=cfg.pressure_datum_m,
        water_depth_m=depth_m,
        water_level_rise_rate_mps=rise_mps,
        water_level_rise_rate_cm_min=rise_cm_min,
        estimated_pressure_pa=pa,
        estimated_pressure_kpa=kpa,
        reading_timestamp=ts,
        reading_quality=quality_rating,
        is_valid=True,
        validation_errors=[],
        status_message="Nominal hydrostatic pressure estimation",
        pressure_source="non_contact_sensor_estimation",
        metadata={
            "fluid_density_kg_m3": cfg.water_density_kg_m3,
            "gravity_m_s2": cfg.gravity_m_s2,
            "signal_quality": signal_quality,
        },
    )


class NonContactPressureEngine:
    """
    Stateful estimation engine for non-contact radar/ultrasonic water level and hydrostatic pressure.
    Manages history window, temporal filtering, and multi-sensor tracking.
    """
    def __init__(self, config: Optional[NonContactPressureConfig] = None):
        self.config = config or NonContactPressureConfig()
        self.last_estimate: Optional[NonContactPressureEstimate] = None
        self.last_valid_estimate: Optional[NonContactPressureEstimate] = None
        self.history: deque[NonContactPressureEstimate] = deque(maxlen=100)

    def process_reading(
        self,
        distance_m: Optional[float],
        timestamp_str: Optional[str] = None,
        signal_quality: float = 1.0,
        current_time: Optional[datetime] = None,
    ) -> NonContactPressureEstimate:
        """Process an incoming non-contact surface distance measurement."""
        prev_dict = self.last_valid_estimate.to_dict() if self.last_valid_estimate else None

        estimate = estimate_pressure_from_sensor(
            measured_surface_distance_m=distance_m,
            config=self.config,
            timestamp_str=timestamp_str,
            signal_quality=signal_quality,
            previous_reading=prev_dict,
            current_time=current_time,
        )

        self.last_estimate = estimate
        if estimate.is_valid:
            self.last_valid_estimate = estimate
        self.history.append(estimate)
        return estimate

    def estimate_pressure(self, reading: NonContactSensorReading) -> NonContactPressureEstimate:
        """Estimate pressure from a NonContactSensorReading dataclass object."""
        dist = reading.measured_surface_distance_m
        mount_h = reading.sensor_mount_height_m or self.config.sensor_mount_height_m
        if dist is None and reading.water_depth_m is not None:
            dist = max(0.0, mount_h - reading.water_depth_m)

        cfg = NonContactPressureConfig(
            sensor_mount_height_m=mount_h,
            sensor_type=reading.sensor_type,
            sensor_max_range_m=self.config.sensor_max_range_m,
            water_density_kg_m3=self.config.water_density_kg_m3,
            gravity_m_s2=self.config.gravity_m_s2,
            pressure_datum_m=self.config.pressure_datum_m,
            sensor_timeout_seconds=self.config.sensor_timeout_seconds,
            max_jump_rate_m_s=self.config.max_jump_rate_m_s,
        )
        self.config = cfg
        return self.process_reading(
            distance_m=dist,
            timestamp_str=reading.timestamp,
            signal_quality=reading.signal_quality,
        )

    def get_latest_report(self) -> Dict[str, Any]:
        """Return structured telemetry for API serialization."""
        if self.last_estimate:
            return self.last_estimate.to_dict()

        # Initial fallback state before any reading arrives
        return NonContactPressureEstimate(
            success=False,
            sensor_type=self.config.sensor_type,
            sensor_mount_height_m=self.config.sensor_mount_height_m,
            pressure_datum_m=self.config.pressure_datum_m,
            is_valid=False,
            reading_quality="SENSOR_OFFLINE",
            status_message="No non-contact sensor readings received yet",
        ).to_dict()


# Global Singleton
_NON_CONTACT_PRESSURE_ENGINE: Optional[NonContactPressureEngine] = None


def get_non_contact_pressure_engine(sensor_mount_height_m: float = 6.0) -> NonContactPressureEngine:
    global _NON_CONTACT_PRESSURE_ENGINE
    if _NON_CONTACT_PRESSURE_ENGINE is None:
        _NON_CONTACT_PRESSURE_ENGINE = NonContactPressureEngine(
            NonContactPressureConfig(sensor_mount_height_m=sensor_mount_height_m)
        )
    return _NON_CONTACT_PRESSURE_ENGINE

