"""
scenario_intelligence.py
------------------------
End-to-end intelligence engine for disaster scenario assessment, multi-sensor
fusion, health monitoring, trend/anomaly analysis, multi-hazard cascading
inference, and alert lifecycle management.

Pipeline:
Sensor Readings -> Health Check -> Trend/Anomaly Tracking -> Semantic Evidence
  -> Scenario Inference Engine (19 Master Scenarios) -> Multi-Hazard Cascades
  -> Alert Lifecycle & Ledger Sync -> Commander & Rescue Intelligence
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from models import (
    SensorType,
    SensorReading,
    SensorHealth,
    SensorHealthStatus,
    SensorTrend,
    SensorEvidence,
    ScenarioInferenceResult,
    DisasterAssessment,
    RiskLevel,
    VictimStatus,
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
    GPSCoordinate,
    GPSMovementState,
    GPSConfig,
    GPS_CONFIG,
    GPSReading,
    WaterTrend,
    WaterLevelClassification,
    WaterLevelConfig,
    WATER_LEVEL_CONFIG,
    WaterLevelReading,
)
from scenarios_master import DISASTER_SCENARIOS, get_scenario_by_id
from scenario_sensor_profiles import get_scenario_sensor_profile, SensorRole
import db


# --------------------------------------------------------------------------- #
# Helper timestamp
# --------------------------------------------------------------------------- #
def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Barometric Pressure Dedicated Analyzer
# --------------------------------------------------------------------------- #
class BarometricPressureAnalyzer:
    """
    Dedicated analyzer for Barometric Pressure environmental monitoring.
    Performs:
    - Strict input validation (rejects NaN, Inf, negative, impossible values)
    - Rate of change & time-series trend analysis (STABLE, RISING, FALLING, RAPIDLY_FALLING, RAPIDLY_RISING)
    - Pressure drop severity classification (NORMAL, SIGNIFICANT_DROP, RAPID_DROP, CRITICAL_DROP)
    - Statistical & physical anomaly detection (NORMAL, ABNORMAL, CRITICAL)
    - Sensor health & offline handling (OFFLINE -> UNAVAILABLE, confidence penalty)
    """
    def __init__(self, window_size: int = PRESSURE_CONFIG.history_window_size):
        self._history: deque[float] = deque(maxlen=window_size)
        self._window_size = window_size

    def validate_reading(self, reading: Any) -> bool:
        if reading is None:
            return False
        if hasattr(reading, "validate"):
            return reading.validate()
        if isinstance(reading, dict):
            p = reading.get("pressure_hpa") or reading.get("barometric_pressure_hpa")
            if p is None:
                return False
            try:
                p_f = float(p)
                if math.isnan(p_f) or math.isinf(p_f):
                    return False
                if p_f < PRESSURE_CONFIG.min_pressure_hpa or p_f > PRESSURE_CONFIG.max_pressure_hpa:
                    return False
                return True
            except (ValueError, TypeError):
                return False
        return False

    def analyze(
        self,
        pressure_hpa: float,
        status: SensorHealthStatus = SensorHealthStatus.ONLINE,
        elapsed_cycles: float = 1.0,
    ) -> Dict[str, Any]:
        if status in (SensorHealthStatus.OFFLINE, SensorHealthStatus.ERROR):
            return {
                "available": False,
                "status": status.value if hasattr(status, "value") else str(status),
                "pressure_hpa": "UNAVAILABLE",
                "unit": "hPa",
                "warning": "Barometric pressure detection unavailable",
                "trend": "UNAVAILABLE",
                "rate_of_change": 0.0,
                "drop_severity": "UNKNOWN",
                "anomaly_state": "UNKNOWN",
                "confidence_penalty": 0.25,
            }

        prev_pressure = self._history[-1] if self._history else pressure_hpa
        self._history.append(pressure_hpa)

        diff = pressure_hpa - prev_pressure
        rate = diff / max(elapsed_cycles, 0.1)

        # Multi-sample trend analysis
        if rate <= -PRESSURE_CONFIG.rapid_falling_threshold_hpa_per_cycle:
            trend = PressureTrend.RAPIDLY_FALLING
        elif rate <= -PRESSURE_CONFIG.falling_threshold_hpa_per_cycle:
            trend = PressureTrend.FALLING
        elif rate >= PRESSURE_CONFIG.rapid_rising_threshold_hpa_per_cycle:
            trend = PressureTrend.RAPIDLY_RISING
        elif rate >= PRESSURE_CONFIG.rising_threshold_hpa_per_cycle:
            trend = PressureTrend.RISING
        else:
            trend = PressureTrend.STABLE

        # If we have multiple historical readings, verify multi-step trajectory
        if len(self._history) >= 3:
            samples = list(self._history)
            overall_diff = samples[-1] - samples[0]
            if overall_diff <= -PRESSURE_CONFIG.rapid_falling_threshold_hpa_per_cycle * 2:
                trend = PressureTrend.RAPIDLY_FALLING
            elif overall_diff <= -PRESSURE_CONFIG.falling_threshold_hpa_per_cycle:
                if trend == PressureTrend.STABLE:
                    trend = PressureTrend.FALLING
            elif overall_diff >= PRESSURE_CONFIG.rapid_rising_threshold_hpa_per_cycle * 2:
                trend = PressureTrend.RAPIDLY_RISING
            elif overall_diff >= PRESSURE_CONFIG.rising_threshold_hpa_per_cycle:
                if trend == PressureTrend.STABLE:
                    trend = PressureTrend.RISING

        # Drop severity & anomaly detection
        cum_drop = (self._history[0] - pressure_hpa) if len(self._history) > 1 else abs(rate)
        if pressure_hpa <= PRESSURE_CONFIG.critical_plunge_threshold_hpa or rate <= -6.0 or cum_drop >= PRESSURE_CONFIG.critical_drop_threshold_hpa:
            drop_sev = PressureDropSeverity.CRITICAL_DROP
            anomaly_state = PressureAnomalyLevel.CRITICAL
        elif pressure_hpa <= PRESSURE_CONFIG.severe_cyclone_threshold_hpa or rate <= -PRESSURE_CONFIG.rapid_falling_threshold_hpa_per_cycle or cum_drop >= PRESSURE_CONFIG.anomaly_absolute_drop_hpa:
            drop_sev = PressureDropSeverity.RAPID_DROP
            anomaly_state = PressureAnomalyLevel.ABNORMAL
        elif rate <= -PRESSURE_CONFIG.falling_threshold_hpa_per_cycle or cum_drop >= 4.0:
            drop_sev = PressureDropSeverity.SIGNIFICANT_DROP
            anomaly_state = PressureAnomalyLevel.NORMAL
        else:
            drop_sev = PressureDropSeverity.NORMAL
            anomaly_state = PressureAnomalyLevel.NORMAL

        return {
            "available": True,
            "status": status.value if hasattr(status, "value") else str(status),
            "pressure_hpa": round(pressure_hpa, 2),
            "unit": "hPa",
            "previous_pressure_hpa": round(prev_pressure, 2),
            "pressure_difference": round(diff, 3),
            "rate_of_change": round(rate, 3),
            "rate_unit": f"hPa/{PRESSURE_CONFIG.rate_calculation_unit}",
            "trend": trend.value,
            "drop_severity": drop_sev.value,
            "anomaly_state": anomaly_state.value,
            "history_samples": len(self._history),
            "confidence_penalty": 0.0,
        }

    def reset(self):
        self._history.clear()


# --------------------------------------------------------------------------- #
# Gas & Smoke Dedicated Analyzer
# --------------------------------------------------------------------------- #
class GasSmokeAnalyzer:
    """
    Dedicated analyzer for gas and smoke hazards.
    Performs:
    - Input validation (rejects NaN, Inf, negative, impossible values)
    - Normalized concentration level grading (NORMAL, ELEVATED, HIGH, CRITICAL)
    - Smoke level grading (NO_SMOKE, LOW, MODERATE, HIGH, CRITICAL)
    - Rate of change & trend analysis
    - Anomaly detection (NORMAL, ABNORMAL, CRITICAL)
    - Sensor health verification (OFFLINE != safe; flags detection unavailable)
    """
    def __init__(self):
        self._gas_history: deque[float] = deque(maxlen=60)
        self._smoke_history: deque[float] = deque(maxlen=60)

    def validate_reading(self, reading: Any) -> bool:
        if reading is None:
            return False
        if hasattr(reading, "validate"):
            return reading.validate()
        if isinstance(reading, dict):
            gc = reading.get("gas_concentration")
            sm = reading.get("smoke_density_pct")
            if gc is None or sm is None:
                return False
            try:
                gc_f = float(gc)
                sm_f = float(sm)
                if math.isnan(gc_f) or math.isinf(gc_f) or math.isnan(sm_f) or math.isinf(sm_f):
                    return False
                if gc_f < 0.0 or sm_f < 0.0 or sm_f > 100.0:
                    return False
                return True
            except (ValueError, TypeError):
                return False
        return False

    def classify_gas(self, concentration: float) -> GasConcentrationLevel:
        if concentration >= 81.0:
            return GasConcentrationLevel.CRITICAL
        elif concentration >= 61.0:
            return GasConcentrationLevel.HIGH
        elif concentration >= 31.0:
            return GasConcentrationLevel.ELEVATED
        return GasConcentrationLevel.NORMAL

    def classify_smoke(self, density_pct: float) -> SmokeLevel:
        if density_pct >= 76.0:
            return SmokeLevel.CRITICAL
        elif density_pct >= 51.0:
            return SmokeLevel.HIGH
        elif density_pct >= 26.0:
            return SmokeLevel.MODERATE
        elif density_pct >= 1.0:
            return SmokeLevel.LOW
        return SmokeLevel.NO_SMOKE

    def analyze(
        self,
        gas_ppm: float,
        smoke_pct: float,
        status: SensorHealthStatus = SensorHealthStatus.ONLINE,
    ) -> Dict[str, Any]:
        if status in (SensorHealthStatus.OFFLINE, SensorHealthStatus.ERROR):
            return {
                "available": False,
                "status": status.value if hasattr(status, "value") else str(status),
                "warning": "Gas detection unavailable",
                "gas_level": "UNKNOWN",
                "smoke_level": "UNKNOWN",
                "gas_trend": "UNAVAILABLE",
                "smoke_trend": "UNAVAILABLE",
                "anomaly_state": "UNKNOWN",
                "confidence_penalty": 0.35,
            }

        prev_gas = self._gas_history[-1] if self._gas_history else gas_ppm
        prev_smoke = self._smoke_history[-1] if self._smoke_history else smoke_pct
        self._gas_history.append(gas_ppm)
        self._smoke_history.append(smoke_pct)

        rate_gas = gas_ppm - prev_gas
        rate_smoke = smoke_pct - prev_smoke

        # Trends
        if rate_gas >= 10.0:
            gas_trend = "RAPIDLY RISING"
        elif rate_gas >= 2.0:
            gas_trend = "RISING"
        elif rate_gas <= -2.0:
            gas_trend = "FALLING"
        else:
            gas_trend = "STABLE"

        if rate_smoke >= 10.0:
            smoke_trend = "RAPIDLY RISING"
        elif rate_smoke >= 2.0:
            smoke_trend = "RISING"
        elif rate_smoke <= -2.0:
            smoke_trend = "FALLING"
        else:
            smoke_trend = "STABLE"

        gas_level = self.classify_gas(gas_ppm)
        smoke_level = self.classify_smoke(smoke_pct)

        # Anomaly determination
        if gas_level == GasConcentrationLevel.CRITICAL or smoke_level == SmokeLevel.CRITICAL or rate_gas >= 20.0 or rate_smoke >= 20.0:
            anomaly_state = "CRITICAL"
        elif gas_level in (GasConcentrationLevel.HIGH, GasConcentrationLevel.ELEVATED) or smoke_level in (SmokeLevel.HIGH, SmokeLevel.MODERATE) or rate_gas >= 8.0 or rate_smoke >= 8.0:
            anomaly_state = "ABNORMAL"
        else:
            anomaly_state = "NORMAL"

        return {
            "available": True,
            "status": status.value if hasattr(status, "value") else str(status),
            "gas_concentration": round(gas_ppm, 2),
            "gas_level": gas_level.value,
            "smoke_density_pct": round(smoke_pct, 2),
            "smoke_level": smoke_level.value,
            "rate_of_change_gas": round(rate_gas, 3),
            "rate_of_change_smoke": round(rate_smoke, 3),
            "gas_trend": gas_trend,
            "smoke_trend": smoke_trend,
            "anomaly_state": anomaly_state,
            "confidence_penalty": 0.0,
        }


# --------------------------------------------------------------------------- #
# Landslide Hazard & Multi-Sensor Fusion Analyzer
# --------------------------------------------------------------------------- #
class LandslideRiskAnalyzer:
    """
    Dedicated analyzer for Soil Moisture + Tilt / Inclination multi-sensor fusion,
    rate of change, trend detection, persistence window, hysteresis filtering,
    and explainable Landslide Risk scoring (0 - 100).
    """
    def __init__(self, window_size: int = LANDSLIDE_CONFIG.history_window_size):
        self._window_size = window_size
        self._moisture_history: deque[float] = deque(maxlen=window_size)
        self._tilt_history: deque[float] = deque(maxlen=window_size)
        self._persistence_cycles: int = 0
        self._recovery_cycles: int = 0
        self._event_state: LandslideEventState = LandslideEventState.NORMAL

    def validate_reading(self, reading: Any) -> bool:
        if reading is None:
            return False
        if hasattr(reading, "validate"):
            return reading.validate()
        if isinstance(reading, dict):
            m = reading.get("soil_moisture_pct") or reading.get("soil_moisture")
            t = reading.get("tilt_angle_deg") or reading.get("tilt_deg")
            if m is None and t is None:
                return False
            try:
                if m is not None:
                    m_f = float(m)
                    if math.isnan(m_f) or math.isinf(m_f) or m_f < LANDSLIDE_CONFIG.min_moisture_pct or m_f > LANDSLIDE_CONFIG.max_moisture_pct:
                        return False
                if t is not None:
                    t_f = float(t)
                    if math.isnan(t_f) or math.isinf(t_f) or t_f < LANDSLIDE_CONFIG.min_tilt_deg or t_f > LANDSLIDE_CONFIG.max_tilt_deg:
                        return False
                return True
            except (ValueError, TypeError):
                return False
        return False

    def analyze(
        self,
        soil_moisture_pct: float,
        tilt_angle_deg: float,
        status: SensorHealthStatus = SensorHealthStatus.ONLINE,
        rainfall_mm_hr: float = 0.0,
        vibration_mm_s: float = 0.0,
        elapsed_cycles: float = 1.0,
        node_id: str = "SLOPE-NODE-01",
    ) -> Dict[str, Any]:
        if status in (SensorHealthStatus.OFFLINE, SensorHealthStatus.ERROR):
            return {
                "available": False,
                "node_id": node_id,
                "status": status.value if hasattr(status, "value") else str(status),
                "warning": "Landslide telemetry unavailable / Sensor Offline",
                "soil_moisture_pct": "UNAVAILABLE",
                "tilt_angle_deg": "UNAVAILABLE",
                "moisture_trend": "UNAVAILABLE",
                "tilt_trend": "UNAVAILABLE",
                "rate_of_change_moisture": 0.0,
                "rate_of_change_tilt": 0.0,
                "risk_score": 0.0,
                "risk_level": "LOW",
                "event_state": "NORMAL",
                "confidence": 0.0,
                "confidence_penalty": 0.5,
                "contributing_factors": ["Telemetry node offline / probe communication failure"],
                "recommended_action": "Inspect slope telemetry node; check battery and LoRa link.",
            }

        prev_m = self._moisture_history[-1] if self._moisture_history else soil_moisture_pct
        prev_t = self._tilt_history[-1] if self._tilt_history else tilt_angle_deg
        self._moisture_history.append(soil_moisture_pct)
        self._tilt_history.append(tilt_angle_deg)

        cycles = max(elapsed_cycles, 0.1)
        rate_m = (soil_moisture_pct - prev_m) / cycles
        rate_t = (tilt_angle_deg - prev_t) / cycles

        # Moisture Trend
        if rate_m >= LANDSLIDE_CONFIG.moisture_rapid_rising_rate_threshold:
            m_trend = MoistureTrend.RAPIDLY_RISING
        elif rate_m >= LANDSLIDE_CONFIG.moisture_rising_rate_threshold:
            m_trend = MoistureTrend.RISING
        elif rate_m <= -LANDSLIDE_CONFIG.moisture_rapid_rising_rate_threshold:
            m_trend = MoistureTrend.RAPIDLY_FALLING
        elif rate_m <= -LANDSLIDE_CONFIG.moisture_rising_rate_threshold:
            m_trend = MoistureTrend.FALLING
        else:
            m_trend = MoistureTrend.STABLE

        # Tilt Trend
        if rate_t >= LANDSLIDE_CONFIG.tilt_rapid_rising_rate_threshold:
            t_trend = TiltTrend.RAPIDLY_RISING
        elif rate_t >= LANDSLIDE_CONFIG.tilt_rising_rate_threshold:
            t_trend = TiltTrend.RISING
        elif rate_t <= -LANDSLIDE_CONFIG.tilt_rapid_rising_rate_threshold:
            t_trend = TiltTrend.RAPIDLY_FALLING
        elif rate_t <= -LANDSLIDE_CONFIG.tilt_rising_rate_threshold:
            t_trend = TiltTrend.FALLING
        else:
            t_trend = TiltTrend.STABLE

        factors: list[str] = []

        # 1. Moisture Subscore (0 - 25)
        if soil_moisture_pct <= LANDSLIDE_CONFIG.moisture_elevated_threshold_pct:
            moisture_score = (soil_moisture_pct / max(LANDSLIDE_CONFIG.moisture_elevated_threshold_pct, 1.0)) * 8.0
        elif soil_moisture_pct <= LANDSLIDE_CONFIG.moisture_high_threshold_pct:
            moisture_score = 8.0 + ((soil_moisture_pct - LANDSLIDE_CONFIG.moisture_elevated_threshold_pct) / (LANDSLIDE_CONFIG.moisture_high_threshold_pct - LANDSLIDE_CONFIG.moisture_elevated_threshold_pct)) * 10.0
            factors.append(f"Elevated soil saturation ({soil_moisture_pct:.1f}%)")
        else:
            moisture_score = 18.0 + min(7.0, ((soil_moisture_pct - LANDSLIDE_CONFIG.moisture_high_threshold_pct) / (LANDSLIDE_CONFIG.moisture_critical_threshold_pct - LANDSLIDE_CONFIG.moisture_high_threshold_pct)) * 7.0)
            factors.append(f"Critical soil water saturation ({soil_moisture_pct:.1f}%)")

        # 2. Moisture Trend Bonus (0 - 15)
        if m_trend == MoistureTrend.RAPIDLY_RISING:
            m_bonus = 15.0
            factors.append(f"Rapid soil saturation rate (+{rate_m:.1f}%/cycle)")
        elif m_trend == MoistureTrend.RISING:
            m_bonus = 8.0
            factors.append(f"Rising soil saturation trend (+{rate_m:.1f}%/cycle)")
        elif m_trend == MoistureTrend.FALLING:
            m_bonus = -3.0
        elif m_trend == MoistureTrend.RAPIDLY_FALLING:
            m_bonus = -6.0
        else:
            m_bonus = 0.0

        # 3. Tilt Subscore (0 - 25)
        if tilt_angle_deg <= LANDSLIDE_CONFIG.tilt_elevated_threshold_deg:
            tilt_score = (tilt_angle_deg / max(LANDSLIDE_CONFIG.tilt_elevated_threshold_deg, 0.1)) * 6.0
        elif tilt_angle_deg <= LANDSLIDE_CONFIG.tilt_high_threshold_deg:
            tilt_score = 6.0 + ((tilt_angle_deg - LANDSLIDE_CONFIG.tilt_elevated_threshold_deg) / (LANDSLIDE_CONFIG.tilt_high_threshold_deg - LANDSLIDE_CONFIG.tilt_elevated_threshold_deg)) * 11.0
            factors.append(f"Inclinometer slope angle deviation ({tilt_angle_deg:.1f}°)")
        else:
            tilt_score = 17.0 + min(8.0, ((tilt_angle_deg - LANDSLIDE_CONFIG.tilt_high_threshold_deg) / (LANDSLIDE_CONFIG.tilt_critical_threshold_deg - LANDSLIDE_CONFIG.tilt_high_threshold_deg)) * 8.0)
            factors.append(f"Severe inclinometer slope shear ({tilt_angle_deg:.1f}°)")

        # 4. Tilt Trend Bonus (0 - 25)
        if t_trend == TiltTrend.RAPIDLY_RISING:
            t_bonus = 25.0
            factors.append(f"Rapid slope shear rate (+{rate_t:.2f}°/cycle)")
        elif t_trend == TiltTrend.RISING:
            t_bonus = 14.0
            factors.append(f"Rising tilt shift trend (+{rate_t:.2f}°/cycle)")
        elif t_trend == TiltTrend.FALLING:
            t_bonus = -5.0
        elif t_trend == TiltTrend.RAPIDLY_FALLING:
            t_bonus = -10.0
        else:
            t_bonus = 0.0

        # 5. Persistence & Compound Context (0 - 10)
        is_abnormal = (soil_moisture_pct >= LANDSLIDE_CONFIG.moisture_elevated_threshold_pct or tilt_angle_deg >= LANDSLIDE_CONFIG.tilt_elevated_threshold_deg)
        if is_abnormal:
            self._persistence_cycles += 1
            self._recovery_cycles = 0
        else:
            self._recovery_cycles += 1
            if self._recovery_cycles >= LANDSLIDE_CONFIG.recovery_cycles_required:
                self._persistence_cycles = 0

        p_bonus = 0.0
        if self._persistence_cycles >= 2 and (soil_moisture_pct >= 60.0 or tilt_angle_deg >= 2.0):
            p_bonus += 5.0
            factors.append(f"Sustained abnormal condition ({self._persistence_cycles} cycles)")
        if self._persistence_cycles >= 3 and (soil_moisture_pct >= 75.0 and tilt_angle_deg >= 3.0):
            p_bonus += 5.0

        if rainfall_mm_hr >= 25.0:
            p_bonus += 3.0
            factors.append(f"Torrential precipitation trigger ({rainfall_mm_hr:.1f} mm/hr)")
        if vibration_mm_s >= 4.0:
            p_bonus += 3.0
            factors.append(f"Seismic ground shaking trigger ({vibration_mm_s:.1f} mm/s)")

        p_score = min(10.0, p_bonus)

        raw_score = max(0.0, min(100.0, moisture_score + m_bonus + tilt_score + t_bonus + p_score))
        if self._persistence_cycles <= 1 and raw_score >= LANDSLIDE_CONFIG.risk_critical_min and not (soil_moisture_pct >= 85.0 and tilt_angle_deg >= 5.0 and len(self._moisture_history) > 1 and self._moisture_history[-2] >= 75.0):
            raw_score = min(raw_score, 68.0)
            factors.append("Single spike under persistence filter (unconfirmed)")

        score = round(raw_score, 1)

        if score >= LANDSLIDE_CONFIG.risk_critical_min:
            risk_level = LandslideRiskLevel.CRITICAL
            self._event_state = LandslideEventState.CRITICAL
            action = "Immediate slope evacuation: Deploy geotechnical barriers, halt base operations, and clear downstream zones."
        elif score >= 50.0:
            risk_level = LandslideRiskLevel.HIGH
            self._event_state = LandslideEventState.HIGH_RISK
            action = "Escalate slope monitoring: Restrict slope-base access and stage geotechnical rescue assets."
        elif score >= 25.0:
            risk_level = LandslideRiskLevel.MODERATE
            self._event_state = LandslideEventState.WATCH if score < 38.0 else LandslideEventState.ELEVATED
            action = "Maintain heightened surveillance: Track moisture/tilt trajectory and survey drainage paths."
        else:
            risk_level = LandslideRiskLevel.LOW
            if self._event_state in (LandslideEventState.CRITICAL, LandslideEventState.HIGH_RISK) and self._recovery_cycles < LANDSLIDE_CONFIG.recovery_cycles_required:
                self._event_state = LandslideEventState.RECOVERY
                action = "Slope stabilization observed; conducting post-event ground verification."
            else:
                self._event_state = LandslideEventState.NORMAL
                action = "Routine slope stability monitoring active."

        if not factors:
            factors.append("Stable slope equilibrium within nominal thresholds")

        return {
            "available": True,
            "node_id": node_id,
            "status": status.value if hasattr(status, "value") else str(status),
            "soil_moisture_pct": round(soil_moisture_pct, 2),
            "tilt_angle_deg": round(tilt_angle_deg, 2),
            "rate_of_change_moisture": round(rate_m, 3),
            "rate_of_change_tilt": round(rate_t, 3),
            "moisture_trend": m_trend.value,
            "tilt_trend": t_trend.value,
            "moisture_subscore": round(moisture_score, 1),
            "moisture_trend_bonus": round(m_bonus, 1),
            "tilt_subscore": round(tilt_score, 1),
            "tilt_trend_bonus": round(t_bonus, 1),
            "persistence_score": round(p_score, 1),
            "persistence_cycles": self._persistence_cycles,
            "risk_score": score,
            "risk_level": risk_level.value,
            "event_state": self._event_state.value,
            "contributing_factors": factors,
            "recommended_action": action,
            "confidence": 0.96 if status == SensorHealthStatus.ONLINE else 0.5,
            "confidence_penalty": 0.0,
        }


# --------------------------------------------------------------------------- #
# Optical & Thermal Camera Dedicated Analyzer
# --------------------------------------------------------------------------- #
class CameraThermalAnalyzer:
    """
    Dedicated analyzer for optical and thermal infrared camera channels.
    Performs:
    - Multi-modal input validation (rejection of corrupted / out-of-range telemetry)
    - Semantic evidence extraction (person count, human classification, heat signatures, smoke penetration)
    - Cross-modal correlation & synergy (Cases 1, 2, 3, 4)
    - Offline & degraded sensor handling (zero false alarms on disconnected units)
    - Anomaly detection (mannequin/false positives, fire hotspots, hot debris)
    """
    def __init__(self, history_window: int = 30):
        self._cam_history: Dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=history_window))
        self._thm_history: Dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=history_window))

    def validate_camera_reading(self, reading: Any) -> bool:
        if reading is None:
            return False
        if hasattr(reading, "validate"):
            return reading.validate()
        if isinstance(reading, dict):
            conf = reading.get("confidence")
            vis = reading.get("visibility", 1.0)
            occ = reading.get("occlusion", 0.0)
            if conf is None:
                return False
            try:
                c_f = float(conf)
                v_f = float(vis)
                o_f = float(occ)
                if math.isnan(c_f) or math.isinf(c_f) or c_f < 0.0 or c_f > 1.0:
                    return False
                if math.isnan(v_f) or math.isinf(v_f) or v_f < 0.0 or v_f > 1.0:
                    return False
                if math.isnan(o_f) or math.isinf(o_f) or o_f < 0.0 or o_f > 1.0:
                    return False
                return True
            except (ValueError, TypeError):
                return False
        return False

    def validate_thermal_reading(self, reading: Any) -> bool:
        if reading is None:
            return False
        if hasattr(reading, "validate"):
            return reading.validate()
        if isinstance(reading, dict):
            temp = reading.get("estimated_temperature")
            conf = reading.get("thermal_confidence", 0.0)
            if temp is None:
                return False
            try:
                t_f = float(temp)
                c_f = float(conf)
                if math.isnan(t_f) or math.isinf(t_f) or t_f < -50.0 or t_f > 200.0:
                    return False
                if math.isnan(c_f) or math.isinf(c_f) or c_f < 0.0 or c_f > 1.0:
                    return False
                return True
            except (ValueError, TypeError):
                return False
        return False

    def analyze(
        self,
        camera_reading: Optional[Any],
        thermal_reading: Optional[Any],
        pir_motion: float = 0.0,
        radar_bpm: float = 0.0,
        victim_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        cam_dict = camera_reading.to_dict() if hasattr(camera_reading, "to_dict") else (camera_reading if isinstance(camera_reading, dict) else {})
        thm_dict = thermal_reading.to_dict() if hasattr(thermal_reading, "to_dict") else (thermal_reading if isinstance(thermal_reading, dict) else {})

        cam_status = cam_dict.get("status", "ONLINE")
        thm_status = thm_dict.get("status", "ONLINE")

        cam_available = cam_status not in ("OFFLINE", "ERROR", CameraHealthStatus.OFFLINE)
        thm_available = thm_status not in ("OFFLINE", "ERROR", ThermalHealthStatus.OFFLINE)

        cam_conf = float(cam_dict.get("confidence", 0.0)) if cam_available else 0.0
        cam_det_state = str(cam_dict.get("detection_state", "NO_DETECTION"))
        cam_class = str(cam_dict.get("classification", "UNKNOWN"))
        cam_count = int(cam_dict.get("person_count", 0)) if cam_available else 0
        cam_vis = float(cam_dict.get("visibility", 1.0)) if cam_available else 0.0
        cam_occ = float(cam_dict.get("occlusion", 0.0)) if cam_available else 0.0
        smoke_present = bool(cam_dict.get("smoke_present", False))
        fire_visible = bool(cam_dict.get("fire_visible", False))

        thm_temp = float(thm_dict.get("estimated_temperature", 20.0)) if thm_available else 20.0
        thm_bg = float(thm_dict.get("background_temperature", 18.0)) if thm_available else 18.0
        thm_delta = float(thm_dict.get("temperature_delta", abs(thm_temp - thm_bg))) if thm_available else 0.0
        thm_conf = float(thm_dict.get("thermal_confidence", 0.0)) if thm_available else 0.0
        thm_human = bool(thm_dict.get("human_signature", False)) if thm_available else False
        thm_det_type = str(thm_dict.get("detection_type", "NO_HEAT"))
        thm_fire_hotspot = bool(thm_dict.get("fire_hotspot", False)) if thm_available else False
        thm_hot_debris = bool(thm_dict.get("hot_debris", False)) if thm_available else False

        evidence_tokens: list[str] = []
        alerts_to_emit: list[dict] = []
        penalties: list[str] = []

        # Optical evidence extraction
        if cam_available:
            if cam_det_state in ("PERSON_DETECTED", "MULTIPLE_PERSONS", "PARTIAL_PERSON") or (cam_class == "HUMAN" and cam_conf >= 0.35):
                evidence_tokens.append("CAMERA_HUMAN_CONFIRMED")
                if cam_count > 1:
                    evidence_tokens.append("CAMERA_MULTIPLE_PERSONS")
            elif cam_det_state == "OCCLUDED_PERSON":
                evidence_tokens.append("CAMERA_OCCLUSION_HEAVY")
            elif cam_det_state == "DEBRIS":
                evidence_tokens.append("CAMERA_DEBRIS_CLASSIFIED")
            
            if smoke_present:
                evidence_tokens.append("CAMERA_SMOKE_OBSCURATION")
            if fire_visible:
                evidence_tokens.append("CAMERA_FIRE_VISIBLE")
        else:
            evidence_tokens.append("CAMERA_OFFLINE_ANOMALY")

        # Thermal evidence extraction
        if thm_available:
            if thm_human and thm_conf >= 0.35:
                evidence_tokens.append("THERMAL_HUMAN_HEAT_CONFIRMED")
                if thm_dict.get("heat_signature_count", 1) > 1:
                    evidence_tokens.append("THERMAL_MULTIPLE_HEAT_SIGNATURES")
            elif thm_det_type == "WEAK_HEAT_SIGNATURE":
                evidence_tokens.append("THERMAL_WEAK_HEAT_SIGNATURE")
            elif thm_fire_hotspot or thm_temp >= 55.0:
                evidence_tokens.append("THERMAL_FIRE_HOTSPOT")
            elif thm_hot_debris:
                evidence_tokens.append("THERMAL_HOT_DEBRIS")
            
            if smoke_present and thm_human:
                evidence_tokens.append("THERMAL_SMOKE_PENETRATION")
        else:
            evidence_tokens.append("THERMAL_OFFLINE_ANOMALY")

        # Cross-modal correlation
        has_cam_human = "CAMERA_HUMAN_CONFIRMED" in evidence_tokens
        has_thm_human = "THERMAL_HUMAN_HEAT_CONFIRMED" in evidence_tokens
        has_pir = pir_motion >= 0.15
        has_radar = radar_bpm >= 15.0

        correlation_case = CameraCorrelationCase.NO_EVIDENCE
        combined_conf = 0.0
        explanation = "No cross-sensor visual/thermal corroboration."

        if not cam_available and not thm_available:
            correlation_case = CameraCorrelationCase.NO_EVIDENCE
            combined_conf = 0.0
            explanation = "Both optical camera and thermal imager are offline. Relying on radar and acoustic modalities."
        elif has_cam_human and has_thm_human and has_pir and has_radar:
            correlation_case = CameraCorrelationCase.CASE_4_QUAD_SENSOR_CORROBORATED
            combined_conf = min(0.99, max(cam_conf, thm_conf) * 0.90 + 0.12)
            explanation = f"Quad-sensor corroborated survivor: Optical human ({int(cam_conf*100)}%), Thermal heat ({thm_temp}°C, {int(thm_conf*100)}%), Radar vitals ({int(radar_bpm)} BPM), and PIR motion confirmed."
            evidence_tokens.append("QUAD_SENSOR_CORROBORATION_CONFIRMED")
        elif has_cam_human and has_thm_human:
            correlation_case = CameraCorrelationCase.CASE_1_STRONG_SURVIVOR
            combined_conf = min(0.98, (cam_conf * 0.5 + thm_conf * 0.5) + CAMERA_CONFIG.synergy_bonus_weight)
            explanation = f"Strong survivor evidence: Optical human detection confirmed by Thermal body heat ({thm_temp}°C, Δ{thm_delta}°C)."
            evidence_tokens.append("CROSS_MODAL_SYNERGY_BONUS")
        elif has_cam_human and not has_thm_human and thm_available:
            correlation_case = CameraCorrelationCase.CASE_2_POSSIBLE_FALSE_POSITIVE
            combined_conf = max(0.05, cam_conf * (1.0 - CAMERA_CONFIG.false_positive_penalty_weight))
            explanation = f"Possible visual false positive: Optical human detected ({int(cam_conf*100)}%) but thermal sensor shows no body heat signature ({thm_temp}°C)."
            penalties.append("THERMAL_HEAT_ABSENCE_PENALTY")
            evidence_tokens.append("FALSE_POSITIVE_FLAGGED")
        elif not has_cam_human and has_thm_human:
            correlation_case = CameraCorrelationCase.CASE_3_HIDDEN_OBSCURED_SURVIVOR
            combined_conf = min(0.92, thm_conf * 0.88)
            explanation = f"Hidden/obscured survivor candidate: Thermal heat signature ({thm_temp}°C, {int(thm_conf*100)}% conf) detected through visual obstruction/rubble (occlusion {int(cam_occ*100)}%)."
            evidence_tokens.append("HIDDEN_SURVIVOR_CANDIDATE")
        elif thm_fire_hotspot:
            combined_conf = 0.0
            explanation = f"Thermal fire hotspot detected at {thm_temp}°C — environmental combustion hazard, not human survivor."
        else:
            combined_conf = max(cam_conf * 0.3, thm_conf * 0.3)
            explanation = "Background environmental baseline with no distinct human signature."

        return {
            "available": cam_available or thm_available,
            "camera_available": cam_available,
            "thermal_available": thm_available,
            "camera_id": cam_dict.get("camera_id", "CAM-001"),
            "thermal_id": thm_dict.get("camera_id", "THERMAL-001"),
            "victim_id": victim_id,
            "correlation_case": correlation_case.value,
            "combined_confidence": round(combined_conf, 3),
            "explainable_summary": explanation,
            "evidence_tokens": evidence_tokens,
            "penalties_applied": penalties,
            "camera_confidence": round(cam_conf, 3),
            "thermal_confidence": round(thm_conf, 3),
            "estimated_temperature": round(thm_temp, 1),
            "temperature_delta": round(thm_delta, 1),
            "visibility": round(cam_vis, 2),
            "occlusion": round(cam_occ, 2),
            "smoke_present": smoke_present,
            "fire_hotspot": thm_fire_hotspot,
        }

    def analyze_cross_modal(
        self,
        victim_id: str,
        cam_rd: Optional[Any] = None,
        thm_rd: Optional[Any] = None,
        pir_motion: float = 0.0,
        radar_bpm: float = 0.0,
    ) -> CameraThermalCorrelation:
        result = self.analyze(
            camera_reading=cam_rd,
            thermal_reading=thm_rd,
            pir_motion=pir_motion,
            radar_bpm=radar_bpm,
            victim_id=victim_id,
        )
        case_enum = CameraCorrelationCase(result["correlation_case"])
        synergy = CAMERA_CONFIG.synergy_bonus_case1 if case_enum == CameraCorrelationCase.CASE_1_STRONG_SURVIVOR else (CAMERA_CONFIG.synergy_bonus_case4 if case_enum in (CameraCorrelationCase.CASE_4_MULTI_SENSOR_CONFIRMED, CameraCorrelationCase.CASE_4_QUAD_SENSOR_CORROBORATED) else 0.0)
        return CameraThermalCorrelation(
            victim_id=victim_id,
            camera_id=result["camera_id"],
            thermal_id=result["thermal_id"],
            thermal_camera_id=result["thermal_id"],
            correlation_case=case_enum,
            combined_confidence=result["combined_confidence"],
            synergy_bonus=synergy,
            explainable_summary=result["explainable_summary"],
            evidence_tokens=result["evidence_tokens"],
            penalties_applied=result["penalties_applied"],
        )


# --------------------------------------------------------------------------- #
# Dedicated Rainfall & Precipitation Analyzer
# --------------------------------------------------------------------------- #
class RainfallAnalyzer:
    """
    Dedicated analyzer for Rainfall and Precipitation telemetry.
    Performs:
    - Input validation (rejection of corrupted / negative values / NaN / Inf)
    - Time-series sliding window for rate-of-change, 3-cycle moving average, and trend analysis
    - Peak intensity detection and cumulative accumulation tracking
    - Meteorological classification (NO_RAIN, LIGHT, MODERATE, HEAVY, VERY_HEAVY, EXTREME)
    - Semantic evidence generation (Cloudburst, Downpour, Compound flood driver, Saturated slope driver)
    - Alert triggers and deduplication
    """
    def __init__(self, history_window: int = 60):
        self._history: deque[float] = deque(maxlen=history_window)
        self._cumulative_mm: float = 0.0
        self._prev_rate: float = 0.0

    def validate_reading(self, reading: Any) -> bool:
        if reading is None:
            return False
        if hasattr(reading, "validate"):
            return reading.validate()
        if isinstance(reading, dict):
            rate = reading.get("rainfall_rate_mm_h", reading.get("rainfall_mm_hr"))
            if rate is None:
                return False
            try:
                r_f = float(rate)
                if math.isnan(r_f) or math.isinf(r_f) or r_f < 0.0 or r_f > 500.0:
                    return False
                return True
            except (ValueError, TypeError):
                return False
        return False

    def analyze(
        self,
        rainfall_reading: Optional[Any],
        soil_moisture_pct: float = 0.0,
        water_level_cm: float = 0.0,
        water_rising_rate: float = 0.0,
        tilt_deg: float = 0.0,
    ) -> Dict[str, Any]:
        d = rainfall_reading.to_dict() if hasattr(rainfall_reading, "to_dict") else (rainfall_reading if isinstance(rainfall_reading, dict) else {})
        status = d.get("status", "ONLINE")

        if status in ("OFFLINE", "ERROR", SensorHealthStatus.OFFLINE):
            return {
                "status": "OFFLINE",
                "rainfall_rate_mm_h": 0.0,
                "cumulative_rainfall_mm": round(self._cumulative_mm, 2),
                "classification": RainfallClassification.NO_RAIN.value,
                "severity": RiskLevel.LOW.value,
                "trend": RainfallTrend.UNKNOWN.value,
                "evidence_tokens": ["RAINFALL_SENSOR_OFFLINE_WARNING"],
                "flood_compound_risk": False,
                "landslide_compound_risk": False,
                "description": "Rainfall sensor probe is offline.",
            }

        rate = float(d.get("rainfall_rate_mm_h", d.get("rainfall_mm_hr", 0.0)))
        cumul = float(d.get("cumulative_rainfall_mm", self._cumulative_mm))
        self._cumulative_mm = max(self._cumulative_mm, cumul)
        self._history.append(rate)

        roc = rate - self._prev_rate
        self._prev_rate = rate

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

        evidence_tokens = []
        if classification == RainfallClassification.EXTREME:
            evidence_tokens.append("RAINFALL_EXTREME_CLOUD_BURST_DETECTED")
        elif classification == RainfallClassification.VERY_HEAVY:
            evidence_tokens.append("RAINFALL_VERY_HEAVY_DOWNPOUR")
        elif classification == RainfallClassification.HEAVY:
            evidence_tokens.append("RAINFALL_HEAVY_PRECIPITATION")

        if self._cumulative_mm >= RAINFALL_CONFIG.critical_accumulation_mm:
            evidence_tokens.append("RAINFALL_ACCUMULATION_CRITICAL")

        # Compound flood risk
        flood_compound = False
        if rate >= RAINFALL_CONFIG.flash_flood_trigger_mm_h and (water_level_cm >= 50.0 or water_rising_rate >= 1.0):
            flood_compound = True
            evidence_tokens.append("RAINFALL_WATER_COMPOUND_FLASH_FLOOD_TRIGGER")

        # Compound landslide risk
        landslide_compound = False
        if rate >= RAINFALL_CONFIG.landslide_trigger_mm_h and (soil_moisture_pct >= 65.0 or tilt_deg >= 1.5):
            landslide_compound = True
            evidence_tokens.append("RAINFALL_SOIL_COMPOUND_LANDSLIDE_TRIGGER")

        return {
            "status": status,
            "rainfall_rate_mm_h": round(rate, 2),
            "cumulative_rainfall_mm": round(self._cumulative_mm, 2),
            "classification": classification.value if hasattr(classification, "value") else str(classification),
            "severity": severity.value if hasattr(severity, "value") else str(severity),
            "trend": trend.value if hasattr(trend, "value") else str(trend),
            "rate_of_change": round(roc, 3),
            "evidence_tokens": evidence_tokens,
            "flood_compound_risk": flood_compound,
            "landslide_compound_risk": landslide_compound,
            "description": f"Precipitation rate at {round(rate, 1)} mm/h ({classification.value}) with {round(self._cumulative_mm, 1)} mm cumulative accumulation.",
        }


# --------------------------------------------------------------------------- #
# Dedicated GPS / GNSS Positioning & Kinematics Analyzer
# --------------------------------------------------------------------------- #
class GPSAnalyzer:
    """
    Dedicated analyzer for GNSS / GPS receiver telemetry.
    Performs:
    - Coordinate & kinematics validation (latitude -90..90, longitude -180..180, speed >= 0, accuracy >= 0)
    - Kinematic impossible jump anomaly detection (>1000m or >50 m/s displacement)
    - Degradation and signal loss classification (0 sats -> OFFLINE, <4 sats or >15m acc -> DEGRADED)
    - Geospatial proximity calculations (Haversine distance to victim, nearest team)
    - Semantic evidence token generation
    """
    def __init__(self, history_window: int = 60):
        self._history: deque[dict] = deque(maxlen=history_window)
        self._prev_lat: Optional[float] = None
        self._prev_lon: Optional[float] = None
        self.total_distance_m: float = 0.0

    def validate_reading(self, reading: Any) -> bool:
        if reading is None:
            return False
        if hasattr(reading, "validate"):
            return reading.validate()
        if isinstance(reading, dict):
            try:
                lat = float(reading.get("latitude", 0.0))
                lon = float(reading.get("longitude", 0.0))
                acc = float(reading.get("accuracy_m", 0.0))
                spd = float(reading.get("speed_mps", 0.0))
                hdg = float(reading.get("heading_deg", 0.0))
                sats = int(reading.get("satellites", 0))
                if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                    return False
                if acc < 0.0 or spd < 0.0 or not (0.0 <= hdg <= 360.0) or sats < 0:
                    return False
                return True
            except (ValueError, TypeError):
                return False
        return False

    def analyze(
        self,
        gps_reading: Optional[Any],
        victim_locations: Optional[dict] = None,
        rescue_teams: Optional[dict] = None,
    ) -> Dict[str, Any]:
        d = gps_reading.to_dict() if hasattr(gps_reading, "to_dict") else (gps_reading if isinstance(gps_reading, dict) else {})
        status = d.get("status", "ONLINE")

        lat = float(d.get("latitude", 32.3739))
        lon = float(d.get("longitude", 77.2491))
        alt = float(d.get("altitude_m", 3950.0))
        acc = float(d.get("accuracy_m", 2.5))
        spd = float(d.get("speed_mps", 0.0))
        hdg = float(d.get("heading_deg", 0.0))
        sats = int(d.get("satellites", 12))
        mov_state = d.get("movement_state", "STATIONARY")
        if hasattr(mov_state, "value"):
            mov_state = mov_state.value

        evidence_tokens = []
        is_jump = False

        if self._prev_lat is not None and self._prev_lon is not None:
            c1 = GPSCoordinate(latitude=self._prev_lat, longitude=self._prev_lon)
            c2 = GPSCoordinate(latitude=lat, longitude=lon)
            step_d = c1.haversine_distance_to(c2)
            if step_d > 1000.0 or spd > 100.0:
                is_jump = True
                mov_state = "JUMP_ANOMALY"
                evidence_tokens.append("GPS_MOVEMENT_ANOMALY")
            elif step_d < 1000.0:
                self.total_distance_m += step_d

        self._prev_lat = lat
        self._prev_lon = lon
        self._history.append({"latitude": lat, "longitude": lon, "timestamp": _utc_now_iso(), "speed_mps": spd})

        if status in ("OFFLINE", "ERROR", SensorHealthStatus.OFFLINE) or sats == 0 or mov_state == "SIGNAL_LOSS":
            evidence_tokens.append("GPS_SIGNAL_OFFLINE")
            fix_quality = "NO_FIX"
        elif status == "DEGRADED" or acc > 15.0 or sats < 4:
            evidence_tokens.append("GPS_SIGNAL_DEGRADED")
            fix_quality = "DEGRADED_FIX"
        else:
            evidence_tokens.append("GPS_SIGNAL_AVAILABLE")
            fix_quality = "3D_FIX_PRECISION"

        if mov_state == "RAPID_MOVEMENT" or spd >= 10.0:
            evidence_tokens.append("GPS_RAPID_DEVICE_MOVEMENT")

        # Proximity to nearest survivor
        nearest_victim_id = None
        nearest_victim_dist_m = float("inf")
        if victim_locations:
            curr_c = GPSCoordinate(latitude=lat, longitude=lon)
            for vid, v_loc in victim_locations.items():
                if isinstance(v_loc, dict):
                    v_coord = GPSCoordinate(latitude=v_loc.get("latitude", 0.0), longitude=v_loc.get("longitude", 0.0))
                elif isinstance(v_loc, GPSCoordinate):
                    v_coord = v_loc
                else:
                    continue
                d_m = curr_c.haversine_distance_to(v_coord)
                if d_m < nearest_victim_dist_m:
                    nearest_victim_dist_m = d_m
                    nearest_victim_id = vid

        return {
            "status": status,
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "altitude_m": round(alt, 1),
            "accuracy_m": round(acc, 2),
            "speed_mps": round(spd, 2),
            "heading_deg": round(hdg, 1),
            "satellites": sats,
            "movement_state": mov_state,
            "fix_quality": fix_quality,
            "is_valid_fix": status != "OFFLINE" and sats >= 3,
            "total_distance_m": round(self.total_distance_m, 1),
            "evidence_tokens": evidence_tokens,
            "nearest_victim_id": nearest_victim_id,
            "nearest_victim_distance_m": round(nearest_victim_dist_m, 1) if nearest_victim_id else None,
            "description": f"GNSS position: ({lat:.6f}, {lon:.6f}) ±{acc:.1f}m, {sats} sats locked, state: {mov_state}.",
        }


# --------------------------------------------------------------------------- #
# 1. Sensor Trend & Anomaly Tracker
# --------------------------------------------------------------------------- #
class SensorTrendTracker:
    """
    Maintains rolling time-series histories per sensor channel and evaluates:
    - Rate of change (per cycle)
    - Trend direction (RISING, FALLING, STABLE)
    - Sudden spike detection (Z-score / variance threshold)
    - Sustained abnormal condition tracking
    - Anomaly score (0.0 to 1.0)
    """

    def __init__(self, window_size: int = 60):
        self.window_size = window_size
        # key: (sensor_type, victim_id or 'SITE') -> deque of float values
        self._history: Dict[Tuple[str, str], deque[float]] = defaultdict(
            lambda: deque(maxlen=self.window_size)
        )
        self._consecutive_abnormal: Dict[Tuple[str, str], int] = defaultdict(int)

    def push_reading(self, reading: SensorReading) -> SensorTrend:
        st_val = reading.sensor_type.value if hasattr(reading.sensor_type, "value") else str(reading.sensor_type)
        vid = reading.victim_id or "SITE"
        key = (st_val, vid)
        val = float(reading.value)

        history = self._history[key]
        prev_val = history[-1] if history else val
        history.append(val)

        # Rate of change
        rate_of_change = val - prev_val

        # Trend direction
        threshold = 0.05 * max(abs(val), 1.0)
        if rate_of_change > threshold:
            trend_dir = "RISING"
        elif rate_of_change < -threshold:
            trend_dir = "FALLING"
        else:
            trend_dir = "STABLE"

        # Statistical spike & anomaly detection
        is_spike = False
        anomaly_score = 0.0
        if len(history) >= 2:
            prev_samples = list(history)[:-1]
            if prev_samples:
                mean = sum(prev_samples) / len(prev_samples)
                variance = sum((x - mean) ** 2 for x in prev_samples) / len(prev_samples)
                std_dev = math.sqrt(variance)
                z_score = abs(val - mean) / max(std_dev, 1e-4)
                anomaly_score = round(min(1.0, z_score / 3.0), 3)
                if z_score > 2.0 or abs(rate_of_change) > max(abs(mean) * 0.4, 5.0):
                    is_spike = True

        # Physical abnormal threshold evaluation
        is_abnormal = self._is_physically_abnormal(reading.sensor_type, val)
        if is_abnormal:
            self._consecutive_abnormal[key] += 1
        else:
            self._consecutive_abnormal[key] = max(0, self._consecutive_abnormal[key] - 1)

        is_sustained = self._consecutive_abnormal[key] >= 3

        return SensorTrend(
            sensor_type=reading.sensor_type,
            current_value=round(val, 3),
            rate_of_change_per_cycle=round(rate_of_change, 3),
            trend_direction=trend_dir,
            is_spike=is_spike,
            is_sustained_abnormal=is_sustained,
            anomaly_score=anomaly_score,
            history_samples=len(history),
        )

    update = push_reading

    def _is_physically_abnormal(self, st: SensorType, val: float) -> bool:
        if st == SensorType.THERMAL_IMAGING:
            return val > 38.0 or val < 20.0
        elif st == SensorType.WATER_LEVEL:
            return val > 30.0
        elif st == SensorType.WATER_FLOW:
            return val > 1.2
        elif st == SensorType.GAS_CONCENTRATION:
            return val > 50.0
        elif st == SensorType.SMOKE_DENSITY:
            return val > 20.0
        elif st == SensorType.BAROMETRIC_PRESSURE:
            return val < 995.0 or val > 1030.0
        elif st == SensorType.RAINFALL_INTENSITY:
            return val > 25.0
        elif st == SensorType.SOIL_MOISTURE:
            return val > 65.0
        elif st == SensorType.IMU_VIBRATION:
            return val > 0.15
        elif st == SensorType.IMU_TILT:
            return val > 5.0
        elif st == SensorType.CO2:
            return val > 1500.0
        elif st == SensorType.TEMPERATURE:
            return val < -10.0 or val > 45.0
        elif st == SensorType.HUMIDITY:
            return val < 15.0 or val > 90.0
        elif st == SensorType.GPS:
            return val < 4.0
        return False

    def reset(self):
        self._history.clear()
        self._consecutive_abnormal.clear()


# --------------------------------------------------------------------------- #
# 2. Sensor Health Monitor
# --------------------------------------------------------------------------- #
class SensorHealthMonitor:
    """
    Evaluates operating health, fault detection, and signal degradation across
    all hardware and environmental channels.
    """

    def evaluate_node_health(
        self,
        node_id: str,
        battery_pct: float,
        readings: List[SensorReading],
    ) -> List[SensorHealth]:
        health_records: List[SensorHealth] = []
        for r in readings:
            status = r.status if hasattr(r, "status") and r.status != SensorHealthStatus.ONLINE else SensorHealthStatus.ONLINE
            error_msg = None
            quality = getattr(r, "quality", r.confidence)

            # Check if reading itself is offline/degraded
            if status in (SensorHealthStatus.OFFLINE, SensorHealthStatus.ERROR):
                error_msg = "Channel reporting offline/error"
            elif status == SensorHealthStatus.DEGRADED:
                error_msg = "Channel reporting degraded status"

            # Battery health check
            if battery_pct <= 0.0:
                status = SensorHealthStatus.OFFLINE
                error_msg = "Battery depleted (0.0%)"
                quality = 0.0
            elif battery_pct < 20.0:
                status = SensorHealthStatus.DEGRADED
                error_msg = f"Low battery ({round(battery_pct, 1)}%)"
                quality = min(quality, 0.6)

            # Noise / confidence degradation check
            if r.noisy or quality < 0.65 or r.confidence < 0.65:
                if status == SensorHealthStatus.ONLINE:
                    status = SensorHealthStatus.DEGRADED
                    error_msg = "Signal degraded / high jitter"

            # Check extreme clipping / corruption
            if self._is_corrupt_reading(r):
                status = SensorHealthStatus.ERROR
                error_msg = "Hardware ADC range clipping or parity fault"
                quality = 0.1

            health_records.append(
                SensorHealth(
                    sensor_id=f"{node_id}-{r.sensor_type.value}",
                    sensor_type=r.sensor_type,
                    status=status,
                    battery_pct=round(battery_pct, 1),
                    signal_quality=round(quality, 2),
                    error_message=error_msg,
                    last_heartbeat=_utc_now_iso(),
                )
            )
        return health_records

    def _is_corrupt_reading(self, r: SensorReading) -> bool:
        v = r.value
        st = r.sensor_type
        if st == SensorType.THERMAL_IMAGING and (v < -50.0 or v > 800.0):
            return True
        if st == SensorType.CO2 and (v < 0.0 or v > 100000.0):
            return True
        if st == SensorType.HEART_RATE_RADAR and (v < 0.0 or v > 300.0):
            return True
        if st == SensorType.WATER_LEVEL and (v < 0.0 or v > 5000.0):
            return True
        return False

    def evaluate_channels(
        self,
        readings: List[SensorReading],
        battery_map: Optional[Dict[str, float]] = None,
    ) -> List[SensorHealth]:
        if battery_map is None:
            battery_map = {}
        records: List[SensorHealth] = []
        for r in readings:
            vid = r.victim_id or "SITE"
            batt = battery_map.get(vid, 100.0)
            res = self.evaluate_node_health(vid, batt, [r])
            records.extend(res)
        return records

    def get_summary(self, records: List[SensorHealth]) -> Dict[str, Any]:
        online = sum(1 for r in records if r.status == SensorHealthStatus.ONLINE)
        degraded = sum(1 for r in records if r.status == SensorHealthStatus.DEGRADED)
        offline = sum(1 for r in records if r.status in (SensorHealthStatus.OFFLINE, SensorHealthStatus.ERROR))
        overall = "CRITICAL_FAULTS" if offline > 0 else ("DEGRADED" if degraded > 0 else "OPTIMAL")
        return {
            "online": online,
            "degraded": degraded,
            "offline": offline,
            "total": len(records),
            "overall_status": overall,
        }


# --------------------------------------------------------------------------- #
# 3. Semantic Sensor Evidence Extractor
# --------------------------------------------------------------------------- #
class SensorEvidenceExtractor:
    """
    Transforms multi-sensor streams, time-series trends, and environmental gauges
    into prioritized, semantic evidence tokens for scenario and risk inference.
    Handles sensor conflicts by weighting high-confidence, uncorrupted channels.
    """

    def extract_evidence(
        self,
        readings: List[SensorReading],
        trends: Optional[Any] = None,
        env_report: Optional[Dict[str, Any]] = None,
        trend_map: Optional[Any] = None,
    ) -> List[SensorEvidence]:
        if env_report is None and isinstance(trends, dict):
            env_report = trends
            trends = []
        elif trends is None:
            trends = []
        elif isinstance(trends, dict):
            env_report = trends
            trends = []
        if env_report is None:
            env_report = {}
        evidence_list: List[SensorEvidence] = []
        if trend_map is None:
            trend_map = {t.sensor_type: t for t in trends if hasattr(t, "sensor_type")}
        elif isinstance(trend_map, list):
            trend_map = {t.sensor_type: t for t in trend_map if hasattr(t, "sensor_type")}

        # 1. Thermal & Temperature Evidence
        thermal_readings = [r for r in readings if r.sensor_type == SensorType.THERMAL_IMAGING]
        if thermal_readings:
            max_thermal = max(r.value for r in thermal_readings)
            min_thermal = min(r.value for r in thermal_readings)
            avg_conf = sum(r.confidence for r in thermal_readings) / len(thermal_readings)

            if max_thermal >= 45.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.THERMAL_IMAGING,
                    observed_value=max_thermal,
                    threshold_triggered=">= 45.0 C",
                    evidence_label="EXTREME_THERMAL_SIGNATURE",
                    confidence=round(avg_conf, 2),
                    description="Thermal imaging detected intense elevated temperature consistent with active fire.",
                ))
            elif min_thermal < 15.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.THERMAL_IMAGING,
                    observed_value=min_thermal,
                    threshold_triggered="< 15.0 C",
                    evidence_label="HYPOTHERMIC_THERMAL_SIGNATURE",
                    confidence=round(avg_conf, 2),
                    description="Thermal signature indicates severe sub-normal body temperatures or snow burial.",
                ))

        # 2. Water Level & Surge Evidence
        water_readings = [r for r in readings if r.sensor_type == SensorType.WATER_LEVEL]
        flow_readings = [r for r in readings if r.sensor_type == SensorType.WATER_FLOW]
        if water_readings:
            max_water = max(r.value for r in water_readings)
            water_trend = trend_map.get(SensorType.WATER_LEVEL)
            if max_water >= 50.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.WATER_LEVEL,
                    observed_value=max_water,
                    threshold_triggered=">= 50.0 cm",
                    evidence_label="CRITICAL_FLOOD_SUBMERSION",
                    confidence=0.96,
                    description=f"Water level reached {max_water} cm at victim location.",
                ))
            if water_trend and water_trend.rate_of_change_per_cycle >= 1.5:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.WATER_LEVEL,
                    observed_value=water_trend.rate_of_change_per_cycle,
                    threshold_triggered=">= 1.5 cm/cycle rise",
                    evidence_label="RAPID_SURGE_WATER_RISE",
                    confidence=0.94,
                    description="Water level is surging rapidly, indicating flash flood or dam breach.",
                ))

        if flow_readings:
            max_flow = max(r.value for r in flow_readings)
            if max_flow >= 1.2:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.WATER_FLOW,
                    observed_value=max_flow,
                    threshold_triggered=">= 1.2 m/s",
                    evidence_label="HIGH_VELOCITY_FLOOD_CURRENT",
                    confidence=0.92,
                    description=f"Water flow velocity measured at {max_flow} m/s, hazardous current.",
                ))

        # 3. Gas & Smoke Evidence
        gas_ppm = float(env_report.get("gas_concentration_ppm", 0.0))
        smoke_pct = float(env_report.get("smoke_density_pct", 0.0))
        gas_trend = trend_map.get(SensorType.GAS_CONCENTRATION)
        smoke_trend = trend_map.get(SensorType.SMOKE_DENSITY)

        if gas_ppm >= 40.0:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.GAS_CONCENTRATION,
                observed_value=gas_ppm,
                threshold_triggered=">= 40.0 ppm",
                evidence_label="TOXIC_COMBUSTIBLE_GAS_ALERT",
                confidence=0.95,
                description=f"Atmospheric gas concentration elevated at {gas_ppm} ppm.",
            ))
        if gas_ppm >= 80.0:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.GAS_CONCENTRATION,
                observed_value=gas_ppm,
                threshold_triggered=">= 80.0 ppm",
                evidence_label="CRITICAL_GAS_CONCENTRATION",
                confidence=0.99,
                description=f"Atmospheric gas concentration reached CRITICAL level ({gas_ppm} ppm).",
            ))

        if gas_trend and gas_trend.rate_of_change_per_cycle >= 8.0:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.GAS_CONCENTRATION,
                observed_value=gas_trend.rate_of_change_per_cycle,
                threshold_triggered=">= 8.0 ppm/cycle rise",
                evidence_label="RAPID_GAS_CONCENTRATION_SURGE",
                confidence=0.96,
                description=f"Gas concentration is surging rapidly (+{gas_trend.rate_of_change_per_cycle} ppm/cycle).",
            ))

        if smoke_pct >= 20.0:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.SMOKE_DENSITY,
                observed_value=smoke_pct,
                threshold_triggered=">= 20.0 %",
                evidence_label="DENSE_SMOKE_OBSCURATION",
                confidence=0.95,
                description=f"Optical smoke density at {smoke_pct}%.",
            ))
        if smoke_pct >= 60.0:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.SMOKE_DENSITY,
                observed_value=smoke_pct,
                threshold_triggered=">= 60.0 %",
                evidence_label="CRITICAL_SMOKE_OBSCURATION",
                confidence=0.99,
                description=f"Smoke particulate density reached critical obscuration ({smoke_pct}%).",
            ))

        if smoke_trend and smoke_trend.rate_of_change_per_cycle >= 8.0:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.SMOKE_DENSITY,
                observed_value=smoke_trend.rate_of_change_per_cycle,
                threshold_triggered=">= 8.0 %/cycle rise",
                evidence_label="RAPID_SMOKE_DENSITY_SURGE",
                confidence=0.96,
                description=f"Smoke density is surging rapidly (+{smoke_trend.rate_of_change_per_cycle} %/cycle).",
            ))

        # 4. Barometric Pressure Drop & Weather Front Evidence
        baro_hpa = float(env_report.get("barometric_pressure_hpa", env_report.get("pressure_hpa", 1013.25)))
        baro_trend = trend_map.get(SensorType.BAROMETRIC_PRESSURE)
        baro_status = env_report.get("barometric_status", "ONLINE")

        if baro_status in ("OFFLINE", "ERROR"):
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.BAROMETRIC_PRESSURE,
                observed_value=0.0,
                threshold_triggered="OFFLINE / SENSOR ERROR",
                evidence_label="BAROMETRIC_SENSOR_OFFLINE",
                confidence=0.50,
                description="Barometric pressure probe is OFFLINE; environmental confidence penalty applied.",
            ))
        else:
            if baro_hpa <= PRESSURE_CONFIG.critical_plunge_threshold_hpa:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.BAROMETRIC_PRESSURE,
                    observed_value=baro_hpa,
                    threshold_triggered=f"<= {PRESSURE_CONFIG.critical_plunge_threshold_hpa} hPa",
                    evidence_label="CRITICAL_BAROMETRIC_PRESSURE_PLUNGE",
                    confidence=0.99,
                    description=f"Atmospheric pressure plunged critically to {baro_hpa} hPa (severe cyclonic / storm surge threshold).",
                ))
            if baro_hpa <= PRESSURE_CONFIG.severe_cyclone_threshold_hpa:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.BAROMETRIC_PRESSURE,
                    observed_value=baro_hpa,
                    threshold_triggered=f"<= {PRESSURE_CONFIG.severe_cyclone_threshold_hpa} hPa",
                    evidence_label="SEVERE_BAROMETRIC_PRESSURE_DROP",
                    confidence=0.98,
                    description=f"Atmospheric pressure plunged to {baro_hpa} hPa.",
                ))
            elif baro_hpa <= 1004.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.BAROMETRIC_PRESSURE,
                    observed_value=baro_hpa,
                    threshold_triggered="<= 1004.0 hPa",
                    evidence_label="BAROMETRIC_PRESSURE_FALLING",
                    confidence=0.92,
                    description=f"Barometric pressure is falling ({baro_hpa} hPa), indicating approaching weather front.",
                ))
            else:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.BAROMETRIC_PRESSURE,
                    observed_value=baro_hpa,
                    threshold_triggered="1008 - 1018 hPa",
                    evidence_label="BAROMETRIC_PRESSURE_NORMAL",
                    confidence=0.95,
                    description=f"Atmospheric pressure is nominal ({baro_hpa} hPa).",
                ))

            if baro_trend and baro_trend.rate_of_change_per_cycle <= -PRESSURE_CONFIG.rapid_falling_threshold_hpa_per_cycle:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.BAROMETRIC_PRESSURE,
                    observed_value=baro_trend.rate_of_change_per_cycle,
                    threshold_triggered=f"<= -{PRESSURE_CONFIG.rapid_falling_threshold_hpa_per_cycle} hPa/cycle drop",
                    evidence_label="RAPID_PRESSURE_DROP_DETECTED",
                    confidence=0.96,
                    description=f"Atmospheric pressure is falling rapidly ({baro_trend.rate_of_change_per_cycle} hPa/cycle).",
                ))

            # Correlated weather deterioration (falling pressure + heavy rainfall/wind)
            rain_mm = float(env_report.get("rainfall_mm_hr", 0.0))
            if (baro_hpa <= 1004.0 or (baro_trend and baro_trend.rate_of_change_per_cycle <= -2.0)) and rain_mm >= 15.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.BAROMETRIC_PRESSURE,
                    observed_value=baro_hpa,
                    threshold_triggered="Low Pressure + Heavy Rainfall",
                    evidence_label="PRESSURE_WEATHER_DETERIORATION",
                    confidence=0.97,
                    description=f"Correlated weather deterioration: falling pressure ({baro_hpa} hPa) combined with {rain_mm} mm/hr precipitation.",
                ))

        # 5. Rainfall & Soil Moisture Evidence (Landslide / Cloudburst / Flash Flood)
        rain_mm_hr = float(env_report.get("rainfall_rate_mm_h", env_report.get("rainfall_mm_hr", 0.0)))
        accumulated_rain_mm = float(env_report.get("cumulative_rainfall_mm", env_report.get("accumulated_rain_mm", 0.0)))
        soil_pct = float(env_report.get("soil_moisture_pct", 0.0))
        tilt_deg = float(env_report.get("tilt_deg", 0.0))
        vib_mm_s = float(env_report.get("vibration_mm_s", 0.0))

        if rain_mm_hr >= RAINFALL_CONFIG.extreme_threshold_mm_h:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RAINFALL_INTENSITY,
                observed_value=rain_mm_hr,
                threshold_triggered=f">= {RAINFALL_CONFIG.extreme_threshold_mm_h} mm/hr",
                evidence_label="RAINFALL_EXTREME_CLOUD_BURST_DETECTED",
                confidence=0.99,
                description=f"Extreme cloudburst precipitation detected at {rain_mm_hr:.1f} mm/h.",
            ))
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RAINFALL_INTENSITY,
                observed_value=rain_mm_hr,
                threshold_triggered=">= 25.0 mm/hr",
                evidence_label="TORRENTIAL_PRECIPITATION",
                confidence=0.98,
                description=f"Torrential precipitation rate at {rain_mm_hr:.1f} mm/h.",
            ))
        elif rain_mm_hr >= RAINFALL_CONFIG.heavy_threshold_mm_h:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RAINFALL_INTENSITY,
                observed_value=rain_mm_hr,
                threshold_triggered=f">= {RAINFALL_CONFIG.heavy_threshold_mm_h} mm/hr",
                evidence_label="RAINFALL_VERY_HEAVY_DOWNPOUR",
                confidence=0.98,
                description=f"Very heavy precipitation downpour at {rain_mm_hr:.1f} mm/h.",
            ))
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RAINFALL_INTENSITY,
                observed_value=rain_mm_hr,
                threshold_triggered=">= 25.0 mm/hr",
                evidence_label="TORRENTIAL_PRECIPITATION",
                confidence=0.97,
                description=f"Torrential precipitation rate at {rain_mm_hr:.1f} mm/h.",
            ))
        elif rain_mm_hr >= RAINFALL_CONFIG.moderate_threshold_mm_h:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RAINFALL_INTENSITY,
                observed_value=rain_mm_hr,
                threshold_triggered=f">= {RAINFALL_CONFIG.moderate_threshold_mm_h} mm/hr",
                evidence_label="RAINFALL_HEAVY_PRECIPITATION",
                confidence=0.96,
                description=f"Heavy precipitation detected at {rain_mm_hr:.1f} mm/h.",
            ))
            if rain_mm_hr >= 25.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.RAINFALL_INTENSITY,
                    observed_value=rain_mm_hr,
                    threshold_triggered=">= 25.0 mm/hr",
                    evidence_label="TORRENTIAL_PRECIPITATION",
                    confidence=0.97,
                    description=f"Precipitation rate at {rain_mm_hr:.1f} mm/hr.",
                ))
        elif rain_mm_hr >= RAINFALL_CONFIG.light_threshold_mm_h:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RAINFALL_INTENSITY,
                observed_value=rain_mm_hr,
                threshold_triggered=f">= {RAINFALL_CONFIG.light_threshold_mm_h} mm/hr",
                evidence_label="RAINFALL_MODERATE_PRECIPITATION",
                confidence=0.94,
                description=f"Moderate precipitation at {rain_mm_hr:.1f} mm/h.",
            ))
        elif rain_mm_hr > RAINFALL_CONFIG.no_rain_threshold:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RAINFALL_INTENSITY,
                observed_value=rain_mm_hr,
                threshold_triggered="> 0.0 mm/hr",
                evidence_label="RAINFALL_LIGHT_DRIZZLE",
                confidence=0.92,
                description=f"Light rainfall / drizzle at {rain_mm_hr:.1f} mm/h.",
            ))

        if accumulated_rain_mm >= RAINFALL_CONFIG.critical_accumulation_mm:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RAINFALL_INTENSITY,
                observed_value=accumulated_rain_mm,
                threshold_triggered=f">= {RAINFALL_CONFIG.critical_accumulation_mm} mm",
                evidence_label="RAINFALL_ACCUMULATION_CRITICAL",
                confidence=0.98,
                description=f"Critical cumulative rainfall accumulation reached {accumulated_rain_mm:.1f} mm.",
            ))

        # Compound rainfall + water flood evidence
        water_readings = [r for r in readings if r.sensor_type == SensorType.WATER_LEVEL]
        max_water = max((r.value for r in water_readings), default=0.0)
        if rain_mm_hr >= RAINFALL_CONFIG.flash_flood_trigger_mm_h and max_water >= 40.0:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RAINFALL_INTENSITY,
                observed_value=rain_mm_hr,
                threshold_triggered="Heavy Rain + Rising Flood Water",
                evidence_label="RAINFALL_WATER_COMPOUND_FLASH_FLOOD_TRIGGER",
                confidence=0.98,
                description=f"Compound flash flood threat: {rain_mm_hr:.1f} mm/h precipitation driving {max_water:.1f} cm flood inundation.",
            ))

        # Compound rainfall + soil landslide evidence
        if rain_mm_hr >= RAINFALL_CONFIG.landslide_trigger_mm_h and (soil_pct >= 65.0 or tilt_deg >= 1.5):
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RAINFALL_INTENSITY,
                observed_value=rain_mm_hr,
                threshold_triggered=f">= {RAINFALL_CONFIG.landslide_trigger_mm_h} mm/hr + Saturated Slope",
                evidence_label="RAINFALL_SOIL_COMPOUND_LANDSLIDE_TRIGGER",
                confidence=0.98,
                description=f"Compound landslide hazard: {rain_mm_hr:.1f} mm/h precipitation saturating hillside (moisture {soil_pct:.1f}%, tilt {tilt_deg:.1f}°).",
            ))

        if (soil_pct >= LANDSLIDE_CONFIG.moisture_critical_threshold_pct and tilt_deg >= LANDSLIDE_CONFIG.tilt_high_threshold_deg) or \
           (soil_pct >= LANDSLIDE_CONFIG.moisture_high_threshold_pct and tilt_deg >= LANDSLIDE_CONFIG.tilt_high_threshold_deg and rain_mm_hr >= RAINFALL_CONFIG.landslide_trigger_mm_h) or \
           (tilt_deg >= LANDSLIDE_CONFIG.tilt_critical_threshold_deg and soil_pct >= 65.0):
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.SOIL_MOISTURE,
                observed_value=soil_pct,
                threshold_triggered=f">= {LANDSLIDE_CONFIG.moisture_critical_threshold_pct}% & tilt >= {LANDSLIDE_CONFIG.tilt_high_threshold_deg}°",
                evidence_label="LANDSLIDE_HAZARD_CRITICAL",
                confidence=0.98,
                description=f"Critical landslide risk: Saturated soil ({soil_pct:.1f}%) combined with severe slope shear ({tilt_deg:.1f}°) and precipitation ({rain_mm_hr:.1f} mm/h).",
            ))
        elif (soil_pct >= LANDSLIDE_CONFIG.moisture_high_threshold_pct and tilt_deg >= LANDSLIDE_CONFIG.tilt_elevated_threshold_deg) or \
             (soil_pct >= LANDSLIDE_CONFIG.moisture_elevated_threshold_pct and tilt_deg >= LANDSLIDE_CONFIG.tilt_high_threshold_deg) or \
             (soil_pct >= LANDSLIDE_CONFIG.moisture_elevated_threshold_pct and tilt_deg >= LANDSLIDE_CONFIG.tilt_elevated_threshold_deg and rain_mm_hr >= 20.0):
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.SOIL_MOISTURE,
                observed_value=soil_pct,
                threshold_triggered=f">= {LANDSLIDE_CONFIG.moisture_high_threshold_pct}% & tilt >= {LANDSLIDE_CONFIG.tilt_elevated_threshold_deg}°",
                evidence_label="LANDSLIDE_EARLY_WARNING",
                confidence=0.95,
                description=f"Early landslide hazard: Elevated moisture ({soil_pct:.1f}%) with active slope tilt ({tilt_deg:.1f}°).",
            ))
        elif soil_pct >= LANDSLIDE_CONFIG.moisture_elevated_threshold_pct:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.SOIL_MOISTURE,
                observed_value=soil_pct,
                threshold_triggered=f">= {LANDSLIDE_CONFIG.moisture_elevated_threshold_pct}%",
                evidence_label="SOIL_SATURATION_INSTABILITY",
                confidence=0.95,
                description=f"Slope soil saturation reached {soil_pct:.1f}%, elevated landslide watch.",
            ))

        # 6. IMU Vibration & Tilt Evidence (Earthquake / Building Collapse / Slope Instability)
        if vib_mm_s >= 2.0 or env_report.get("aftershock_active", False):
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.IMU_VIBRATION,
                observed_value=vib_mm_s,
                threshold_triggered=">= 2.0 mm/s or aftershock",
                evidence_label="SEISMIC_TREMOR_DETECTED",
                confidence=0.96,
                description=f"Ground vibration at {vib_mm_s} mm/s with active tremors.",
            ))

        if tilt_deg >= 3.0:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.IMU_TILT,
                observed_value=tilt_deg,
                threshold_triggered=">= 3.0 deg",
                evidence_label="STRUCTURAL_TILT_DEVIATION",
                confidence=0.95,
                description=f"Inclinometer tilt shifted to {tilt_deg} degrees.",
            ))

        # 7. Vital Signs & Radar / PIR Presence
        radar_readings = [r for r in readings if r.sensor_type == SensorType.HEART_RATE_RADAR]
        pir_readings = [r for r in readings if r.sensor_type == SensorType.PIR_MOTION]
        acoustic_readings = [r for r in readings if r.sensor_type == SensorType.ACOUSTIC]

        active_vitals = [r for r in radar_readings if r.value > 20.0]
        if active_vitals:
            avg_bpm = sum(r.value for r in active_vitals) / len(active_vitals)
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.HEART_RATE_RADAR,
                observed_value=round(avg_bpm, 1),
                threshold_triggered="> 20.0 bpm",
                evidence_label="SURVIVOR_VITALS_CONFIRMED",
                confidence=0.96,
                description=f"Doppler radar confirmed human vital signs (avg {round(avg_bpm, 1)} BPM).",
            ))

        active_motion = [r for r in pir_readings if r.value > 0.15]
        if active_motion:
            max_mot = max(r.value for r in active_motion)
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.PIR_MOTION,
                observed_value=round(max_mot, 2),
                threshold_triggered="> 0.15 index",
                evidence_label="MOTION_ACTIVITY_DETECTED",
                confidence=0.90,
                description=f"PIR motion sensor recorded activity (index {round(max_mot, 2)}).",
            ))

        acoustic_taps = [r for r in acoustic_readings if r.value >= 25.0]
        if acoustic_taps:
            max_db = max(r.value for r in acoustic_taps)
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.ACOUSTIC,
                observed_value=round(max_db, 1),
                threshold_triggered=">= 25.0 dB",
                evidence_label="ACOUSTIC_DISTRESS_SIGNALS",
                confidence=0.88,
                description=f"Acoustic microphones detected tapping/vocal distress at {round(max_db, 1)} dB.",
            ))

        # 8. Optical & Thermal Camera Evidence
        cam_readings = [r for r in readings if r.sensor_type == SensorType.RGB_CAMERA]
        thm_readings = [r for r in readings if r.sensor_type == SensorType.THERMAL_IMAGING]

        # Check for animal detection in camera or thermal metadata
        is_animal_cam = False
        is_animal_thm = False
        for r in cam_readings:
            raw = getattr(r, "raw_data", {}) or {}
            if "ANIMAL" in str(raw.get("classification", "")).upper():
                is_animal_cam = True
        for r in thm_readings:
            raw = getattr(r, "raw_data", {}) or {}
            if "ANIMAL" in str(raw.get("detection_type", "")).upper() or "ANIMAL" in str(raw.get("classification", "")).upper():
                is_animal_thm = True

        if is_animal_cam or is_animal_thm:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RGB_CAMERA if is_animal_cam else SensorType.THERMAL_IMAGING,
                observed_value=0.0,
                threshold_triggered="Animal Classification Signature",
                evidence_label="ANIMAL_ACTIVITY_DETECTED",
                confidence=0.95,
                description="Animal signature detected (non-human movement/heat); filtered out from human survivor detection.",
            ))

        active_cam_humans = [r for r in cam_readings if r.value >= 0.50 and not is_animal_cam]
        if active_cam_humans:
            max_c_conf = max(r.value for r in active_cam_humans)
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RGB_CAMERA,
                observed_value=round(max_c_conf, 2),
                threshold_triggered=">= 0.50 conf",
                evidence_label="CAMERA_HUMAN_CONFIRMED",
                confidence=0.92,
                description=f"Optical camera detected visual human presence ({int(max_c_conf * 100)}% confidence).",
            ))

        active_thm_humans = [r for r in thm_readings if (r.value >= 28.0 and r.value <= 42.0) and not is_animal_thm]
        if active_thm_humans:
            max_t = max(r.value for r in active_thm_humans)
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.THERMAL_IMAGING,
                observed_value=round(max_t, 1),
                threshold_triggered="28.0 - 42.0 C",
                evidence_label="THERMAL_HUMAN_HEAT_CONFIRMED",
                confidence=0.94,
                description=f"Thermal infrared camera confirmed human body heat signature ({round(max_t, 1)} °C).",
            ))

        # Cross-modal Quad-sensor & Synergy correlation
        if active_cam_humans and active_thm_humans and active_vitals and active_motion:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RGB_CAMERA,
                observed_value=1.0,
                threshold_triggered="Quad-Modality Corroboration (Camera + Thermal + Radar + PIR)",
                evidence_label="QUAD_SENSOR_CORROBORATION_CONFIRMED",
                confidence=0.99,
                description="Quad-sensor multi-modal corroboration: Optical human, Thermal body heat, Radar pulse, and PIR movement all active with very high confidence.",
            ))
        elif active_cam_humans and active_thm_humans:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RGB_CAMERA,
                observed_value=0.95,
                threshold_triggered="Optical Human + Thermal Heat Corroboration",
                evidence_label="STRONG_SURVIVOR_CORROBORATION",
                confidence=0.96,
                description="Cross-modal synergy confirmed: Optical camera visual identification corroborated by Long-Wave Infrared thermal heat.",
            ))
        elif active_cam_humans and thm_readings and all(r.value < 15.0 for r in thm_readings):
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.RGB_CAMERA,
                observed_value=0.50,
                threshold_triggered="Optical Detection without Thermal Heat",
                evidence_label="CAMERA_THERMAL_FALSE_POSITIVE_WARNING",
                confidence=0.75,
                description="Potential false positive warning: Visual camera detected human candidate but thermal sensor detected no body heat.",
            ))

        # 9. Hazardous Area + Survivor Correlation
        if (gas_ppm >= 40.0 or smoke_pct >= 30.0) and (active_vitals or active_motion or acoustic_taps or active_cam_humans or active_thm_humans):
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.GAS_CONCENTRATION,
                observed_value=max(gas_ppm, smoke_pct),
                threshold_triggered="Gas/Smoke Elevated + Human Presence Detected",
                evidence_label="HAZARDOUS_AREA_SURVIVOR_DETECTED",
                confidence=0.98,
                description="Human survivor presence detected inside hazardous gas/smoke environment. Urgent life-safety rescue required.",
            ))

        # 10. Ambient Temperature Evidence
        temp_readings = [r for r in readings if r.sensor_type == SensorType.TEMPERATURE]
        if temp_readings:
            temp_c = max(r.value for r in temp_readings)
            temp_status = temp_readings[0].status
        else:
            temp_c = float(env_report.get("temperature_c", env_report.get("ambient_temp_c", 15.0)))
            temp_status = env_report.get("temperature_status", "ONLINE")

        temp_trend = trend_map.get(SensorType.TEMPERATURE)

        if temp_status in ("OFFLINE", "ERROR", SensorHealthStatus.OFFLINE):
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.TEMPERATURE,
                observed_value=0.0,
                threshold_triggered="OFFLINE / SENSOR ERROR",
                evidence_label="TEMPERATURE_SENSOR_OFFLINE",
                confidence=0.50,
                description="Ambient temperature sensor is OFFLINE; environmental thermal monitoring discounted.",
            ))
        else:
            if temp_c >= 50.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.TEMPERATURE,
                    observed_value=temp_c,
                    threshold_triggered=">= 50.0 °C",
                    evidence_label="FIRE_ENVIRONMENTAL_TEMPERATURE",
                    confidence=0.99,
                    description=f"Extreme ambient temperature ({temp_c:.1f} °C) detected, indicative of immediate fire proximity.",
                ))
            if temp_c >= 45.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.TEMPERATURE,
                    observed_value=temp_c,
                    threshold_triggered=">= 45.0 °C",
                    evidence_label="EXTREME_HEATWAVE_TEMPERATURE",
                    confidence=0.99,
                    description=f"Critical extreme heatwave temperature reached ({temp_c:.1f} °C). Life-threatening heat stress.",
                ))
            elif temp_c >= 40.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.TEMPERATURE,
                    observed_value=temp_c,
                    threshold_triggered=">= 40.0 °C",
                    evidence_label="HIGH_AMBIENT_TEMPERATURE",
                    confidence=0.95,
                    description=f"High ambient temperature ({temp_c:.1f} °C) indicating severe heatwave / thermal stress.",
                ))
            elif temp_c <= -10.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.TEMPERATURE,
                    observed_value=temp_c,
                    threshold_triggered="<= -10.0 °C",
                    evidence_label="HYPOTHERMIC_AMBIENT_TEMPERATURE",
                    confidence=0.98,
                    description=f"Severe sub-zero ambient temperature ({temp_c:.1f} °C) posing imminent hypothermia risk.",
                ))
            elif temp_c <= 0.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.TEMPERATURE,
                    observed_value=temp_c,
                    threshold_triggered="<= 0.0 °C",
                    evidence_label="FREEZING_AMBIENT_TEMPERATURE",
                    confidence=0.96,
                    description=f"Freezing ambient air temperature ({temp_c:.1f} °C) detected.",
                ))

            if temp_trend and (getattr(temp_trend, "rate_of_change_per_cycle", 0.0) >= 2.5 or getattr(temp_trend, "trend", "") in ("RAPIDLY_RISING",)):
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.TEMPERATURE,
                    observed_value=getattr(temp_trend, "rate_of_change_per_cycle", 0.0),
                    threshold_triggered=">= 2.5 °C/cycle rise",
                    evidence_label="RAPID_TEMPERATURE_RISE",
                    confidence=0.95,
                    description=f"Ambient temperature is rising rapidly (+{getattr(temp_trend, 'rate_of_change_per_cycle', 0.0):.1f} °C/cycle).",
                ))

        # 11. Relative Atmospheric Humidity Evidence
        humid_readings = [r for r in readings if r.sensor_type == SensorType.HUMIDITY]
        if humid_readings:
            humidity_pct = max(r.value for r in humid_readings)
            humid_status = humid_readings[0].status
        else:
            humidity_pct = float(env_report.get("humidity_pct", 50.0))
            humid_status = env_report.get("humidity_status", "ONLINE")

        humid_trend = trend_map.get(SensorType.HUMIDITY)

        if humid_status in ("OFFLINE", "ERROR", SensorHealthStatus.OFFLINE):
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.HUMIDITY,
                observed_value=0.0,
                threshold_triggered="OFFLINE / SENSOR ERROR",
                evidence_label="HUMIDITY_SENSOR_OFFLINE",
                confidence=0.50,
                description="Atmospheric humidity sensor is OFFLINE; humidity corroboration discounted.",
            ))
        else:
            if humidity_pct >= 90.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.HUMIDITY,
                    observed_value=humidity_pct,
                    threshold_triggered=">= 90.0 %",
                    evidence_label="SATURATED_ATMOSPHERIC_HUMIDITY",
                    confidence=0.98,
                    description=f"Near-saturated atmospheric moisture ({humidity_pct:.1f}%) indicating torrential storm/flood environment.",
                ))
            elif humidity_pct >= 80.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.HUMIDITY,
                    observed_value=humidity_pct,
                    threshold_triggered=">= 80.0 %",
                    evidence_label="HIGH_ATMOSPHERIC_HUMIDITY",
                    confidence=0.95,
                    description=f"High atmospheric humidity ({humidity_pct:.1f}%) supporting active precipitation / cyclone.",
                ))
            elif humidity_pct <= 25.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.HUMIDITY,
                    observed_value=humidity_pct,
                    threshold_triggered="<= 25.0 %",
                    evidence_label="ARID_DRY_ATMOSPHERE",
                    confidence=0.94,
                    description=f"Very dry, arid atmospheric humidity ({humidity_pct:.1f}%) amplifying wildfire vulnerability.",
                ))

            # Compound Heat + Humidity
            if temp_c >= 35.0 and humidity_pct >= 70.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.HUMIDITY,
                    observed_value=humidity_pct,
                    threshold_triggered="Temp >= 35.0 C AND Humidity >= 70.0 %",
                    evidence_label="COMPOUND_HEAT_HUMIDITY_HAZARD",
                    confidence=0.97,
                    description=f"Extreme compound heat-humidity hazard ({temp_c:.1f}°C, {humidity_pct:.1f}% RH): severe wet-bulb heatstroke risk.",
                ))

            # Compound Rain + Humidity
            if humidity_pct >= 85.0 and rain_mm_hr >= 25.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.HUMIDITY,
                    observed_value=humidity_pct,
                    threshold_triggered="Humidity >= 85.0 % AND Rainfall >= 25.0 mm/h",
                    evidence_label="COMPOUND_HUMIDITY_RAINFALL_FLOOD_TRIGGER",
                    confidence=0.98,
                    description="Coupled saturated air and torrential downpour confirming active flash flood / cloudburst conditions.",
                ))

        # 12. GPS Positioning & Kinematics Evidence
        gps_readings = [r for r in readings if r.sensor_type == SensorType.GPS]
        if gps_readings:
            gps_r = gps_readings[0]
            gps_status = gps_r.status
            raw = gps_r.raw_data or {}
            sats = int(raw.get("satellites", gps_r.value if gps_r.value else 12))
            acc = float(raw.get("accuracy_m", 2.5))
            spd = float(raw.get("speed_mps", 0.0))
            mov_state = raw.get("movement_state", "STATIONARY")
            if hasattr(mov_state, "value"):
                mov_state = mov_state.value
        else:
            gps_status = env_report.get("gps_status", "ONLINE")
            sats = int(env_report.get("satellites", 12))
            acc = float(env_report.get("accuracy_m", 2.5))
            spd = float(env_report.get("speed_mps", 0.0))
            mov_state = env_report.get("movement_state", "STATIONARY")

        if gps_status in ("OFFLINE", "ERROR", SensorHealthStatus.OFFLINE) or sats == 0 or mov_state == "SIGNAL_LOSS":
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.GPS,
                observed_value=0.0,
                threshold_triggered="0 satellites / OFFLINE",
                evidence_label="GPS_SIGNAL_OFFLINE",
                confidence=0.98,
                description="GPS satellite fix lost / receiver offline; spatial tracking unavailable, relying on dead reckoning / last known coordinates.",
            ))
        elif gps_status == "DEGRADED" or acc > 15.0 or sats < 4:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.GPS,
                observed_value=acc,
                threshold_triggered="Accuracy > 15.0m or Sats < 4",
                evidence_label="GPS_SIGNAL_DEGRADED",
                confidence=0.92,
                description=f"Degraded GNSS positioning geometry ({sats} satellites, ±{acc:.1f}m accuracy); spatial margin enlarged.",
            ))
        else:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.GPS,
                observed_value=acc,
                threshold_triggered="Accuracy <= 5.0m and Sats >= 4",
                evidence_label="GPS_SIGNAL_AVAILABLE",
                confidence=0.99,
                description=f"High-precision 3D GNSS fix acquired ({sats} satellites lock, ±{acc:.1f}m accuracy).",
            ))

        if mov_state == "JUMP_ANOMALY":
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.GPS,
                observed_value=spd,
                threshold_triggered="Kinematic Jump Anomaly / Impossible Displacement",
                evidence_label="GPS_MOVEMENT_ANOMALY",
                confidence=0.95,
                description="GPS telemetry anomaly detected: impossible kinematic position jump (>1km/cycle or >50 m/s). Possible multipath/spoofing.",
            ))
        elif mov_state == "RAPID_MOVEMENT" or spd >= 10.0:
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.GPS,
                observed_value=spd,
                threshold_triggered="Speed >= 10.0 m/s",
                evidence_label="GPS_RAPID_DEVICE_MOVEMENT",
                confidence=0.94,
                description=f"Rapid responder transit / aerial drone reconnaissance underway ({spd:.1f} m/s).",
            ))

        # 13. Water-Level & Flow Evidence (Flood / Flash Flood / Dam Break / Tsunami / Storm Surge)
        water_readings = [r for r in readings if r.sensor_type == SensorType.WATER_LEVEL]
        flow_readings = [r for r in readings if r.sensor_type == SensorType.WATER_FLOW]

        if water_readings:
            water_lvl = max(r.value for r in water_readings)
            water_status = water_readings[0].status
        else:
            water_lvl = float(env_report.get("water_level_cm", 0.0))
            water_status = env_report.get("water_level_status", "ONLINE")

        if flow_readings:
            water_flow = max(r.value for r in flow_readings)
        else:
            water_flow = float(env_report.get("water_flow_mps", 0.0))

        water_trend = trend_map.get(SensorType.WATER_LEVEL)
        water_rate = getattr(water_trend, "rate_of_change_per_cycle", 0.0) if water_trend else 0.0
        water_dir = getattr(water_trend, "trend_direction", "STABLE") if water_trend else "STABLE"

        if water_status in ("OFFLINE", "ERROR", SensorHealthStatus.OFFLINE):
            evidence_list.append(SensorEvidence(
                sensor_type=SensorType.WATER_LEVEL,
                observed_value=0.0,
                threshold_triggered="OFFLINE / SENSOR ERROR",
                evidence_label="WATER_LEVEL_SENSOR_OFFLINE",
                confidence=0.50,
                description="Water-level hydrostatic probe is OFFLINE; flood depth metrics discounted.",
            ))
        else:
            # Water level depth thresholds
            if water_lvl >= WATER_LEVEL_CONFIG.critical_threshold_cm:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.WATER_LEVEL,
                    observed_value=water_lvl,
                    threshold_triggered=f">= {WATER_LEVEL_CONFIG.critical_threshold_cm} cm",
                    evidence_label="CRITICAL_FLOOD_SUBMERSION",
                    confidence=0.99,
                    description=f"Critical flood inundation depth ({water_lvl:.1f} cm) posing extreme life-safety threat.",
                ))
            elif water_lvl >= WATER_LEVEL_CONFIG.high_threshold_cm:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.WATER_LEVEL,
                    observed_value=water_lvl,
                    threshold_triggered=f">= {WATER_LEVEL_CONFIG.high_threshold_cm} cm",
                    evidence_label="HIGH_WATER_LEVEL",
                    confidence=0.96,
                    description=f"High water level ({water_lvl:.1f} cm) confirming active flood inundation.",
                ))
            elif water_lvl >= WATER_LEVEL_CONFIG.warning_threshold_cm:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.WATER_LEVEL,
                    observed_value=water_lvl,
                    threshold_triggered=f">= {WATER_LEVEL_CONFIG.warning_threshold_cm} cm",
                    evidence_label="WATER_LEVEL_WARNING",
                    confidence=0.92,
                    description=f"Elevated water level ({water_lvl:.1f} cm) exceeding baseline safety threshold.",
                ))

            # Water flow velocity threshold
            if water_flow >= WATER_LEVEL_CONFIG.high_flow_velocity_threshold_mps:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.WATER_FLOW,
                    observed_value=water_flow,
                    threshold_triggered=f">= {WATER_LEVEL_CONFIG.high_flow_velocity_threshold_mps} m/s",
                    evidence_label="HIGH_VELOCITY_FLOOD_CURRENT",
                    confidence=0.95,
                    description=f"Dangerous fast-moving flood current velocity ({water_flow:.1f} m/s).",
                ))

            # Rate of rise & trend evidence
            if water_rate >= WATER_LEVEL_CONFIG.dam_break_rising_rate_cm_per_cycle and water_lvl >= 60.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.WATER_LEVEL,
                    observed_value=water_rate,
                    threshold_triggered=f">= {WATER_LEVEL_CONFIG.dam_break_rising_rate_cm_per_cycle} cm/cycle",
                    evidence_label="DAM_BREAK_WATER_SURGE",
                    confidence=0.99,
                    description=f"Catastrophic water surge rate (+{water_rate:.1f} cm/cycle) indicative of structural dam breach / impoundment failure.",
                ))
            elif water_rate >= WATER_LEVEL_CONFIG.tsunami_rising_rate_cm_per_cycle or (water_rate >= 20.0 and water_flow >= 3.0):
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.WATER_LEVEL,
                    observed_value=water_rate,
                    threshold_triggered="Extreme Surge Rate + High Velocity Current",
                    evidence_label="TSUNAMI_WATER_ANOMALY",
                    confidence=0.98,
                    description=f"Massive oceanic/riverine wave surge (+{water_rate:.1f} cm/cycle at {water_flow:.1f} m/s) consistent with tsunami/surge waveform.",
                ))
            elif water_rate >= WATER_LEVEL_CONFIG.rapid_rising_rate_cm_per_cycle or water_dir == "RAPIDLY_RISING":
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.WATER_LEVEL,
                    observed_value=water_rate,
                    threshold_triggered=f">= {WATER_LEVEL_CONFIG.rapid_rising_rate_cm_per_cycle} cm/cycle or RAPIDLY_RISING",
                    evidence_label="RAPID_SURGE_WATER_RISE",
                    confidence=0.96,
                    description=f"Rapid rate of water rise (+{water_rate:.1f} cm/cycle) confirming rapid inundation surge.",
                ))

            # Compound Flash Flood Evidence: Rapid rise / high water + heavy rain
            if (water_lvl >= 40.0 or water_rate >= 8.0) and rain_mm_hr >= 25.0:
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.WATER_LEVEL,
                    observed_value=water_lvl,
                    threshold_triggered="Rising Water >= 40cm + Rain >= 25 mm/h",
                    evidence_label="FLASH_FLOOD_RISK",
                    confidence=0.98,
                    description=f"Intense precipitation ({rain_mm_hr:.1f} mm/h) coupled with rising water ({water_lvl:.1f} cm) confirms active flash flood.",
                ))

            # Storm Surge Evidence: Low barometric pressure + rising water
            if baro_hpa <= 995.0 and (water_lvl >= 30.0 or water_rate >= 5.0):
                evidence_list.append(SensorEvidence(
                    sensor_type=SensorType.WATER_LEVEL,
                    observed_value=water_lvl,
                    threshold_triggered="Barometric Drop <= 995 hPa + Water Rise",
                    evidence_label="STORM_SURGE_WATER_RISK",
                    confidence=0.96,
                    description=f"Cyclonic low pressure ({baro_hpa:.1f} hPa) driving coastal/estuarine storm surge ({water_lvl:.1f} cm).",
                ))

        return evidence_list


# --------------------------------------------------------------------------- #
# 4. Disaster Scenario Inference Engine (19 Master Scenarios)
# --------------------------------------------------------------------------- #
class DisasterScenarioInferenceEngine:
    """
    Evaluates evidence against all 19 Disaster Scenarios in the master catalog.
    Computes confidence score (0-100%), overall risk level, survivor status,
    and recommended tactical rescue response.
    """

    def infer_scenarios(
        self,
        evidence: List[SensorEvidence],
        env_report: Dict[str, Any],
        active_scenario_hint: Optional[str] = None,
    ) -> List[ScenarioInferenceResult]:
        evidence_labels = {e.evidence_label for e in evidence}
        results: List[ScenarioInferenceResult] = []

        for scenario in DISASTER_SCENARIOS:
            s_id = scenario["id"]
            s_name = scenario["name"]
            score, risk, primary_ev, action = self._evaluate_single_scenario(
                s_id, evidence_labels, env_report, active_scenario_hint
            )
            results.append(
                ScenarioInferenceResult(
                    scenario_id=s_id,
                    scenario_name=s_name,
                    confidence_pct=round(score, 1),
                    risk_level=risk,
                    primary_evidence=primary_ev,
                    secondary_hazards=self._get_cascading_candidates(s_id),
                    recommended_action=action,
                )
            )

        # Sort by confidence descending
        results.sort(key=lambda r: r.confidence_pct, reverse=True)
        return results

    def infer_scenario(
        self,
        evidence: List[SensorEvidence],
        readings: Optional[List[SensorReading]] = None,
        env_report: Optional[Dict[str, Any]] = None,
        active_scenario_hint: Optional[str] = None,
    ) -> DisasterAssessment:
        if env_report is None:
            env_report = {}
        all_results = self.infer_scenarios(evidence, env_report, active_scenario_hint)
        primary = all_results[0] if all_results else None
        secondaries = all_results[1:4] if len(all_results) > 1 else []
        ev_labels = {e.evidence_label for e in evidence}
        overall_risk = primary.risk_level if primary else RiskLevel.LOW
        if "HAZARDOUS_AREA_SURVIVOR_DETECTED" in ev_labels:
            overall_risk = RiskLevel.CRITICAL

        return DisasterAssessment(
            primary_scenario=primary,
            secondary_scenarios=secondaries,
            overall_risk=overall_risk,
            confidence_pct=primary.confidence_pct if primary else 0.0,
            active_evidence=evidence,
            recommended_action=primary.recommended_action if primary else "",
        )

    def _evaluate_single_scenario(
        self,
        scenario_id: str,
        ev_labels: set[str],
        env_report: Dict[str, Any],
        hint: Optional[str] = None,
    ) -> Tuple[float, RiskLevel, List[str], str]:
        score = 15.0  # baseline prior
        matched_ev: List[str] = []
        risk = RiskLevel.LOW
        action = "Maintain continuous perimeter monitoring."

        rain = float(env_report.get("rainfall_mm_hr", 0.0))
        soil = float(env_report.get("soil_moisture_pct", 0.0))
        vib = float(env_report.get("vibration_mm_s", 0.0))
        tilt = float(env_report.get("tilt_deg", 0.0))
        gas = float(env_report.get("gas_concentration_ppm", 0.0))
        smoke = float(env_report.get("smoke_density_pct", 0.0))
        baro = float(env_report.get("barometric_pressure_hpa", 1013.25))
        temp = float(env_report.get("ambient_temp_c", 20.0))

        # Check hint affinity
        if hint and (hint == scenario_id or hint.startswith(scenario_id)):
            score += 25.0

        if scenario_id == "earthquake":
            if "SEISMIC_TREMOR_DETECTED" in ev_labels or vib >= 2.0:
                score += 40.0
                matched_ev.append("High-amplitude ground vibration / aftershocks")
            if "STRUCTURAL_TILT_DEVIATION" in ev_labels or tilt >= 2.0:
                score += 25.0
                matched_ev.append("Ground / building tilt deviation")
            if "ACOUSTIC_DISTRESS_SIGNALS" in ev_labels or "SURVIVOR_VITALS_CONFIRMED" in ev_labels:
                score += 15.0
                matched_ev.append("Acoustic/Radar trapped survivor vitals")
            action = "Deploy Urban Search & Rescue (USAR), acoustic void probes, and heavy extrication equipment."

        elif scenario_id == "flood":
            if "CRITICAL_FLOOD_SUBMERSION" in ev_labels:
                score += 45.0
                matched_ev.append("Significant standing flood water level")
            if "RAPID_SURGE_WATER_RISE" in ev_labels or rain >= 15.0:
                score += 30.0
                matched_ev.append("Torrential rainfall driving water rise")
            if "HIGH_VELOCITY_FLOOD_CURRENT" in ev_labels:
                score += 15.0
                matched_ev.append("Swift water current")
            if "COMPOUND_HUMIDITY_RAINFALL_FLOOD_TRIGGER" in ev_labels or "SATURATED_ATMOSPHERIC_HUMIDITY" in ev_labels:
                score += 15.0
                matched_ev.append("Saturated atmospheric humidity corroborating flood environment")
            action = "Deploy swift-water rescue teams, motorized inflatable rescue boats, and high-ground staging."

        elif scenario_id == "cyclone":
            if "SEVERE_BAROMETRIC_PRESSURE_DROP" in ev_labels or baro <= 990.0:
                score += 50.0
                matched_ev.append("Steep barometric pressure plunge")
            if "TORRENTIAL_PRECIPITATION" in ev_labels or rain >= 30.0:
                score += 30.0
                matched_ev.append("Extreme precipitation rate")
            if "HIGH_ATMOSPHERIC_HUMIDITY" in ev_labels or "SATURATED_ATMOSPHERIC_HUMIDITY" in ev_labels:
                score += 15.0
                matched_ev.append("High atmospheric humidity supporting storm front")
            action = "Activate storm surge defenses, order mandatory coastal evacuation, and secure high-wind shelters."

        elif scenario_id == "landslide":
            if "LANDSLIDE_HAZARD_CRITICAL" in ev_labels or (soil >= 78.0 and tilt >= 3.5):
                score += 65.0
                matched_ev.append("Critical slope saturation and active ground shear")
            elif "LANDSLIDE_EARLY_WARNING" in ev_labels or (soil >= 65.0 and tilt >= 1.5):
                score += 45.0
                matched_ev.append("Early slope instability warning")
            elif "SOIL_SATURATION_INSTABILITY" in ev_labels or soil >= 60.0:
                score += 30.0
                matched_ev.append("Elevated slope soil saturation")
            if "STRUCTURAL_TILT_DEVIATION" in ev_labels or tilt >= 2.5:
                score += 20.0
                matched_ev.append("Inclinometer ground shift detected")
            if rain >= 20.0:
                score += 15.0
                matched_ev.append("Sustained rainfall saturating hillside")
            action = "Deploy geotechnical radar, establish slope hazard perimeter, and evacuate base-of-slope populated zones."

        elif scenario_id == "building_collapse":
            if "STRUCTURAL_TILT_DEVIATION" in ev_labels or tilt >= 4.0:
                score += 40.0
                matched_ev.append("Severe structural lean / tilt")
            if "ACOUSTIC_DISTRESS_SIGNALS" in ev_labels:
                score += 30.0
                matched_ev.append("Tapping / acoustic cries in rubble voids")
            if "SURVIVOR_VITALS_CONFIRMED" in ev_labels:
                score += 15.0
                matched_ev.append("Radar vitals in confined spaces")
            action = "Deploy canine search teams, structural shoring teams, and fiber-optic search cameras."

        elif scenario_id == "urban_fire":
            if "EXTREME_THERMAL_SIGNATURE" in ev_labels or "FIRE_ENVIRONMENTAL_TEMPERATURE" in ev_labels or temp >= 45.0:
                score += 45.0
                matched_ev.append("High ambient thermal radiation / fire heat")
            if "DENSE_SMOKE_OBSCURATION" in ev_labels or "CRITICAL_SMOKE_OBSCURATION" in ev_labels or smoke >= 20.0:
                score += 30.0
                matched_ev.append("Dense particulate smoke obscuration")
            if "TOXIC_COMBUSTIBLE_GAS_ALERT" in ev_labels or gas >= 30.0:
                score += 15.0
                matched_ev.append("Combustion gas byproducts detected")
            if "RAPID_TEMPERATURE_RISE" in ev_labels:
                score += 15.0
                matched_ev.append("Rapidly spiking ambient temperature")
            if temp < 35.0 and smoke < 15.0:
                # Gas alone without heat or smoke is not fire
                score = min(score, 15.0)
            action = "Deploy fire suppression units, establish water relays, and deploy positive-pressure ventilation."

        elif scenario_id == "wildfire":
            if "EXTREME_THERMAL_SIGNATURE" in ev_labels or "FIRE_ENVIRONMENTAL_TEMPERATURE" in ev_labels or temp >= 40.0:
                score += 40.0
                matched_ev.append("Intense vegetation heat signature")
            if "DENSE_SMOKE_OBSCURATION" in ev_labels or "CRITICAL_SMOKE_OBSCURATION" in ev_labels or smoke >= 25.0:
                score += 35.0
                matched_ev.append("Widespread smoke plume")
            if "ARID_DRY_ATMOSPHERE" in ev_labels or (soil <= 40.0 and rain <= 5.0):
                score += 15.0
                matched_ev.append("Arid dry atmospheric / soil conditions")
            action = "Establish containment perimeter, deploy aerial water drops, and initiate wilderness evacuation."

        elif scenario_id == "chemical_leak":
            if "CRITICAL_GAS_CONCENTRATION" in ev_labels or gas >= 70.0:
                score += 65.0
                matched_ev.append("Critical atmospheric toxic gas concentration")
            elif "TOXIC_COMBUSTIBLE_GAS_ALERT" in ev_labels or gas >= 35.0:
                score += 50.0
                matched_ev.append("Elevated toxic gas concentration")
            if "RAPID_GAS_CONCENTRATION_SURGE" in ev_labels:
                score += 20.0
                matched_ev.append("Rapidly surging gas concentration")
            if temp <= 38.0 and smoke <= 20.0:
                score += 15.0
                matched_ev.append("Low smoke and ambient temperature confirm chemical leak rather than fire")
            action = "Establish HazMat hot zone perimeter, deploy self-contained breathing apparatus (SCBA) crews."

        elif scenario_id == "industrial_accident":
            if ("TOXIC_COMBUSTIBLE_GAS_ALERT" in ev_labels or "CRITICAL_GAS_CONCENTRATION" in ev_labels or gas >= 35.0):
                score += 40.0
                matched_ev.append("Industrial chemical/gas surge detected")
            if ("DENSE_SMOKE_OBSCURATION" in ev_labels or smoke >= 20.0 or "EXTREME_THERMAL_SIGNATURE" in ev_labels or temp >= 35.0):
                score += 35.0
                matched_ev.append("Industrial smoke/thermal footprint detected")
            if "RAPID_GAS_CONCENTRATION_SURGE" in ev_labels:
                score += 15.0
                matched_ev.append("Sudden industrial gas spike")
            action = "Isolate industrial plant valves, deploy foam suppression, and search factory floor."

        elif scenario_id == "avalanche":
            if "HYPOTHERMIC_THERMAL_SIGNATURE" in ev_labels or "FREEZING_AMBIENT_TEMPERATURE" in ev_labels or "HYPOTHERMIC_AMBIENT_TEMPERATURE" in ev_labels or temp <= 0.0:
                score += 45.0
                matched_ev.append("Sub-freezing ambient temperature and cold signatures")
            if "SURVIVOR_VITALS_CONFIRMED" in ev_labels:
                score += 25.0
                matched_ev.append("Faint subsurface radar vitals under snowpack")
            action = "Deploy avalanche transceivers, probe search lines, and thermal re-warming medical teams."

        elif scenario_id == "tsunami":
            if "CRITICAL_FLOOD_SUBMERSION" in ev_labels and "HIGH_VELOCITY_FLOOD_CURRENT" in ev_labels:
                score += 55.0
                matched_ev.append("Violent sea surge current and deep water")
            action = "Evacuate all coastal sectors to elevation >= 30m immediately; deploy offshore rescue boats."

        elif scenario_id == "dam_failure":
            if "RAPID_SURGE_WATER_RISE" in ev_labels and "HIGH_VELOCITY_FLOOD_CURRENT" in ev_labels:
                score += 65.0
                matched_ev.append("Catastrophic water surge rate and extreme current")
            action = "Sound emergency valley sirens, clear downstream floodway, and deploy rapid boat evacuation."

        elif scenario_id == "cloudburst":
            if "TORRENTIAL_PRECIPITATION" in ev_labels and rain >= 40.0:
                score += 65.0
                matched_ev.append("Extreme precipitation rate (cloudburst threshold)")
            if "SATURATED_ATMOSPHERIC_HUMIDITY" in ev_labels or "COMPOUND_HUMIDITY_RAINFALL_FLOOD_TRIGGER" in ev_labels:
                score += 15.0
                matched_ev.append("Saturated atmospheric humidity corroborating cloudburst")
            action = "Alert hillside communities, clear stormwater catchments, and rescue flash torrent victims."

        elif scenario_id in ("heatwave", "extreme_heat"):
            if "EXTREME_HEATWAVE_TEMPERATURE" in ev_labels or temp >= 45.0:
                score += 65.0
                matched_ev.append("Critical extreme heatwave temperature anomaly (>= 45°C)")
            elif "HIGH_AMBIENT_TEMPERATURE" in ev_labels or temp >= 40.0:
                score += 50.0
                matched_ev.append("High ambient air temperature anomaly (>= 40°C)")
            if "COMPOUND_HEAT_HUMIDITY_HAZARD" in ev_labels:
                score += 25.0
                matched_ev.append("Dangerous compound heat and humidity (wet-bulb stress)")
            action = "Deploy mobile hydration stations, cooling centers, and vulnerable citizen checkups."

        elif scenario_id == "drought":
            if temp >= 35.0 and rain <= 0.5:
                score += 35.0
                matched_ev.append("Protracted arid heat with zero rainfall")
            if "ARID_DRY_ATMOSPHERE" in ev_labels:
                score += 20.0
                matched_ev.append("Severely depleted atmospheric relative humidity")
            action = "Coordinate bulk potable water distribution and agricultural emergency logistics."

        elif scenario_id == "stampede":
            if "MOTION_ACTIVITY_DETECTED" in ev_labels and "ACOUSTIC_DISTRESS_SIGNALS" in ev_labels:
                score += 40.0
                matched_ev.append("Crowd density motion spikes and acoustic crush screams")
            action = "Open emergency dispersal gates, deploy mass-casualty triage, and establish one-way flow."

        elif scenario_id == "transport_accident":
            if "ACOUSTIC_DISTRESS_SIGNALS" in ev_labels and "SURVIVOR_VITALS_CONFIRMED" in ev_labels:
                score += 35.0
                matched_ev.append("Extrication distress signals and multi-victim vitals")
            action = "Deploy hydraulic cutters, stabilize vehicle wreckage, and triage traumatic impact injuries."

        elif scenario_id == "infrastructure_entrapment":
            if "ACOUSTIC_DISTRESS_SIGNALS" in ev_labels and "SURVIVOR_VITALS_CONFIRMED" in ev_labels:
                score += 40.0
                matched_ev.append("Subterranean tapping acoustic signals and localized radar vitals")
            action = "Deploy technical confined-space SAR teams, borehole cameras, and atmospheric ventilation."

        elif scenario_id == "multi_hazard":
            compound_count = sum([
                1 if "SEISMIC_TREMOR_DETECTED" in ev_labels else 0,
                1 if "CRITICAL_FLOOD_SUBMERSION" in ev_labels or "TORRENTIAL_PRECIPITATION" in ev_labels else 0,
                1 if "EXTREME_THERMAL_SIGNATURE" in ev_labels or "DENSE_SMOKE_OBSCURATION" in ev_labels else 0,
                1 if "TOXIC_COMBUSTIBLE_GAS_ALERT" in ev_labels else 0,
                1 if "SOIL_SATURATION_INSTABILITY" in ev_labels else 0,
            ])
            if compound_count >= 2:
                score += 30.0 * compound_count
                matched_ev.append(f"Simultaneous detection across {compound_count} independent hazard modalities")
            action = "Execute Multi-Agency Incident Command System (ICS) and cross-domain task force deployment."

        score = min(100.0, max(5.0, score))

        # Risk classification
        if score >= 75.0:
            risk = RiskLevel.CRITICAL
        elif score >= 50.0:
            risk = RiskLevel.HIGH
        elif score >= 30.0:
            risk = RiskLevel.MEDIUM
        else:
            risk = RiskLevel.LOW

        return score, risk, matched_ev, action

    def _get_cascading_candidates(self, primary_id: str) -> List[str]:
        return MultiHazardCascadeEngine().evaluate_cascades(primary_id)


# --------------------------------------------------------------------------- #
# 4. Multi-Hazard Cascade Engine
# --------------------------------------------------------------------------- #
class MultiHazardCascadeEngine:
    """Evaluates cascading secondary hazards triggered by primary disasters."""
    def __init__(self):
        self.cascade_map = {
            "earthquake": ["building_collapse", "landslide", "urban_fire", "chemical_leak", "tsunami"],
            "flood": ["dam_failure", "landslide", "infrastructure_entrapment"],
            "cyclone": ["flood", "landslide", "building_collapse", "storm_surge"],
            "landslide": ["infrastructure_entrapment", "transport_accident", "flood"],
            "urban_fire": ["building_collapse", "chemical_leak"],
            "wildfire": ["urban_fire", "landslide", "smoke_hazard"],
            "industrial_accident": ["chemical_leak", "urban_fire", "building_collapse"],
            "cloudburst": ["flood", "landslide", "dam_failure", "flash_flood"],
            "tsunami": ["flood", "building_collapse", "coastal_inundation"],
            "avalanche": ["hypothermia", "trauma", "suffocation"],
            "volcanic_eruption": ["pyroclastic_flow", "lahar", "ash_fall", "toxic_gas"],
        }

    def evaluate_cascades(self, primary_id: Any, env_report: Optional[Any] = None) -> List[str]:
        actual_id = getattr(primary_id, "scenario_id", primary_id) if not isinstance(primary_id, str) else primary_id
        candidates = list(self.cascade_map.get(str(actual_id), ["multi_hazard"]))
        if isinstance(env_report, dict):
            if env_report.get("rainfall_mm_hr", 0) > 30.0 and "landslide" not in candidates:
                candidates.append("landslide")
            if env_report.get("gas_concentration_ppm", 0) > 100.0 and "chemical_leak" not in candidates:
                candidates.append("chemical_leak")
        elif isinstance(env_report, (list, tuple)):
            for item in env_report:
                sec_id = getattr(item, "scenario_id", item)
                if isinstance(sec_id, str) and sec_id not in candidates:
                    candidates.append(sec_id)
        return candidates


# --------------------------------------------------------------------------- #
# 5. Alert Lifecycle Manager
# --------------------------------------------------------------------------- #
class AlertLifecycleManager:
    """
    Manages active alert lifecycles: deduplication, severity elevation,
    auto-escalation, and auto-resolution in the active alert ledger.
    """

    def evaluate_and_sync(
        self,
        session_id: str,
        cycle: int,
        assessment: DisasterAssessment,
        active_alerts_db: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        return self.sync_alerts(
            session_id=session_id,
            primary_scenario=assessment.primary_scenario,
            secondary_scenarios=assessment.secondary_scenarios,
            evidence=assessment.active_evidence,
        )

    def sync_alerts(
        self,
        session_id: str,
        primary_scenario: Optional[ScenarioInferenceResult] = None,
        secondary_scenarios: Optional[List[ScenarioInferenceResult]] = None,
        evidence: Optional[List[SensorEvidence]] = None,
    ) -> List[Dict[str, Any]]:
        active_keys: set[str] = set()
        if isinstance(primary_scenario, list) and evidence is None:
            evidence = primary_scenario
            primary_scenario = None
        sec_list = secondary_scenarios or []
        ev_list = evidence or []

        # 1. Primary Scenario Alert
        if primary_scenario and hasattr(primary_scenario, "confidence_pct") and primary_scenario.confidence_pct >= 40.0:
            alert_key = f"{session_id}-{primary_scenario.scenario_id}"
            active_keys.add(alert_key)
            title = f"DISASTER ALERT: {primary_scenario.scenario_name.upper()}"
            summary = "; ".join(primary_scenario.primary_evidence) if primary_scenario.primary_evidence else primary_scenario.recommended_action
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type=primary_scenario.scenario_id,
                alert_title=title,
                severity=primary_scenario.risk_level.value,
                confidence_pct=primary_scenario.confidence_pct,
                evidence_summary=summary,
            )

        # 2. Secondary High-Confidence Cascading Alerts
        for sec in sec_list:
            if sec.confidence_pct >= 60.0 and (not primary_scenario or sec.scenario_id != primary_scenario.scenario_id):
                alert_key = f"{session_id}-{sec.scenario_id}"
                active_keys.add(alert_key)
                title = f"CASCADING HAZARD: {sec.scenario_name.upper()}"
                summary = "; ".join(sec.primary_evidence) if sec.primary_evidence else f"Secondary risk resulting from {primary_scenario.scenario_name if primary_scenario else 'incident'}."
                db.upsert_active_alert(
                    alert_key=alert_key,
                    session_id=session_id,
                    hazard_type=sec.scenario_id,
                    alert_title=title,
                    severity=sec.risk_level.value,
                    confidence_pct=sec.confidence_pct,
                    evidence_summary=summary,
                )

        # 3. Life-Safety Survivor Hazard Alert
        for ev in ev_list:
            if ev.evidence_label == "HAZARDOUS_AREA_SURVIVOR_DETECTED":
                alert_key = f"{session_id}-survivor-hazard"
                active_keys.add(alert_key)
                db.upsert_active_alert(
                    alert_key=alert_key,
                    session_id=session_id,
                    hazard_type="hazardous_area_survivor",
                    alert_title="LIFE-SAFETY ALERT: SURVIVOR IN HAZARDOUS ATMOSPHERE",
                    severity="CRITICAL",
                    confidence_pct=98.0,
                    evidence_summary="Survivor vital signs detected within critical toxic gas / dense smoke plume.",
                )

        # 4. Dedicated Barometric Pressure & Weather Warnings
        for ev in evidence:
            if ev.evidence_label in ("CRITICAL_BAROMETRIC_PRESSURE_PLUNGE", "SEVERE_BAROMETRIC_PRESSURE_DROP"):
                alert_key = f"{session_id}-pressure-severe-drop"
                active_keys.add(alert_key)
                db.upsert_active_alert(
                    alert_key=alert_key,
                    session_id=session_id,
                    hazard_type="barometric_pressure_drop",
                    alert_title="WEATHER ALERT: SEVERE BAROMETRIC PRESSURE DROP",
                    severity="HIGH" if ev.evidence_label == "SEVERE_BAROMETRIC_PRESSURE_DROP" else "CRITICAL",
                    confidence_pct=ev.confidence * 100.0,
                    evidence_summary=ev.description,
                )
            elif ev.evidence_label == "RAPID_PRESSURE_DROP_DETECTED":
                alert_key = f"{session_id}-pressure-rapid-drop"
                active_keys.add(alert_key)
                db.upsert_active_alert(
                    alert_key=alert_key,
                    session_id=session_id,
                    hazard_type="rapid_pressure_drop",
                    alert_title="METEOROLOGICAL WARNING: RAPID PRESSURE PLUNGE",
                    severity="HIGH",
                    confidence_pct=ev.confidence * 100.0,
                    evidence_summary=ev.description,
                )
            elif ev.evidence_label == "PRESSURE_WEATHER_DETERIORATION":
                alert_key = f"{session_id}-pressure-weather-deterioration"
                active_keys.add(alert_key)
                db.upsert_active_alert(
                    alert_key=alert_key,
                    session_id=session_id,
                    hazard_type="weather_deterioration",
                    alert_title="WEATHER WARNING: ADVERSE CYCLONIC CONDITIONS",
                    severity="HIGH",
                    confidence_pct=ev.confidence * 100.0,
                    evidence_summary=ev.description,
                )

        # 5. Dedicated Landslide & Slope Hazard Warnings (Mutually Exclusive Hierarchy)
        ev_map = {e.evidence_label: e for e in evidence}
        if "LANDSLIDE_HAZARD_CRITICAL" in ev_map:
            ev = ev_map["LANDSLIDE_HAZARD_CRITICAL"]
            alert_key = f"{session_id}-landslide-critical"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="landslide_critical",
                alert_title="EARLY WARNING: CRITICAL LANDSLIDE RISK & SLOPE SHEAR",
                severity="CRITICAL",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )
        elif "LANDSLIDE_EARLY_WARNING" in ev_map:
            ev = ev_map["LANDSLIDE_EARLY_WARNING"]
            alert_key = f"{session_id}-landslide-early-warning"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="landslide_early_warning",
                alert_title="HAZARD ALERT: ELEVATED SLOPE INSTABILITY & LANDSLIDE RISK",
                severity="HIGH",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )
        elif "SOIL_SATURATION_INSTABILITY" in ev_map:
            ev = ev_map["SOIL_SATURATION_INSTABILITY"]
            alert_key = f"{session_id}-landslide-watch"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="soil_saturation_watch",
                alert_title="HAZARD WATCH: CRITICAL SOIL WATER SATURATION",
                severity="MEDIUM",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        # 6. Optical & Thermal Camera Survivor & Hazard Warnings
        for ev in evidence:
            if ev.evidence_label in ("CAMERA_HUMAN_CONFIRMED", "QUAD_SENSOR_CORROBORATION_CONFIRMED", "STRONG_SURVIVOR_CORROBORATION"):
                alert_key = f"{session_id}-cam-human-{ev.evidence_label.lower()}"
                active_keys.add(alert_key)
                db.upsert_active_alert(
                    alert_key=alert_key,
                    session_id=session_id,
                    hazard_type="camera_human_detected",
                    alert_title="AI OPTICAL/THERMAL DETECTION: CONFIRMED SURVIVOR SIGNATURE",
                    severity="HIGH",
                    confidence_pct=ev.confidence * 100.0,
                    evidence_summary=ev.description,
                )
            elif ev.evidence_label == "THERMAL_FIRE_HOTSPOT":
                alert_key = f"{session_id}-thermal-fire-hotspot"
                active_keys.add(alert_key)
                db.upsert_active_alert(
                    alert_key=alert_key,
                    session_id=session_id,
                    hazard_type="thermal_fire_hotspot",
                    alert_title="THERMAL HAZARD ALERT: ACTIVE COMBUSTION HOTSPOT DETECTED",
                    severity="HIGH",
                    confidence_pct=ev.confidence * 100.0,
                    evidence_summary=ev.description,
                )
            elif ev.evidence_label == "CAMERA_THERMAL_FALSE_POSITIVE_WARNING":
                alert_key = f"{session_id}-cam-false-positive"
                active_keys.add(alert_key)
                db.upsert_active_alert(
                    alert_key=alert_key,
                    session_id=session_id,
                    hazard_type="camera_false_positive_warning",
                    alert_title="DATA DISCREPANCY: OPTICAL DETECTION WITHOUT THERMAL BODY HEAT",
                    severity="LOW",
                    confidence_pct=ev.confidence * 100.0,
                    evidence_summary=ev.description,
                )

        # 7. Dedicated Rainfall & Severe Weather Alerts (Priority / Mutually Exclusive Intensity)
        ev_map = {e.evidence_label: e for e in evidence}
        if "RAINFALL_EXTREME_CLOUD_BURST_DETECTED" in ev_map:
            ev = ev_map["RAINFALL_EXTREME_CLOUD_BURST_DETECTED"]
            alert_key = f"{session_id}-rainfall-cloudburst"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="rainfall_cloudburst",
                alert_title="METEOROLOGICAL ALERT: EXTREME TORRENTIAL CLOUDBURST",
                severity="CRITICAL",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )
        elif "RAINFALL_VERY_HEAVY_DOWNPOUR" in ev_map:
            ev = ev_map["RAINFALL_VERY_HEAVY_DOWNPOUR"]
            alert_key = f"{session_id}-rainfall-very-heavy"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="rainfall_very_heavy",
                alert_title="WEATHER WARNING: VERY HEAVY PRECIPITATION DOWNPOUR",
                severity="HIGH",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )
        elif "RAINFALL_HEAVY_PRECIPITATION" in ev_map or "TORRENTIAL_PRECIPITATION" in ev_map:
            ev = ev_map.get("RAINFALL_HEAVY_PRECIPITATION") or ev_map.get("TORRENTIAL_PRECIPITATION")
            alert_key = f"{session_id}-rainfall-heavy"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="rainfall_heavy",
                alert_title="PRECIPITATION WARNING: HEAVY RAINFALL",
                severity="HIGH",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        if "RAINFALL_WATER_COMPOUND_FLASH_FLOOD_TRIGGER" in ev_map:
            ev = ev_map["RAINFALL_WATER_COMPOUND_FLASH_FLOOD_TRIGGER"]
            alert_key = f"{session_id}-rainfall-compound-flood"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="compound_flood_risk",
                alert_title="COMPOUND FLOOD RISK: RAINFALL DRIVING RAPID WATER INUNDATION",
                severity="CRITICAL",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        if "RAINFALL_SOIL_COMPOUND_LANDSLIDE_TRIGGER" in ev_map:
            ev = ev_map["RAINFALL_SOIL_COMPOUND_LANDSLIDE_TRIGGER"]
            alert_key = f"{session_id}-rainfall-compound-landslide"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="compound_landslide_risk",
                alert_title="COMPOUND LANDSLIDE RISK: RAINFALL SATURATING UNSTABLE SLOPE",
                severity="CRITICAL",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        # 8. Dedicated Temperature & Thermal Heat Warnings
        if "EXTREME_HEATWAVE_TEMPERATURE" in ev_map or "FIRE_ENVIRONMENTAL_TEMPERATURE" in ev_map:
            ev = ev_map.get("EXTREME_HEATWAVE_TEMPERATURE") or ev_map.get("FIRE_ENVIRONMENTAL_TEMPERATURE")
            alert_key = f"{session_id}-temperature-extreme-heat"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="extreme_heatwave",
                alert_title="EXTREME THERMAL ALERT: LIFE-THREATENING HEATWAVE TEMPERATURE",
                severity="CRITICAL",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )
        elif "HIGH_AMBIENT_TEMPERATURE" in ev_map:
            ev = ev_map["HIGH_AMBIENT_TEMPERATURE"]
            alert_key = f"{session_id}-temperature-high-heat"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="high_temperature",
                alert_title="THERMAL ADVISORY: SEVERE HIGH AMBIENT TEMPERATURE",
                severity="HIGH",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        if "COMPOUND_HEAT_HUMIDITY_HAZARD" in ev_map:
            ev = ev_map["COMPOUND_HEAT_HUMIDITY_HAZARD"]
            alert_key = f"{session_id}-heat-humidity-compound"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="compound_heat_humidity",
                alert_title="COMPOUND HAZARD ALERT: SEVERE WET-BULB HEAT STRESS",
                severity="HIGH",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        # 9. Dedicated GPS Positioning & Kinematic Alerts
        if "GPS_SIGNAL_OFFLINE" in ev_map:
            ev = ev_map["GPS_SIGNAL_OFFLINE"]
            alert_key = f"{session_id}-gps-signal-loss"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="gps_signal_loss",
                alert_title="NAVIGATION ALERT: TOTAL GNSS SATELLITE SIGNAL LOSS",
                severity="HIGH",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )
        elif "GPS_SIGNAL_DEGRADED" in ev_map:
            ev = ev_map["GPS_SIGNAL_DEGRADED"]
            alert_key = f"{session_id}-gps-degraded"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="gps_degraded_fix",
                alert_title="NAVIGATION ADVISORY: DEGRADED GNSS POSITIONING ACCURACY",
                severity="MEDIUM",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        if "GPS_MOVEMENT_ANOMALY" in ev_map:
            ev = ev_map["GPS_MOVEMENT_ANOMALY"]
            alert_key = f"{session_id}-gps-jump-anomaly"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="gps_jump_anomaly",
                alert_title="SENSOR ANOMALY: IMPOSSIBLE KINEMATIC POSITION JUMP / SPOOFING",
                severity="HIGH",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        # 10. Dedicated Water-Level & Inundation Alerts (Mutually Exclusive Hierarchy)
        if "CRITICAL_FLOOD_SUBMERSION" in ev_map:
            ev = ev_map["CRITICAL_FLOOD_SUBMERSION"]
            alert_key = f"{session_id}-water-critical-flood"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="critical_flood",
                alert_title="CRITICAL FLOOD ALERT: DANGEROUS SUBMERSION DEPTH",
                severity="CRITICAL",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )
        elif "HIGH_WATER_LEVEL" in ev_map:
            ev = ev_map["HIGH_WATER_LEVEL"]
            alert_key = f"{session_id}-water-high-flood"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="high_water_level",
                alert_title="HIGH WATER ALERT: FLOOD INUNDATION DETECTED",
                severity="HIGH",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )
        elif "WATER_LEVEL_WARNING" in ev_map:
            ev = ev_map["WATER_LEVEL_WARNING"]
            alert_key = f"{session_id}-water-warning"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="water_level_warning",
                alert_title="WATER LEVEL ADVISORY: ELEVATED WATER LEVEL",
                severity="MEDIUM",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        if "DAM_BREAK_WATER_SURGE" in ev_map:
            ev = ev_map["DAM_BREAK_WATER_SURGE"]
            alert_key = f"{session_id}-dam-break-surge"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="dam_break_risk",
                alert_title="CATASTROPHIC SURGE ALERT: DAM BREAK INUNDATION",
                severity="CRITICAL",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        if "TSUNAMI_WATER_ANOMALY" in ev_map:
            ev = ev_map["TSUNAMI_WATER_ANOMALY"]
            alert_key = f"{session_id}-tsunami-surge"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="tsunami_water_signal",
                alert_title="OCEANOGRAPHIC SURGE ALERT: TSUNAMI WAVE SURGE",
                severity="CRITICAL",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        if "RAPID_SURGE_WATER_RISE" in ev_map and "DAM_BREAK_WATER_SURGE" not in ev_map and "TSUNAMI_WATER_ANOMALY" not in ev_map:
            ev = ev_map["RAPID_SURGE_WATER_RISE"]
            alert_key = f"{session_id}-rapid-water-rise"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="rapid_water_rise",
                alert_title="HYDROLOGICAL WARNING: RAPID WATER LEVEL SURGE",
                severity="HIGH",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        if "FLASH_FLOOD_RISK" in ev_map:
            ev = ev_map["FLASH_FLOOD_RISK"]
            alert_key = f"{session_id}-flash-flood-risk"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="flash_flood_risk",
                alert_title="FLASH FLOOD WARNING: RAPID INUNDATION SURGE",
                severity="HIGH",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        if "STORM_SURGE_WATER_RISK" in ev_map:
            ev = ev_map["STORM_SURGE_WATER_RISK"]
            alert_key = f"{session_id}-storm-surge-risk"
            active_keys.add(alert_key)
            db.upsert_active_alert(
                alert_key=alert_key,
                session_id=session_id,
                hazard_type="storm_surge_risk",
                alert_title="COASTAL WARNING: CYCLONIC STORM SURGE",
                severity="HIGH",
                confidence_pct=ev.confidence * 100.0,
                evidence_summary=ev.description,
            )

        # 11. Auto-resolve inactive alerts for this session
        existing_active = db.list_active_alerts(session_id=session_id, status="ACTIVE")
        for alert in existing_active:
            if alert["alert_key"] not in active_keys:
                db.resolve_active_alert(alert["alert_key"])

        # Retrieve active alerts from DB
        return db.list_active_alerts(session_id=session_id, status="ACTIVE")


# --------------------------------------------------------------------------- #
# 6. Unified Scenario Intelligence Coordinator
# --------------------------------------------------------------------------- #
class ScenarioIntelligenceEngine:
    """
    Unified end-to-end intelligence engine coordinating sensor validation,
    time-series trends, health checks, evidence extraction, scenario inference,
    cascading disaster assessment, and alert synchronization.
    """

    def __init__(self):
        self.trend_tracker = SensorTrendTracker(window_size=60)
        self.health_monitor = SensorHealthMonitor()
        self.evidence_extractor = SensorEvidenceExtractor()
        self.inference_engine = DisasterScenarioInferenceEngine()
        self.alert_manager = AlertLifecycleManager()
        self.camera_thermal_analyzer = CameraThermalAnalyzer(history_window=30)
        self.rainfall_analyzer = RainfallAnalyzer(history_window=60)
        self.gps_analyzer = GPSAnalyzer(history_window=60)
        self.latest_trends: List[SensorTrend] = []

    def process_cycle(
        self,
        session_id: str,
        cycle: int,
        readings: List[SensorReading],
        env_report: Dict[str, Any],
        battery_map: Dict[str, float],
        active_scenario_hint: Optional[str] = None,
    ) -> DisasterAssessment:
        # Step 1: Push trends for all incoming readings
        trends: List[SensorTrend] = [self.trend_tracker.push_reading(r) for r in readings]
        self.latest_trends = trends

        # Step 2: Health evaluation per node
        health_records: List[SensorHealth] = []
        by_node: Dict[str, List[SensorReading]] = defaultdict(list)
        for r in readings:
            by_node[r.victim_id or "SITE"].append(r)

        for nid, n_readings in by_node.items():
            bat = battery_map.get(nid, 100.0)
            health_records.extend(self.health_monitor.evaluate_node_health(nid, bat, n_readings))

        # Step 3: Extract prioritized semantic evidence
        evidence_list = self.evidence_extractor.extract_evidence(readings, trends, env_report)

        # Step 4: Infer scenario matches
        scenario_matches = self.inference_engine.infer_scenarios(
            evidence_list, env_report, active_scenario_hint
        )

        primary = scenario_matches[0] if scenario_matches else ScenarioInferenceResult(
            scenario_id="unknown",
            scenario_name="Unknown Scenario",
            confidence_pct=0.0,
            risk_level=RiskLevel.LOW,
            primary_evidence=[],
            secondary_hazards=[],
            recommended_action="Monitor site.",
        )
        secondary = [s for s in scenario_matches[1:4] if s.confidence_pct >= 25.0]

        # Step 5: Determine survivor status summary
        has_vitals = any(e.evidence_label == "SURVIVOR_VITALS_CONFIRMED" for e in evidence_list)
        has_motion = any(e.evidence_label == "MOTION_ACTIVITY_DETECTED" for e in evidence_list)
        has_human_cam = any(e.evidence_label == "CAMERA_HUMAN_CONFIRMED" for e in evidence_list)
        has_human_thm = any(e.evidence_label == "THERMAL_HUMAN_HEAT_CONFIRMED" for e in evidence_list)
        has_quad = any(e.evidence_label == "QUAD_SENSOR_CORROBORATION_CONFIRMED" for e in evidence_list)
        has_animal_only = any(e.evidence_label == "ANIMAL_ACTIVITY_DETECTED" for e in evidence_list) and not (has_vitals or has_human_cam or has_human_thm)

        if has_quad or (has_vitals and has_human_cam and has_human_thm):
            survivor_status = "CONFIRMED_MULTI_MODAL_SURVIVORS"
        elif has_vitals and has_motion:
            survivor_status = "DETECTED_ACTIVE_SURVIVORS"
        elif has_vitals:
            survivor_status = "DETECTED_IMMOBILE_SURVIVORS"
        elif has_human_cam or has_human_thm:
            survivor_status = "VISUALLY_CONFIRMED_SURVIVORS"
        elif has_motion and not has_animal_only:
            survivor_status = "POSSIBLE_SURVIVOR_MOVEMENT"
        elif has_animal_only:
            survivor_status = "ANIMAL_ACTIVITY_NON_SURVIVOR"
        else:
            survivor_status = "ACTIVE_SEARCH_IN_PROGRESS"

        # Step 6: Sync alerts into active ledger
        active_alerts = self.alert_manager.sync_alerts(
            session_id=session_id,
            primary_scenario=primary,
            secondary_scenarios=secondary,
            evidence=evidence_list,
        )

        assessment = DisasterAssessment(
            primary_scenario=primary,
            secondary_scenarios=secondary,
            active_evidence=evidence_list,
            overall_risk=primary.risk_level,
            confidence_pct=primary.confidence_pct,
            survivor_status=survivor_status,
            recommended_action=primary.recommended_action,
            assessed_at=_utc_now_iso(),
            cycle=cycle,
        )

        # Step 7: Persist intelligence batch to database
        try:
            db.log_sensor_health_batch(session_id, cycle, health_records)
            db.log_sensor_trends_batch(session_id, cycle, trends)
            db.log_scenario_intelligence(session_id, cycle, {
                "primary_scenario": {
                    "scenario_id": primary.scenario_id,
                    "scenario_name": primary.scenario_name,
                    "confidence_pct": primary.confidence_pct,
                    "risk_level": primary.risk_level.value,
                    "recommended_action": primary.recommended_action,
                },
                "secondary_scenarios": [
                    {
                        "scenario_id": s.scenario_id,
                        "scenario_name": s.scenario_name,
                        "confidence_pct": s.confidence_pct,
                        "risk_level": s.risk_level.value,
                    }
                    for s in secondary
                ],
                "active_evidence": [
                    {
                        "sensor_type": e.sensor_type.value,
                        "evidence_label": e.evidence_label,
                        "observed_value": e.observed_value,
                        "confidence": e.confidence,
                        "description": e.description,
                    }
                    for e in evidence_list
                ],
                "confidence_pct": primary.confidence_pct,
                "overall_risk": primary.risk_level.value,
                "survivor_status": survivor_status,
            })
        except Exception as e:
            # Soft fallback if DB connection fails in transient test runners
            pass

        return assessment

    def reset(self):
        self.trend_tracker.reset()


# Global singleton instance
global_scenario_intelligence = ScenarioIntelligenceEngine()
