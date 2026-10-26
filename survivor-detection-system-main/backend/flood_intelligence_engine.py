"""
backend/flood_intelligence_engine.py
------------------------------------
RIDGEWATCH Multi-Sensor Flash-Flood Intelligence, Risk Scoring & Early-Warning Engine.
Inspired by severe Nepal-style flash-flood emergencies (e.g., Melamchi & Seti River surge dynamics).

PHYSICAL & METEOROLOGICAL PRINCIPLE:
Flash floods in steep mountainous terrain and urban catchment basins are driven by:
1. Intense localized rainfall / cloudbursts (antecedent & instantaneous precipitation).
2. Upstream river gorge damming or sudden glacial/reservoir outburst release.
3. Rapid water column depth increase and non-contact hydrostatic pressure escalation (P = ρ·g·h).
4. Saturated slope destabilization leading to combined debris flows and channel choking.

RISK CLASSIFICATION SYSTEM:
- 0–25:   NORMAL   - Base riverbed flow, nominal surface distance, zero evacuation required.
- 26–50:  WATCH    - Steady water rise or elevated rainfall; SAR teams put on initial standby.
- 51–75:  WARNING  - Rapid rise rate or upstream surge; notify authorities, prepare evacuations.
- 76–100: CRITICAL - Severe inundation or catastrophic surge; trigger sirens, emergency alerts & evacuations.
"""

from __future__ import annotations

import os
import math
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from collections import deque

logger = logging.getLogger("ridgewatch.flood_intelligence")


class FloodRiskLevel(str, Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class FloodRiskThresholds:
    """Configurable thresholds for flash-flood risk scoring and early warnings."""
    normal_max: float = 25.0
    watch_max: float = 50.0
    warning_max: float = 75.0
    
    # Physical thresholds
    watch_depth_m: float = 0.50          # 50 cm
    warning_depth_m: float = 1.20        # 120 cm
    critical_depth_m: float = 2.00       # 200 cm

    watch_rise_rate_cm_min: float = 2.0     # 2 cm/min
    warning_rise_rate_cm_min: float = 6.0   # 6 cm/min
    critical_rise_rate_cm_min: float = 15.0 # 15 cm/min

    watch_rainfall_mm_h: float = 15.0       # 15 mm/h
    warning_rainfall_mm_h: float = 35.0     # 35 mm/h
    critical_rainfall_mm_h: float = 65.0    # 65 mm/h


@dataclass
class FloodRiskAssessment:
    """Structured assessment result produced by FloodIntelligenceEngine."""
    assessment_id: str = field(default_factory=lambda: f"FLDRISK-{uuid.uuid4().hex[:8]}")
    risk_score: float = 0.0              # 0.0 - 100.0
    risk_level: FloodRiskLevel = FloodRiskLevel.NORMAL
    confidence: float = 1.0              # 0.0 - 1.0
    early_warning_status: str = "NORMAL_FLOW"  # "NORMAL_FLOW", "SURGE_DETECTED", "RAPID_ACCELERATION", "PREDICTION_UNAVAILABLE", "LOW_CONFIDENCE"
    water_depth_m: float = 0.0
    estimated_pressure_kpa: Optional[float] = None
    rise_rate_cm_min: float = 0.0
    acceleration_cm_min2: float = 0.0
    rainfall_rate_mm_h: float = 0.0
    river_flow_mps: float = 0.0
    debris_flow_risk: str = "LOW"
    data_freshness: str = "REALTIME_FRESH"
    contributing_factors: List[Dict[str, Any]] = field(default_factory=list)
    recommended_action: str = "Maintain standard hydrological surveillance"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    pressure_source: str = "non_contact_sensor_estimation"
    mode: str = "REAL_SENSOR_DATA"       # "REAL_SENSOR_DATA", "SIMULATION_DATA", "UNAVAILABLE_DATA"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "risk_score": round(self.risk_score, 1),
            "risk_level": self.risk_level.value if hasattr(self.risk_level, "value") else str(self.risk_level),
            "confidence": round(self.confidence, 2),
            "early_warning_status": self.early_warning_status,
            "water_depth_m": round(self.water_depth_m, 3),
            "estimated_pressure_kpa": round(self.estimated_pressure_kpa, 3) if self.estimated_pressure_kpa is not None else None,
            "rise_rate_cm_min": round(self.rise_rate_cm_min, 2),
            "acceleration_cm_min2": round(self.acceleration_cm_min2, 2),
            "rainfall_rate_mm_h": round(self.rainfall_rate_mm_h, 1),
            "river_flow_mps": round(self.river_flow_mps, 2),
            "debris_flow_risk": self.debris_flow_risk,
            "data_freshness": self.data_freshness,
            "contributing_factors": self.contributing_factors,
            "recommended_action": self.recommended_action,
            "timestamp": self.timestamp,
            "pressure_source": self.pressure_source,
            "mode": self.mode,
        }


class FloodIntelligenceEngine:
    """
    Multi-sensor flash-flood early warning, risk scoring, and surge intelligence engine.
    """
    def __init__(self, thresholds: Optional[FloodRiskThresholds] = None):
        self.thresholds = thresholds or FloodRiskThresholds()
        self.depth_history: deque[Tuple[float, str]] = deque(maxlen=60)
        self.last_assessment: Optional[FloodRiskAssessment] = None
        self.alert_cooldown_seconds: float = 120.0
        self.last_alert_timestamp: Optional[datetime] = None

    def evaluate_flood_risk(
        self,
        water_depth_m: Optional[float],
        measured_surface_distance_m: Optional[float] = None,
        estimated_pressure_kpa: Optional[float] = None,
        rainfall_rate_mm_h: float = 0.0,
        river_flow_mps: float = 0.0,
        upstream_water_depth_m: Optional[float] = None,
        downstream_water_depth_m: Optional[float] = None,
        landslide_risk_score: float = 0.0,
        ground_vibration_g: float = 0.0,
        sensor_quality: float = 1.0,
        is_stale: bool = False,
        is_simulation: bool = False,
        timestamp_str: Optional[str] = None,
    ) -> FloodRiskAssessment:
        """
        Evaluate multi-sensor signals and compute comprehensive flash-flood risk.
        """
        ts = timestamp_str or datetime.now(timezone.utc).isoformat()
        mode_label = "SIMULATION_DATA" if is_simulation else "REAL_SENSOR_DATA"

        # Check for completely missing / offline water data
        if water_depth_m is None or math.isnan(water_depth_m) or is_stale or sensor_quality <= 0.0:
            return FloodRiskAssessment(
                risk_score=20.0 if rainfall_rate_mm_h > 30.0 else 0.0,
                risk_level=FloodRiskLevel.NORMAL if rainfall_rate_mm_h <= 30.0 else FloodRiskLevel.WATCH,
                confidence=0.0,
                early_warning_status="PREDICTION_UNAVAILABLE",
                water_depth_m=0.0,
                estimated_pressure_kpa=None,
                rise_rate_cm_min=0.0,
                acceleration_cm_min2=0.0,
                rainfall_rate_mm_h=rainfall_rate_mm_h,
                river_flow_mps=river_flow_mps,
                data_freshness="STALE_OR_OFFLINE",
                contributing_factors=[{"factor": "SENSOR_OFFLINE", "weight": 0.0, "description": "Water-level sensor telemetry offline or corrupted"}],
                recommended_action="Dispatch technicians to verify hydrological telemetry links immediately",
                timestamp=ts,
                mode="UNAVAILABLE_DATA" if not is_simulation else "SIMULATION_DATA",
            )

        # 1. Depth & Rate-of-Rise Tracking
        self.depth_history.append((water_depth_m, ts))
        rise_rate_cm_min = 0.0
        accel_cm_min2 = 0.0

        if len(self.depth_history) >= 2:
            prev_d, _ = self.depth_history[-2]
            # Assuming step is nominally ~1 cycle (1.0 - 4.0s), compute cm/min
            rise_rate_cm_min = (water_depth_m - prev_d) * 100.0 * 15.0 # per minute approx
        if len(self.depth_history) >= 3:
            prev_d1, _ = self.depth_history[-2]
            prev_d2, _ = self.depth_history[-3]
            rate1 = (water_depth_m - prev_d1) * 100.0
            rate2 = (prev_d1 - prev_d2) * 100.0
            accel_cm_min2 = (rate1 - rate2) * 15.0

        # 2. Weighted Factor Calculations (0 to 100)
        factors: List[Dict[str, Any]] = []
        score_accumulator = 0.0

        # Component A: Water Column Depth (Weight: 35%)
        depth_score = min(100.0, (water_depth_m / self.thresholds.critical_depth_m) * 100.0)
        score_accumulator += depth_score * 0.35
        factors.append({
            "factor": "WATER_DEPTH",
            "value": f"{water_depth_m:.2f} m",
            "sub_score": round(depth_score, 1),
            "weight_pct": 35,
            "description": f"Measured water column height relative to datum ({water_depth_m:.2f} m)",
        })

        # Component B: Rise Rate & Acceleration (Weight: 25%)
        rise_score = min(100.0, max(0.0, (rise_rate_cm_min / self.thresholds.critical_rise_rate_cm_min) * 100.0))
        if accel_cm_min2 > 5.0:
            rise_score = min(100.0, rise_score + 15.0)
        score_accumulator += rise_score * 0.25
        factors.append({
            "factor": "RISE_RATE_DYNAMICS",
            "value": f"{rise_rate_cm_min:.1f} cm/min",
            "sub_score": round(rise_score, 1),
            "weight_pct": 25,
            "description": f"Hydrological rate of rise ({rise_rate_cm_min:.1f} cm/min, accel: {accel_cm_min2:.1f} cm/min²)",
        })

        # Component C: Rainfall & Precipitation Intensity (Weight: 20%)
        rain_score = min(100.0, (rainfall_rate_mm_h / self.thresholds.critical_rainfall_mm_h) * 100.0)
        score_accumulator += rain_score * 0.20
        factors.append({
            "factor": "RAINFALL_INTENSITY",
            "value": f"{rainfall_rate_mm_h:.1f} mm/h",
            "sub_score": round(rain_score, 1),
            "weight_pct": 20,
            "description": f"Precipitation intensity from optical disdrometer ({rainfall_rate_mm_h:.1f} mm/h)",
        })

        # Component D: River Velocity & Hydrodynamic Force (Weight: 10%)
        flow_score = min(100.0, (river_flow_mps / 4.0) * 100.0)
        score_accumulator += flow_score * 0.10
        factors.append({
            "factor": "RIVER_FLOW_VELOCITY",
            "value": f"{river_flow_mps:.2f} m/s",
            "sub_score": round(flow_score, 1),
            "weight_pct": 10,
            "description": f"Doppler flood velocity ({river_flow_mps:.2f} m/s)",
        })

        # Component E: Upstream Surge & Debris Flow Coupling (Weight: 10%)
        debris_risk_str = "LOW"
        upstream_score = 0.0
        if upstream_water_depth_m is not None and upstream_water_depth_m > water_depth_m:
            delta_up = upstream_water_depth_m - water_depth_m
            upstream_score = min(100.0, (delta_up / 1.0) * 100.0)
        if landslide_risk_score > 60.0 or ground_vibration_g > 0.35:
            debris_risk_str = "HIGH"
            upstream_score = max(upstream_score, landslide_risk_score)
        score_accumulator += upstream_score * 0.10
        factors.append({
            "factor": "UPSTREAM_SURGE_DEBRIS",
            "value": f"Debris: {debris_risk_str}",
            "sub_score": round(upstream_score, 1),
            "weight_pct": 10,
            "description": f"Upstream channel differential and slope debris coupling (Score: {upstream_score:.1f})",
        })

        # Final Risk Score Clamp
        final_risk_score = min(100.0, max(0.0, score_accumulator))

        # Risk Level Classification
        if final_risk_score >= self.thresholds.warning_max:
            risk_lvl = FloodRiskLevel.CRITICAL
            recommended_action = "CRITICAL EMERGENCY: Trigger siren network, evacuate low-lying basins & deploy SAR swiftwater units immediately."
        elif final_risk_score >= self.thresholds.watch_max:
            risk_lvl = FloodRiskLevel.WARNING
            recommended_action = "WARNING: Alert local emergency authorities, notify SAR commanders, and prepare designated evacuation corridors."
        elif final_risk_score >= self.thresholds.normal_max:
            risk_lvl = FloodRiskLevel.WATCH
            recommended_action = "WATCH: Elevated water level/precipitation detected. Place rescue teams on active standby."
        else:
            risk_lvl = FloodRiskLevel.NORMAL
            recommended_action = "Nominal hydrological status. Continue standard real-time monitoring."

        # Early Warning Status
        early_warn = "NORMAL_FLOW"
        if accel_cm_min2 > 8.0 or (rise_rate_cm_min >= 10.0 and water_depth_m >= 0.8):
            early_warn = "RAPID_ACCELERATION"
        elif rise_rate_cm_min >= 4.0 or (upstream_water_depth_m and upstream_water_depth_m > water_depth_m + 0.5):
            early_warn = "SURGE_DETECTED"

        confidence_val = round(min(1.0, max(0.2, sensor_quality * (0.95 if not is_stale else 0.4))), 2)

        rise_mps = (rise_rate_cm_min / 100.0) / 60.0
        accel_mps2 = (accel_cm_min2 / 100.0) / 3600.0
        time_to_inund = None
        if rise_mps > 0.0001:
            time_to_inund = max(0.1, (2.0 - water_depth_m) / (rise_mps * 60.0))

        warning_flag = risk_lvl in (FloodRiskLevel.WARNING, FloodRiskLevel.CRITICAL)
        evac_flag = risk_lvl == FloodRiskLevel.CRITICAL or (time_to_inund is not None and time_to_inund < 15.0)
        swiftwater_flag = risk_lvl in (FloodRiskLevel.WARNING, FloodRiskLevel.CRITICAL) and (water_depth_m >= 1.0 or river_flow_mps >= 1.5)

        press_kpa = estimated_pressure_kpa if estimated_pressure_kpa is not None else round((1000.0 * 9.80665 * water_depth_m) / 1000.0, 3)

        assessment = FloodRiskAssessment(
            risk_score=final_risk_score,
            risk_level=risk_lvl,
            confidence=confidence_val,
            early_warning_status=early_warn,
            water_depth_m=water_depth_m,
            estimated_pressure_kpa=press_kpa,
            rise_rate_cm_min=rise_rate_cm_min,
            acceleration_cm_min2=accel_cm_min2,
            rainfall_rate_mm_h=rainfall_rate_mm_h,
            river_flow_mps=river_flow_mps,
            debris_flow_risk=debris_risk_str,
            data_freshness="REALTIME_FRESH" if not is_stale else "STALE",
            contributing_factors=factors,
            recommended_action=recommended_action,
            timestamp=ts,
            pressure_source="non_contact_sensor_estimation",
            mode=mode_label,
        )

        # Dynamic convenience attributes
        assessment.hydrostatic_pressure_kpa = press_kpa
        assessment.rise_rate_mps = rise_mps
        assessment.rate_acceleration_mps2 = accel_mps2
        assessment.measured_distance_m = measured_surface_distance_m if measured_surface_distance_m is not None else max(0.0, 6.0 - water_depth_m)
        assessment.rainfall_intensity_mmh = rainfall_rate_mm_h
        assessment.warning_issued = warning_flag
        assessment.evacuation_recommended = evac_flag
        assessment.swiftwater_rescue_flag = swiftwater_flag
        assessment.time_to_inundation_minutes = time_to_inund
        assessment.reading_quality = "VALID" if not is_stale else "STALE"
        assessment.assessment_timestamp = ts
        assessment.upstream_surge_active = upstream_score >= 10.0
        assessment.debris_damming_risk = debris_risk_str in ("HIGH", "CRITICAL")

        self.last_assessment = assessment
        return assessment

    def process_cycle(
        self,
        measured_surface_distance_m: Optional[float] = None,
        water_depth_m: Optional[float] = None,
        sensor_mount_height_m: float = 6.0,
        rainfall_rate_mmh: float = 0.0,
        flow_velocity_mps: float = 0.0,
        upstream_surge_active: bool = False,
        soil_moisture_pct: float = 40.0,
        slope_tilt_deg: float = 0.0,
        acoustic_rumble_db: float = 30.0,
        is_live_sensor: bool = False,
    ) -> FloodIntelligenceReport:
        if water_depth_m is None and measured_surface_distance_m is not None:
            water_depth_m = max(0.0, sensor_mount_height_m - measured_surface_distance_m)
        elif water_depth_m is None:
            water_depth_m = 1.0

        if measured_surface_distance_m is None:
            measured_surface_distance_m = max(0.0, sensor_mount_height_m - water_depth_m)

        ls_score = min(100.0, (soil_moisture_pct / 75.0) * 50.0 + (slope_tilt_deg / 15.0) * 50.0)
        vib_g = min(1.0, acoustic_rumble_db / 100.0)

        ca = self.evaluate_flood_risk(
            water_depth_m=water_depth_m,
            measured_surface_distance_m=measured_surface_distance_m,
            rainfall_rate_mm_h=rainfall_rate_mmh,
            river_flow_mps=flow_velocity_mps,
            upstream_water_depth_m=(water_depth_m + 0.6) if upstream_surge_active else None,
            landslide_risk_score=ls_score,
            ground_vibration_g=vib_g,
            is_simulation=not is_live_sensor,
        )

        return FloodIntelligenceReport(
            current_assessment=ca,
            system_status="ONLINE",
            alert_summary=ca.recommended_action,
            swiftwater_rescue_recommended=getattr(ca, "swiftwater_rescue_flag", False),
        )

    def get_latest_report(self) -> FloodIntelligenceReport:
        if self.last_assessment is None:
            return self.process_cycle()
        return FloodIntelligenceReport(
            current_assessment=self.last_assessment,
            system_status="ONLINE",
            alert_summary=self.last_assessment.recommended_action,
            swiftwater_rescue_recommended=getattr(self.last_assessment, "swiftwater_rescue_flag", False),
        )


@dataclass
class FloodIntelligenceReport:
    current_assessment: FloodRiskAssessment
    system_status: str = "ONLINE"
    alert_summary: str = ""
    swiftwater_rescue_recommended: bool = False

    def to_dict(self) -> Dict[str, Any]:
        ca_dict = self.current_assessment.to_dict()
        ca_dict["hydrostatic_pressure_kpa"] = getattr(self.current_assessment, "hydrostatic_pressure_kpa", ca_dict.get("estimated_pressure_kpa"))
        ca_dict["rise_rate_mps"] = getattr(self.current_assessment, "rise_rate_mps", 0.0)
        ca_dict["rate_acceleration_mps2"] = getattr(self.current_assessment, "rate_acceleration_mps2", 0.0)
        ca_dict["measured_distance_m"] = getattr(self.current_assessment, "measured_distance_m", 0.0)
        ca_dict["rainfall_intensity_mmh"] = getattr(self.current_assessment, "rainfall_intensity_mmh", 0.0)
        ca_dict["warning_issued"] = getattr(self.current_assessment, "warning_issued", False)
        ca_dict["evacuation_recommended"] = getattr(self.current_assessment, "evacuation_recommended", False)
        ca_dict["swiftwater_rescue_flag"] = getattr(self.current_assessment, "swiftwater_rescue_flag", False)
        ca_dict["time_to_inundation_minutes"] = getattr(self.current_assessment, "time_to_inundation_minutes", None)
        ca_dict["reading_quality"] = getattr(self.current_assessment, "reading_quality", "VALID")
        ca_dict["upstream_surge_active"] = getattr(self.current_assessment, "upstream_surge_active", False)
        ca_dict["debris_damming_risk"] = getattr(self.current_assessment, "debris_damming_risk", False)

        return {
            "current_assessment": ca_dict,
            "system_status": self.system_status,
            "alert_summary": self.alert_summary,
            "swiftwater_rescue_recommended": self.swiftwater_rescue_recommended,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Global Singleton
_FLOOD_INTELLIGENCE_ENGINE: Optional[FloodIntelligenceEngine] = None


def get_flood_intelligence_engine() -> FloodIntelligenceEngine:
    global _FLOOD_INTELLIGENCE_ENGINE
    if _FLOOD_INTELLIGENCE_ENGINE is None:
        _FLOOD_INTELLIGENCE_ENGINE = FloodIntelligenceEngine()
    return _FLOOD_INTELLIGENCE_ENGINE
