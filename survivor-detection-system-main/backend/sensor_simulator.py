"""
sensor_simulator.py
--------------------
Generates realistic multi-sensor readings (thermal imaging, PIR motion,
acoustic, CO2, heart-rate radar, RGB camera) for each victim profile in a
scenario.

Design notes
------------
Values are NOT drawn uniformly at random each cycle - that produces
readings that visibly jump around and look nothing like a real sensor
feed. Instead each (victim, sensor) pair follows a bounded
mean-reverting random walk (a discretised Ornstein-Uhlenbeck process):

    value[t+1] = value[t] + theta * (mean - value[t]) + sigma * gauss_noise

  - `mean`  is the midpoint of that victim's expected signature range
  - `theta` pulls the value back toward the physiologically-plausible
    band (so a critical victim's heart rate wanders but doesn't drift
    off to 150 bpm)
  - `sigma` is the step size, scaled to the width of the signature range
    so a wide-range sensor (CO2 ppm) and a narrow-range sensor
    (0-1 motion) both look equally "alive"

On top of that, an optional degradation model simulates battery/signal
weakening over the mission: as elapsed cycles increase, each victim's
transmitter battery drains, sensor confidence drops, occasional dropped
readings occur, and the signal gets noisier - independent of the
victim's actual physiological state. This lets the fusion engine (next
step) be tested against imperfect, real-world-like data.
"""

from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass, field
from typing import Optional

from models import (
    SensorType,
    SensorReading,
    SensorHealth,
    SensorHealthStatus,
    VictimProfile,
    GPSCoordinate,
    HIMALAYA_VICTIMS,
    GasType,
    GasConcentrationLevel,
    SmokeLevel,
    GasSmokeReading,
    GasSmokeSensorInterface,
    PressureTrend,
    PressureDropSeverity,
    PressureAnomalyLevel,
    PressureConfig,
    PRESSURE_CONFIG,
    BarometricPressureReading,
    BarometricPressureInterface,
    MoistureTrend,
    TiltTrend,
    LandslideRiskLevel,
    LandslideEventState,
    LandslideConfig,
    LANDSLIDE_CONFIG,
    SoilMoistureReading,
    TiltReading,
    LandslideRiskAssessment,
    SoilMoistureSensorInterface,
    TiltSensorInterface,
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
    CameraSensorInterface,
    ThermalCameraSensorInterface,
    RainfallClassification,
    RainfallTrend,
    RainfallConfig,
    RAINFALL_CONFIG,
    RainfallReading,
    RainfallSensorInterface,
    TemperatureTrend,
    HumidityTrend,
    TemperatureConfig,
    TEMPERATURE_CONFIG,
    HumidityConfig,
    HUMIDITY_CONFIG,
    TemperatureReading,
    TemperatureSensorInterface,
    HumidityReading,
    HumiditySensorInterface,
    GPSMovementState,
    GPSConfig,
    GPS_CONFIG,
    GPSReading,
    GPSSensorInterface,
    WaterTrend,
    WaterLevelClassification,
    WaterLevelConfig,
    WATER_LEVEL_CONFIG,
    WaterLevelReading,
    WaterLevelSensorInterface,
    RiskLevel,
)
from non_contact_pressure import (
    NonContactPressureConfig,
    NonContactPressureEngine,
    NonContactPressureEstimate,
)
from collections import deque
from scenario_loader import SiteEnvironment
from scenario_sensor_profiles import (
    ScenarioSensorProfile,
    SensorRole,
    get_scenario_sensor_profile,
)


# --------------------------------------------------------------------------- #
# Tunable simulation constants
# --------------------------------------------------------------------------- #

THETA = 0.35              # mean-reversion strength (0-1, higher = snaps back faster)
GPS_JITTER_DEG = 0.000015  # ~1-2m of GPS drift per cycle, realistic for handheld/GPS-tagged nodes

# Battery/degradation model
BATTERY_START_PCT = 100.0
BATTERY_DRAIN_MEAN_PCT = 0.35       # average drain per cycle
BATTERY_DRAIN_JITTER_PCT = 0.15     # random variation in drain (cold weather effect)
BATTERY_COLD_SNAP_PROB = 0.05       # chance of an extra cold-weather drain spike
BATTERY_COLD_SNAP_EXTRA_PCT = 2.0

DROPOUT_BATTERY_THRESHOLD_PCT = 25.0   # below this, readings can start dropping out
DROPOUT_PROB_AT_ZERO_BATTERY = 0.6     # dropout probability as battery -> 0

CONFIDENCE_FLOOR = 0.15  # minimum confidence a live sensor will still report

# Solar charging + Battery Management System (BMS) model
SOLAR_CYCLE_LENGTH_CYCLES = 60         # simulated cycles per full day/night cycle
SOLAR_PEAK_CHARGE_PCT = 0.55           # max panel charge added per cycle at solar noon, before BMS cap
SOLAR_CLOUD_VARIATION = 0.30           # cloud cover attenuates panel output cycle-to-cycle (0-1 fraction)
BMS_MAX_CHARGE_RATE_PCT = 0.35         # BMS hard cap on charge accepted per cycle (protects cells from fast-charge damage)
BMS_OVERCHARGE_CEILING_PCT = 100.0     # BMS cuts the charging circuit at/above this (anti-overcharge)

# Tilt/inclinometer chain-coupling threshold
SOIL_SATURATION_COUPLING_THRESHOLD_PCT = 60.0

# Kit-level IMU constants
KIT_VIBRATION_BASELINE_G = 0.02             # ambient micro-vibration when the kit is undisturbed (g)
KIT_VIBRATION_BASELINE_NOISE_G = 0.008      # cycle-to-cycle jitter around baseline
KIT_VIBRATION_SPIKE_PROB_PER_CYCLE = 0.01   # chance of a disturbance event per cycle
KIT_VIBRATION_SPIKE_PEAK_MIN_G = 0.15
KIT_VIBRATION_SPIKE_PEAK_MAX_G = 0.7
KIT_VIBRATION_SPIKE_DECAY_CYCLES = 4        # cycles for a spike to decay back to baseline

KIT_TILT_CREEP_RATE_DEG_PER_CYCLE = 0.01    # ambient slow drift of an undisturbed kit
KIT_TILT_SHIFT_PROBABILITY = 0.01           # baseline chance of the kit tipping/shifting per cycle
KIT_TILT_SHIFT_RANGE_DEG = (1.0, 6.0)       # how far tilt jumps when the kit tips
KIT_TILT_VIBRATION_COUPLING_MULTIPLIER = 4.0   # shift-probability boost when vibration spiked


def _sensor_range(sig, sensor_type: SensorType) -> tuple:
    """Look up the (min, max) expected range for a sensor type on a signature."""
    mapping = {
        SensorType.THERMAL_IMAGING: sig.thermal_imaging_c,
        SensorType.PIR_MOTION: sig.pir_motion,
        SensorType.ACOUSTIC: sig.acoustic_db,
        SensorType.CO2: sig.co2_ppm,
        SensorType.HEART_RATE_RADAR: sig.heart_rate_radar_bpm,
        SensorType.RGB_CAMERA: sig.rgb_camera_conf,
        SensorType.WATER_LEVEL: getattr(sig, "water_level_cm", (0.0, 0.0)),
        SensorType.WATER_FLOW: getattr(sig, "water_flow_ms", (0.0, 0.0)),
        SensorType.GAS_CONCENTRATION: getattr(sig, "gas_concentration_ppm", (0.0, 0.0)),
        SensorType.SMOKE_DENSITY: getattr(sig, "smoke_density_pct", (0.0, 0.0)),
    }
    return mapping.get(sensor_type, (0.0, 1.0))


def _sensor_unit(sensor_type: SensorType) -> str:
    return {
        SensorType.THERMAL_IMAGING: "degC",
        SensorType.PIR_MOTION: "motion_index",
        SensorType.ACOUSTIC: "dB",
        SensorType.CO2: "ppm",
        SensorType.HEART_RATE_RADAR: "bpm",
        SensorType.RGB_CAMERA: "confidence",
        SensorType.WATER_LEVEL: "cm",
        SensorType.WATER_FLOW: "m/s",
        SensorType.IMU_TILT: "deg",
        SensorType.IMU_VIBRATION: "g",
        SensorType.GAS_CONCENTRATION: "ppm",
        SensorType.SMOKE_DENSITY: "%",
        SensorType.BAROMETRIC_PRESSURE: "hPa",
        SensorType.RAINFALL_INTENSITY: "mm/hr",
        SensorType.SOIL_MOISTURE: "%",
        SensorType.TEMPERATURE: "°C",
        SensorType.HUMIDITY: "%",
        SensorType.GPS: "coords",
    }.get(sensor_type, "")


@dataclass
class _SensorTrack:
    """Running random-walk state for one (victim, sensor_type) pair."""
    current_value: float
    range_min: float
    range_max: float

    @property
    def mean(self) -> float:
        return (self.range_min + self.range_max) / 2.0

    @property
    def width(self) -> float:
        return max(self.range_max - self.range_min, 1e-6)

    def step(self, rng: random.Random, noise_multiplier: float = 1.0) -> float:
        sigma = 0.12 * self.width * noise_multiplier
        drift = THETA * (self.mean - self.current_value)
        noise = rng.gauss(0.0, sigma)
        new_value = self.current_value + drift + noise

        # allow a small overshoot beyond the nominal range (real sensors do this)
        overshoot = 0.08 * self.width
        lo, hi = self.range_min - overshoot, self.range_max + overshoot
        new_value = max(lo, min(hi, new_value))

        self.current_value = new_value
        return new_value


@dataclass
class _VictimNode:
    """Simulated sensor-node state for one victim: battery + all sensor tracks."""
    victim: VictimProfile
    tracks: dict = field(default_factory=dict)
    battery_pct: float = BATTERY_START_PCT
    location: GPSCoordinate = None
    enable_water_sensor: bool = False
    enable_water_flow_sensor: bool = False
    charging: bool = False              # solar panel actively adding charge this cycle
    bms_capped: bool = False            # BMS limited the charge below what the panel could deliver
    last_solar_input_pct: float = 0.0   # charge actually applied this cycle (post-BMS-cap)

    # Kit-level IMU: 3-axis accelerometer and inclinometer
    kit_tilt_deg: float = 0.0
    kit_vibration_g: float = 0.0
    acc_x_g: float = 0.0
    acc_y_g: float = 0.0
    acc_z_g: float = 1.0                # 1g baseline gravitational component
    acc_magnitude_g: float = 1.0        # sqrt(x^2 + y^2 + z^2)
    impact_detected: bool = False
    sustained_vibration_cycles: int = 0
    kit_vibration_spike_active: bool = False    # mirrors SensorSimulator._aftershock_active, but per-kit
    kit_vibration_peak_g: float = 0.0
    kit_vibration_cycles_remaining: int = 0
    last_kit_tilt_shift: bool = False           # True only on the exact cycle this kit's tilt just shifted
    last_kit_vibration_spike: bool = False      # True only on the exact cycle this kit's vibration just spiked

    def __post_init__(self):
        sig = self.victim.signature_range
        core_sensors = (
            SensorType.THERMAL_IMAGING,
            SensorType.PIR_MOTION,
            SensorType.ACOUSTIC,
            SensorType.CO2,
            SensorType.HEART_RATE_RADAR,
            SensorType.RGB_CAMERA,
        )
        for st in core_sensors:
            lo, hi = _sensor_range(sig, st)
            self.tracks[st] = _SensorTrack(
                current_value=(lo + hi) / 2.0, range_min=lo, range_max=hi
            )

        if self.enable_water_sensor:
            lo, hi = getattr(sig, "water_level_cm", (0.0, 0.0))
            self.tracks[SensorType.WATER_LEVEL] = _SensorTrack(
                current_value=max(0.0, getattr(self.victim, "initial_water_level_cm", 0.0)),
                range_min=lo,
                range_max=hi,
            )
        if self.enable_water_flow_sensor:
            lo, hi = getattr(sig, "water_flow_ms", (0.0, 0.0))
            self.tracks[SensorType.WATER_FLOW] = _SensorTrack(
                current_value=max(0.0, getattr(self.victim, "initial_water_flow_ms", 0.0)),
                range_min=lo,
                range_max=hi,
            )

        self.location = GPSCoordinate(
            latitude=self.victim.location.latitude,
            longitude=self.victim.location.longitude,
            altitude_m=self.victim.location.altitude_m,
        )


SensorNode = _VictimNode


class GasSmokeSimulationAdapter(GasSmokeSensorInterface):
    """
    Hardware-ready Simulation adapter implementing GasSmokeSensorInterface.
    Provides realistic scenario-driven profiles, rate of change,
    and diagnostic health reporting for gas and smoke probes.
    """
    def __init__(
        self,
        gas_type: GasType = GasType.GENERIC_SMOKE,
        sensor_id: str = "GAS-SMOKE-SITE",
        device_id: str = "DEV-GAS-01",
        location: Optional[GPSCoordinate] = None,
        scenario_profile: str = "NORMAL",
        initial_gas_ppm: float = 10.0,
        initial_smoke_pct: float = 5.0,
    ):
        self.gas_type = gas_type
        self.sensor_id = sensor_id
        self.device_id = device_id
        self.location = location or GPSCoordinate(latitude=32.3740, longitude=77.2490)
        self.scenario_profile = scenario_profile
        self.status = SensorHealthStatus.ONLINE
        self.battery_pct = 98.0
        self.signal_quality = 0.98

        self._gas_concentration = initial_gas_ppm
        self._smoke_density_pct = initial_smoke_pct
        self._prev_gas = initial_gas_ppm
        self._prev_smoke = initial_smoke_pct
        self._rate_of_change_gas = 0.0
        self._rate_of_change_smoke = 0.0
        self.history: list[GasSmokeReading] = []

    def set_gas_type(self, gas_type: GasType) -> None:
        self.gas_type = gas_type

    def set_status(self, status: SensorHealthStatus) -> None:
        self.status = status

    def set_scenario_profile(self, profile: str) -> None:
        self.scenario_profile = profile

    def step(self, rng: Optional[random.Random] = None) -> GasSmokeReading:
        r = rng or random
        self._prev_gas = self._gas_concentration
        self._prev_smoke = self._smoke_density_pct

        prof = self.scenario_profile.upper()
        if prof in ("FIRE", "URBAN_FIRE"):
            self._gas_concentration = min(100.0, self._gas_concentration + r.uniform(5.0, 12.0))
            self._smoke_density_pct = min(100.0, self._smoke_density_pct + r.uniform(8.0, 16.0))
        elif prof in ("WILDFIRE", "FOREST_FIRE"):
            self._gas_concentration = min(80.0, self._gas_concentration + r.uniform(2.0, 6.0))
            self._smoke_density_pct = min(100.0, self._smoke_density_pct + r.uniform(10.0, 18.0))
        elif prof in ("INDUSTRIAL_ACCIDENT", "INDUSTRIAL"):
            self._gas_concentration = min(100.0, self._gas_concentration + r.uniform(12.0, 25.0))
            self._smoke_density_pct = min(100.0, self._smoke_density_pct + r.uniform(4.0, 10.0))
        elif prof in ("CHEMICAL_LEAK", "TOXIC_GAS"):
            self._gas_concentration = min(100.0, self._gas_concentration + r.uniform(12.0, 22.0))
            self._smoke_density_pct = min(15.0, max(2.0, self._smoke_density_pct + r.uniform(-0.5, 0.8)))
        elif prof in ("BUILDING_COLLAPSE", "EARTHQUAKE"):
            self._gas_concentration = min(60.0, self._gas_concentration + r.uniform(1.0, 4.0))
            self._smoke_density_pct = min(70.0, self._smoke_density_pct + r.uniform(3.0, 8.0))
        else: # NORMAL
            self._gas_concentration = max(5.0, min(25.0, self._gas_concentration + r.uniform(-1.0, 1.0)))
            self._smoke_density_pct = max(0.0, min(12.0, self._smoke_density_pct + r.uniform(-0.5, 0.5)))

        self._rate_of_change_gas = round(self._gas_concentration - self._prev_gas, 3)
        self._rate_of_change_smoke = round(self._smoke_density_pct - self._prev_smoke, 3)

        return self.read_sensor()

    def read_sensor(self) -> GasSmokeReading:
        # Determine gas level
        gc = self._gas_concentration
        if gc >= 81.0:
            g_level = GasConcentrationLevel.CRITICAL
        elif gc >= 61.0:
            g_level = GasConcentrationLevel.HIGH
        elif gc >= 31.0:
            g_level = GasConcentrationLevel.ELEVATED
        else:
            g_level = GasConcentrationLevel.NORMAL

        # Determine smoke level
        sm = self._smoke_density_pct
        if sm >= 76.0:
            s_level = SmokeLevel.CRITICAL
        elif sm >= 51.0:
            s_level = SmokeLevel.HIGH
        elif sm >= 26.0:
            s_level = SmokeLevel.MODERATE
        elif sm >= 1.0:
            s_level = SmokeLevel.LOW
        else:
            s_level = SmokeLevel.NO_SMOKE

        reading = GasSmokeReading(
            sensor_id=self.sensor_id,
            device_id=self.device_id,
            gas_type=self.gas_type,
            gas_concentration=round(self._gas_concentration, 2),
            gas_unit="ppm",
            gas_level=g_level,
            smoke_density_pct=round(self._smoke_density_pct, 2),
            smoke_level=s_level,
            rate_of_change_gas=self._rate_of_change_gas,
            rate_of_change_smoke=self._rate_of_change_smoke,
            location=self.location,
            status=self.status,
            confidence=0.95 if self.status == SensorHealthStatus.ONLINE else (0.5 if self.status == SensorHealthStatus.DEGRADED else 0.0),
            quality=self.signal_quality,
        )
        self.history.append(reading)
        if len(self.history) > 100:
            self.history.pop(0)
        return reading

    def get_health(self) -> SensorHealth:
        from datetime import datetime, timezone
        return SensorHealth(
            sensor_id=self.sensor_id,
            sensor_type=SensorType.GAS_CONCENTRATION,
            status=self.status,
            battery_pct=round(self.battery_pct, 1),
            signal_quality=round(self.signal_quality, 2),
            error_message="Sensor offline / signal unacquired" if self.status == SensorHealthStatus.OFFLINE else None,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
        )


class BarometricPressureSimulationAdapter(BarometricPressureInterface):
    """
    Hardware-ready Simulation adapter implementing BarometricPressureInterface.
    Provides realistic scenario-driven profiles, rate of change, trend detection,
    and diagnostic health reporting for Barometric Pressure sensors (BMP280/BME280/Sim).
    """
    def __init__(
        self,
        sensor_id: str = "ENV-BARO-01",
        device_id: str = "DEV-BARO-01",
        location: Optional[GPSCoordinate] = None,
        scenario_profile: str = "NORMAL_WEATHER",
        initial_pressure_hpa: float = 1013.25,
    ):
        self.sensor_id = sensor_id
        self.device_id = device_id
        self.location = location or GPSCoordinate(latitude=32.3740, longitude=77.2490)
        self.scenario_profile = scenario_profile
        self.status = SensorHealthStatus.ONLINE
        self.battery_pct = 99.0
        self.signal_quality = 0.99
        self.sampling_interval_s = PRESSURE_CONFIG.sampling_interval_seconds
        
        self._pressure_hpa = initial_pressure_hpa
        self._prev_pressure_hpa = initial_pressure_hpa
        self._rate_of_change = 0.0
        self.history: list[BarometricPressureReading] = []
        self._history_deque: deque[float] = deque(maxlen=PRESSURE_CONFIG.history_window_size)
        self._history_deque.append(initial_pressure_hpa)

    def set_status(self, status: SensorHealthStatus) -> None:
        self.status = status

    def set_sampling_interval(self, seconds: float) -> None:
        self.sampling_interval_s = seconds

    def set_scenario_profile(self, profile: str) -> None:
        self.scenario_profile = profile

    def step(self, rng: Optional[random.Random] = None) -> BarometricPressureReading:
        r = rng or random
        self._prev_pressure_hpa = self._pressure_hpa
        prof = self.scenario_profile.upper()

        if prof in ("NORMAL", "NORMAL_WEATHER"):
            noise = r.uniform(-0.4, 0.4)
            self._pressure_hpa = max(1008.0, min(1018.0, self._pressure_hpa * 0.7 + 1013.25 * 0.3 + noise))
        elif prof in ("FALLING", "FALLING_PRESSURE"):
            self._pressure_hpa = max(998.0, self._pressure_hpa - r.uniform(1.5, 2.5))
        elif prof in ("RAPID", "RAPID_PRESSURE_DROP", "RAPID_DROP"):
            self._pressure_hpa = max(980.0, self._pressure_hpa - r.uniform(3.5, 5.0))
        elif prof in ("CYCLONE", "SEVERE_CYCLONE"):
            self._pressure_hpa = max(955.0, self._pressure_hpa - r.uniform(4.0, 7.5))
        elif prof in ("STORM_SURGE", "STORM"):
            self._pressure_hpa = max(965.0, self._pressure_hpa - r.uniform(3.0, 6.0))
        elif prof in ("FLOOD", "FLOOD_WEATHER"):
            self._pressure_hpa = max(990.0, self._pressure_hpa - r.uniform(0.8, 2.0))
        elif prof in ("MULTI_HAZARD", "MULTI_HAZARD_DISASTER"):
            self._pressure_hpa = max(960.0, self._pressure_hpa - r.uniform(2.5, 5.5))
        else:
            self._pressure_hpa = max(990.0, min(1030.0, self._pressure_hpa + r.uniform(-0.5, 0.5)))

        self._rate_of_change = round(self._pressure_hpa - self._prev_pressure_hpa, 3)
        self._history_deque.append(self._pressure_hpa)

        return self.read_sensor()

    def read_sensor(self) -> BarometricPressureReading:
        rate = self._rate_of_change
        cum_drop = (self._history_deque[0] - self._pressure_hpa) if len(self._history_deque) > 1 else abs(rate)

        if rate <= -PRESSURE_CONFIG.rapid_falling_threshold_hpa_per_cycle or (rate <= 0 and cum_drop >= PRESSURE_CONFIG.anomaly_absolute_drop_hpa):
            trend = PressureTrend.RAPIDLY_FALLING
        elif rate <= -PRESSURE_CONFIG.falling_threshold_hpa_per_cycle or (rate <= 0 and cum_drop >= 4.0):
            trend = PressureTrend.FALLING
        elif rate >= PRESSURE_CONFIG.rapid_rising_threshold_hpa_per_cycle:
            trend = PressureTrend.RAPIDLY_RISING
        elif rate >= PRESSURE_CONFIG.rising_threshold_hpa_per_cycle:
            trend = PressureTrend.RISING
        else:
            trend = PressureTrend.STABLE
        if self._pressure_hpa <= PRESSURE_CONFIG.critical_plunge_threshold_hpa or rate <= -6.0 or cum_drop >= PRESSURE_CONFIG.critical_drop_threshold_hpa:
            drop_severity = PressureDropSeverity.CRITICAL_DROP
            anomaly_level = PressureAnomalyLevel.CRITICAL
        elif self._pressure_hpa <= PRESSURE_CONFIG.severe_cyclone_threshold_hpa or rate <= -PRESSURE_CONFIG.rapid_falling_threshold_hpa_per_cycle or cum_drop >= PRESSURE_CONFIG.anomaly_absolute_drop_hpa:
            drop_severity = PressureDropSeverity.RAPID_DROP
            anomaly_level = PressureAnomalyLevel.ABNORMAL
        elif rate <= -PRESSURE_CONFIG.falling_threshold_hpa_per_cycle or cum_drop >= 4.0:
            drop_severity = PressureDropSeverity.SIGNIFICANT_DROP
            anomaly_level = PressureAnomalyLevel.NORMAL
        else:
            drop_severity = PressureDropSeverity.NORMAL
            anomaly_level = PressureAnomalyLevel.NORMAL

        reading = BarometricPressureReading(
            sensor_id=self.sensor_id,
            device_id=self.device_id,
            pressure_hpa=round(self._pressure_hpa, 2),
            unit="hPa",
            rate_of_change=self._rate_of_change,
            trend=trend,
            drop_severity=drop_severity,
            anomaly_level=anomaly_level,
            location=self.location,
            status=self.status,
            confidence=0.99 if self.status == SensorHealthStatus.ONLINE else (0.5 if self.status == SensorHealthStatus.DEGRADED else 0.0),
            quality=self.signal_quality,
            metadata={"mode": "SIMULATED"},
        )
        self.history.append(reading)
        if len(self.history) > 100:
            self.history.pop(0)
        return reading

    def get_health(self) -> SensorHealth:
        from datetime import datetime, timezone
        return SensorHealth(
            sensor_id=self.sensor_id,
            sensor_type=SensorType.BAROMETRIC_PRESSURE,
            status=self.status,
            battery_pct=round(self.battery_pct, 1),
            signal_quality=round(self.signal_quality, 2),
            error_message="Sensor offline / atmospheric communication loss" if self.status == SensorHealthStatus.OFFLINE else None,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
        )


# --------------------------------------------------------------------------- #
# Dedicated Rainfall Simulation Adapter
# --------------------------------------------------------------------------- #

class RainfallSimulationAdapter(RainfallSensorInterface):
    """
    Hardware-ready Simulation adapter implementing RainfallSensorInterface.
    Provides realistic scenario-driven precipitation profiles, cumulative accumulation,
    rate of change, trend detection, and diagnostic health reporting for optical/tipping-bucket rain gauges.
    """
    def __init__(
        self,
        sensor_id: str = "ENV-RAIN-01",
        device_id: str = "DEV-RAIN-01",
        location: Optional[GPSCoordinate] = None,
        scenario_profile: str = "AUTO",
        initial_rainfall_rate: float = 0.0,
        initial_cumulative_mm: float = 0.0,
    ):
        self.sensor_id = sensor_id
        self.device_id = device_id
        self.location = location or GPSCoordinate(latitude=32.3740, longitude=77.2490)
        self.scenario_profile = scenario_profile
        self.status = SensorHealthStatus.ONLINE
        self.battery_pct = 99.0
        self.signal_quality = 0.99
        
        self._rainfall_rate_mm_h = max(0.0, initial_rainfall_rate)
        self._prev_rainfall_rate_mm_h = max(0.0, initial_rainfall_rate)
        self._cumulative_rainfall_mm = max(0.0, initial_cumulative_mm)
        self._rate_of_change = 0.0
        self.history: list[RainfallReading] = []
        self._history_deque: deque[float] = deque(maxlen=60)
        self._history_deque.append(self._rainfall_rate_mm_h)

    def set_status(self, status: SensorHealthStatus) -> None:
        self.status = status

    def set_simulation_profile(self, profile: str) -> None:
        self.scenario_profile = profile
        if profile.upper() in ("RAIN_SENSOR_FAILURE", "OFFLINE"):
            self.status = SensorHealthStatus.OFFLINE
        elif self.status == SensorHealthStatus.OFFLINE:
            self.status = SensorHealthStatus.ONLINE

    @property
    def _simulation_profile(self) -> str:
        return self.scenario_profile

    @_simulation_profile.setter
    def _simulation_profile(self, val: str) -> None:
        self.scenario_profile = val

    def step_cycle(self, rng: Optional[random.Random] = None, base_rainfall_hint: Optional[float] = None) -> RainfallReading:
        return self.step(rng=rng, base_rainfall_hint=base_rainfall_hint)

    def step(self, rng: Optional[random.Random] = None, base_rainfall_hint: Optional[float] = None) -> RainfallReading:
        r = rng or random
        self._prev_rainfall_rate_mm_h = self._rainfall_rate_mm_h
        prof = self.scenario_profile.upper()

        if prof == "NO_RAIN":
            self._rainfall_rate_mm_h = 0.0
        elif prof == "LIGHT":
            self._rainfall_rate_mm_h = max(0.1, min(5.0, 2.5 + r.uniform(-0.8, 0.8)))
        elif prof == "MODERATE":
            self._rainfall_rate_mm_h = max(5.1, min(20.0, 12.0 + r.uniform(-2.5, 2.5)))
        elif prof == "HEAVY":
            self._rainfall_rate_mm_h = max(20.1, min(50.0, 35.0 + r.uniform(-4.0, 5.0)))
        elif prof in ("VERY_HEAVY", "TORRENTIAL_MONSOON"):
            self._rainfall_rate_mm_h = max(50.1, min(100.0, 75.0 + r.uniform(-6.0, 8.0)))
        elif prof in ("EXTREME", "CLOUDBURST"):
            self._rainfall_rate_mm_h = max(100.1, min(220.0, 130.0 + r.uniform(-10.0, 15.0)))
        elif prof in ("RAIN_SENSOR_FAILURE", "OFFLINE"):
            self.status = SensorHealthStatus.OFFLINE
            self._rainfall_rate_mm_h = 0.0
        else:
            # AUTO / SCENARIO-DRIVEN
            if base_rainfall_hint is not None:
                noise = r.uniform(-1.0, 1.0)
                self._rainfall_rate_mm_h = max(0.0, base_rainfall_hint + noise)
            else:
                self._rainfall_rate_mm_h = max(0.0, self._rainfall_rate_mm_h * 0.85 + r.uniform(-0.5, 0.5))

        self._rate_of_change = round(self._rainfall_rate_mm_h - self._prev_rainfall_rate_mm_h, 3)
        self._history_deque.append(self._rainfall_rate_mm_h)

        # Accumulate rainfall (mm per 4-second cycle => rate_mm_h * 4 / 3600)
        cycle_hours = 4.0 / 3600.0
        if self._rainfall_rate_mm_h > 0.0:
            self._cumulative_rainfall_mm += round(self._rainfall_rate_mm_h * cycle_hours, 3)

        return self.read_sensor()

    def read_sensor(self) -> RainfallReading:
        rate = self._rainfall_rate_mm_h
        roc = self._rate_of_change

        if roc >= 5.0:
            trend = RainfallTrend.RAPIDLY_INCREASING
        elif roc >= 1.0:
            trend = RainfallTrend.INCREASING
        elif roc <= -1.0:
            trend = RainfallTrend.DECREASING
        else:
            trend = RainfallTrend.STABLE

        if rate <= RAINFALL_CONFIG.no_rain_threshold:
            classification = RainfallClassification.NO_RAIN
            severity = RiskLevel.LOW
        elif rate <= RAINFALL_CONFIG.light_threshold_mm_h:
            classification = RainfallClassification.LIGHT
            severity = RiskLevel.LOW
        elif rate <= RAINFALL_CONFIG.moderate_threshold_mm_h:
            classification = RainfallClassification.MODERATE
            severity = RiskLevel.MEDIUM
        elif rate <= RAINFALL_CONFIG.heavy_threshold_mm_h:
            classification = RainfallClassification.HEAVY
            severity = RiskLevel.HIGH
        elif rate <= RAINFALL_CONFIG.very_heavy_threshold_mm_h:
            classification = RainfallClassification.VERY_HEAVY
            severity = RiskLevel.HIGH
        else:
            classification = RainfallClassification.EXTREME
            severity = RiskLevel.CRITICAL

        reading = RainfallReading(
            sensor_id=self.sensor_id,
            device_id=self.device_id,
            rainfall_rate_mm_h=round(self._rainfall_rate_mm_h, 2),
            rainfall_mm_hr=round(self._rainfall_rate_mm_h, 2),
            cumulative_rainfall_mm=round(self._cumulative_rainfall_mm, 2),
            unit="mm/h",
            rate_of_change=self._rate_of_change,
            trend=trend,
            classification=classification,
            severity=severity,
            location=self.location,
            status=self.status,
            confidence=0.98 if self.status == SensorHealthStatus.ONLINE else (0.5 if self.status == SensorHealthStatus.DEGRADED else 0.0),
            quality=self.signal_quality,
            metadata={"mode": "SIMULATED", "scenario_profile": self.scenario_profile},
        )
        self.history.append(reading)
        if len(self.history) > 100:
            self.history.pop(0)
        return reading

    def get_cumulative_rainfall(self) -> float:
        return round(self._cumulative_rainfall_mm, 2)

    def reset_cumulative(self) -> None:
        self._cumulative_rainfall_mm = 0.0

    def get_health(self) -> SensorHealth:
        from datetime import datetime, timezone
        return SensorHealth(
            sensor_id=self.sensor_id,
            sensor_type=SensorType.RAINFALL_INTENSITY,
            status=self.status,
            battery_pct=round(self.battery_pct, 1),
            signal_quality=round(self.signal_quality, 2),
            error_message="Rainfall sensor offline" if self.status == SensorHealthStatus.OFFLINE else None,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
        )


# --------------------------------------------------------------------------- #
# Dedicated Ambient Temperature & Humidity Simulation Adapters
# --------------------------------------------------------------------------- #

class TemperatureSimulationAdapter(TemperatureSensorInterface):
    """
    Hardware-ready Simulation adapter implementing TemperatureSensorInterface.
    Provides realistic scenario-driven ambient temperature profiles, rate of change,
    trend detection (STABLE, RISING, FALLING, RAPIDLY_RISING, RAPIDLY_FALLING),
    and diagnostic health reporting for precision thermistors / RTDs / BME280.
    """
    def __init__(
        self,
        sensor_id: str = "ENV-TEMP-01",
        device_id: str = "DEV-TEMP-01",
        location: Optional[GPSCoordinate] = None,
        scenario_profile: str = "AUTO",
        initial_temp_c: float = 15.0,
    ):
        self.sensor_id = sensor_id
        self.device_id = device_id
        self.location = location or GPSCoordinate(latitude=32.3740, longitude=77.2490)
        self.scenario_profile = scenario_profile
        self.status = SensorHealthStatus.ONLINE
        self.battery_pct = 99.0
        self.signal_quality = 0.99
        self.sampling_interval_s = TEMPERATURE_CONFIG.sampling_interval_seconds

        self._temperature_c = float(initial_temp_c)
        self._prev_temperature_c = float(initial_temp_c)
        self._rate_of_change = 0.0
        self.history: list[TemperatureReading] = []
        self._history_deque: deque[float] = deque(maxlen=TEMPERATURE_CONFIG.history_window_size)
        self._history_deque.append(self._temperature_c)

    def set_status(self, status: SensorHealthStatus) -> None:
        self.status = status

    def set_simulation_profile(self, profile_name: str) -> None:
        self.scenario_profile = profile_name
        p_up = profile_name.upper()
        if p_up in ("OFFLINE", "SENSOR_FAILURE", "TEMP_SENSOR_FAILURE"):
            self.status = SensorHealthStatus.OFFLINE
        elif p_up in ("DEGRADED", "NOISY"):
            self.status = SensorHealthStatus.DEGRADED
        elif self.status in (SensorHealthStatus.OFFLINE, SensorHealthStatus.DEGRADED):
            self.status = SensorHealthStatus.ONLINE

    def step(
        self,
        rng: Optional[random.Random] = None,
        base_temp_hint: Optional[float] = None,
        diurnal_offset: float = 0.0,
        cycle: int = 1,
        **kwargs,
    ) -> TemperatureReading:
        r = rng or random
        self._prev_temperature_c = self._temperature_c
        prof = self.scenario_profile.upper()

        if prof in ("NORMAL", "NORMAL_WEATHER", "STABLE"):
            target = 15.0 + diurnal_offset
            self._temperature_c = self._temperature_c + 0.15 * (target - self._temperature_c) + r.uniform(-0.3, 0.3)
        elif prof in ("EXTREME_HEAT", "HEATWAVE", "HEAT"):
            target = 46.0 + r.uniform(0.0, 4.0)
            self._temperature_c = max(43.0, min(58.0, self._temperature_c + r.uniform(1.2, 2.8)))
        elif prof in ("FIRE", "WILDFIRE", "URBAN_FIRE"):
            target = 65.0 + r.uniform(0.0, 15.0)
            self._temperature_c = max(52.0, min(95.0, self._temperature_c + r.uniform(3.0, 6.5)))
        elif prof in ("COLD", "FREEZING", "AVALANCHE", "HIMALAYA_AVALANCHE"):
            target = -8.0 + diurnal_offset
            self._temperature_c = min(-2.0, self._temperature_c + 0.3 * (target - self._temperature_c) + r.uniform(-0.4, 0.4))
        elif prof in ("HEAVY_RAIN", "FLOOD"):
            target = 18.0 + diurnal_offset
            self._temperature_c = self._temperature_c + 0.15 * (target - self._temperature_c) + r.uniform(-0.3, 0.3)
        elif prof in ("CYCLONE", "STORM"):
            target = 22.0 + diurnal_offset
            self._temperature_c = self._temperature_c + 0.15 * (target - self._temperature_c) + r.uniform(-0.5, 0.5)
        elif prof in ("DEGRADED", "NOISY"):
            self.status = SensorHealthStatus.DEGRADED
            self._temperature_c += r.uniform(-3.5, 3.5)
        elif prof in ("OFFLINE", "SENSOR_FAILURE", "TEMP_SENSOR_FAILURE"):
            self.status = SensorHealthStatus.OFFLINE
        else:
            # AUTO / scenario-hint driven
            if base_temp_hint is not None:
                self._temperature_c = base_temp_hint + r.uniform(-0.2, 0.2)
            else:
                self._temperature_c += r.uniform(-0.2, 0.2)

        self._temperature_c = max(TEMPERATURE_CONFIG.min_temp_c, min(TEMPERATURE_CONFIG.max_temp_c, self._temperature_c))
        self._rate_of_change = round(self._temperature_c - self._prev_temperature_c, 3)
        self._history_deque.append(self._temperature_c)

        return self.read_sensor()

    def read_sensor(self) -> TemperatureReading:
        rate = self._rate_of_change
        if rate >= TEMPERATURE_CONFIG.rapid_rising_rate_threshold_c_per_cycle:
            trend = TemperatureTrend.RAPIDLY_RISING
        elif rate >= TEMPERATURE_CONFIG.rising_rate_threshold_c_per_cycle:
            trend = TemperatureTrend.RISING
        elif rate <= -TEMPERATURE_CONFIG.rapid_rising_rate_threshold_c_per_cycle:
            trend = TemperatureTrend.RAPIDLY_FALLING
        elif rate <= -TEMPERATURE_CONFIG.rising_rate_threshold_c_per_cycle:
            trend = TemperatureTrend.FALLING
        else:
            trend = TemperatureTrend.STABLE

        reading = TemperatureReading(
            sensor_id=self.sensor_id,
            device_id=self.device_id,
            temperature_c=round(self._temperature_c, 2),
            ambient_temp_c=round(self._temperature_c, 2),
            unit="°C",
            rate_of_change=rate,
            trend=trend,
            location=self.location,
            status=self.status,
            confidence=0.98 if self.status == SensorHealthStatus.ONLINE else (0.50 if self.status == SensorHealthStatus.DEGRADED else 0.0),
            quality=self.signal_quality if self.status == SensorHealthStatus.ONLINE else (0.45 if self.status == SensorHealthStatus.DEGRADED else 0.0),
            metadata={"mode": "SIMULATED", "profile": self.scenario_profile},
        )
        self.history.append(reading)
        if len(self.history) > 100:
            self.history.pop(0)
        return reading

    def get_health(self) -> SensorHealth:
        from datetime import datetime, timezone
        err = None
        if self.status == SensorHealthStatus.OFFLINE:
            err = "Temperature probe offline / communication loss"
        elif self.status == SensorHealthStatus.DEGRADED:
            err = "Thermal sensor signal degraded / high noise"
        return SensorHealth(
            sensor_id=self.sensor_id,
            sensor_type=SensorType.TEMPERATURE,
            status=self.status,
            battery_pct=round(self.battery_pct, 1),
            signal_quality=round(self.signal_quality if self.status == SensorHealthStatus.ONLINE else 0.45, 2),
            error_message=err,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
        )


class HumiditySimulationAdapter(HumiditySensorInterface):
    """
    Hardware-ready Simulation adapter implementing HumiditySensorInterface.
    Provides realistic scenario-driven relative humidity profiles, rate of change,
    trend detection (STABLE, RISING, FALLING, RAPIDLY_RISING, RAPIDLY_FALLING),
    and diagnostic health reporting for capacitive hygrometers / BME280.
    """
    def __init__(
        self,
        sensor_id: str = "ENV-HUMID-01",
        device_id: str = "DEV-HUMID-01",
        location: Optional[GPSCoordinate] = None,
        scenario_profile: str = "AUTO",
        initial_humidity_pct: float = 50.0,
    ):
        self.sensor_id = sensor_id
        self.device_id = device_id
        self.location = location or GPSCoordinate(latitude=32.3740, longitude=77.2490)
        self.scenario_profile = scenario_profile
        self.status = SensorHealthStatus.ONLINE
        self.battery_pct = 99.0
        self.signal_quality = 0.99
        self.sampling_interval_s = HUMIDITY_CONFIG.sampling_interval_seconds

        self._humidity_pct = float(initial_humidity_pct)
        self._prev_humidity_pct = float(initial_humidity_pct)
        self._rate_of_change = 0.0
        self.history: list[HumidityReading] = []
        self._history_deque: deque[float] = deque(maxlen=HUMIDITY_CONFIG.history_window_size)
        self._history_deque.append(self._humidity_pct)

    def set_status(self, status: SensorHealthStatus) -> None:
        self.status = status

    def set_simulation_profile(self, profile_name: str) -> None:
        self.scenario_profile = profile_name
        p_up = profile_name.upper()
        if p_up in ("OFFLINE", "SENSOR_FAILURE", "HUMID_SENSOR_FAILURE"):
            self.status = SensorHealthStatus.OFFLINE
        elif p_up in ("DEGRADED", "NOISY"):
            self.status = SensorHealthStatus.DEGRADED
        elif self.status in (SensorHealthStatus.OFFLINE, SensorHealthStatus.DEGRADED):
            self.status = SensorHealthStatus.ONLINE

    def step(
        self,
        rng: Optional[random.Random] = None,
        base_humidity_hint: Optional[float] = None,
        rainfall_rate_mm_h: float = 0.0,
        rainfall_mm_hr: Optional[float] = None,
        cycle: int = 1,
        **kwargs,
    ) -> HumidityReading:
        if rainfall_mm_hr is not None:
            rainfall_rate_mm_h = rainfall_mm_hr
        r = rng or random
        self._prev_humidity_pct = self._humidity_pct
        prof = self.scenario_profile.upper()

        if prof in ("NORMAL", "NORMAL_WEATHER", "STABLE"):
            target = 50.0
            self._humidity_pct = self._humidity_pct + 0.15 * (target - self._humidity_pct) + r.uniform(-0.5, 0.5)
        elif prof in ("HIGH_HUMIDITY", "SATURATED", "TROPICAL"):
            target = 90.0 + r.uniform(0.0, 5.0)
            self._humidity_pct = max(85.0, min(100.0, self._humidity_pct + r.uniform(1.5, 3.5)))
        elif prof in ("FLOOD", "HEAVY_RAIN", "URBAN_FLOOD"):
            rain_boost = min(35.0, rainfall_rate_mm_h * 0.5) if rainfall_rate_mm_h > 0 else 20.0
            target = min(98.0, 75.0 + rain_boost)
            self._humidity_pct = min(100.0, max(82.0, self._humidity_pct + 0.25 * (target - self._humidity_pct) + r.uniform(0.5, 1.8)))
        elif prof in ("CYCLONE", "STORM", "CLOUDBURST"):
            target = min(100.0, 92.0 + r.uniform(2.0, 7.0))
            self._humidity_pct = max(88.0, min(100.0, self._humidity_pct + r.uniform(2.0, 4.5)))
        elif prof in ("ARID", "DRY", "LOW_HUMIDITY", "WILDFIRE", "FIRE"):
            target = 18.0 + r.uniform(-2.0, 2.0)
            self._humidity_pct = min(25.0, max(5.0, self._humidity_pct - r.uniform(1.5, 3.0)))
        elif prof in ("DEGRADED", "NOISY"):
            self.status = SensorHealthStatus.DEGRADED
            self._humidity_pct += r.uniform(-6.0, 6.0)
        elif prof in ("OFFLINE", "SENSOR_FAILURE", "HUMID_SENSOR_FAILURE"):
            self.status = SensorHealthStatus.OFFLINE
        else:
            # AUTO / scenario-hint driven
            if base_humidity_hint is not None:
                rain_boost = min(35.0, rainfall_rate_mm_h * 0.4)
                target = min(100.0, base_humidity_hint + rain_boost)
                self._humidity_pct = self._humidity_pct + 0.15 * (target - self._humidity_pct) + r.uniform(-0.4, 0.4)
            else:
                rain_effect = min(25.0, rainfall_rate_mm_h * 0.4)
                self._humidity_pct = min(100.0, self._humidity_pct + rain_effect * 0.1 + r.uniform(-0.5, 0.5))

        self._humidity_pct = max(HUMIDITY_CONFIG.min_humidity_pct, min(HUMIDITY_CONFIG.max_humidity_pct, self._humidity_pct))
        self._rate_of_change = round(self._humidity_pct - self._prev_humidity_pct, 3)
        self._history_deque.append(self._humidity_pct)

        return self.read_sensor()

    def read_sensor(self) -> HumidityReading:
        rate = self._rate_of_change
        if rate >= HUMIDITY_CONFIG.rapid_rising_rate_threshold_pct_per_cycle:
            trend = HumidityTrend.RAPIDLY_RISING
        elif rate >= HUMIDITY_CONFIG.rising_rate_threshold_pct_per_cycle:
            trend = HumidityTrend.RISING
        elif rate <= -HUMIDITY_CONFIG.rapid_rising_rate_threshold_pct_per_cycle:
            trend = HumidityTrend.RAPIDLY_FALLING
        elif rate <= -HUMIDITY_CONFIG.rising_rate_threshold_pct_per_cycle:
            trend = HumidityTrend.FALLING
        else:
            trend = HumidityTrend.STABLE

        reading = HumidityReading(
            sensor_id=self.sensor_id,
            device_id=self.device_id,
            humidity_pct=round(self._humidity_pct, 2),
            unit="%",
            rate_of_change=rate,
            trend=trend,
            location=self.location,
            status=self.status,
            confidence=0.98 if self.status == SensorHealthStatus.ONLINE else (0.50 if self.status == SensorHealthStatus.DEGRADED else 0.0),
            quality=self.signal_quality if self.status == SensorHealthStatus.ONLINE else (0.45 if self.status == SensorHealthStatus.DEGRADED else 0.0),
            metadata={"mode": "SIMULATED", "profile": self.scenario_profile},
        )
        self.history.append(reading)
        if len(self.history) > 100:
            self.history.pop(0)
        return reading

    def get_health(self) -> SensorHealth:
        from datetime import datetime, timezone
        err = None
        if self.status == SensorHealthStatus.OFFLINE:
            err = "Humidity probe offline / communication loss"
        elif self.status == SensorHealthStatus.DEGRADED:
            err = "Hygrometer sensor signal degraded / high noise"
        return SensorHealth(
            sensor_id=self.sensor_id,
            sensor_type=SensorType.HUMIDITY,
            status=self.status,
            battery_pct=round(self.battery_pct, 1),
            signal_quality=round(self.signal_quality if self.status == SensorHealthStatus.ONLINE else 0.45, 2),
            error_message=err,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
        )


class WaterLevelSimulationAdapter(WaterLevelSensorInterface):
    """
    Hardware-ready Simulation adapter implementing WaterLevelSensorInterface.
    Provides realistic scenario-driven water depth (cm) and flow velocity (m/s) profiles,
    rate of change, trend detection (STABLE, RISING, FALLING, RAPIDLY_RISING, RAPIDLY_FALLING),
    and diagnostic health reporting for hydrostatic level probes and Doppler velocity meters.
    """
    def __init__(
        self,
        sensor_id: str = "ENV-WATER-01",
        device_id: str = "DEV-WATER-01",
        location: Optional[GPSCoordinate] = None,
        scenario_profile: str = "AUTO",
        initial_water_level_cm: float = 0.0,
        initial_flow_mps: float = 0.0,
    ):
        self.sensor_id = sensor_id
        self.device_id = device_id
        self.location = location or GPSCoordinate(latitude=32.3740, longitude=77.2490)
        self.scenario_profile = scenario_profile
        self.status = SensorHealthStatus.ONLINE
        self.battery_pct = 99.0
        self.signal_quality = 0.99
        self.sampling_interval_s = WATER_LEVEL_CONFIG.sampling_interval_seconds

        self._water_level_cm = float(initial_water_level_cm)
        self._prev_water_level_cm = float(initial_water_level_cm)
        self._water_flow_mps = float(initial_flow_mps)
        self._rate_of_change = 0.0
        self.history: list[WaterLevelReading] = []
        self._history_deque: deque[float] = deque(maxlen=WATER_LEVEL_CONFIG.history_window_size)
        self._history_deque.append(self._water_level_cm)
        self.non_contact_engine = NonContactPressureEngine(NonContactPressureConfig())

    def set_status(self, status: SensorHealthStatus) -> None:
        self.status = status

    def set_simulation_profile(self, profile_name: str) -> None:
        self.scenario_profile = profile_name

    def step(
        self,
        rng: Optional[random.Random] = None,
        base_water_level_hint: Optional[float] = None,
        rainfall_rate_mm_h: float = 0.0,
        cycle: int = 0,
    ) -> WaterLevelReading:
        r = rng or random
        self._prev_water_level_cm = self._water_level_cm
        prof = (self.scenario_profile or "AUTO").upper()

        if prof in ("NORMAL", "STABLE", "BASELINE"):
            noise = r.uniform(-0.2, 0.2)
            self._water_level_cm = max(0.0, min(15.0, self._water_level_cm * 0.8 + 2.0 * 0.2 + noise))
            self._water_flow_mps = max(0.05, min(0.5, 0.15 + r.uniform(-0.05, 0.05)))
        elif prof in ("FLOOD", "FLOOD_URBAN", "RISING_FLOOD"):
            rise = r.uniform(4.0, 8.0) + (rainfall_rate_mm_h * 0.08)
            self._water_level_cm = min(WATER_LEVEL_CONFIG.max_water_level_cm, self._water_level_cm + rise)
            self._water_flow_mps = max(0.5, min(2.5, 0.8 + self._water_level_cm * 0.01 + r.uniform(-0.1, 0.1)))
        elif prof in ("FLASH_FLOOD", "CLOUDBURST", "RAPID_FLOOD"):
            rise = r.uniform(12.0, 22.0) + (rainfall_rate_mm_h * 0.15)
            self._water_level_cm = min(WATER_LEVEL_CONFIG.max_water_level_cm, self._water_level_cm + rise)
            self._water_flow_mps = max(1.5, min(4.5, 2.0 + r.uniform(-0.2, 0.5)))
        elif prof in ("DAM_BREAK", "DAM_FAILURE", "CATASTROPHIC_SURGE"):
            rise = r.uniform(30.0, 55.0)
            self._water_level_cm = min(WATER_LEVEL_CONFIG.max_water_level_cm, self._water_level_cm + rise)
            self._water_flow_mps = max(3.5, min(8.0, 4.5 + r.uniform(-0.5, 1.0)))
        elif prof in ("TSUNAMI", "TSUNAMI_SURGE"):
            rise = r.uniform(35.0, 65.0)
            self._water_level_cm = min(WATER_LEVEL_CONFIG.max_water_level_cm, self._water_level_cm + rise)
            self._water_flow_mps = max(4.0, min(10.0, 5.0 + r.uniform(-0.5, 1.5)))
        elif prof in ("STORM_SURGE", "COASTAL_FLOOD"):
            rise = r.uniform(8.0, 16.0)
            self._water_level_cm = min(WATER_LEVEL_CONFIG.max_water_level_cm, self._water_level_cm + rise)
            self._water_flow_mps = max(1.0, min(3.0, 1.5 + r.uniform(-0.2, 0.3)))
        elif prof in ("FALLING", "RECEDING_FLOOD"):
            drop = r.uniform(3.0, 7.0)
            self._water_level_cm = max(0.0, self._water_level_cm - drop)
            self._water_flow_mps = max(0.1, self._water_flow_mps * 0.9)
        elif prof in ("OFFLINE", "SENSOR_FAILURE"):
            self.status = SensorHealthStatus.OFFLINE
        elif prof == "DEGRADED":
            self.status = SensorHealthStatus.DEGRADED
            self.signal_quality = 0.50
        else:
            # AUTO mode
            if base_water_level_hint is not None:
                noise = r.uniform(-0.5, 0.5)
                self._water_level_cm = max(0.0, base_water_level_hint + noise)
            else:
                rain_rise = (rainfall_rate_mm_h * 0.05) if rainfall_rate_mm_h > 10.0 else 0.0
                self._water_level_cm = max(0.0, self._water_level_cm + rain_rise + r.uniform(-0.2, 0.2))
            self._water_flow_mps = max(0.1, min(3.0, 0.2 + (self._water_level_cm * 0.01)))

        self._rate_of_change = round(self._water_level_cm - self._prev_water_level_cm, 3)
        self._history_deque.append(self._water_level_cm)
        return self.read_sensor()

    def read_sensor(self) -> WaterLevelReading:
        rate = self._rate_of_change
        cum_delta = (self._water_level_cm - self._history_deque[0]) if len(self._history_deque) > 1 else rate

        if rate >= WATER_LEVEL_CONFIG.rapid_rising_rate_cm_per_cycle or cum_delta >= 25.0:
            trend = WaterTrend.RAPIDLY_RISING
        elif rate >= 2.0 or cum_delta >= 8.0:
            trend = WaterTrend.RISING
        elif rate <= -WATER_LEVEL_CONFIG.rapid_rising_rate_cm_per_cycle or cum_delta <= -25.0:
            trend = WaterTrend.RAPIDLY_FALLING
        elif rate <= -2.0 or cum_delta <= -8.0:
            trend = WaterTrend.FALLING
        else:
            trend = WaterTrend.STABLE

        if self._water_level_cm >= WATER_LEVEL_CONFIG.critical_threshold_cm:
            cls_val = WaterLevelClassification.CRITICAL
            sev = RiskLevel.CRITICAL
        elif self._water_level_cm >= WATER_LEVEL_CONFIG.high_threshold_cm:
            cls_val = WaterLevelClassification.HIGH
            sev = RiskLevel.HIGH
        elif self._water_level_cm >= WATER_LEVEL_CONFIG.warning_threshold_cm:
            cls_val = WaterLevelClassification.WARNING
            sev = RiskLevel.MEDIUM
        else:
            cls_val = WaterLevelClassification.NORMAL
            sev = RiskLevel.LOW

        # Derive non-contact surface distance & hydrostatic pressure estimation
        depth_m = max(0.0, self._water_level_cm / 100.0)
        mount_h = self.non_contact_engine.config.sensor_mount_height_m
        datum_m = self.non_contact_engine.config.pressure_datum_m
        surface_dist_m = max(0.0, (mount_h - datum_m) - depth_m)

        estimate = self.non_contact_engine.process_reading(
            distance_m=surface_dist_m if self.status != SensorHealthStatus.OFFLINE else None,
            signal_quality=self.signal_quality if self.status == SensorHealthStatus.ONLINE else (0.45 if self.status == SensorHealthStatus.DEGRADED else 0.0),
        )

        reading = WaterLevelReading(
            sensor_id=self.sensor_id,
            device_id=self.device_id,
            water_level_cm=round(self._water_level_cm, 2),
            water_flow_mps=round(self._water_flow_mps, 2),
            unit="cm",
            rate_of_change=rate,
            trend=trend,
            classification=cls_val,
            severity=sev,
            location=self.location,
            status=self.status,
            confidence=0.98 if self.status == SensorHealthStatus.ONLINE else (0.50 if self.status == SensorHealthStatus.DEGRADED else 0.0),
            quality=self.signal_quality if self.status == SensorHealthStatus.ONLINE else (0.45 if self.status == SensorHealthStatus.DEGRADED else 0.0),
            sensor_type=self.non_contact_engine.config.sensor_type,
            measured_surface_distance_m=estimate.measured_surface_distance_m,
            water_depth_m=estimate.water_depth_m,
            estimated_pressure_pa=estimate.estimated_pressure_pa,
            estimated_pressure_kpa=estimate.estimated_pressure_kpa,
            reading_timestamp=estimate.reading_timestamp,
            reading_quality=estimate.reading_quality,
            pressure_source="non_contact_sensor_estimation",
            metadata={"mode": "SIMULATED", "profile": self.scenario_profile, "non_contact_status": estimate.status_message},
        )
        self.history.append(reading)
        if len(self.history) > 100:
            self.history.pop(0)
        return reading

    def get_health(self) -> SensorHealth:
        from datetime import datetime, timezone
        err = None
        if self.status == SensorHealthStatus.OFFLINE:
            err = "Water level probe offline / communication loss"
        elif self.status == SensorHealthStatus.DEGRADED:
            err = "Hydrostatic level probe degraded / signal attenuation"
        return SensorHealth(
            sensor_id=self.sensor_id,
            sensor_type=SensorType.WATER_LEVEL,
            status=self.status,
            battery_pct=round(self.battery_pct, 1),
            signal_quality=round(self.signal_quality if self.status == SensorHealthStatus.ONLINE else 0.45, 2),
            error_message=err,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
        )


class GPSSimulationAdapter(GPSSensorInterface):
    """
    Hardware-ready Simulation adapter implementing GPSSensorInterface.
    Provides realistic GNSS receiver telemetry (latitude, longitude, altitude,
    accuracy, speed, heading, satellite count, fix status, and movement states).

    Simulation Profiles:
    - STATIONARY: Fixed site/device position with realistic GNSS micro-jitter (±0.000015° drift, speed < 0.2 m/s).
    - NORMAL_MOVEMENT: Realistic SAR responder walking patrol (speed 1.2 - 2.5 m/s, bearing updates).
    - RESCUE_TEAM_MOVEMENT: Directed transit toward designated target coordinates (speed 0.6 - 3.0 m/s).
    - SURVIVOR_LOCATION: Position fixed on target survivor coordinates with accuracy radius.
    - GPS_DEGRADED: Low satellite coverage / multipath interference (3 satellites, accuracy > 15m).
    - GPS_SIGNAL_LOSS: Total satellite loss / tunnel / heavy canopy (0 satellites, OFFLINE status).
    - GPS_JUMP: Injects single-cycle impossible jump (>1 km) to trigger anomaly detection.
    - RAPID_MOVEMENT: Fast vehicle / drone transit (speed 15 - 35 m/s).
    - OFFLINE: Hardware probe disconnected / communication failure.
    """
    def __init__(
        self,
        sensor_id: str = "DEV-GPS-01",
        device_id: str = "RESCUE-KIT-01",
        initial_location: Optional[GPSCoordinate] = None,
        scenario_profile: str = "STATIONARY",
        initial_lat: Optional[float] = None,
        initial_lon: Optional[float] = None,
        initial_alt: Optional[float] = None,
        target_lat: Optional[float] = None,
        target_lon: Optional[float] = None,
    ):
        self.sensor_id = sensor_id
        self.device_id = device_id
        if initial_lat is not None and initial_lon is not None:
            loc = GPSCoordinate(latitude=float(initial_lat), longitude=float(initial_lon), altitude_m=float(initial_alt or 3950.0))
        else:
            loc = initial_location or GPSCoordinate(latitude=32.3739, longitude=77.2491, altitude_m=3950.0)
        self._latitude = float(loc.latitude)
        self._longitude = float(loc.longitude)
        self._altitude_m = float(loc.altitude_m if loc.altitude_m is not None else 3950.0)
        self._prev_latitude = self._latitude
        self._prev_longitude = self._longitude
        self.target_lat = float(target_lat) if target_lat is not None else None
        self.target_lon = float(target_lon) if target_lon is not None else None

        self.scenario_profile = scenario_profile
        self.status = SensorHealthStatus.ONLINE
        self.accuracy_m = GPS_CONFIG.default_accuracy_m
        self.speed_mps = 0.0
        self.heading_deg = 0.0
        self.satellites = GPS_CONFIG.default_satellites
        self.battery_pct = 99.0
        self.signal_quality = 0.99
        self.is_valid_fix = True
        self.movement_state = GPSMovementState.STATIONARY
        self.total_distance_m = 0.0
        self.anomaly_count = 0

        self.history: list[GPSReading] = []
        self.trail: list[dict] = []
        self._history_deque: deque[GPSReading] = deque(maxlen=GPS_CONFIG.history_window_size)

    def set_location(self, latitude: float, longitude: float, altitude_m: Optional[float] = None) -> None:
        self._latitude = float(latitude)
        self._longitude = float(longitude)
        if altitude_m is not None:
            self._altitude_m = float(altitude_m)

    def set_status(self, status: SensorHealthStatus) -> None:
        self.status = status

    def set_simulation_profile(self, profile_name: str) -> None:
        self.scenario_profile = profile_name
        p_up = profile_name.upper()
        if p_up in ("OFFLINE", "SIGNAL_LOSS", "GPS_SIGNAL_LOSS", "SENSOR_FAILURE"):
            self.status = SensorHealthStatus.OFFLINE
            self.satellites = 0
            self.is_valid_fix = False
            self.movement_state = GPSMovementState.SIGNAL_LOSS
        elif p_up in ("DEGRADED", "GPS_DEGRADED", "POOR_ACCURACY"):
            self.status = SensorHealthStatus.DEGRADED
            self.satellites = 3
            self.accuracy_m = 25.0
            self.is_valid_fix = True
        elif self.status in (SensorHealthStatus.OFFLINE, SensorHealthStatus.DEGRADED):
            self.status = SensorHealthStatus.ONLINE
            self.satellites = GPS_CONFIG.default_satellites
            self.accuracy_m = GPS_CONFIG.default_accuracy_m
            self.is_valid_fix = True

    def detect_impossible_jump(self, lat1: float, lon1: float, lat2: float, lon2: float, dt_s: float = 1.0) -> bool:
        """Evaluate if displacement between consecutive readings exceeds physical kinematic limits."""
        c1 = GPSCoordinate(latitude=lat1, longitude=lon1)
        c2 = GPSCoordinate(latitude=lat2, longitude=lon2)
        dist_m = c1.haversine_distance_to(c2)
        if dist_m > GPS_CONFIG.jump_distance_threshold_m:
            return True
        calculated_speed = dist_m / max(dt_s, 0.1)
        return calculated_speed > GPS_CONFIG.max_speed_mps

    def step(
        self,
        rng: Optional[random.Random] = None,
        target_location: Optional[GPSCoordinate] = None,
        cycle: int = 1,
        dt_s: float = 1.0,
        **kwargs,
    ) -> GPSReading:
        r = rng or random
        self._prev_latitude = self._latitude
        self._prev_longitude = self._longitude
        prof = self.scenario_profile.upper()

        is_jump = False

        if prof in ("STATIONARY", "FIXED", "NORMAL"):
            # Micro GNSS jitter (1-2 meters drift)
            self._latitude += r.gauss(0, 0.00001)
            self._longitude += r.gauss(0, 0.00001)
            self.speed_mps = round(r.uniform(0.0, 0.15), 2)
            self.heading_deg = (self.heading_deg + r.uniform(-5.0, 5.0)) % 360.0
            self.accuracy_m = round(r.uniform(1.8, 3.2), 1)
            self.satellites = int(r.randint(10, 14))
            self.status = SensorHealthStatus.ONLINE
            self.is_valid_fix = True
            self.movement_state = GPSMovementState.STATIONARY

        elif prof in ("NORMAL_MOVEMENT", "WALKING", "PATROL"):
            # Simulated search patrol: move ~1.4 m/s in current heading with slight curves
            speed = r.uniform(1.2, 2.0)
            self.speed_mps = round(speed, 2)
            self.heading_deg = (self.heading_deg + r.uniform(-10.0, 10.0)) % 360.0
            rad_h = math.radians(self.heading_deg)
            dx = math.sin(rad_h) * speed * dt_s
            dy = math.cos(rad_h) * speed * dt_s
            self._latitude += dy / 111000.0
            self._longitude += dx / (111000.0 * max(0.1, math.cos(math.radians(self._latitude))))
            self.accuracy_m = round(r.uniform(2.0, 4.0), 1)
            self.satellites = int(r.randint(9, 13))
            self.status = SensorHealthStatus.ONLINE
            self.is_valid_fix = True
            self.movement_state = GPSMovementState.MOVING

        elif prof in ("RESCUE_TEAM_MOVEMENT", "DISPATCH_TRANSIT"):
            # Move toward target location if provided
            target = target_location or (GPSCoordinate(latitude=self.target_lat, longitude=self.target_lon) if (self.target_lat is not None and self.target_lon is not None) else None)
            if target:
                bearing = math.degrees(math.atan2(
                    target.longitude - self._longitude,
                    target.latitude - self._latitude
                )) % 360.0
                self.heading_deg = round(bearing, 1)
                curr_c = GPSCoordinate(latitude=self._latitude, longitude=self._longitude)
                dist_m = curr_c.haversine_distance_to(target)
                if dist_m > 3.0:
                    speed = min(dist_m, r.uniform(1.5, 3.5))
                    self.speed_mps = round(speed, 2)
                    frac = min(1.0, (speed * dt_s) / max(dist_m, 1.0))
                    self._latitude += frac * (target.latitude - self._latitude)
                    self._longitude += frac * (target.longitude - self._longitude)
                    self.movement_state = GPSMovementState.MOVING
                else:
                    self.speed_mps = 0.0
                    self.movement_state = GPSMovementState.STATIONARY
            else:
                self.speed_mps = round(r.uniform(1.0, 2.5), 2)
                self.movement_state = GPSMovementState.MOVING
            self.accuracy_m = round(r.uniform(2.0, 3.5), 1)
            self.satellites = int(r.randint(10, 14))
            self.status = SensorHealthStatus.ONLINE
            self.is_valid_fix = True

        elif prof in ("RAPID_MOVEMENT", "VEHICLE", "DRONE"):
            speed = r.uniform(15.0, 25.0)
            self.speed_mps = round(speed, 2)
            rad_h = math.radians(self.heading_deg)
            dx = math.sin(rad_h) * speed * dt_s
            dy = math.cos(rad_h) * speed * dt_s
            self._latitude += dy / 111000.0
            self._longitude += dx / (111000.0 * max(0.1, math.cos(math.radians(self._latitude))))
            self.accuracy_m = round(r.uniform(3.0, 6.0), 1)
            self.satellites = int(r.randint(8, 12))
            self.status = SensorHealthStatus.ONLINE
            self.is_valid_fix = True
            self.movement_state = GPSMovementState.RAPID_MOVEMENT

        elif prof in ("SURVIVOR_LOCATION", "VICTIM_LOCATED"):
            if target_location:
                self._latitude = target_location.latitude + r.gauss(0, 0.00001)
                self._longitude = target_location.longitude + r.gauss(0, 0.00001)
            self.speed_mps = 0.0
            self.accuracy_m = round(r.uniform(1.5, 3.0), 1)
            self.satellites = int(r.randint(11, 15))
            self.status = SensorHealthStatus.ONLINE
            self.is_valid_fix = True
            self.movement_state = GPSMovementState.STATIONARY

        elif prof in ("GPS_DEGRADED", "DEGRADED", "NOISY"):
            self._latitude += r.gauss(0, 0.0002)
            self._longitude += r.gauss(0, 0.0002)
            self.accuracy_m = round(r.uniform(18.0, 35.0), 1)
            self.satellites = int(r.randint(2, 4))
            self.status = SensorHealthStatus.DEGRADED
            self.is_valid_fix = True
            self.movement_state = GPSMovementState.MOVING if self.speed_mps > 0.5 else GPSMovementState.STATIONARY

        elif prof in ("GPS_SIGNAL_LOSS", "OFFLINE", "SIGNAL_LOSS"):
            self.satellites = 0
            self.accuracy_m = 999.0
            self.status = SensorHealthStatus.OFFLINE
            self.is_valid_fix = False
            self.movement_state = GPSMovementState.SIGNAL_LOSS

        elif prof in ("GPS_JUMP", "JUMP_ANOMALY", "SPOOFING"):
            # Inject jump of ~2-5 km
            self._latitude += r.uniform(0.02, 0.05)
            self._longitude += r.uniform(0.02, 0.05)
            self.speed_mps = 250.0
            self.movement_state = GPSMovementState.JUMP_ANOMALY
            self.anomaly_count += 1
            is_jump = True

        else:
            self._latitude += r.gauss(0, 0.00001)
            self._longitude += r.gauss(0, 0.00001)

        # Check for impossible jump
        if not is_jump and self.detect_impossible_jump(self._prev_latitude, self._prev_longitude, self._latitude, self._longitude, dt_s):
            self.movement_state = GPSMovementState.JUMP_ANOMALY
            self.anomaly_count += 1

        # Distance accumulation
        step_dist = GPSCoordinate(latitude=self._prev_latitude, longitude=self._prev_longitude).haversine_distance_to(
            GPSCoordinate(latitude=self._latitude, longitude=self._longitude)
        )
        if step_dist < GPS_CONFIG.jump_distance_threshold_m:
            self.total_distance_m += step_dist

        return self.read_sensor()

    def read_sensor(self) -> GPSReading:
        if self.status == SensorHealthStatus.OFFLINE or self.satellites == 0:
            fix_quality = "NO_FIX"
        elif self.status == SensorHealthStatus.DEGRADED or self.satellites < 4 or self.accuracy_m > 15.0:
            fix_quality = "DEGRADED_FIX"
        else:
            fix_quality = "3D_FIX_PRECISION"

        reading = GPSReading(
            sensor_id=self.sensor_id,
            device_id=self.device_id,
            sensor_type=SensorType.GPS,
            latitude=round(self._latitude, 6),
            longitude=round(self._longitude, 6),
            altitude_m=round(self._altitude_m, 1),
            accuracy_m=round(self.accuracy_m, 2),
            speed_mps=round(self.speed_mps, 2),
            heading_deg=round(self.heading_deg, 1),
            satellites=int(self.satellites),
            movement_state=self.movement_state,
            is_valid_fix=bool(self.is_valid_fix),
            fix_quality=fix_quality,
            status=self.status,
            confidence=0.98 if self.status == SensorHealthStatus.ONLINE else (0.50 if self.status == SensorHealthStatus.DEGRADED else 0.0),
            quality=self.signal_quality if self.status == SensorHealthStatus.ONLINE else (0.40 if self.status == SensorHealthStatus.DEGRADED else 0.0),
            metadata={"mode": "SIMULATED", "profile": self.scenario_profile, "total_distance_m": round(self.total_distance_m, 1)},
        )
        self.history.append(reading)
        if len(self.history) > 100:
            self.history.pop(0)

        self.trail.append({
            "latitude": reading.latitude,
            "longitude": reading.longitude,
            "timestamp": reading.timestamp,
            "speed_mps": reading.speed_mps,
        })
        if len(self.trail) > 200:
            self.trail.pop(0)

        return reading

    def get_health(self) -> SensorHealth:
        from datetime import datetime, timezone
        err = None
        if self.status == SensorHealthStatus.OFFLINE or not self.is_valid_fix:
            err = "GPS receiver signal lost / no satellite lock (0 satellites)"
        elif self.status == SensorHealthStatus.DEGRADED or self.accuracy_m > GPS_CONFIG.degraded_accuracy_m:
            err = f"Degraded GNSS fix: poor geometry ({self.satellites} satellites, ±{self.accuracy_m:.1f}m accuracy)"
        return SensorHealth(
            sensor_id=self.sensor_id,
            sensor_type=SensorType.GPS,
            status=self.status,
            battery_pct=round(self.battery_pct, 1),
            signal_quality=round(self.signal_quality if self.status == SensorHealthStatus.ONLINE else 0.40, 2),
            error_message=err,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
        )


# --------------------------------------------------------------------------- #
# Soil Moisture & Tilt Simulation Adapter
# --------------------------------------------------------------------------- #

@dataclass
class _SlopeNodeState:
    node_id: str
    sensor_id_soil: str
    sensor_id_tilt: str
    device_id: str
    location: GPSCoordinate
    baseline_soil_moisture_pct: float
    baseline_tilt_deg: float
    soil_moisture_pct: float
    prev_soil_moisture_pct: float
    tilt_x: float = 0.0
    tilt_y: float = 0.0
    tilt_z: float = 1.0
    tilt_angle_deg: float = 0.5
    prev_tilt_angle_deg: float = 0.5
    moisture_rate: float = 0.0
    tilt_rate: float = 0.0
    moisture_trend: MoistureTrend = MoistureTrend.STABLE
    tilt_trend: TiltTrend = TiltTrend.STABLE
    status: SensorHealthStatus = SensorHealthStatus.ONLINE
    battery_pct: float = 99.0
    signal_quality: float = 0.99
    moisture_history: deque[float] = field(default_factory=lambda: deque(maxlen=LANDSLIDE_CONFIG.history_window_size))
    tilt_history: deque[float] = field(default_factory=lambda: deque(maxlen=LANDSLIDE_CONFIG.history_window_size))
    persistence_cycles: int = 0
    recovery_cycles: int = 0
    event_state: LandslideEventState = LandslideEventState.NORMAL


class LandslideSensorSimulationAdapter(SoilMoistureSensorInterface, TiltSensorInterface):
    """
    Hardware-ready Simulation adapter for multi-node Soil Moisture (FDR) and Tilt (Inclinometer) sensors.
    Features:
    - Multi-node slope deployment (SLOPE-NODE-01: Upper Ridge, SLOPE-NODE-02: Mid-Slope, SLOPE-NODE-03: Base Slope)
    - Node baseline calibrations with mean-reverting drift
    - 9 Deterministic & Configurable Simulation Profiles:
      * NORMAL: Stable baseline moisture & tilt, low risk
      * WET_SOIL: Increasing moisture, stable tilt, moderate concern
      * INCREASING_MOISTURE: Saturated soil (>75%), baseline tilt
      * TILT_ANOMALY: Tilt deviation without soil saturation (rock displacement/creep)
      * EARLY_LANDSLIDE: Concurrently increasing moisture & tilt (early warning)
      * CRITICAL_LANDSLIDE: Saturated moisture + rapid tilt escalation (critical hazard)
      * SENSOR_FAILURE: Offline/degraded sensor telemetry, confidence drop
      * NOISY_SENSOR: Single cycle spike, debounced by persistence filter
      * RECOVERY: Gradual step-down normalization back to baseline
    - Explainable multi-factor Landslide Risk Score calculation (0-100)
    - Full diagnostic health reporting
    """
    def __init__(
        self,
        scenario_profile: str = "NORMAL",
        base_location: Optional[GPSCoordinate] = None,
        initial_moisture_pct: Optional[float] = None,
        initial_tilt_deg: Optional[float] = None,
    ):
        loc = base_location or GPSCoordinate(latitude=32.3740, longitude=77.2490)
        m0 = initial_moisture_pct if (initial_moisture_pct is not None and initial_moisture_pct > 0.0) else 38.0
        t0 = initial_tilt_deg if (initial_tilt_deg is not None and initial_tilt_deg > 0.0) else 0.5
        self.scenario_profile = scenario_profile
        self.cycle_count = 0
        self.single_spike_fired = False

        # Initialize 3 slope telemetry nodes
        self.nodes: dict[str, _SlopeNodeState] = {
            "SLOPE-NODE-01": _SlopeNodeState(
                node_id="SLOPE-NODE-01",
                sensor_id_soil="SOIL-NODE-01",
                sensor_id_tilt="TILT-NODE-01",
                device_id="DEV-SLOPE-01",
                location=GPSCoordinate(latitude=round(loc.latitude + 0.0010, 4), longitude=round(loc.longitude - 0.0005, 4), altitude_m=(loc.altitude_m + 60.0) if loc.altitude_m is not None else 3200.0),
                baseline_soil_moisture_pct=max(10.0, m0 - 3.0),
                baseline_tilt_deg=max(0.1, t0 - 0.1),
                soil_moisture_pct=max(10.0, m0 - 3.0),
                prev_soil_moisture_pct=max(10.0, m0 - 3.0),
                tilt_angle_deg=max(0.1, t0 - 0.1),
                prev_tilt_angle_deg=max(0.1, t0 - 0.1),
            ),
            "SLOPE-NODE-02": _SlopeNodeState(
                node_id="SLOPE-NODE-02",
                sensor_id_soil="SOIL-NODE-02",
                sensor_id_tilt="TILT-NODE-02",
                device_id="DEV-SLOPE-02",
                location=GPSCoordinate(latitude=round(loc.latitude, 4), longitude=round(loc.longitude, 4), altitude_m=loc.altitude_m if loc.altitude_m is not None else 3140.0),
                baseline_soil_moisture_pct=m0,
                baseline_tilt_deg=t0,
                soil_moisture_pct=m0,
                prev_soil_moisture_pct=m0,
                tilt_angle_deg=t0,
                prev_tilt_angle_deg=t0,
            ),
            "SLOPE-NODE-03": _SlopeNodeState(
                node_id="SLOPE-NODE-03",
                sensor_id_soil="SOIL-NODE-03",
                sensor_id_tilt="TILT-NODE-03",
                device_id="DEV-SLOPE-03",
                location=GPSCoordinate(latitude=round(loc.latitude - 0.0010, 4), longitude=round(loc.longitude + 0.0005, 4), altitude_m=(loc.altitude_m - 55.0) if loc.altitude_m is not None else 3085.0),
                baseline_soil_moisture_pct=min(90.0, m0 + 4.0),
                baseline_tilt_deg=t0 + 0.4,
                soil_moisture_pct=min(90.0, m0 + 4.0),
                prev_soil_moisture_pct=min(90.0, m0 + 4.0),
                tilt_angle_deg=t0 + 0.4,
                prev_tilt_angle_deg=t0 + 0.4,
            ),
        }
        for n in self.nodes.values():
            n.moisture_history.append(n.soil_moisture_pct)
            n.tilt_history.append(n.tilt_angle_deg)

    def set_scenario_profile(self, profile: str) -> None:
        self.scenario_profile = profile.upper()
        if self.scenario_profile == "NOISY_SENSOR":
            self.single_spike_fired = False

    def set_node_status(self, node_id: str, status: SensorHealthStatus) -> None:
        if node_id in self.nodes:
            self.nodes[node_id].status = status

    def set_node_moisture(self, node_id: str, moisture_pct: float) -> None:
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.prev_soil_moisture_pct = node.soil_moisture_pct
            node.soil_moisture_pct = max(0.0, min(100.0, moisture_pct))
            node.moisture_rate = round(node.soil_moisture_pct - node.prev_soil_moisture_pct, 3)
            node.moisture_history.append(node.soil_moisture_pct)
            self._update_trends(node)

    def set_node_tilt(self, node_id: str, tilt_deg: float) -> None:
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.prev_tilt_angle_deg = node.tilt_angle_deg
            node.tilt_angle_deg = max(0.0, min(90.0, tilt_deg))
            node.tilt_rate = round(node.tilt_angle_deg - node.prev_tilt_angle_deg, 3)
            node.tilt_history.append(node.tilt_angle_deg)
            rad = math.radians(node.tilt_angle_deg)
            node.tilt_x = round(math.sin(rad) * 0.707, 3)
            node.tilt_y = round(math.sin(rad) * 0.707, 3)
            node.tilt_z = round(math.cos(rad), 3)
            self._update_trends(node)

    def _update_trends(self, node: _SlopeNodeState) -> None:
        mr = node.moisture_rate
        if mr >= LANDSLIDE_CONFIG.moisture_rapid_rising_rate_threshold:
            node.moisture_trend = MoistureTrend.RAPIDLY_RISING
        elif mr >= LANDSLIDE_CONFIG.moisture_rising_rate_threshold:
            node.moisture_trend = MoistureTrend.RISING
        elif mr <= -LANDSLIDE_CONFIG.moisture_rapid_rising_rate_threshold:
            node.moisture_trend = MoistureTrend.RAPIDLY_FALLING
        elif mr <= -LANDSLIDE_CONFIG.moisture_rising_rate_threshold:
            node.moisture_trend = MoistureTrend.FALLING
        else:
            node.moisture_trend = MoistureTrend.STABLE

        tr = node.tilt_rate
        if tr >= LANDSLIDE_CONFIG.tilt_rapid_rising_rate_threshold:
            node.tilt_trend = TiltTrend.RAPIDLY_RISING
        elif tr >= LANDSLIDE_CONFIG.tilt_rising_rate_threshold:
            node.tilt_trend = TiltTrend.RISING
        elif tr <= -LANDSLIDE_CONFIG.tilt_rapid_rising_rate_threshold:
            node.tilt_trend = TiltTrend.RAPIDLY_FALLING
        elif tr <= -LANDSLIDE_CONFIG.tilt_rising_rate_threshold:
            node.tilt_trend = TiltTrend.FALLING
        else:
            node.tilt_trend = TiltTrend.STABLE

    def step(
        self,
        rng: Optional[random.Random] = None,
        rainfall_mm_hr: float = 0.0,
        vibration_mm_s: float = 0.0,
    ) -> list[LandslideRiskAssessment]:
        r = rng or random
        self.cycle_count += 1
        prof = self.scenario_profile.upper()
        assessments: list[LandslideRiskAssessment] = []

        for idx, (nid, node) in enumerate(self.nodes.items()):
            node.prev_soil_moisture_pct = node.soil_moisture_pct
            node.prev_tilt_angle_deg = node.tilt_angle_deg

            if prof in ("NORMAL", "NORMAL_SLOPE"):
                node.status = SensorHealthStatus.ONLINE
                noise_m = r.uniform(-0.3, 0.3)
                rain_effect = (rainfall_mm_hr * 0.12) if rainfall_mm_hr > 0 else 0.0
                if rain_effect > 0:
                    node.soil_moisture_pct = min(95.0, node.soil_moisture_pct + rain_effect + noise_m)
                else:
                    node.soil_moisture_pct = max(0.0, min(100.0, node.soil_moisture_pct * 0.8 + node.baseline_soil_moisture_pct * 0.2 + noise_m))
                noise_t = r.uniform(-0.04, 0.04)
                if node.tilt_angle_deg > (node.baseline_tilt_deg + 1.0):
                    # Plastic deformation: retain elevated tilt unless explicitly in RECOVERY mode
                    node.tilt_angle_deg = max(0.0, min(90.0, node.tilt_angle_deg + noise_t))
                else:
                    node.tilt_angle_deg = max(0.0, min(90.0, node.tilt_angle_deg * 0.8 + node.baseline_tilt_deg * 0.2 + noise_t))
                node.recovery_cycles = 0

            elif prof in ("WET_SOIL", "WET"):
                node.status = SensorHealthStatus.ONLINE
                target = min(68.0, node.baseline_soil_moisture_pct + 24.0 + idx * 2.5)
                node.soil_moisture_pct = min(target, node.soil_moisture_pct + r.uniform(2.0, 3.5))
                node.tilt_angle_deg = max(0.0, min(1.2, node.tilt_angle_deg * 0.8 + node.baseline_tilt_deg * 0.2 + r.uniform(-0.03, 0.03)))

            elif prof in ("INCREASING_MOISTURE", "SATURATING"):
                node.status = SensorHealthStatus.ONLINE
                node.soil_moisture_pct = min(88.0, max(58.0, node.soil_moisture_pct + r.uniform(3.0, 5.0)))
                node.tilt_angle_deg = max(0.0, min(1.3, node.tilt_angle_deg * 0.8 + node.baseline_tilt_deg * 0.2 + r.uniform(-0.03, 0.03)))

            elif prof in ("TILT_ANOMALY", "CREEP"):
                node.status = SensorHealthStatus.ONLINE
                node.soil_moisture_pct = max(0.0, min(50.0, node.soil_moisture_pct * 0.8 + node.baseline_soil_moisture_pct * 0.2 + r.uniform(-0.3, 0.3)))
                target_tilt = 3.8 + idx * 0.4
                node.tilt_angle_deg = min(target_tilt, node.tilt_angle_deg + r.uniform(0.6, 1.2))

            elif prof in ("EARLY_LANDSLIDE", "EARLY_WARNING"):
                node.status = SensorHealthStatus.ONLINE
                target_m = 75.0 + idx * 3.0
                node.soil_moisture_pct = min(target_m, max(68.0, node.soil_moisture_pct + r.uniform(3.0, 5.0)))
                target_t = 3.2 + idx * 0.4
                node.tilt_angle_deg = min(target_t, max(2.5, node.tilt_angle_deg + r.uniform(0.5, 1.0)))

            elif prof in ("CRITICAL_LANDSLIDE", "CRITICAL", "LANDSLIDE"):
                node.status = SensorHealthStatus.ONLINE
                node.soil_moisture_pct = min(94.0, max(82.0, node.soil_moisture_pct + r.uniform(3.0, 5.0)))
                node.tilt_angle_deg = min(12.0, node.tilt_angle_deg + r.uniform(0.8, 1.6))

            elif prof in ("SENSOR_FAILURE", "FAILURE", "OFFLINE"):
                node.status = SensorHealthStatus.OFFLINE
                node.signal_quality = 0.0
                node.battery_pct = max(0.0, node.battery_pct - 10.0)

            elif prof in ("NOISY_SENSOR", "NOISE"):
                node.status = SensorHealthStatus.ONLINE
                if not self.single_spike_fired:
                    node.soil_moisture_pct = 85.0
                    node.tilt_angle_deg = 5.2
                    self.single_spike_fired = True
                else:
                    node.soil_moisture_pct = node.baseline_soil_moisture_pct + r.uniform(-0.3, 0.3)
                    node.tilt_angle_deg = node.baseline_tilt_deg + r.uniform(-0.04, 0.04)

            elif prof in ("RECOVERY", "NORMALIZING"):
                node.status = SensorHealthStatus.ONLINE
                node.soil_moisture_pct = max(node.baseline_soil_moisture_pct, node.soil_moisture_pct - r.uniform(5.0, 10.0))
                node.tilt_angle_deg = max(node.baseline_tilt_deg, node.tilt_angle_deg - r.uniform(1.0, 2.0))

            # Rates & histories
            node.moisture_rate = round(node.soil_moisture_pct - node.prev_soil_moisture_pct, 3)
            node.tilt_rate = round(node.tilt_angle_deg - node.prev_tilt_angle_deg, 3)
            node.moisture_history.append(node.soil_moisture_pct)
            node.tilt_history.append(node.tilt_angle_deg)
            self._update_trends(node)

            # Reconstruct 3-axis gravity vector
            rad = math.radians(node.tilt_angle_deg)
            node.tilt_x = round(math.sin(rad) * 0.707, 3)
            node.tilt_y = round(math.sin(rad) * 0.707, 3)
            node.tilt_z = round(math.cos(rad), 3)

            # Evaluate Assessment
            assessment = self.assess_node_risk(node, rainfall_mm_hr=rainfall_mm_hr, vibration_mm_s=vibration_mm_s)
            assessments.append(assessment)

        return assessments

    def assess_node_risk(
        self,
        node: _SlopeNodeState,
        rainfall_mm_hr: float = 0.0,
        vibration_mm_s: float = 0.0,
    ) -> LandslideRiskAssessment:
        m = node.soil_moisture_pct
        t = node.tilt_angle_deg
        factors: list[str] = []

        if node.status in (SensorHealthStatus.OFFLINE, SensorHealthStatus.ERROR):
            return LandslideRiskAssessment(
                node_id=node.node_id,
                location=node.location,
                soil_moisture_pct=round(m, 2),
                moisture_trend=MoistureTrend.UNKNOWN,
                moisture_rate=0.0,
                tilt_angle_deg=round(t, 2),
                tilt_trend=TiltTrend.UNKNOWN,
                tilt_rate=0.0,
                persistence_cycles=0,
                landslide_risk_score=0.0,
                risk_level=LandslideRiskLevel.LOW,
                confidence=0.0,
                event_state=LandslideEventState.NORMAL,
                contributing_factors=["Telemetry offline / communication unacquired", "Insufficient sensor data"],
                recommended_action="Inspect slope telemetry node; check battery and LoRa link.",
                status=node.status,
                quality=0.0,
            )

        # 1. Soil Moisture Subscore (0 - 25 pts)
        if m <= LANDSLIDE_CONFIG.moisture_elevated_threshold_pct:
            moisture_score = (m / max(LANDSLIDE_CONFIG.moisture_elevated_threshold_pct, 1.0)) * 8.0
        elif m <= LANDSLIDE_CONFIG.moisture_high_threshold_pct:
            moisture_score = 8.0 + ((m - LANDSLIDE_CONFIG.moisture_elevated_threshold_pct) / (LANDSLIDE_CONFIG.moisture_high_threshold_pct - LANDSLIDE_CONFIG.moisture_elevated_threshold_pct)) * 10.0
            factors.append(f"Elevated soil saturation ({m:.1f}%)")
        else:
            moisture_score = 18.0 + min(7.0, ((m - LANDSLIDE_CONFIG.moisture_high_threshold_pct) / (LANDSLIDE_CONFIG.moisture_critical_threshold_pct - LANDSLIDE_CONFIG.moisture_high_threshold_pct)) * 7.0)
            factors.append(f"Critical soil water saturation ({m:.1f}%)")

        # 2. Moisture Trend / Rate Bonus (0 - 15 pts)
        if node.moisture_trend == MoistureTrend.RAPIDLY_RISING:
            moisture_trend_bonus = 15.0
            factors.append(f"Rapid soil saturation rate (+{node.moisture_rate:.1f}%/cycle)")
        elif node.moisture_trend == MoistureTrend.RISING:
            moisture_trend_bonus = 8.0
            factors.append(f"Rising soil saturation trend (+{node.moisture_rate:.1f}%/cycle)")
        elif node.moisture_trend == MoistureTrend.FALLING:
            moisture_trend_bonus = -3.0
        elif node.moisture_trend == MoistureTrend.RAPIDLY_FALLING:
            moisture_trend_bonus = -6.0
        else:
            moisture_trend_bonus = 0.0

        # 3. Tilt Magnitude Subscore (0 - 25 pts)
        if t <= LANDSLIDE_CONFIG.tilt_elevated_threshold_deg:
            tilt_score = (t / max(LANDSLIDE_CONFIG.tilt_elevated_threshold_deg, 0.1)) * 6.0
        elif t <= LANDSLIDE_CONFIG.tilt_high_threshold_deg:
            tilt_score = 6.0 + ((t - LANDSLIDE_CONFIG.tilt_elevated_threshold_deg) / (LANDSLIDE_CONFIG.tilt_high_threshold_deg - LANDSLIDE_CONFIG.tilt_elevated_threshold_deg)) * 11.0
            factors.append(f"Inclinometer slope angle deviation ({t:.1f}°)")
        else:
            tilt_score = 17.0 + min(8.0, ((t - LANDSLIDE_CONFIG.tilt_high_threshold_deg) / (LANDSLIDE_CONFIG.tilt_critical_threshold_deg - LANDSLIDE_CONFIG.tilt_high_threshold_deg)) * 8.0)
            factors.append(f"Severe inclinometer slope shear ({t:.1f}°)")

        # 4. Tilt Trend / Rate Bonus (0 - 25 pts)
        if node.tilt_trend == TiltTrend.RAPIDLY_RISING:
            tilt_trend_bonus = 25.0
            factors.append(f"Rapid slope shear rate (+{node.tilt_rate:.2f}°/cycle)")
        elif node.tilt_trend == TiltTrend.RISING:
            tilt_trend_bonus = 14.0
            factors.append(f"Rising tilt shift trend (+{node.tilt_rate:.2f}°/cycle)")
        elif node.tilt_trend == TiltTrend.FALLING:
            tilt_trend_bonus = -5.0
        elif node.tilt_trend == TiltTrend.RAPIDLY_FALLING:
            tilt_trend_bonus = -10.0
        else:
            tilt_trend_bonus = 0.0

        # 5. Compound Context & Persistence Filter (0 - 10 pts)
        is_abnormal = (m >= LANDSLIDE_CONFIG.moisture_elevated_threshold_pct or t >= LANDSLIDE_CONFIG.tilt_elevated_threshold_deg)
        if is_abnormal:
            node.persistence_cycles += 1
            node.recovery_cycles = 0
        else:
            node.recovery_cycles += 1
            if node.recovery_cycles >= LANDSLIDE_CONFIG.recovery_cycles_required:
                node.persistence_cycles = 0

        persistence_bonus = 0.0
        if node.persistence_cycles >= 2 and (m >= 60.0 or t >= 2.0):
            persistence_bonus += 5.0
            factors.append(f"Sustained abnormal condition ({node.persistence_cycles} cycles)")
        if node.persistence_cycles >= 3 and (m >= 75.0 and t >= 3.0):
            persistence_bonus += 5.0

        if rainfall_mm_hr >= 25.0:
            persistence_bonus += 3.0
            factors.append(f"Torrential precipitation trigger ({rainfall_mm_hr:.1f} mm/hr)")
        if vibration_mm_s >= 4.0:
            persistence_bonus += 3.0
            factors.append(f"Seismic ground shaking trigger ({vibration_mm_s:.1f} mm/s)")

        persistence_score = min(10.0, persistence_bonus)

        # Single spike debouncing check:
        # If persistence is only 1 cycle and only 1 sensor flared without sustained confirmation
        raw_score = max(0.0, min(100.0, moisture_score + moisture_trend_bonus + tilt_score + tilt_trend_bonus + persistence_score))
        if node.persistence_cycles <= 1 and raw_score >= LANDSLIDE_CONFIG.risk_critical_min and not (m >= 85.0 and t >= 5.0 and len(node.moisture_history) > 1 and node.moisture_history[-2] >= 75.0):
            # Debounce single cycle spike to high threshold max
            raw_score = min(raw_score, 68.0)
            factors.append("Single spike under persistence filter (unconfirmed)")

        score = round(raw_score, 1)

        # Classification
        if score >= LANDSLIDE_CONFIG.risk_critical_min:
            risk_level = LandslideRiskLevel.CRITICAL
            node.event_state = LandslideEventState.CRITICAL
            action = "Immediate slope evacuation: Deploy geotechnical barriers, halt base operations, and clear downstream zones."
        elif score >= LANDSLIDE_CONFIG.risk_high_max - 24.0:  # 50.0 - 74.9
            risk_level = LandslideRiskLevel.HIGH
            node.event_state = LandslideEventState.HIGH_RISK
            action = "Escalate slope monitoring: Restrict slope-base access and stage geotechnical rescue assets."
        elif score >= LANDSLIDE_CONFIG.risk_low_max + 1.0:    # 25.0 - 49.9
            risk_level = LandslideRiskLevel.MODERATE
            node.event_state = LandslideEventState.WATCH if score < 38.0 else LandslideEventState.ELEVATED
            action = "Maintain heightened surveillance: Track moisture/tilt trajectory and survey drainage paths."
        else:
            risk_level = LandslideRiskLevel.LOW
            if node.event_state in (LandslideEventState.CRITICAL, LandslideEventState.HIGH_RISK) and node.recovery_cycles < LANDSLIDE_CONFIG.recovery_cycles_required:
                node.event_state = LandslideEventState.RECOVERY
                action = "Slope stabilization observed; conducting post-event ground verification."
            else:
                node.event_state = LandslideEventState.NORMAL
                action = "Routine slope stability monitoring active."

        if not factors:
            factors.append("Stable slope equilibrium within nominal thresholds")

        return LandslideRiskAssessment(
            node_id=node.node_id,
            location=node.location,
            soil_moisture_pct=round(m, 2),
            moisture_trend=node.moisture_trend,
            moisture_rate=round(node.moisture_rate, 3),
            tilt_angle_deg=round(t, 2),
            tilt_trend=node.tilt_trend,
            tilt_rate=round(node.tilt_rate, 3),
            persistence_cycles=node.persistence_cycles,
            landslide_risk_score=score,
            risk_level=risk_level,
            confidence=0.96 if node.status == SensorHealthStatus.ONLINE else 0.5,
            event_state=node.event_state,
            contributing_factors=factors,
            recommended_action=action,
            status=node.status,
            quality=node.signal_quality,
        )

    def read_soil_moisture(self, node_id: Optional[str] = None) -> SoilMoistureReading:
        nid = node_id or "SLOPE-NODE-01"
        node = self.nodes.get(nid, next(iter(self.nodes.values())))
        return SoilMoistureReading(
            sensor_id=node.sensor_id_soil,
            node_id=node.node_id,
            device_id=node.device_id,
            soil_moisture_pct=round(node.soil_moisture_pct, 2),
            rate_of_change=round(node.moisture_rate, 3),
            trend=node.moisture_trend,
            location=node.location,
            status=node.status,
            confidence=0.95 if node.status == SensorHealthStatus.ONLINE else (0.5 if node.status == SensorHealthStatus.DEGRADED else 0.0),
            quality=node.signal_quality,
            metadata={"mode": "SIMULATED", "scenario_profile": self.scenario_profile},
        )

    def read_tilt(self, node_id: Optional[str] = None) -> TiltReading:
        nid = node_id or "SLOPE-NODE-01"
        node = self.nodes.get(nid, next(iter(self.nodes.values())))
        return TiltReading(
            sensor_id=node.sensor_id_tilt,
            node_id=node.node_id,
            device_id=node.device_id,
            tilt_x=node.tilt_x,
            tilt_y=node.tilt_y,
            tilt_z=node.tilt_z,
            tilt_angle_deg=round(node.tilt_angle_deg, 2),
            tilt_rate=round(node.tilt_rate, 3),
            trend=node.tilt_trend,
            location=node.location,
            status=node.status,
            confidence=0.95 if node.status == SensorHealthStatus.ONLINE else (0.5 if node.status == SensorHealthStatus.DEGRADED else 0.0),
            quality=node.signal_quality,
            metadata={"mode": "SIMULATED", "scenario_profile": self.scenario_profile},
        )

    def get_soil_health(self, node_id: Optional[str] = None) -> SensorHealth:
        nid = node_id or "SLOPE-NODE-01"
        node = self.nodes.get(nid, next(iter(self.nodes.values())))
        from datetime import datetime, timezone
        return SensorHealth(
            sensor_id=node.sensor_id_soil,
            sensor_type=SensorType.SOIL_MOISTURE,
            status=node.status,
            battery_pct=round(node.battery_pct, 1),
            signal_quality=round(node.signal_quality, 2),
            error_message="Moisture probe offline" if node.status == SensorHealthStatus.OFFLINE else None,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
        )

    def get_tilt_health(self, node_id: Optional[str] = None) -> SensorHealth:
        nid = node_id or "SLOPE-NODE-01"
        node = self.nodes.get(nid, next(iter(self.nodes.values())))
        from datetime import datetime, timezone
        return SensorHealth(
            sensor_id=node.sensor_id_tilt,
            sensor_type=SensorType.IMU_TILT,
            status=node.status,
            battery_pct=round(node.battery_pct, 1),
            signal_quality=round(node.signal_quality, 2),
            error_message="Inclinometer offline" if node.status == SensorHealthStatus.OFFLINE else None,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
        )

    def get_primary_node_moisture(self) -> float:
        return round(self.nodes["SLOPE-NODE-01"].soil_moisture_pct, 1)

    def get_primary_node_tilt(self) -> float:
        return round(self.nodes["SLOPE-NODE-01"].tilt_angle_deg, 2)

    def reset(self) -> None:
        self.cycle_count = 0
        self.single_spike_fired = False
        for node in self.nodes.values():
            node.soil_moisture_pct = node.baseline_soil_moisture_pct
            node.prev_soil_moisture_pct = node.baseline_soil_moisture_pct
            node.tilt_angle_deg = node.baseline_tilt_deg
            node.prev_tilt_angle_deg = node.baseline_tilt_deg
            node.moisture_rate = 0.0
            node.tilt_rate = 0.0
            node.moisture_trend = MoistureTrend.STABLE
            node.tilt_trend = TiltTrend.STABLE
            node.persistence_cycles = 0
            node.recovery_cycles = 0
            node.event_state = LandslideEventState.NORMAL
            node.moisture_history.clear()
            node.tilt_history.clear()
            node.moisture_history.append(node.soil_moisture_pct)
            node.tilt_history.append(node.tilt_angle_deg)


# --------------------------------------------------------------------------- #
# Optical Camera Simulation Adapter
# --------------------------------------------------------------------------- #

@dataclass
class _CameraNodeState:
    camera_id: str
    device_id: str
    victim_id: Optional[str]
    location: GPSCoordinate
    detection_state: CameraDetectionState = CameraDetectionState.NO_DETECTION
    detection_type: str = "none"
    classification: CameraClassification = CameraClassification.UNKNOWN
    classification_confidence: float = 0.0
    person_count: int = 0
    confidence: float = 0.0
    visibility: float = 1.0
    occlusion: float = 0.0
    image_quality: float = 1.0
    motion_detected: bool = False
    smoke_present: bool = False
    fire_visible: bool = False
    debris_present: bool = False
    orientation: str = "0° NADIR"
    field_of_view_deg: float = 85.0
    range_m: float = 30.0
    status: CameraHealthStatus = CameraHealthStatus.ONLINE
    health_score: float = 100.0
    confidence_history: deque[float] = field(default_factory=lambda: deque(maxlen=30))


class CameraSimulationAdapter(CameraSensorInterface):
    """
    Hardware-ready simulation adapter for optical / RGB camera channels.
    Supports multi-camera arrays (CAM-001..CAM-004 + CAM-SITE-01),
    realistic optical visibility/occlusion physics, scenario-aware degradation,
    false-positive generation (mannequins/debris), and manual test profiles.
    """
    def __init__(
        self,
        victims: Optional[list[VictimProfile]] = None,
        base_location: Optional[GPSCoordinate] = None,
        scenario_id: Optional[str] = None,
    ):
        self.scenario_id = scenario_id or "earthquake_building_collapse"
        self.profile = "AUTO"
        self.cycle_count = 0
        loc = base_location or GPSCoordinate(latitude=32.3740, longitude=77.2490, altitude_m=3950.0)

        self.cameras: dict[str, _CameraNodeState] = {}
        vlist = victims or []
        for i, v in enumerate(vlist):
            cid = f"CAM-00{i+1}"
            vloc = v.location if hasattr(v, "location") and v.location else loc
            self.cameras[cid] = _CameraNodeState(
                camera_id=cid,
                device_id=f"DEV-CAM-0{i+1}",
                victim_id=v.victim_id,
                location=GPSCoordinate(latitude=vloc.latitude, longitude=vloc.longitude, altitude_m=vloc.altitude_m),
            )
        
        # Site-wide surveillance camera
        site_alt = (loc.altitude_m + 20.0) if loc.altitude_m is not None else 100.0
        self.cameras["CAM-SITE-01"] = _CameraNodeState(
            camera_id="CAM-SITE-01",
            device_id="DEV-CAM-SITE",
            victim_id=None,
            location=GPSCoordinate(latitude=loc.latitude + 0.0008, longitude=loc.longitude + 0.0008, altitude_m=site_alt),
            orientation="30° PANORAMA",
            field_of_view_deg=120.0,
            range_m=100.0,
        )
        self.step(random.Random(1))

    def set_scenario_profile(self, profile_name: str) -> None:
        self.profile = profile_name.upper()
        self.step(random.Random(self.cycle_count + 1))

    def step(
        self,
        rng: random.Random,
        victims: Optional[list[VictimProfile]] = None,
        smoke_pct: float = 0.0,
        rain_mm_hr: float = 0.0,
        raw_camera_confs: Optional[dict[str, float]] = None,
    ) -> None:
        self.cycle_count += 1
        raw_confs = raw_camera_confs or {}

        # Optical environmental attenuation
        env_vis = 1.0
        if smoke_pct > 10.0:
            env_vis *= max(0.10, 1.0 - (smoke_pct / 100.0) * 0.85)
        if rain_mm_hr > 5.0:
            env_vis *= max(0.40, 1.0 - (rain_mm_hr / 100.0) * 0.50)

        for cid, cam in self.cameras.items():
            if self.profile == "CAMERA_FAILURE":
                cam.status = CameraHealthStatus.OFFLINE
                cam.health_score = 0.0
                cam.confidence = 0.0
                cam.detection_state = CameraDetectionState.NO_DETECTION
                cam.classification = CameraClassification.UNKNOWN
                cam.person_count = 0
                cam.confidence_history.append(0.0)
                continue

            cam.status = CameraHealthStatus.ONLINE
            cam.health_score = 98.0 + rng.uniform(-1.0, 1.5)
            cam.smoke_present = smoke_pct >= 20.0 or (self.scenario_id in ("wildfire_forest", "chemical_gas_leak"))
            cam.fire_visible = self.scenario_id == "wildfire_forest" and (smoke_pct >= 35.0 or self.profile == "FIRE")

            if self.profile == "PERSON_DETECTED":
                cam.detection_state = CameraDetectionState.PERSON_DETECTED
                cam.classification = CameraClassification.HUMAN
                cam.classification_confidence = round(rng.uniform(0.88, 0.96), 2)
                cam.person_count = 1
                cam.visibility = round(min(1.0, env_vis * rng.uniform(0.85, 0.95)), 2)
                cam.occlusion = round(rng.uniform(0.05, 0.15), 2)
                cam.image_quality = round(rng.uniform(0.88, 0.96), 2)
                cam.confidence = round(min(1.0, cam.visibility * (1.0 - cam.occlusion) * rng.uniform(0.90, 0.98)), 2)
                cam.motion_detected = True
                cam.debris_present = False
            elif self.profile in ("NO_PERSON", "NO_DETECTION"):
                cam.detection_state = CameraDetectionState.NO_DETECTION
                cam.classification = CameraClassification.UNKNOWN
                cam.classification_confidence = 0.0
                cam.person_count = 0
                cam.visibility = round(env_vis, 2)
                cam.occlusion = 0.0
                cam.image_quality = round(rng.uniform(0.85, 0.95), 2)
                cam.confidence = round(rng.uniform(0.0, 0.04), 2)
                cam.motion_detected = False
                cam.debris_present = False
            elif self.profile == "MULTIPLE_PERSONS":
                cam.detection_state = CameraDetectionState.MULTIPLE_PERSONS
                cam.classification = CameraClassification.HUMAN
                cam.classification_confidence = round(rng.uniform(0.90, 0.98), 2)
                cam.person_count = rng.choice([2, 3])
                cam.visibility = round(min(1.0, env_vis * rng.uniform(0.85, 0.95)), 2)
                cam.occlusion = round(rng.uniform(0.05, 0.20), 2)
                cam.image_quality = round(rng.uniform(0.85, 0.95), 2)
                cam.confidence = round(min(1.0, rng.uniform(0.88, 0.96)), 2)
                cam.motion_detected = True
            elif self.profile == "PARTIAL_PERSON":
                cam.detection_state = CameraDetectionState.PARTIAL_PERSON
                cam.classification = CameraClassification.HUMAN
                cam.classification_confidence = round(rng.uniform(0.65, 0.80), 2)
                cam.person_count = 1
                cam.visibility = round(min(1.0, env_vis * rng.uniform(0.70, 0.85)), 2)
                cam.occlusion = round(rng.uniform(0.40, 0.55), 2)
                cam.image_quality = round(rng.uniform(0.75, 0.88), 2)
                cam.confidence = round(rng.uniform(0.45, 0.65), 2)
                cam.motion_detected = False
            elif self.profile == "OCCLUDED_PERSON":
                cam.detection_state = CameraDetectionState.OCCLUDED_PERSON
                cam.classification = CameraClassification.HUMAN
                cam.classification_confidence = round(rng.uniform(0.50, 0.70), 2)
                cam.person_count = 1
                cam.visibility = round(min(1.0, env_vis * rng.uniform(0.50, 0.70)), 2)
                cam.occlusion = round(rng.uniform(0.70, 0.85), 2)
                cam.image_quality = round(rng.uniform(0.60, 0.75), 2)
                cam.confidence = round(rng.uniform(0.25, 0.42), 2)
                cam.motion_detected = False
                cam.debris_present = True
            elif self.profile == "DEBRIS":
                cam.detection_state = CameraDetectionState.DEBRIS
                cam.classification = CameraClassification.DEBRIS
                cam.classification_confidence = round(rng.uniform(0.75, 0.90), 2)
                cam.person_count = 0
                cam.visibility = round(env_vis, 2)
                cam.occlusion = round(rng.uniform(0.20, 0.40), 2)
                cam.confidence = round(rng.uniform(0.55, 0.75), 2)
                cam.debris_present = True
            elif self.profile == "SMOKE":
                cam.detection_state = CameraDetectionState.SMOKE
                cam.classification = CameraClassification.UNKNOWN
                cam.classification_confidence = 0.0
                cam.person_count = 0
                cam.visibility = round(rng.uniform(0.10, 0.25), 2)
                cam.occlusion = round(rng.uniform(0.75, 0.90), 2)
                cam.confidence = round(rng.uniform(0.10, 0.25), 2)
                cam.smoke_present = True
            elif self.profile == "FIRE":
                cam.detection_state = CameraDetectionState.FIRE
                cam.classification = CameraClassification.UNKNOWN
                cam.classification_confidence = 0.0
                cam.person_count = 0
                cam.visibility = round(rng.uniform(0.20, 0.40), 2)
                cam.confidence = round(rng.uniform(0.80, 0.95), 2)
                cam.fire_visible = True
            elif self.profile == "LOW_VISIBILITY":
                cam.status = CameraHealthStatus.LOW_VISIBILITY
                cam.visibility = round(rng.uniform(0.12, 0.28), 2)
                cam.occlusion = round(rng.uniform(0.50, 0.70), 2)
                cam.confidence = round(rng.uniform(0.15, 0.30), 2)
            else:
                # AUTO Scenario-aware mode
                vid = cam.victim_id
                target_raw = raw_confs.get(vid, 0.0) if vid else 0.2
                cam.visibility = round(max(0.10, min(1.0, env_vis)), 2)

                if self.scenario_id == "himalaya_avalanche":
                    cam.visibility = round(min(cam.visibility, 0.15), 2)
                    cam.occlusion = 0.85
                    cam.confidence = round(target_raw * 0.2, 2)
                    cam.detection_state = CameraDetectionState.OCCLUDED_PERSON if cam.confidence > 0.05 else CameraDetectionState.NO_DETECTION
                    cam.classification = CameraClassification.HUMAN if cam.confidence > 0.05 else CameraClassification.UNKNOWN
                    cam.person_count = 1 if cam.confidence > 0.05 else 0
                elif self.scenario_id == "wildfire_forest":
                    cam.visibility = round(min(cam.visibility, 0.30), 2)
                    cam.smoke_present = True
                    cam.fire_visible = True
                    cam.confidence = round(target_raw * cam.visibility, 2)
                    cam.detection_state = CameraDetectionState.PERSON_DETECTED if cam.confidence >= 0.40 else (CameraDetectionState.SMOKE if cam.smoke_present else CameraDetectionState.NO_DETECTION)
                    cam.classification = CameraClassification.HUMAN if cam.confidence >= 0.40 else CameraClassification.UNKNOWN
                    cam.person_count = 1 if cam.confidence >= 0.40 else 0
                elif self.scenario_id == "flood_urban":
                    cam.visibility = round(min(cam.visibility, 0.65), 2)
                    cam.confidence = round(target_raw * cam.visibility, 2)
                    cam.detection_state = CameraDetectionState.PERSON_DETECTED if cam.confidence >= 0.40 else (CameraDetectionState.PARTIAL_PERSON if cam.confidence >= 0.15 else CameraDetectionState.NO_DETECTION)
                    cam.classification = CameraClassification.HUMAN if cam.confidence >= 0.15 else CameraClassification.UNKNOWN
                    cam.person_count = 1 if cam.confidence >= 0.15 else 0
                else:
                    # Earthquake or general collapse
                    cam.debris_present = True
                    cam.occlusion = round(rng.uniform(0.20, 0.50), 2)
                    cam.confidence = round(target_raw * (1.0 - cam.occlusion * 0.5), 2)
                    if cam.confidence >= 0.60:
                        cam.detection_state = CameraDetectionState.PERSON_DETECTED
                        cam.classification = CameraClassification.HUMAN
                        cam.person_count = 1
                    elif cam.confidence >= 0.25:
                        cam.detection_state = CameraDetectionState.PARTIAL_PERSON
                        cam.classification = CameraClassification.HUMAN
                        cam.person_count = 1
                    elif cam.confidence >= 0.10:
                        cam.detection_state = CameraDetectionState.OCCLUDED_PERSON
                        cam.classification = CameraClassification.HUMAN
                        cam.person_count = 1
                    else:
                        cam.detection_state = CameraDetectionState.NO_DETECTION
                        cam.classification = CameraClassification.UNKNOWN
                        cam.person_count = 0

            cam.confidence_history.append(cam.confidence)

    def read_camera(self, camera_id: Optional[str] = None, victim_id: Optional[str] = None) -> CameraReading:
        cam = None
        if camera_id and camera_id in self.cameras:
            cam = self.cameras[camera_id]
        elif victim_id:
            for c in self.cameras.values():
                if c.victim_id == victim_id:
                    cam = c
                    break
        if not cam:
            cam = next(iter(self.cameras.values()))

        from datetime import datetime, timezone
        return CameraReading(
            reading_id=f"CAMR-{uuid.uuid4().hex[:8]}",
            sensor_type="camera",
            camera_id=cam.camera_id,
            device_id=cam.device_id,
            victim_id=cam.victim_id,
            location=cam.location,
            detection_state=cam.detection_state,
            detection_type=cam.detection_type,
            classification=cam.classification,
            classification_confidence=cam.classification_confidence,
            person_count=cam.person_count,
            confidence=cam.confidence,
            visibility=cam.visibility,
            occlusion=cam.occlusion,
            image_quality=cam.image_quality,
            motion_detected=cam.motion_detected,
            smoke_present=cam.smoke_present,
            fire_visible=cam.fire_visible,
            debris_present=cam.debris_present,
            orientation=cam.orientation,
            field_of_view_deg=cam.field_of_view_deg,
            range_m=cam.range_m,
            status=cam.status,
            health_score=cam.health_score,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def get_camera_health(self, camera_id: Optional[str] = None) -> SensorHealth:
        cid = camera_id or "CAM-001"
        cam = self.cameras.get(cid, next(iter(self.cameras.values())))
        from datetime import datetime, timezone
        stat = SensorHealthStatus.ONLINE if cam.status == CameraHealthStatus.ONLINE else (SensorHealthStatus.OFFLINE if cam.status == CameraHealthStatus.OFFLINE else SensorHealthStatus.DEGRADED)
        return SensorHealth(
            sensor_id=cam.camera_id,
            sensor_type=SensorType.RGB_CAMERA,
            status=stat,
            battery_pct=round(cam.health_score, 1),
            signal_quality=round(cam.image_quality, 2),
            error_message="Camera offline" if stat == SensorHealthStatus.OFFLINE else None,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
        )

    def get_victim_confidence(self, victim_id: str) -> float:
        for c in self.cameras.values():
            if c.victim_id == victim_id:
                return c.confidence
        return 0.0


# --------------------------------------------------------------------------- #
# Thermal Camera Simulation Adapter
# --------------------------------------------------------------------------- #

@dataclass
class _ThermalNodeState:
    camera_id: str
    device_id: str
    victim_id: Optional[str]
    location: GPSCoordinate
    detection_type: ThermalDetectionType = ThermalDetectionType.NO_HEAT
    classification: ThermalClassification = ThermalClassification.NO_SIGNATURE
    classification_confidence: float = 0.0
    heat_signature_detected: bool = False
    human_signature: bool = False
    heat_signature_count: int = 0
    thermal_confidence: float = 0.0
    estimated_temperature: float = 20.0
    background_temperature: float = 18.0
    temperature_delta: float = 2.0
    thermal_visibility: float = 1.0
    thermal_contrast: float = 1.0
    occlusion: float = 0.0
    fire_hotspot: bool = False
    hot_debris: bool = False
    orientation: str = "0° NADIR"
    field_of_view_deg: float = 60.0
    range_m: float = 40.0
    status: ThermalHealthStatus = ThermalHealthStatus.ONLINE
    health_score: float = 100.0
    temp_history: deque[float] = field(default_factory=lambda: deque(maxlen=30))


class ThermalCameraSimulationAdapter(ThermalCameraSensorInterface):
    """
    Hardware-ready simulation adapter for Long-Wave Infrared (LWIR) thermal cameras.
    Supports multi-node thermal arrays (THERMAL-001..004 + THERMAL-SITE-01),
    differential surface temperature estimation, thermal contrast, smoke penetration,
    hotspot/debris differentiation, and manual test profiles.
    """
    def __init__(
        self,
        victims: Optional[list[VictimProfile]] = None,
        base_location: Optional[GPSCoordinate] = None,
        scenario_id: Optional[str] = None,
    ):
        self.scenario_id = scenario_id or "earthquake_building_collapse"
        self.profile = "AUTO"
        self.cycle_count = 0
        loc = base_location or GPSCoordinate(latitude=32.3740, longitude=77.2490, altitude_m=3950.0)

        self.cameras: dict[str, _ThermalNodeState] = {}
        vlist = victims or []
        for i, v in enumerate(vlist):
            cid = f"THERMAL-00{i+1}"
            vloc = v.location if hasattr(v, "location") and v.location else loc
            self.cameras[cid] = _ThermalNodeState(
                camera_id=cid,
                device_id=f"DEV-THM-0{i+1}",
                victim_id=v.victim_id,
                location=GPSCoordinate(latitude=vloc.latitude, longitude=vloc.longitude, altitude_m=vloc.altitude_m),
            )
        
        # Site-wide thermal imager
        site_alt = (loc.altitude_m + 20.0) if loc.altitude_m is not None else 100.0
        self.cameras["THERMAL-SITE-01"] = _ThermalNodeState(
            camera_id="THERMAL-SITE-01",
            device_id="DEV-THM-SITE",
            victim_id=None,
            location=GPSCoordinate(latitude=loc.latitude + 0.0008, longitude=loc.longitude + 0.0008, altitude_m=site_alt),
            orientation="30° PANORAMA",
            field_of_view_deg=90.0,
            range_m=120.0,
        )
        self.step(random.Random(1))

    def set_scenario_profile(self, profile_name: str) -> None:
        self.profile = profile_name.upper()
        self.step(random.Random(self.cycle_count + 1))

    def step(
        self,
        rng: random.Random,
        ambient_temp_c: float = 20.0,
        raw_thermal_temps: Optional[dict[str, float]] = None,
    ) -> None:
        self.cycle_count += 1
        raw_temps = raw_thermal_temps or {}

        for cid, thm in self.cameras.items():
            if self.profile == "THERMAL_FAILURE":
                thm.status = ThermalHealthStatus.OFFLINE
                thm.health_score = 0.0
                thm.thermal_confidence = 0.0
                thm.heat_signature_detected = False
                thm.human_signature = False
                thm.detection_type = ThermalDetectionType.NO_HEAT
                thm.classification = ThermalClassification.NO_SIGNATURE
                thm.temp_history.append(ambient_temp_c)
                continue

            thm.status = ThermalHealthStatus.ONLINE
            thm.health_score = 98.5 + rng.uniform(-1.0, 1.2)
            thm.background_temperature = round(ambient_temp_c, 1)

            if self.profile in ("HUMAN_HEAT", "HUMAN_HEAT_SIGNATURE"):
                thm.detection_type = ThermalDetectionType.HUMAN_HEAT_SIGNATURE
                thm.classification = ThermalClassification.HUMAN_HEAT_SIGNATURE
                thm.classification_confidence = round(rng.uniform(0.88, 0.96), 2)
                thm.heat_signature_detected = True
                thm.human_signature = True
                thm.heat_signature_count = 1
                thm.estimated_temperature = round(rng.uniform(33.5, 36.5), 1)
                thm.temperature_delta = round(thm.estimated_temperature - thm.background_temperature, 1)
                thm.thermal_confidence = round(rng.uniform(0.88, 0.96), 2)
                thm.thermal_visibility = 0.95
                thm.thermal_contrast = 1.8
                thm.occlusion = 0.05
                thm.fire_hotspot = False
                thm.hot_debris = False
            elif self.profile in ("NO_HEAT", "NO_DETECTION"):
                thm.detection_type = ThermalDetectionType.NO_HEAT
                thm.classification = ThermalClassification.NO_SIGNATURE
                thm.classification_confidence = 0.0
                thm.heat_signature_detected = False
                thm.human_signature = False
                thm.heat_signature_count = 0
                thm.estimated_temperature = round(ambient_temp_c + rng.uniform(-0.3, 0.3), 1)
                thm.temperature_delta = round(abs(thm.estimated_temperature - thm.background_temperature), 1)
                thm.thermal_confidence = 0.0
                thm.thermal_contrast = 1.0
                thm.fire_hotspot = False
                thm.hot_debris = False
            elif self.profile in ("WEAK_HEAT", "WEAK_HEAT_SIGNATURE"):
                thm.detection_type = ThermalDetectionType.WEAK_HEAT_SIGNATURE
                thm.classification = ThermalClassification.HUMAN_HEAT_SIGNATURE
                thm.classification_confidence = round(rng.uniform(0.55, 0.70), 2)
                thm.heat_signature_detected = True
                thm.human_signature = True
                thm.heat_signature_count = 1
                thm.estimated_temperature = round(ambient_temp_c + rng.uniform(3.5, 6.0), 1)
                thm.temperature_delta = round(thm.estimated_temperature - thm.background_temperature, 1)
                thm.thermal_confidence = round(rng.uniform(0.42, 0.60), 2)
                thm.thermal_contrast = 1.3
                thm.occlusion = 0.45
                thm.fire_hotspot = False
                thm.hot_debris = False
            elif self.profile == "MULTIPLE_HEAT":
                thm.detection_type = ThermalDetectionType.MULTIPLE_HUMAN_HEAT
                thm.classification = ThermalClassification.HUMAN_HEAT_SIGNATURE
                thm.classification_confidence = round(rng.uniform(0.90, 0.98), 2)
                thm.heat_signature_detected = True
                thm.human_signature = True
                thm.heat_signature_count = rng.choice([2, 3])
                thm.estimated_temperature = round(rng.uniform(34.0, 36.8), 1)
                thm.temperature_delta = round(thm.estimated_temperature - thm.background_temperature, 1)
                thm.thermal_confidence = round(rng.uniform(0.90, 0.98), 2)
                thm.thermal_contrast = 2.0
                thm.fire_hotspot = False
                thm.hot_debris = False
            elif self.profile == "FIRE_HOTSPOT":
                thm.detection_type = ThermalDetectionType.FIRE_HOTSPOT
                thm.classification = ThermalClassification.FIRE_HOTSPOT
                thm.classification_confidence = round(rng.uniform(0.92, 0.99), 2)
                thm.heat_signature_detected = True
                thm.human_signature = False
                thm.heat_signature_count = 1
                thm.estimated_temperature = round(rng.uniform(65.0, 110.0), 1)
                thm.temperature_delta = round(thm.estimated_temperature - thm.background_temperature, 1)
                thm.thermal_confidence = round(rng.uniform(0.92, 0.98), 2)
                thm.fire_hotspot = True
                thm.hot_debris = False
            elif self.profile == "HOT_DEBRIS":
                thm.detection_type = ThermalDetectionType.HOT_DEBRIS
                thm.classification = ThermalClassification.HOT_OBJECT
                thm.classification_confidence = round(rng.uniform(0.70, 0.85), 2)
                thm.heat_signature_detected = True
                thm.human_signature = False
                thm.heat_signature_count = 1
                thm.estimated_temperature = round(rng.uniform(42.0, 55.0), 1)
                thm.temperature_delta = round(thm.estimated_temperature - thm.background_temperature, 1)
                thm.thermal_confidence = round(rng.uniform(0.65, 0.80), 2)
                thm.fire_hotspot = False
                thm.hot_debris = True
            elif self.profile == "THERMAL_NOISE":
                thm.status = ThermalHealthStatus.THERMAL_NOISE
                thm.thermal_confidence = round(rng.uniform(0.18, 0.32), 2)
                thm.detection_type = ThermalDetectionType.THERMAL_NOISE
                thm.estimated_temperature = round(ambient_temp_c + rng.uniform(-4.0, 4.0), 1)
                thm.temperature_delta = round(abs(thm.estimated_temperature - thm.background_temperature), 1)
            else:
                # AUTO Scenario-aware mode
                vid = thm.victim_id
                target_temp = raw_temps.get(vid, ambient_temp_c) if vid else ambient_temp_c
                thm.estimated_temperature = round(target_temp + rng.gauss(0, 0.3), 1)
                thm.temperature_delta = round(thm.estimated_temperature - thm.background_temperature, 1)

                if self.scenario_id == "wildfire_forest" and thm.estimated_temperature >= 45.0:
                    thm.fire_hotspot = True
                    thm.detection_type = ThermalDetectionType.FIRE_HOTSPOT
                    thm.classification = ThermalClassification.FIRE_HOTSPOT
                    thm.human_signature = False
                    thm.thermal_confidence = 0.95
                elif thm.estimated_temperature >= 30.0:
                    thm.heat_signature_detected = True
                    thm.human_signature = True
                    thm.heat_signature_count = 1
                    thm.detection_type = ThermalDetectionType.HUMAN_HEAT_SIGNATURE
                    thm.classification = ThermalClassification.HUMAN_HEAT_SIGNATURE
                    thm.classification_confidence = round(min(1.0, (thm.estimated_temperature - 25.0) / 10.0), 2)
                    thm.thermal_confidence = round(min(1.0, 0.70 + (thm.estimated_temperature - 30.0) * 0.05), 2)
                elif thm.estimated_temperature >= 20.0:
                    thm.heat_signature_detected = True
                    thm.human_signature = True
                    thm.heat_signature_count = 1
                    thm.detection_type = ThermalDetectionType.WEAK_HEAT_SIGNATURE
                    thm.classification = ThermalClassification.HUMAN_HEAT_SIGNATURE
                    thm.classification_confidence = 0.60
                    thm.thermal_confidence = round(max(0.20, (thm.estimated_temperature - ambient_temp_c) / 15.0), 2)
                else:
                    thm.heat_signature_detected = False
                    thm.human_signature = False
                    thm.heat_signature_count = 0
                    thm.detection_type = ThermalDetectionType.NO_HEAT
                    thm.classification = ThermalClassification.NO_SIGNATURE
                    thm.thermal_confidence = 0.0

            thm.temp_history.append(thm.estimated_temperature)

    def read_thermal(self, camera_id: Optional[str] = None, victim_id: Optional[str] = None) -> ThermalCameraReading:
        thm = None
        if camera_id and camera_id in self.cameras:
            thm = self.cameras[camera_id]
        elif victim_id:
            for t in self.cameras.values():
                if t.victim_id == victim_id:
                    thm = t
                    break
        if not thm:
            thm = next(iter(self.cameras.values()))

        from datetime import datetime, timezone
        return ThermalCameraReading(
            reading_id=f"THMR-{uuid.uuid4().hex[:8]}",
            sensor_type="thermal_camera",
            camera_id=thm.camera_id,
            device_id=thm.device_id,
            victim_id=thm.victim_id,
            location=thm.location,
            detection_type=thm.detection_type,
            classification=thm.classification,
            classification_confidence=thm.classification_confidence,
            heat_signature_detected=thm.heat_signature_detected,
            human_signature=thm.human_signature,
            heat_signature_count=thm.heat_signature_count,
            thermal_confidence=thm.thermal_confidence,
            estimated_temperature=thm.estimated_temperature,
            background_temperature=thm.background_temperature,
            temperature_delta=thm.temperature_delta,
            thermal_visibility=thm.thermal_visibility,
            thermal_contrast=thm.thermal_contrast,
            occlusion=thm.occlusion,
            fire_hotspot=thm.fire_hotspot,
            hot_debris=thm.hot_debris,
            orientation=thm.orientation,
            field_of_view_deg=thm.field_of_view_deg,
            range_m=thm.range_m,
            status=thm.status,
            health_score=thm.health_score,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def get_thermal_health(self, camera_id: Optional[str] = None) -> SensorHealth:
        cid = camera_id or "THERMAL-001"
        thm = self.cameras.get(cid, next(iter(self.cameras.values())))
        from datetime import datetime, timezone
        stat = SensorHealthStatus.ONLINE if thm.status == ThermalHealthStatus.ONLINE else (SensorHealthStatus.OFFLINE if thm.status == ThermalHealthStatus.OFFLINE else SensorHealthStatus.DEGRADED)
        return SensorHealth(
            sensor_id=thm.camera_id,
            sensor_type=SensorType.THERMAL_IMAGING,
            status=stat,
            battery_pct=round(thm.health_score, 1),
            signal_quality=round(thm.thermal_visibility, 2),
            error_message="Thermal imager offline" if stat == SensorHealthStatus.OFFLINE else None,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
        )

    def get_victim_temperature(self, victim_id: str) -> float:
        for t in self.cameras.values():
            if t.victim_id == victim_id:
                return t.estimated_temperature
        return 20.0


class SensorSimulator:
    """
    Drives per-cycle sensor reading generation for a set of victims.

    Usage:
        sim = SensorSimulator(HIMALAYA_VICTIMS, seed=42, enable_degradation=True)
        readings = sim.generate_cycle()   # -> list[SensorReading], call again each tick
    """

    def __init__(
        self,
        victims: list[VictimProfile] = None,
        seed: Optional[int] = None,
        enable_degradation: bool = True,
        dropout_enabled: bool = True,
        enable_water_sensor: bool = False,
        enable_water_flow_sensor: bool = False,
        enable_solar_charging: bool = False,
        site_environment: SiteEnvironment = None,
        scenario_id: Optional[str] = None,
    ):
        self.victims = victims if victims is not None else HIMALAYA_VICTIMS
        self.rng = random.Random(seed)
        self.enable_degradation = enable_degradation
        self.dropout_enabled = dropout_enabled
        self.enable_water_sensor = enable_water_sensor
        self.enable_water_flow_sensor = enable_water_flow_sensor
        self.enable_solar_charging = enable_solar_charging
        self.cycle_count = 0
        self.nodes: dict[str, _VictimNode] = {
            v.victim_id: _VictimNode(
                victim=v,
                enable_water_sensor=self.enable_water_sensor,
                enable_water_flow_sensor=self.enable_water_flow_sensor,
            )
            for v in self.victims
        }

        # Site-wide environmental sensors (e.g. rain gauge) - one shared
        # reading for the whole disaster zone, NOT a per-victim track like
        # self.nodes above.
        self.site_environment = site_environment or SiteEnvironment()
        self.scenario_id = scenario_id or getattr(self.site_environment, "scenario_id", None)
        self.profile: ScenarioSensorProfile = get_scenario_sensor_profile(self.scenario_id)

        self._rain_mm_hr = self.site_environment.initial_rainfall_mm_hr
        self._soil_moisture_pct = self.site_environment.initial_soil_moisture_pct
        self._vibration_mm_s = self.site_environment.baseline_vibration_mm_s
        self._aftershock_active = False
        self._aftershock_peak_mm_s = 0.0
        self._aftershock_cycles_remaining = 0
        self._tilt_deg = self.site_environment.baseline_tilt_deg
        self._last_vibration_spike = False
        self._last_tilt_shift = False
        self._ambient_temp_c = self.site_environment.initial_ambient_temp_c
        self._humidity_pct = self.site_environment.initial_humidity_pct
        self._gas_ppm = getattr(self.site_environment, "initial_gas_concentration_ppm", 0.0)
        self._smoke_pct = getattr(self.site_environment, "initial_smoke_density_pct", 0.0)
        self._pressure_hpa = getattr(self.site_environment, "initial_barometric_pressure_hpa", 1013.25)

        self.gas_smoke_adapter = GasSmokeSimulationAdapter(
            gas_type=GasType.GENERIC_SMOKE,
            location=getattr(self.site_environment, "site_location", None) or GPSCoordinate(latitude=32.3740, longitude=77.2490),
            initial_gas_ppm=self._gas_ppm if self._gas_ppm > 0 else (45.0 if self.profile.scenario_id == "chemical_gas_leak" else 5.0),
            initial_smoke_pct=self._smoke_pct if self._smoke_pct > 0 else (30.0 if self.profile.scenario_id in ("chemical_gas_leak", "wildfire_forest") else 0.0),
        )
        self.barometric_adapter = BarometricPressureSimulationAdapter(
            sensor_id="ENV-BARO-01",
            device_id="DEV-BARO-01",
            location=getattr(self.site_environment, "site_location", None) or GPSCoordinate(latitude=32.3740, longitude=77.2490),
            scenario_profile="NORMAL_WEATHER",
            initial_pressure_hpa=self._pressure_hpa if self._pressure_hpa > 0 else 1013.25,
        )
        self.landslide_adapter = LandslideSensorSimulationAdapter(
            scenario_profile="NORMAL",
            base_location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490)),
            initial_moisture_pct=self._soil_moisture_pct,
            initial_tilt_deg=self._tilt_deg,
        )
        self.camera_rng = random.Random((seed or 42) + 101)
        self.thermal_rng = random.Random((seed or 42) + 202)
        self.rain_rng = random.Random((seed or 42) + 303)
        self.camera_adapter = CameraSimulationAdapter(
            victims=self.victims,
            base_location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490)),
            scenario_id=self.scenario_id or getattr(self.site_environment, "scenario_id", "earthquake_building_collapse"),
        )
        self.thermal_adapter = ThermalCameraSimulationAdapter(
            victims=self.victims,
            base_location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490)),
            scenario_id=self.scenario_id or getattr(self.site_environment, "scenario_id", "earthquake_building_collapse"),
        )
        self.rainfall_adapter = RainfallSimulationAdapter(
            sensor_id="ENV-RAIN-01",
            device_id="DEV-RAIN-01",
            location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490)),
            scenario_profile="AUTO",
            initial_rainfall_rate=self._rain_mm_hr,
        )
        self.temperature_rng = random.Random((seed or 42) + 404)
        self.humidity_rng = random.Random((seed or 42) + 505)
        self.temperature_adapter = TemperatureSimulationAdapter(
            sensor_id="ENV-TEMP-01",
            device_id="DEV-TEMP-01",
            location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490)),
            scenario_profile="AUTO",
            initial_temp_c=self._ambient_temp_c,
        )
        self.humidity_adapter = HumiditySimulationAdapter(
            sensor_id="ENV-HUMID-01",
            device_id="DEV-HUMID-01",
            location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490)),
            scenario_profile="AUTO",
            initial_humidity_pct=self._humidity_pct,
        )
        self.gps_rng = random.Random((seed or 42) + 606)
        self.gps_adapter = GPSSimulationAdapter(
            sensor_id="DEV-GPS-01",
            device_id="RESCUE-KIT-01",
            initial_location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490, altitude_m=3950.0)),
            scenario_profile="STATIONARY",
        )
        self.water_level_rng = random.Random((seed or 42) + 707)
        self.water_level_adapter = WaterLevelSimulationAdapter(
            sensor_id="ENV-WATER-01",
            device_id="DEV-WATER-01",
            location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490)),
            scenario_profile="AUTO",
            initial_water_level_cm=0.0,
            initial_flow_mps=0.0,
        )

    def set_scenario(self, scenario_id: str) -> None:
        """Dynamically reconfigure simulator active scenario profile and adapter behaviors."""
        self.scenario_id = scenario_id
        self.profile = get_scenario_sensor_profile(scenario_id)
        if hasattr(self, "camera_adapter"):
            self.camera_adapter.scenario_id = scenario_id
        if hasattr(self, "thermal_adapter"):
            self.thermal_adapter.scenario_id = scenario_id

    # ------------------------------------------------------------------- #
    # Degradation model
    # ------------------------------------------------------------------- #

    def _drain_battery(self, node: _VictimNode) -> None:
        """Simulate battery/signal weakening over time (optional realism feature)."""
        drain = BATTERY_DRAIN_MEAN_PCT + self.rng.gauss(0, BATTERY_DRAIN_JITTER_PCT)
        if self.rng.random() < BATTERY_COLD_SNAP_PROB:
            drain += BATTERY_COLD_SNAP_EXTRA_PCT  # simulates Himalayan cold sapping li-ion cells
        node.battery_pct = max(0.0, node.battery_pct - max(drain, 0.0))

    def add_victim(self, victim: VictimProfile) -> None:
        """
        Inject a new victim into an ALREADY-RUNNING simulation (Step 12,
        admin "add person"). Unlike __init__'s bulk node creation, this adds
        exactly one _VictimNode to self.nodes mid-run - the new node starts
        fresh (BATTERY_START_PCT, mid-range track values) and is picked up
        automatically by the very next generate_cycle(), since that method
        already just iterates self.nodes.items().

        Raises ValueError if victim_id already exists - admin-added ids must
        be unique against the running scenario, same as scenario-load-time.
        """
        if victim.victim_id in self.nodes:
            raise ValueError(f"Victim '{victim.victim_id}' already exists in this scenario")

        self.victims.append(victim)
        self.nodes[victim.victim_id] = _VictimNode(
            victim=victim,
            enable_water_sensor=self.enable_water_sensor,
            enable_water_flow_sensor=self.enable_water_flow_sensor,
        )

    def _step_rainfall(self) -> float:
        """
        Rain intensity is bursty, not monotonic - showers come and go.
        Mean-reverts loosely toward the scenario's baseline rate with
        Gaussian jitter scaled by rainfall_volatility_mm_hr.
        """
        if not self.profile.is_active(SensorType.RAINFALL_INTENSITY):
            self._rain_mm_hr = 0.0
            return 0.0

        baseline = self.site_environment.initial_rainfall_mm_hr
        theta = 0.25
        noise = self.rng.gauss(0, self.site_environment.rainfall_volatility_mm_hr)
        self._rain_mm_hr = max(0.0, self._rain_mm_hr + theta * (baseline - self._rain_mm_hr) + noise)
        return self._rain_mm_hr

    def _step_soil_moisture(self) -> float:
        """
        Soil saturation rises with recent rainfall and drains back down
        slowly (percolation/runoff) when it's dry — mean-reverts toward a
        rain-driven target rather than the static scenario baseline, so a
        dry spell after heavy rain still shows the slope draining out.
        """
        if not self.profile.is_active(SensorType.SOIL_MOISTURE):
            self._soil_moisture_pct = getattr(self.site_environment, "initial_soil_moisture_pct", 30.0)
            return self._soil_moisture_pct

        env = self.site_environment
        rain_driven_target = min(
            100.0,
            env.initial_soil_moisture_pct + self._rain_mm_hr * env.soil_saturation_from_rain_pct_per_mm_hr,
        )
        theta = 0.12   # slower reversion than rain itself - soil holds water longer than air does
        noise = self.rng.gauss(0, env.soil_moisture_volatility_pct)
        self._soil_moisture_pct = max(
            0.0, min(100.0, self._soil_moisture_pct + theta * (rain_driven_target - self._soil_moisture_pct) + noise)
        )
        return self._soil_moisture_pct

    def _step_seismic(self) -> tuple:
        """
        Baseline ambient vibration most cycles; occasionally an aftershock
        event triggers (probability aftershock_prob_per_cycle), spikes to a
        random peak PGV, then exponentially decays back to baseline over
        aftershock_decay_cycles.
        """
        env = self.site_environment
        baseline = env.baseline_vibration_mm_s
        spike_triggered_this_cycle = False

        if not self._aftershock_active and env.aftershock_prob_per_cycle > 0:
            if self.rng.random() < env.aftershock_prob_per_cycle:
                self._aftershock_active = True
                spike_triggered_this_cycle = True
                self._aftershock_peak_mm_s = self.rng.uniform(
                    env.aftershock_peak_min_mm_s, env.aftershock_peak_max_mm_s
                )
                self._aftershock_cycles_remaining = env.aftershock_decay_cycles

        if self._aftershock_active:
            decay_frac = self._aftershock_cycles_remaining / max(env.aftershock_decay_cycles, 1)
            self._vibration_mm_s = baseline + (self._aftershock_peak_mm_s - baseline) * decay_frac
            self._aftershock_cycles_remaining -= 1
            if self._aftershock_cycles_remaining <= 0:
                self._aftershock_active = False
                self._vibration_mm_s = baseline
        else:
            noise = self.rng.gauss(0, baseline * 0.15)
            self._vibration_mm_s = max(0.0, baseline + noise)

        return self._vibration_mm_s, spike_triggered_this_cycle

    def _step_tilt(self) -> tuple:
        """
        Ground/structure tilt = slow ambient creep + occasional step-shift
        events.
        """
        env = self.site_environment
        self._tilt_deg = max(
            0.0,
            self._tilt_deg + env.tilt_creep_rate_deg_per_cycle
            + self.rng.gauss(0, env.tilt_creep_rate_deg_per_cycle * 0.5),
        )

        shift_probability = env.tilt_shift_probability
        soil_pct = getattr(self, "_soil_moisture_pct", 0.0)
        if soil_pct >= SOIL_SATURATION_COUPLING_THRESHOLD_PCT:
            shift_probability *= 3.0
        if getattr(self, "_last_vibration_spike", False):
            shift_probability *= 4.0

        is_shift = self.rng.random() < min(shift_probability, 1.0)
        if is_shift:
            lo, hi = env.tilt_shift_range_deg
            self._tilt_deg += self.rng.uniform(lo, hi)

        return self._tilt_deg, is_shift

    def _step_kit_vibration(self, node: _VictimNode) -> tuple:
        """Per-kit accelerometer vibration (g-force)."""
        env = self.site_environment
        baseline = getattr(env, "kit_vibration_baseline_g", KIT_VIBRATION_BASELINE_G)
        spike_prob = getattr(env, "kit_vibration_spike_probability", KIT_VIBRATION_SPIKE_PROB_PER_CYCLE)
        spike_triggered_this_cycle = False

        if not node.kit_vibration_spike_active and self.rng.random() < spike_prob:
            node.kit_vibration_spike_active = True
            spike_triggered_this_cycle = True
            node.kit_vibration_peak_g = self.rng.uniform(
                KIT_VIBRATION_SPIKE_PEAK_MIN_G, KIT_VIBRATION_SPIKE_PEAK_MAX_G
            )
            node.kit_vibration_cycles_remaining = KIT_VIBRATION_SPIKE_DECAY_CYCLES

        if node.kit_vibration_spike_active:
            decay_frac = node.kit_vibration_cycles_remaining / max(KIT_VIBRATION_SPIKE_DECAY_CYCLES, 1)
            node.kit_vibration_g = baseline + (node.kit_vibration_peak_g - baseline) * decay_frac
            node.kit_vibration_cycles_remaining -= 1
            if node.kit_vibration_cycles_remaining <= 0:
                node.kit_vibration_spike_active = False
                node.kit_vibration_g = baseline
        else:
            noise = self.rng.gauss(0, KIT_VIBRATION_BASELINE_NOISE_G)
            node.kit_vibration_g = max(0.0, baseline + noise)

        # 3-Axis IMU Calculation
        angle = self.rng.uniform(0, 2 * math.pi)
        node.acc_x_g = round(node.kit_vibration_g * math.cos(angle) + self.rng.gauss(0, 0.003), 3)
        node.acc_y_g = round(node.kit_vibration_g * math.sin(angle) + self.rng.gauss(0, 0.003), 3)
        # z-axis includes 1g Earth gravity + vertical disturbance
        node.acc_z_g = round(1.0 + node.kit_vibration_g * 0.4 + self.rng.gauss(0, 0.003), 3)
        node.acc_magnitude_g = round(math.sqrt(node.acc_x_g**2 + node.acc_y_g**2 + node.acc_z_g**2), 3)
        node.impact_detected = bool(node.acc_magnitude_g > 1.6 or spike_triggered_this_cycle)
        if node.kit_vibration_g > 0.08:
            node.sustained_vibration_cycles += 1
        else:
            node.sustained_vibration_cycles = max(0, node.sustained_vibration_cycles - 1)

        return node.kit_vibration_g, spike_triggered_this_cycle

    def _step_kit_tilt(self, node: _VictimNode) -> tuple:
        """Per-kit inclinometer tilt (degrees from vertical)."""
        env = self.site_environment
        creep_rate = getattr(env, "kit_tilt_creep_rate_deg_per_cycle", KIT_TILT_CREEP_RATE_DEG_PER_CYCLE)
        node.kit_tilt_deg = max(
            0.0,
            node.kit_tilt_deg + creep_rate
            + self.rng.gauss(0, creep_rate * 0.5),
        )

        shift_probability = getattr(env, "kit_tilt_shift_probability", KIT_TILT_SHIFT_PROBABILITY)
        if getattr(node, "last_kit_vibration_spike", False):
            shift_probability *= KIT_TILT_VIBRATION_COUPLING_MULTIPLIER

        is_shift = self.rng.random() < min(shift_probability, 1.0)
        if is_shift:
            lo, hi = KIT_TILT_SHIFT_RANGE_DEG
            node.kit_tilt_deg += self.rng.uniform(lo, hi)

        return node.kit_tilt_deg, is_shift

    def _step_temperature(self) -> float:
        """Ambient air temperature - site-wide."""
        env = self.site_environment
        diurnal = env.temp_diurnal_swing_c * self._solar_irradiance_factor()
        target = env.initial_ambient_temp_c + diurnal
        theta = 0.2
        noise = self.rng.gauss(0, env.ambient_temp_volatility_c)
        self._ambient_temp_c = self._ambient_temp_c + theta * (target - self._ambient_temp_c) + noise
        return self._ambient_temp_c

    def _step_humidity(self) -> float:
        """Relative humidity - site-wide."""
        env = self.site_environment
        rain_driven_target = min(
            100.0,
            env.initial_humidity_pct + self._rain_mm_hr * env.humidity_rain_amplifier_pct_per_mm_hr,
        )
        theta = 0.15
        noise = self.rng.gauss(0, env.humidity_volatility_pct)
        self._humidity_pct = max(
            0.0, min(100.0, self._humidity_pct + theta * (rain_driven_target - self._humidity_pct) + noise)
        )
        return self._humidity_pct

    def _step_gas(self) -> float:
        """Ambient toxic/combustible gas concentration (ppm)."""
        if not self.profile.is_active(SensorType.GAS_CONCENTRATION):
            # Inactive in flood, earthquake, etc. - keep strictly at non-hazardous ambient floor
            self._gas_ppm = 0.0
            return 0.0

        env = self.site_environment
        baseline = getattr(env, "initial_gas_concentration_ppm", 0.0)
        if baseline == 0.0 and self.profile.scenario_id == "chemical_gas_leak":
            baseline = 55.0  # Realistically high for active chemical leak
        volatility = getattr(env, "gas_volatility_ppm", 2.0)
        theta = 0.18
        noise = self.rng.gauss(0, volatility)
        self._gas_ppm = max(0.0, getattr(self, "_gas_ppm", baseline) + theta * (baseline - getattr(self, "_gas_ppm", baseline)) + noise)
        return self._gas_ppm

    def _step_smoke(self) -> float:
        """Ambient smoke / optical density (%)."""
        if not self.profile.is_active(SensorType.SMOKE_DENSITY):
            self._smoke_pct = 0.0
            return 0.0

        env = self.site_environment
        baseline = getattr(env, "initial_smoke_density_pct", 0.0)
        if baseline == 0.0 and self.profile.scenario_id in ("chemical_gas_leak", "wildfire_forest"):
            baseline = 35.0  # Realistically elevated for chemical smoke / wildfire
        volatility = getattr(env, "smoke_volatility_pct", 1.0)
        theta = 0.20
        noise = self.rng.gauss(0, volatility)
        self._smoke_pct = max(0.0, min(100.0, getattr(self, "_smoke_pct", baseline) + theta * (baseline - getattr(self, "_smoke_pct", baseline)) + noise))
        return self._smoke_pct

    def _step_pressure(self) -> float:
        """Barometric atmospheric pressure (hPa)."""
        env = self.site_environment
        baseline = getattr(env, "initial_barometric_pressure_hpa", 1013.25)
        volatility = getattr(env, "pressure_volatility_hpa", 0.5)
        drop_rate = getattr(env, "pressure_drop_rate_hpa_per_cycle", 0.0)
        target = max(870.0, baseline - drop_rate * self.cycle_count)
        theta = 0.25
        noise = self.rng.gauss(0, volatility)
        self._pressure_hpa = getattr(self, "_pressure_hpa", baseline) + theta * (target - getattr(self, "_pressure_hpa", baseline)) + noise
        return self._pressure_hpa

    def _solar_irradiance_factor(self) -> float:
        phase = (self.cycle_count % SOLAR_CYCLE_LENGTH_CYCLES) / SOLAR_CYCLE_LENGTH_CYCLES
        raw = math.sin(math.pi * phase * 2)
        return max(0.0, raw)

    def _apply_solar_charging(self, node: _VictimNode) -> None:
        node.charging = False
        node.bms_capped = False
        node.last_solar_input_pct = 0.0

        irradiance = self._solar_irradiance_factor()
        if irradiance <= 0.0:
            return

        if node.battery_pct >= BMS_OVERCHARGE_CEILING_PCT:
            return

        cloud_factor = 1.0 - self.rng.random() * SOLAR_CLOUD_VARIATION
        raw_charge = irradiance * SOLAR_PEAK_CHARGE_PCT * cloud_factor
        capped_charge = min(raw_charge, BMS_MAX_CHARGE_RATE_PCT)
        bms_capped = capped_charge < raw_charge

        headroom = BMS_OVERCHARGE_CEILING_PCT - node.battery_pct
        applied_charge = min(capped_charge, headroom)
        if applied_charge < capped_charge:
            bms_capped = True

        node.battery_pct = min(BMS_OVERCHARGE_CEILING_PCT, node.battery_pct + applied_charge)
        node.charging = applied_charge > 0.0
        node.bms_capped = bms_capped
        node.last_solar_input_pct = round(applied_charge, 3)

    def _degraded_confidence(self, node: _VictimNode) -> float:
        if not self.enable_degradation:
            return 1.0
        if node.battery_pct >= 70.0:
            return 1.0
        frac = node.battery_pct / 70.0
        return max(CONFIDENCE_FLOOR, frac)

    def _should_drop_reading(self, node: _VictimNode) -> bool:
        if not (self.enable_degradation and self.dropout_enabled):
            return False
        if node.battery_pct >= DROPOUT_BATTERY_THRESHOLD_PCT:
            return False
        severity = 1.0 - (node.battery_pct / DROPOUT_BATTERY_THRESHOLD_PCT)
        prob = severity * DROPOUT_PROB_AT_ZERO_BATTERY
        return self.rng.random() < prob

    def _noise_multiplier(self, node: _VictimNode) -> float:
        if not self.enable_degradation:
            return 1.0
        if node.battery_pct >= 50.0:
            return 1.0
        return 1.0 + (50.0 - node.battery_pct) / 50.0 * 1.5

    def _jitter_location(self, node: _VictimNode) -> GPSCoordinate:
        node.location.latitude += self.rng.gauss(0, GPS_JITTER_DEG)
        node.location.longitude += self.rng.gauss(0, GPS_JITTER_DEG)
        return node.location

    def _step_water_level(self, node: _VictimNode) -> float:
        if not self.profile.is_active(SensorType.WATER_LEVEL):
            if SensorType.WATER_LEVEL in node.tracks:
                node.tracks[SensorType.WATER_LEVEL].current_value = 0.0
            return 0.0

        rate = node.victim.water_rising_rate_cm_per_cycle
        rate += self._rain_mm_hr * self.site_environment.rain_to_water_rise_amplifier
        jitter = self.rng.gauss(0, max(rate * 0.15, 0.3))
        track = node.tracks[SensorType.WATER_LEVEL]
        track.current_value = max(0.0, track.current_value + rate + jitter)
        return track.current_value

    def _step_water_flow(self, node: _VictimNode) -> float:
        if not self.profile.is_active(SensorType.WATER_FLOW):
            if SensorType.WATER_FLOW in node.tracks:
                node.tracks[SensorType.WATER_FLOW].current_value = 0.0
            return 0.0

        track = node.tracks[SensorType.WATER_FLOW]
        rising_rate = node.victim.water_rising_rate_cm_per_cycle
        drift_bonus = min(rising_rate * 0.08, 0.5)
        volatility = node.victim.water_flow_volatility_ms
        noise = self.rng.gauss(0, volatility)
        new_value = max(0.0, track.current_value + drift_bonus * 0.1 + noise * 0.3)
        track.current_value = new_value
        return new_value

    # ------------------------------------------------------------------- #
    # Public API
    # ------------------------------------------------------------------- #

    def generate_cycle(self) -> list[SensorReading]:
        """Advance the simulation by one cycle and return all readings produced."""
        self.cycle_count += 1
        self._step_rainfall()
        if hasattr(self, "rainfall_adapter"):
            if not self.profile.is_active(SensorType.RAINFALL_INTENSITY):
                self._rain_mm_hr = 0.0
                self.rainfall_adapter._rainfall_rate_mm_h = 0.0
            elif self.rainfall_adapter.scenario_profile != "AUTO":
                self.rainfall_adapter.step(self.rain_rng)
                self._rain_mm_hr = self.rainfall_adapter._rainfall_rate_mm_h
            else:
                self.rainfall_adapter.step(self.rain_rng, base_rainfall_hint=self._rain_mm_hr)
                self._rain_mm_hr = self.rainfall_adapter._rainfall_rate_mm_h
            self._accumulated_rain_mm = self.rainfall_adapter._cumulative_rainfall_mm
        else:
            self._accumulated_rain_mm = getattr(self, "_accumulated_rain_mm", 0.0) + (self._rain_mm_hr / 3600.0) * 5.0
        self._step_soil_moisture()
        self._vibration_mm_s, vibration_spike_this_cycle = self._step_seismic()
        self._last_vibration_spike = vibration_spike_this_cycle
        self._tilt_deg, tilt_shift_this_cycle = self._step_tilt()
        self._last_tilt_shift = tilt_shift_this_cycle
        self._step_temperature()
        if hasattr(self, "temperature_adapter"):
            if self.temperature_adapter.scenario_profile != "AUTO":
                self.temperature_adapter.step(self.temperature_rng)
                self._ambient_temp_c = self.temperature_adapter._temperature_c
            else:
                diurnal = self.site_environment.temp_diurnal_swing_c * self._solar_irradiance_factor()
                self.temperature_adapter.step(self.temperature_rng, base_temp_hint=self._ambient_temp_c, diurnal_offset=diurnal)
                self._ambient_temp_c = self.temperature_adapter._temperature_c

        self._step_humidity()
        if hasattr(self, "humidity_adapter"):
            if self.humidity_adapter.scenario_profile != "AUTO":
                self.humidity_adapter.step(self.humidity_rng, rainfall_rate_mm_h=self._rain_mm_hr)
                self._humidity_pct = self.humidity_adapter._humidity_pct
            else:
                self.humidity_adapter.step(self.humidity_rng, base_humidity_hint=self._humidity_pct, rainfall_rate_mm_h=self._rain_mm_hr)
                self._humidity_pct = self.humidity_adapter._humidity_pct

        self._step_gas()
        self._step_smoke()
        self._step_pressure()
        if hasattr(self, "landslide_adapter"):
            if abs(self._tilt_deg - self.landslide_adapter.get_primary_node_tilt()) > 1.0:
                self.landslide_adapter.set_node_tilt("SLOPE-NODE-01", self._tilt_deg)
            self.landslide_adapter.step(
                self.rng,
                rainfall_mm_hr=self._rain_mm_hr,
                vibration_mm_s=self._vibration_mm_s,
            )
            self._soil_moisture_pct = self.landslide_adapter.get_primary_node_moisture()
            self._tilt_deg = self.landslide_adapter.get_primary_node_tilt()

        # Step Camera and Thermal simulation adapters
        raw_cam_map = {}
        raw_thm_map = {}
        for vid, node in self.nodes.items():
            if SensorType.RGB_CAMERA in node.tracks:
                raw_cam_map[vid] = node.tracks[SensorType.RGB_CAMERA].current_value
            if SensorType.THERMAL_IMAGING in node.tracks:
                raw_thm_map[vid] = node.tracks[SensorType.THERMAL_IMAGING].current_value

        if hasattr(self, "camera_adapter"):
            self.camera_adapter.step(
                self.camera_rng,
                victims=self.victims,
                smoke_pct=self._smoke_pct,
                rain_mm_hr=self._rain_mm_hr,
                raw_camera_confs=raw_cam_map,
            )
        if hasattr(self, "thermal_adapter"):
            self.thermal_adapter.step(
                self.thermal_rng,
                ambient_temp_c=self._ambient_temp_c,
                raw_thermal_temps=raw_thm_map,
            )
        if hasattr(self, "gps_adapter"):
            target_loc = self.victims[0].location if self.victims else None
            self.gps_adapter.step(self.gps_rng, target_location=target_loc, cycle=self.cycle_count)
        if hasattr(self, "water_level_adapter"):
            if self.water_level_adapter.scenario_profile != "AUTO":
                self.water_level_adapter.step(self.water_level_rng, rainfall_rate_mm_h=self._rain_mm_hr, cycle=self.cycle_count)
            else:
                max_node_w = max((n.tracks[SensorType.WATER_LEVEL].current_value for n in self.nodes.values() if SensorType.WATER_LEVEL in n.tracks), default=0.0)
                self.water_level_adapter.step(self.water_level_rng, base_water_level_hint=max_node_w, rainfall_rate_mm_h=self._rain_mm_hr, cycle=self.cycle_count)

        readings: list[SensorReading] = []

        # Victim-specific sensor readings
        for victim_id, node in self.nodes.items():
            if self.enable_degradation:
                self._drain_battery(node)
            if self.enable_solar_charging:
                self._apply_solar_charging(node)

            if self._should_drop_reading(node):
                node.last_kit_tilt_shift = False
                node.last_kit_vibration_spike = False
                continue

            confidence = self._degraded_confidence(node)
            noise_mult = self._noise_multiplier(node)
            location = self._jitter_location(node)
            is_noisy = noise_mult > 1.0 or confidence < 0.9

            kit_vibration_g, kit_vibration_spike = self._step_kit_vibration(node)
            node.last_kit_vibration_spike = kit_vibration_spike
            kit_tilt_deg, kit_tilt_shift = self._step_kit_tilt(node)
            node.last_kit_tilt_shift = kit_tilt_shift

            health_status = SensorHealthStatus.ONLINE
            if node.battery_pct <= 0.0:
                health_status = SensorHealthStatus.OFFLINE
            elif node.battery_pct < 25.0 or is_noisy:
                health_status = SensorHealthStatus.DEGRADED

            for sensor_type, track in node.tracks.items():
                if sensor_type == SensorType.WATER_LEVEL:
                    value = self._step_water_level(node)
                elif sensor_type == SensorType.WATER_FLOW:
                    value = self._step_water_flow(node)
                else:
                    value = track.step(self.rng, noise_multiplier=noise_mult)
                    if sensor_type == SensorType.RGB_CAMERA and hasattr(self, "camera_adapter") and self.camera_adapter.profile != "AUTO":
                        value = self.camera_adapter.get_victim_confidence(victim_id)
                    elif sensor_type == SensorType.THERMAL_IMAGING and hasattr(self, "thermal_adapter") and self.thermal_adapter.profile != "AUTO":
                        value = self.thermal_adapter.get_victim_temperature(victim_id)
                reading = SensorReading(
                    sensor_type=sensor_type,
                    value=round(value, 2),
                    unit=_sensor_unit(sensor_type),
                    location=GPSCoordinate(
                        latitude=location.latitude,
                        longitude=location.longitude,
                        altitude_m=location.altitude_m,
                    ),
                    victim_id=victim_id,
                    confidence=round(confidence, 2),
                    noisy=is_noisy,
                    device_id=f"KIT-{victim_id}",
                    status=health_status,
                    quality=round(confidence, 2),
                )
                readings.append(reading)

            # IMU readings
            for imu_type, imu_value in (
                (SensorType.IMU_TILT, kit_tilt_deg),
                (SensorType.IMU_VIBRATION, kit_vibration_g),
            ):
                reading = SensorReading(
                    sensor_type=imu_type,
                    value=round(imu_value, 3),
                    unit=_sensor_unit(imu_type),
                    location=GPSCoordinate(
                        latitude=location.latitude,
                        longitude=location.longitude,
                        altitude_m=location.altitude_m,
                    ),
                    victim_id=victim_id,
                    confidence=round(confidence, 2),
                    noisy=is_noisy,
                    device_id=f"KIT-{victim_id}",
                    status=health_status,
                    quality=round(confidence, 2),
                    raw_data={
                        "acc_x_g": node.acc_x_g,
                        "acc_y_g": node.acc_y_g,
                        "acc_z_g": node.acc_z_g,
                        "acc_magnitude_g": node.acc_magnitude_g,
                        "impact_detected": node.impact_detected,
                        "sustained_vibration_cycles": node.sustained_vibration_cycles,
                    } if imu_type == SensorType.IMU_VIBRATION else {"tilt_deg": kit_tilt_deg},
                )
                readings.append(reading)

        return readings

    def get_sensor_health_report(self) -> list[SensorHealth]:
        """Generate structured health report for every active sensor channel."""
        health_list: list[SensorHealth] = []
        for vid, node in self.nodes.items():
            status = SensorHealthStatus.ONLINE
            error_msg = None
            if node.battery_pct <= 0.0:
                status = SensorHealthStatus.OFFLINE
                error_msg = "Battery depleted (0%)"
            elif node.battery_pct < 20.0:
                status = SensorHealthStatus.DEGRADED
                error_msg = f"Low battery warning ({round(node.battery_pct, 1)}%)"

            for st in node.tracks.keys():
                health_list.append(SensorHealth(
                    sensor_id=f"SENS-{vid}-{st.value}",
                    sensor_type=st,
                    status=status,
                    battery_pct=round(node.battery_pct, 1),
                    signal_quality=round(self._degraded_confidence(node), 2),
                    error_message=error_msg,
                ))

            # Kit IMU
            health_list.append(SensorHealth(
                sensor_id=f"SENS-{vid}-IMU",
                sensor_type=SensorType.IMU_VIBRATION,
                status=status,
                battery_pct=round(node.battery_pct, 1),
                signal_quality=round(self._degraded_confidence(node), 2),
                error_message=error_msg,
            ))

        # Site-wide Environmental Gauges
        env_sensors = [
            (SensorType.RAINFALL_INTENSITY, "ENV-RAIN-01", self.rainfall_adapter if hasattr(self, "rainfall_adapter") else None),
            (SensorType.SOIL_MOISTURE, "ENV-SOIL-01", None),
            (SensorType.BAROMETRIC_PRESSURE, "ENV-BARO-01", self.barometric_adapter if hasattr(self, "barometric_adapter") else None),
            (SensorType.GAS_CONCENTRATION, "ENV-GAS-01", self.gas_smoke_adapter if hasattr(self, "gas_smoke_adapter") else None),
            (SensorType.SMOKE_DENSITY, "ENV-SMOKE-01", self.gas_smoke_adapter if hasattr(self, "gas_smoke_adapter") else None),
            (SensorType.TEMPERATURE, "ENV-TEMP-01", self.temperature_adapter if hasattr(self, "temperature_adapter") else None),
            (SensorType.HUMIDITY, "ENV-HUMID-01", self.humidity_adapter if hasattr(self, "humidity_adapter") else None),
            (SensorType.GPS, "DEV-GPS-01", self.gps_adapter if hasattr(self, "gps_adapter") else None),
        ]
        for st, sid, adapter in env_sensors:
            if adapter and hasattr(adapter, "get_health"):
                health_list.append(adapter.get_health())
            else:
                health_list.append(SensorHealth(
                    sensor_id=sid,
                    sensor_type=st,
                    status=SensorHealthStatus.ONLINE,
                    battery_pct=100.0,
                    signal_quality=0.99,
                    error_message=None,
                ))

        return health_list

    def battery_report(self) -> dict:
        """Convenience accessor for current battery levels."""
        return {vid: round(node.battery_pct, 1) for vid, node in self.nodes.items()}

    def power_report(self) -> dict:
        return {
            vid: {
                "battery_pct": round(node.battery_pct, 1),
                "charging": bool(self.enable_solar_charging and node.charging),
                "solar_input_pct": round(node.last_solar_input_pct, 3) if self.enable_solar_charging else 0.0,
                "bms_capped": bool(self.enable_solar_charging and node.bms_capped),
                "power_source": "solar+battery" if self.enable_solar_charging else "battery",
            }
            for vid, node in self.nodes.items()
        }

    def is_daylight(self) -> bool:
        return self.enable_solar_charging and self._solar_irradiance_factor() > 0.0

    def water_report(self) -> dict:
        if not self.enable_water_sensor:
            return {}
        return {
            vid: round(node.tracks[SensorType.WATER_LEVEL].current_value, 1)
            for vid, node in self.nodes.items()
            if SensorType.WATER_LEVEL in node.tracks
        }

    def rain_report(self) -> dict:
        return {
            "rainfall_mm_hr": round(self._rain_mm_hr, 2),
            "accumulated_rain_mm": round(getattr(self, "_accumulated_rain_mm", 0.0), 2),
        }

    def soil_report(self) -> dict:
        return {"soil_moisture_pct": round(self._soil_moisture_pct, 1)}

    def seismic_report(self) -> dict:
        return {
            "vibration_mm_s": round(self._vibration_mm_s, 2),
            "aftershock_active": self._aftershock_active,
        }

    def tilt_report(self) -> dict:
        return {
            "tilt_deg": round(self._tilt_deg, 2),
            "shift_detected": bool(getattr(self, "_last_tilt_shift", False)),
        }

    def gas_report(self) -> dict:
        return {"gas_concentration_ppm": round(getattr(self, "_gas_ppm", 0.0), 2)}

    def smoke_report(self) -> dict:
        return {"smoke_density_pct": round(getattr(self, "_smoke_pct", 0.0), 2)}

    def pressure_report(self) -> dict:
        return {"barometric_pressure_hpa": round(getattr(self, "_pressure_hpa", 1013.25), 2)}

    def imu_report(self) -> dict:
        return {
            vid: {
                "kit_tilt_deg": round(node.kit_tilt_deg, 2),
                "kit_vibration_g": round(node.kit_vibration_g, 3),
                "acc_magnitude_g": round(getattr(node, "acc_magnitude_g", 1.0), 3),
                "impact_detected": getattr(node, "impact_detected", False),
                "sustained_vibration_cycles": getattr(node, "sustained_vibration_cycles", 0),
                "kit_disturbed": bool(node.last_kit_tilt_shift or node.last_kit_vibration_spike),
            }
            for vid, node in self.nodes.items()
        }

    def imu_3axis_report(self) -> dict:
        return {
            vid: {
                "acc_x_g": round(getattr(node, "acc_x_g", 0.0), 3),
                "acc_y_g": round(getattr(node, "acc_y_g", 0.0), 3),
                "acc_z_g": round(getattr(node, "acc_z_g", 1.0), 3),
                "ax_g": round(getattr(node, "acc_x_g", 0.0), 3),
                "ay_g": round(getattr(node, "acc_y_g", 0.0), 3),
                "az_g": round(getattr(node, "acc_z_g", 1.0), 3),
                "magnitude_g": round(getattr(node, "acc_magnitude_g", 1.0), 3),
                "tilt_deg": round(node.kit_tilt_deg, 2),
                "impact_detected": getattr(node, "impact_detected", False),
                "sustained_vibration": getattr(node, "sustained_vibration_cycles", 0) > 0,
                "sustained_vibration_cycles": getattr(node, "sustained_vibration_cycles", 0),
            }
            for vid, node in self.nodes.items()
        }

    def temperature_report(self) -> dict:
        trend = "STABLE"
        roc = 0.0
        status = "ONLINE"
        if hasattr(self, "temperature_adapter"):
            r_obj = self.temperature_adapter.read_sensor()
            trend = r_obj.trend.value if hasattr(r_obj.trend, "value") else str(r_obj.trend)
            roc = r_obj.rate_of_change
            status = r_obj.status.value if hasattr(r_obj.status, "value") else str(r_obj.status)
        return {
            "ambient_temp_c": round(self._ambient_temp_c, 1),
            "temperature_c": round(self._ambient_temp_c, 2),
            "rate_of_change": roc,
            "trend": trend,
            "status": status,
            "unit": "°C",
        }

    def humidity_report(self) -> dict:
        trend = "STABLE"
        roc = 0.0
        status = "ONLINE"
        if hasattr(self, "humidity_adapter"):
            r_obj = self.humidity_adapter.read_sensor()
            trend = r_obj.trend.value if hasattr(r_obj.trend, "value") else str(r_obj.trend)
            roc = r_obj.rate_of_change
            status = r_obj.status.value if hasattr(r_obj.status, "value") else str(r_obj.status)
        return {
            "humidity_pct": round(self._humidity_pct, 1),
            "rate_of_change": roc,
            "trend": trend,
            "status": status,
            "unit": "%",
        }

    def water_flow_report(self) -> dict:
        if not self.enable_water_flow_sensor:
            return {}
        return {
            vid: round(node.tracks[SensorType.WATER_FLOW].current_value, 2)
            for vid, node in self.nodes.items()
            if SensorType.WATER_FLOW in node.tracks
        }

    def environmental_full_report(self) -> dict:
        rain_cls = "NO_RAIN"
        if hasattr(self, "rainfall_adapter"):
            r_obj = self.rainfall_adapter.read_sensor()
            rain_cls = r_obj.classification.value if hasattr(r_obj.classification, "value") else str(r_obj.classification)

        temp_trend = "STABLE"
        if hasattr(self, "temperature_adapter"):
            t_obj = self.temperature_adapter.read_sensor()
            temp_trend = t_obj.trend.value if hasattr(t_obj.trend, "value") else str(t_obj.trend)

        humid_trend = "STABLE"
        if hasattr(self, "humidity_adapter"):
            h_obj = self.humidity_adapter.read_sensor()
            humid_trend = h_obj.trend.value if hasattr(h_obj.trend, "value") else str(h_obj.trend)

        water_lvl = 0.0
        water_flow = 0.0
        water_tr = "STABLE"
        water_cls = "NORMAL"
        if hasattr(self, "water_level_adapter"):
            w_obj = self.water_level_adapter.read_sensor()
            water_lvl = w_obj.water_level_cm
            water_flow = w_obj.water_flow_mps
            water_tr = w_obj.trend.value if hasattr(w_obj.trend, "value") else str(w_obj.trend)
            water_cls = w_obj.classification.value if hasattr(w_obj.classification, "value") else str(w_obj.classification)

        return {
            "rainfall_mm_hr": round(self._rain_mm_hr, 2),
            "rainfall_rate_mm_h": round(self._rain_mm_hr, 2),
            "accumulated_rain_mm": round(getattr(self, "_accumulated_rain_mm", 0.0), 2),
            "cumulative_rainfall_mm": round(getattr(self, "_accumulated_rain_mm", 0.0), 2),
            "rainfall_classification": rain_cls,
            "soil_moisture_pct": round(self._soil_moisture_pct, 1),
            "vibration_mm_s": round(self._vibration_mm_s, 2),
            "aftershock_active": self._aftershock_active,
            "tilt_deg": round(self._tilt_deg, 2),
            "ambient_temp_c": round(self._ambient_temp_c, 1),
            "temperature_c": round(self._ambient_temp_c, 2),
            "temperature_trend": temp_trend,
            "humidity_pct": round(self._humidity_pct, 1),
            "humidity_trend": humid_trend,
            "water_level_cm": round(water_lvl, 2),
            "water_flow_mps": round(water_flow, 2),
            "water_level_trend": water_tr,
            "water_classification": water_cls,
            "gas_concentration_ppm": round(getattr(self, "_gas_ppm", 0.0), 2),
            "smoke_density_pct": round(getattr(self, "_smoke_pct", 0.0), 2),
            "barometric_pressure_hpa": round(getattr(self, "_pressure_hpa", 1013.25), 2),
        }

    def generate_environmental_readings(self) -> list[SensorReading]:
        """Generate site-wide environmental readings for intelligence and analysis."""
        site_loc = self.victims[0].location if self.victims else GPSCoordinate(0.0, 0.0)
        temp_status = self.temperature_adapter.status if hasattr(self, "temperature_adapter") else SensorHealthStatus.ONLINE
        humid_status = self.humidity_adapter.status if hasattr(self, "humidity_adapter") else SensorHealthStatus.ONLINE
        water_status = self.water_level_adapter.status if hasattr(self, "water_level_adapter") else SensorHealthStatus.ONLINE
        w_obj = self.water_level_adapter.read_sensor() if hasattr(self, "water_level_adapter") else None

        return [
            SensorReading(
                sensor_type=SensorType.RAINFALL_INTENSITY,
                value=round(self._rain_mm_hr, 2),
                unit="mm/hr",
                location=site_loc,
                device_id="ENV-RAIN-01",
                confidence=0.98,
                status=SensorHealthStatus.ONLINE,
                quality=0.98,
                raw_data={"accumulated_mm": round(getattr(self, "_accumulated_rain_mm", 0.0), 2)},
            ),
            SensorReading(
                sensor_type=SensorType.SOIL_MOISTURE,
                value=round(self._soil_moisture_pct, 1),
                unit="%",
                location=site_loc,
                device_id="ENV-SOIL-01",
                confidence=0.95,
                status=SensorHealthStatus.ONLINE,
                quality=0.95,
            ),
            SensorReading(
                sensor_type=SensorType.BAROMETRIC_PRESSURE,
                value=round(getattr(self, "_pressure_hpa", 1013.25), 2),
                unit="hPa",
                location=site_loc,
                device_id="ENV-BARO-01",
                confidence=0.99,
                status=SensorHealthStatus.ONLINE,
                quality=0.99,
            ),
            SensorReading(
                sensor_type=SensorType.GAS_CONCENTRATION,
                value=round(getattr(self, "_gas_ppm", 0.0), 2),
                unit="ppm",
                location=site_loc,
                device_id="ENV-GAS-01",
                confidence=0.95,
                status=SensorHealthStatus.ONLINE,
                quality=0.95,
            ),
            SensorReading(
                sensor_type=SensorType.SMOKE_DENSITY,
                value=round(getattr(self, "_smoke_pct", 0.0), 2),
                unit="%",
                location=site_loc,
                device_id="ENV-SMOKE-01",
                confidence=0.95,
                status=SensorHealthStatus.ONLINE,
                quality=0.95,
            ),
            SensorReading(
                sensor_type=SensorType.TEMPERATURE,
                value=round(self._ambient_temp_c, 2),
                unit="°C",
                location=site_loc,
                device_id="ENV-TEMP-01",
                confidence=0.98 if temp_status == SensorHealthStatus.ONLINE else (0.50 if temp_status == SensorHealthStatus.DEGRADED else 0.0),
                status=temp_status,
                quality=self.temperature_adapter.signal_quality if hasattr(self, "temperature_adapter") else 0.98,
                raw_data={"rate_of_change": self.temperature_adapter._rate_of_change if hasattr(self, "temperature_adapter") else 0.0},
            ),
            SensorReading(
                sensor_type=SensorType.HUMIDITY,
                value=round(self._humidity_pct, 2),
                unit="%",
                location=site_loc,
                device_id="ENV-HUMID-01",
                confidence=0.98 if humid_status == SensorHealthStatus.ONLINE else (0.50 if humid_status == SensorHealthStatus.DEGRADED else 0.0),
                status=humid_status,
                quality=self.humidity_adapter.signal_quality if hasattr(self, "humidity_adapter") else 0.98,
                raw_data={"rate_of_change": self.humidity_adapter._rate_of_change if hasattr(self, "humidity_adapter") else 0.0},
            ),
            SensorReading(
                sensor_type=SensorType.WATER_LEVEL,
                value=round(w_obj.water_level_cm if w_obj else 0.0, 2),
                unit="cm",
                location=site_loc,
                device_id="ENV-WATER-01",
                confidence=0.98 if water_status == SensorHealthStatus.ONLINE else (0.50 if water_status == SensorHealthStatus.DEGRADED else 0.0),
                status=water_status,
                quality=self.water_level_adapter.signal_quality if hasattr(self, "water_level_adapter") else 0.98,
                raw_data={"rate_of_change": self.water_level_adapter._rate_of_change if hasattr(self, "water_level_adapter") else 0.0, "water_flow_mps": round(w_obj.water_flow_mps if w_obj else 0.0, 2)},
            ),
            SensorReading(
                sensor_type=SensorType.WATER_FLOW,
                value=round(w_obj.water_flow_mps if w_obj else 0.0, 2),
                unit="m/s",
                location=site_loc,
                device_id="ENV-WATER-01",
                confidence=0.98 if water_status == SensorHealthStatus.ONLINE else (0.50 if water_status == SensorHealthStatus.DEGRADED else 0.0),
                status=water_status,
                quality=self.water_level_adapter.signal_quality if hasattr(self, "water_level_adapter") else 0.98,
            ),
            SensorReading(
                sensor_type=SensorType.GPS,
                value=float(self.gps_adapter.satellites if hasattr(self, "gps_adapter") else 12.0),
                unit="sats",
                location=GPSCoordinate(
                    latitude=self.gps_adapter._latitude if hasattr(self, "gps_adapter") else site_loc.latitude,
                    longitude=self.gps_adapter._longitude if hasattr(self, "gps_adapter") else site_loc.longitude,
                    altitude_m=self.gps_adapter._altitude_m if hasattr(self, "gps_adapter") else site_loc.altitude_m,
                ),
                device_id="DEV-GPS-01",
                confidence=0.98 if (hasattr(self, "gps_adapter") and self.gps_adapter.status == SensorHealthStatus.ONLINE) else (0.50 if (hasattr(self, "gps_adapter") and self.gps_adapter.status == SensorHealthStatus.DEGRADED) else 0.0),
                status=self.gps_adapter.status if hasattr(self, "gps_adapter") else SensorHealthStatus.ONLINE,
                quality=self.gps_adapter.signal_quality if hasattr(self, "gps_adapter") else 0.98,
                raw_data=self.gps_adapter.read_sensor().to_dict() if hasattr(self, "gps_adapter") else {},
            ),
        ]

    def reset(self) -> None:
        """Reset the simulation to cycle 0 with fresh battery/track state."""
        self.cycle_count = 0
        self.nodes = {
            v.victim_id: _VictimNode(
                victim=v,
                enable_water_sensor=self.enable_water_sensor,
                enable_water_flow_sensor=self.enable_water_flow_sensor,
            )
            for v in self.victims
        }
        self._rain_mm_hr = self.site_environment.initial_rainfall_mm_hr
        self._accumulated_rain_mm = 0.0
        self._soil_moisture_pct = self.site_environment.initial_soil_moisture_pct
        self._vibration_mm_s = self.site_environment.baseline_vibration_mm_s
        self._aftershock_active = False
        self._aftershock_peak_mm_s = 0.0
        self._aftershock_cycles_remaining = 0
        self._tilt_deg = self.site_environment.baseline_tilt_deg
        self._last_vibration_spike = False
        self._last_tilt_shift = False
        self._gas_ppm = getattr(self.site_environment, "initial_gas_concentration_ppm", 0.0)
        self._smoke_pct = getattr(self.site_environment, "initial_smoke_density_pct", 0.0)
        self._ambient_temp_c = self.site_environment.initial_ambient_temp_c
        self._humidity_pct = self.site_environment.initial_humidity_pct
        self.gas_smoke_adapter = GasSmokeSimulationAdapter(
            gas_type=GasType.GENERIC_SMOKE,
            location=getattr(self.site_environment, "site_location", None) or GPSCoordinate(latitude=32.3740, longitude=77.2490),
            initial_gas_ppm=self._gas_ppm if self._gas_ppm > 0 else 10.0,
            initial_smoke_pct=self._smoke_pct if self._smoke_pct > 0 else 5.0,
        )
        self.barometric_adapter = BarometricPressureSimulationAdapter(
            sensor_id="ENV-BARO-01",
            device_id="DEV-BARO-01",
            location=getattr(self.site_environment, "site_location", None) or GPSCoordinate(latitude=32.3740, longitude=77.2490),
            scenario_profile="NORMAL_WEATHER",
            initial_pressure_hpa=self._pressure_hpa if self._pressure_hpa > 0 else 1013.25,
        )
        self.landslide_adapter = LandslideSensorSimulationAdapter(
            scenario_profile="NORMAL",
            base_location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490)),
            initial_moisture_pct=self._soil_moisture_pct,
            initial_tilt_deg=self._tilt_deg,
        )
        self.rainfall_adapter = RainfallSimulationAdapter(
            sensor_id="ENV-RAIN-01",
            device_id="DEV-RAIN-01",
            location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490)),
            scenario_profile="AUTO",
            initial_rainfall_rate=self._rain_mm_hr,
        )
        self.temperature_adapter = TemperatureSimulationAdapter(
            sensor_id="ENV-TEMP-01",
            device_id="DEV-TEMP-01",
            location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490)),
            scenario_profile="AUTO",
            initial_temp_c=self._ambient_temp_c,
        )
        self.humidity_adapter = HumiditySimulationAdapter(
            sensor_id="ENV-HUMID-01",
            device_id="DEV-HUMID-01",
            location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490)),
            scenario_profile="AUTO",
            initial_humidity_pct=self._humidity_pct,
        )
        self.gps_adapter = GPSSimulationAdapter(
            sensor_id="DEV-GPS-01",
            device_id="RESCUE-KIT-01",
            initial_location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490, altitude_m=3950.0)),
            scenario_profile="STATIONARY",
        )
        self.water_level_adapter = WaterLevelSimulationAdapter(
            sensor_id="ENV-WATER-01",
            device_id="DEV-WATER-01",
            location=getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490)),
            scenario_profile="AUTO",
            initial_water_level_cm=0.0,
            initial_flow_mps=0.0,
        )

    def temperature_report(self) -> dict:
        """Structured report for ambient temperature."""
        if hasattr(self, "temperature_adapter"):
            return self.temperature_adapter.read_sensor().to_dict()
        return {"temperature_c": self._ambient_temp_c, "trend": "STABLE", "rate_of_change": 0.0}

    def humidity_report(self) -> dict:
        """Structured report for atmospheric relative humidity."""
        if hasattr(self, "humidity_adapter"):
            return self.humidity_adapter.read_sensor().to_dict()
        return {"humidity_pct": self._humidity_pct, "trend": "STABLE", "rate_of_change": 0.0}

    def water_level_report(self) -> dict:
        """Structured report for water level and flow telemetry."""
        if hasattr(self, "water_level_adapter"):
            return self.water_level_adapter.read_sensor().to_dict()
        return {"water_level_cm": 0.0, "water_flow_mps": 0.0, "trend": "STABLE", "classification": "NORMAL"}

    def non_contact_pressure_report(self) -> dict:
        """Structured report for non-contact flood-water level & hydrostatic pressure estimation."""
        if hasattr(self, "water_level_adapter") and hasattr(self.water_level_adapter, "non_contact_engine"):
            return self.water_level_adapter.non_contact_engine.get_latest_report()
        from non_contact_pressure import NonContactPressureEngine
        return NonContactPressureEngine().get_latest_report()

    def generate_temperature_readings(self) -> list[TemperatureReading]:
        """Generate one cycle of validated temperature readings."""
        if hasattr(self, "temperature_adapter"):
            reading = self.temperature_adapter.read_sensor()
            return [reading]
        return []

    def generate_humidity_readings(self) -> list[HumidityReading]:
        """Generate one cycle of validated humidity readings."""
        if hasattr(self, "humidity_adapter"):
            reading = self.humidity_adapter.read_sensor()
            return [reading]
        return []

    def generate_water_level_readings(self) -> list[WaterLevelReading]:
        """Generate one cycle of validated water level readings."""
        if hasattr(self, "water_level_adapter"):
            reading = self.water_level_adapter.read_sensor()
            return [reading]
        return []

    def gas_smoke_report(self) -> dict:
        """Structured comprehensive report from the gas/smoke module."""
        reading = self.gas_smoke_adapter.read_sensor()
        return reading.to_dict()

    def generate_gas_smoke_readings(self) -> list[GasSmokeReading]:
        """Generate one cycle of validated gas/smoke readings."""
        # Synchronize with simulator environmental stepping
        self.gas_smoke_adapter._gas_concentration = getattr(self, "_gas_ppm", self.gas_smoke_adapter._gas_concentration)
        self.gas_smoke_adapter._smoke_density_pct = getattr(self, "_smoke_pct", self.gas_smoke_adapter._smoke_density_pct)
        reading = self.gas_smoke_adapter.step(self.rng)
        return [reading]

    def barometric_pressure_report(self) -> dict:
        """Structured comprehensive report from the barometric pressure module."""
        reading = self.barometric_adapter.read_sensor()
        return reading.to_dict()

    def generate_barometric_readings(self) -> list[BarometricPressureReading]:
        """Generate one cycle of validated barometric pressure readings."""
        reading = self.barometric_adapter.step(self.rng)
        self._pressure_hpa = reading.pressure_hpa
        return [reading]

    def soil_moisture_report(self, node_id: Optional[str] = None) -> dict:
        """Structured comprehensive report for Soil Moisture."""
        if hasattr(self, "landslide_adapter"):
            if abs(self._soil_moisture_pct - self.landslide_adapter.get_primary_node_moisture()) > 0.5:
                self.landslide_adapter.set_node_moisture("SLOPE-NODE-01", self._soil_moisture_pct)
        reading = self.landslide_adapter.read_soil_moisture(node_id)
        d = reading.to_dict()
        d["soil_moisture_pct"] = round(reading.soil_moisture_pct, 1)
        return d

    def tilt_report(self, node_id: Optional[str] = None) -> dict:
        """Structured comprehensive report for Tilt / Inclinometer."""
        if hasattr(self, "landslide_adapter"):
            if abs(self._tilt_deg - self.landslide_adapter.get_primary_node_tilt()) > 0.5:
                self.landslide_adapter.set_node_tilt("SLOPE-NODE-01", self._tilt_deg)
        reading = self.landslide_adapter.read_tilt(node_id)
        d = reading.to_dict()
        d["tilt_deg"] = round(reading.tilt_angle_deg, 2)
        d["shift_detected"] = bool(getattr(self, "_last_tilt_shift", False)) or reading.tilt_angle_deg > 3.0
        return d

    def landslide_hazard_report(self, node_id: Optional[str] = None) -> dict:
        """Structured comprehensive report for Landslide Risk Assessment."""
        nid = node_id or "SLOPE-NODE-01"
        node = self.landslide_adapter.nodes.get(nid, self.landslide_adapter.nodes["SLOPE-NODE-01"])
        assessment = self.landslide_adapter.assess_node_risk(
            node,
            rainfall_mm_hr=getattr(self, "_rain_mm_hr", 0.0),
            vibration_mm_s=getattr(self, "_vibration_mm_s", 0.0),
        )
        return assessment.to_dict()

    def landslide_nodes_report(self) -> dict:
        """Structured report for all slope nodes telemetry and risk assessments."""
        nodes_out = {}
        highest_risk = 0.0
        primary_status = "NORMAL"
        primary_action = "Routine slope monitoring active."
        affected_nodes = []

        for nid, node in self.landslide_adapter.nodes.items():
            ass = self.landslide_adapter.assess_node_risk(
                node,
                rainfall_mm_hr=getattr(self, "_rain_mm_hr", 0.0),
                vibration_mm_s=getattr(self, "_vibration_mm_s", 0.0),
            )
            d = ass.to_dict()
            nodes_out[nid] = d
            if ass.landslide_risk_score > highest_risk:
                highest_risk = ass.landslide_risk_score
                primary_status = ass.risk_level.value if hasattr(ass.risk_level, "value") else str(ass.risk_level)
                primary_action = ass.recommended_action
            if ass.landslide_risk_score >= 50.0:
                affected_nodes.append(nid)

        return {
            "highest_risk_score": highest_risk,
            "overall_risk_level": primary_status,
            "recommended_action": primary_action,
            "affected_nodes": affected_nodes,
            "nodes": nodes_out,
        }

    def generate_landslide_readings(self) -> list[LandslideRiskAssessment]:
        """Generate one cycle of validated Landslide risk assessments across all slope nodes."""
        return self.landslide_adapter.step(
            self.rng,
            rainfall_mm_hr=getattr(self, "_rain_mm_hr", 0.0),
            vibration_mm_s=getattr(self, "_vibration_mm_s", 0.0),
        )

    def camera_report(self, victim_id: Optional[str] = None, camera_id: Optional[str] = None) -> dict:
        """Structured comprehensive report for an optical Camera channel."""
        reading = self.camera_adapter.read_camera(camera_id=camera_id, victim_id=victim_id)
        return reading.to_dict()

    def thermal_report(self, victim_id: Optional[str] = None, camera_id: Optional[str] = None) -> dict:
        """Structured comprehensive report for a Thermal Infrared Camera channel."""
        reading = self.thermal_adapter.read_thermal(camera_id=camera_id, victim_id=victim_id)
        return reading.to_dict()

    def cameras_all_report(self) -> dict:
        """Structured report across all optical camera nodes."""
        cams_out = {}
        for cid in self.camera_adapter.cameras:
            cams_out[cid] = self.camera_adapter.read_camera(camera_id=cid).to_dict()
        return {
            "camera_count": len(cams_out),
            "profile": self.camera_adapter.profile,
            "cameras": cams_out,
        }

    def thermal_all_report(self) -> dict:
        """Structured report across all thermal camera nodes."""
        thms_out = {}
        for cid in self.thermal_adapter.cameras:
            thms_out[cid] = self.thermal_adapter.read_thermal(camera_id=cid).to_dict()
        return {
            "thermal_count": len(thms_out),
            "profile": self.thermal_adapter.profile,
            "thermal_cameras": thms_out,
        }

    def camera_thermal_correlation_report(self, victim_id: str) -> dict:
        """Generate cross-modal Optical + Thermal correlation analysis for a target victim."""
        cam_r = self.camera_adapter.read_camera(victim_id=victim_id)
        thm_r = self.thermal_adapter.read_thermal(victim_id=victim_id)

        # Cross-modal correlation logic
        evidence_tokens = []
        penalties = []
        case = CameraCorrelationCase.NO_EVIDENCE
        combined_conf = 0.0
        summary = "No decisive visual or thermal indicators."

        # Case 4: Complete cross-modal corroboration with other sensors
        # Evaluated first if both optical human + thermal human match
        has_cam_human = cam_r.detection_state in (CameraDetectionState.PERSON_DETECTED, CameraDetectionState.MULTIPLE_PERSONS, CameraDetectionState.PARTIAL_PERSON) and cam_r.confidence >= 0.40
        has_thm_human = thm_r.human_signature and thm_r.thermal_confidence >= 0.40

        if has_cam_human and has_thm_human:
            case = CameraCorrelationCase.CASE_1_STRONG_SURVIVOR
            combined_conf = min(1.0, (cam_r.confidence * 0.5 + thm_r.thermal_confidence * 0.5) + CAMERA_CONFIG.synergy_bonus_weight)
            summary = f"Strong survivor evidence: Optical human detection ({int(cam_r.confidence*100)}%) confirmed by Thermal heat signature ({thm_r.estimated_temperature}°C, {int(thm_r.thermal_confidence*100)}% conf)."
            evidence_tokens.extend(["CAMERA_HUMAN_DETECTED", "THERMAL_HUMAN_HEAT_CONFIRMED", "CROSS_MODAL_SYNERGY_BONUS"])
        elif has_cam_human and not has_thm_human:
            case = CameraCorrelationCase.CASE_2_POSSIBLE_FALSE_POSITIVE
            combined_conf = max(0.05, cam_r.confidence * (1.0 - CAMERA_CONFIG.false_positive_penalty_weight))
            summary = f"Possible visual false-positive or cold object: Optical camera detected person ({int(cam_r.confidence*100)}%) but thermal camera detected no body heat ({thm_r.estimated_temperature}°C)."
            evidence_tokens.append("CAMERA_HUMAN_DETECTED")
            penalties.append("THERMAL_HEAT_ABSENCE_PENALTY")
        elif not has_cam_human and has_thm_human:
            case = CameraCorrelationCase.CASE_3_HIDDEN_OBSCURED_SURVIVOR
            combined_conf = thm_r.thermal_confidence * 0.85
            summary = f"Possible hidden or obscured survivor: Thermal camera detected human heat signature ({thm_r.estimated_temperature}°C, {int(thm_r.thermal_confidence*100)}%) despite camera occlusion ({int(cam_r.occlusion*100)}%)."
            evidence_tokens.extend(["THERMAL_HUMAN_HEAT_CONFIRMED", "HIDDEN_SURVIVOR_CANDIDATE"])
            if cam_r.smoke_present:
                evidence_tokens.append("OPTICAL_SMOKE_OBSCURATION")
        elif thm_r.fire_hotspot:
            summary = f"Thermal fire hotspot detected ({thm_r.estimated_temperature}°C) — Hazard alert active, non-survivor thermal signature."
            evidence_tokens.append("THERMAL_FIRE_HOTSPOT")
        elif thm_r.hot_debris:
            summary = f"Hot debris signature detected ({thm_r.estimated_temperature}°C) — Solar-heated material classified."
            evidence_tokens.append("THERMAL_HOT_DEBRIS")

        corr = CameraThermalCorrelation(
            victim_id=victim_id,
            camera_id=cam_r.camera_id,
            thermal_id=thm_r.camera_id,
            correlation_case=case,
            combined_confidence=combined_conf,
            explainable_summary=summary,
            evidence_tokens=evidence_tokens,
            penalties_applied=penalties,
        )
        return corr.to_dict()

    def generate_camera_readings(self) -> list[CameraReading]:
        return [self.camera_adapter.read_camera(camera_id=cid) for cid in self.camera_adapter.cameras]

    def generate_thermal_readings(self) -> list[ThermalCameraReading]:
        return [self.thermal_adapter.read_thermal(camera_id=cid) for cid in self.thermal_adapter.cameras]

    def rainfall_report(self) -> dict:
        """Structured comprehensive report from the dedicated Rainfall / Precipitation module."""
        reading = self.rainfall_adapter.read_sensor()
        return reading.to_dict()

    def generate_rainfall_readings(self) -> list[RainfallReading]:
        """Generate one cycle of validated dedicated Rainfall readings."""
        return [self.rainfall_adapter.read_sensor()]

    def gps_report(self) -> dict:
        """Convenience accessor for current GPS positioning and kinematic telemetry."""
        if hasattr(self, "gps_adapter"):
            return self.gps_adapter.read_sensor().to_dict()
        loc = getattr(self.site_environment, "site_location", None) or (self.victims[0].location if self.victims else GPSCoordinate(latitude=32.3740, longitude=77.2490, altitude_m=3950.0))
        return {
            "sensor_id": "DEV-GPS-01",
            "device_id": "RESCUE-KIT-01",
            "sensor_type": "gps",
            "latitude": round(loc.latitude, 6),
            "longitude": round(loc.longitude, 6),
            "altitude_m": round(loc.altitude_m if loc.altitude_m is not None else 3950.0, 1),
            "accuracy_m": 2.5,
            "speed_mps": 0.0,
            "heading_deg": 0.0,
            "satellites": 12,
            "movement_state": "STATIONARY",
            "is_valid_fix": True,
            "status": "ONLINE",
            "confidence": 0.98,
            "quality": 0.98,
            "metadata": {"mode": "DEFAULT"},
        }

    def generate_gps_readings(self) -> list[GPSReading]:
        """Generate one cycle of validated dedicated GPS readings."""
        if hasattr(self, "gps_adapter"):
            return [self.gps_adapter.read_sensor()]
        return []

