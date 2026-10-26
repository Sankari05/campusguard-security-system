"""
fusion_engine.py
-----------------
AI multi-sensor fusion and rescue-prioritization engine.

Pipeline
--------
1. Weighted sensor fusion (radar + thermal + acoustic + CO2 + camera) turns
   raw SensorReadings into a single life-sign **Confidence %** per victim.
   This is deliberately GENERIC and does NOT look up ground-truth victim
   status from models.py - a real detection system only has sensor data,
   not the answer key. Thresholds below are physiologically motivated
   (ambient snow temperature, resting heart-rate floor, CO2 above ambient,
   etc.), not tuned to any specific VictimProfile.

2. A rule-based triage classifier turns Confidence % (+ a couple of
   discrete signal patterns, e.g. deliberate tapping) into one of five
   operational classes:

        HIGH            - confirmed or strongly-corroborated life signs,
                           needs urgent extraction
        MEDIUM          - probable life signs, moderate/partial confidence
        LOW             - weak or unreliable signal, needs re-scan/confirmation
        NO_VITAL_SIGNS  - no life-sign corroboration (covers both "nothing
                           here" and "confirmed fatality")
        SAFE            - visually confirmed, ambulatory, self-evacuating

3. A **hazard-adjusted** Survivor Priority Score (SPS) combines the
   Confidence % with situational hazard context (burial depth, secondary
   collapse/avalanche risk, prolonged exposure time). Hazard context does
   NOT change the medical triage class (that stays a function of sensor
   evidence only) - it changes operational urgency/ordering *within* and
   across classes, which matches real SAR doctrine: a marginal survivor in
   a highly unstable, deep, or long-exposure location gets moved up the
   queue relative to an equally-classified victim in a safer spot.

4. `rank_victims()` implements the triage doctrine ordering:
      urgent survivable cases (HIGH > MEDIUM > LOW)
      before confirmed-fatality recovery (NO_VITAL_SIGNS)
      before safe / self-evacuating cases (SAFE, always last)
   with SPS (descending) as the tie-breaker inside each class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Iterable

from models import SensorType, SensorReading, GPSCoordinate, SensorHealthStatus
from scenario_sensor_profiles import (
    ScenarioSensorProfile,
    SensorRole,
    get_scenario_sensor_profile,
)


# --------------------------------------------------------------------------- #
# Triage classification enum & doctrine ordering
# --------------------------------------------------------------------------- #

class TriageClass(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NO_VITAL_SIGNS = "NO_VITAL_SIGNS"
    SAFE = "SAFE"


# Lower number = rescued sooner. This IS the triage doctrine referenced in
# rank_victims(): survivable urgent cases first, fatality recovery next,
# self-evacuating safe victims last.
TRIAGE_DOCTRINE_ORDER = {
    TriageClass.HIGH: 0,
    TriageClass.MEDIUM: 1,
    TriageClass.LOW: 2,
    TriageClass.NO_VITAL_SIGNS: 3,
    TriageClass.SAFE: 4,
}


# --------------------------------------------------------------------------- #
# Generic physiological reference thresholds (NOT victim-specific)
# --------------------------------------------------------------------------- #

AMBIENT_TEMP_C = -5.0          # typical avalanche debris / snowpack ambient
BODY_TEMP_NORMAL_C = 33.0      # skin/near-surface temp of a warm live person
THERMAL_SCORE_FLOOR_RAW = 0.15  # below this normalized value -> treated as ambient (no heat)

HR_NOISE_FLOOR_BPM = 15.0      # radar readings below this are treated as sensor noise, not a pulse
HR_SCORE_SPAN_BPM = 60.0       # bpm span used to normalize radar_score to 1.0

ACOUSTIC_DB_FLOOR = 2.0
ACOUSTIC_DB_SPAN = 50.0
ACOUSTIC_TAP_THRESHOLD_DB = 20.0     # audible deliberate tapping / calling / clear breathing
MOTION_SPAN = 0.6
MOTION_TAP_THRESHOLD = 0.12          # deliberate/repeated movement threshold
KIT_VIBRATION_TAP_THRESHOLD_G = 0.10 # a conscious survivor rhythmically banging on their own kit
                                      # registers as a vibration spike on that kit's IMU, corroborating
                                      # the acoustic/motion tap signals - comfortably above ambient kit
                                      # jitter (baseline ~0.02g) but below a full disturbance-event peak

AMBIENT_CO2_PPM = 410.0
CO2_SCORE_SPAN_PPM = 1090.0

CAMERA_SAFE_THRESHOLD = 0.6          # visual confirmation strong enough to call "seen"
MOTION_SAFE_THRESHOLD = 0.5          # combined with camera => ambulatory / self-evacuating
THERMAL_SAFE_MIN_C = 25.0            # near-normal body temp, not just "warmer than ambient"

# Fusion weights for Confidence % (must sum to 1.0)
WEIGHT_RADAR = 0.35
WEIGHT_THERMAL = 0.25
WEIGHT_ACOUSTIC = 0.25
WEIGHT_CO2 = 0.10
WEIGHT_CAMERA = 0.05

# Configurable Subsurface UWB Bioradar Weight for Landslide Scenario
# NOTE: This weight is a SIMULATION / DESIGN PARAMETER, not experimentally validated.
WEIGHT_UWB_LANDSLIDE = 0.40

# Triage confidence-% thresholds
HIGH_THRESHOLD_PCT = 30.0
TAP_HIGH_MIN_PCT = 15.0          # lower bar for HIGH when deliberate tapping is present
MEDIUM_THRESHOLD_PCT = 15.0
LOW_THRESHOLD_PCT = 5.0
# below LOW_THRESHOLD_PCT -> NO_VITAL_SIGNS

# Hazard multiplier caps
HAZARD_DEPTH_MAX_BONUS = 0.15
HAZARD_SECONDARY_BONUS = 0.30
HAZARD_EXPOSURE_MAX_BONUS = 0.10
HAZARD_DEPTH_REF_M = 3.0
HAZARD_EXPOSURE_REF_MIN = 240.0

# Water is an urgency signal, not a life-sign score (see HazardContext below):
# how deep and how fast rising water is doesn't tell you whether the victim
# is alive, it tells you how much time rescue has left. So it's folded into
# the hazard multiplier bonus terms, not the Confidence % sensor weights.
WATER_RISK_MAX_BONUS = 0.25
WATER_RISK_REF_CM = 150.0
WATER_RISING_URGENCY_MAX_BONUS = 0.20
WATER_RISING_REF_CM_PER_CYCLE = 4.0

# Current velocity (flow speed) at the victim's location: fast-moving water
# is a sweeping/approach-risk hazard independent of depth - a shallow but
# fast-flowing current can still knock a rescuer or victim off their feet.
WATER_FLOW_RISK_MAX_BONUS = 0.20
WATER_FLOW_REF_MS = 2.5   # ~2.5 m/s = strong current, adult can be swept off feet

# Site-wide rain intensity: heavy rain makes rescue operations riskier
# (visibility, footing, swift-water conditions) independent of the water
# level/flow at any individual victim's location.
RAIN_RISK_MAX_BONUS = 0.15
RAIN_RISK_REF_MM_HR = 40.0   # ~40mm/hr = intense monsoon downpour, visibility/footing badly affected

# Soil saturation is a landslide-risk amplifier, not a standalone hazard: a
# saturated slope only matters when there's an active secondary hazard path
# (secondary_hazard=True) to slide - it's a cross-coupled bonus, gated on
# that flag, rather than a free-standing term like rain/water above.
SOIL_SATURATION_LANDSLIDE_THRESHOLD_PCT = 60.0   # above this, saturated slope = active slide risk
SOIL_RISK_MAX_BONUS = 0.25

# Ground vibration (mm/s PGV) from the shared seismic sensor: elevated
# ambient/aftershock shaking raises urgency for further-collapse risk on
# already-unstable structures (earthquake scenario), independent of a
# victim's actual life-sign evidence.
VIBRATION_RISK_MAX_BONUS = 0.20
VIBRATION_RISK_REF_MM_S = 20.0   # ~20mm/s PGV = moderate structural shaking, further-collapse risk

# Compound risk: an aftershock striking soil already past the landslide
# threshold (Step 7) is worse than either alone - active tremor is what
# actually triggers a saturated slope to move.
AFTERSHOCK_SOIL_COMPOUND_BONUS = 0.15   # extra bonus when active aftershock hits already-saturated soil

# Ground/structure tilt (degrees) from the shared inclinometer (Step 9):
# unlike vibration, a tilt reading is a ratchet - it does NOT decay back to
# baseline, so a sustained tilt reflects a real, permanent shift/settling
# event rather than a passing tremor. Gated on secondary_hazard, same as
# soil, because tilt only matters as a hazard signal when there's an active
# slope/structural-failure path for it to indicate progress along.
TILT_DANGER_THRESHOLD_DEG = 5.0    # above this, slope/structure is significantly out of level - active instability
TILT_RISK_MAX_BONUS = 0.30         # highest single term alongside secondary_hazard - a shifted slope is as acute as a confirmed active hazard path
TILT_RISK_REF_DEG = 15.0

# Kit-level IMU (Step 10): a single victim's own kit registering a fresh
# tilt shift or vibration spike (see sensor_simulator._step_kit_tilt()/
# _step_kit_vibration(), surfaced via SensorSimulator.imu_report()'s
# kit_disturbed flag). Deliberately smaller than VIBRATION_RISK_MAX_BONUS/
# TILT_RISK_MAX_BONUS above and NOT gated on secondary_hazard: this is a
# localized, noisier signal (could be debris settling, an animal, a
# rescuer nearby, or the victim themselves moving) - not a confirmed
# slope/structure failure the way the site-wide seismic/tilt sensors are.
KIT_IMU_RISK_BONUS = 0.10

# Ambient temperature & humidity (site-wide environmental sensors): these
# feed the hazard multiplier as an exposure-risk signal, the same way rain
# does - they say nothing about whether a given victim is alive (that stays
# purely a function of sensor evidence, per the design principle in
# fusion_engine's module docstring), only how much time/risk rescue has
# before ambient conditions themselves become dangerous.
#
# Cold exposure: below a threshold air temperature, every additional degree
# of cold raises hypothermia risk for anyone buried/exposed - an
# uncoupled bonus (no secondary_hazard gate needed), same shape as rain.
COLD_EXPOSURE_THRESHOLD_C = 5.0     # below this, cold starts adding hypothermia-risk urgency
COLD_EXPOSURE_REF_C = -20.0         # bonus saturates at this air temperature
COLD_EXPOSURE_MAX_BONUS = 0.20

# Heat + humidity: unlike cold, heat alone isn't much of a rescue-operation
# risk - it's heat *combined with* high humidity (poor evaporative cooling,
# heat-stroke/dehydration risk for both victims and rescue teams) that
# matters, so this is a compound bonus gated on both crossing their
# thresholds simultaneously - same pattern as the aftershock/soil compound
# bonus above.
HEAT_HUMIDITY_TEMP_THRESHOLD_C = 32.0
HEAT_HUMIDITY_PCT_THRESHOLD = 70.0
HEAT_HUMIDITY_TEMP_REF_C = 45.0
HEAT_HUMIDITY_MAX_BONUS = 0.20

# Barometric pressure drop bonus (cyclone / storm surge urgency)
PRESSURE_DROP_RISK_THRESHOLD_HPA = 1000.0
PRESSURE_DROP_RISK_REF_HPA = 960.0
PRESSURE_DROP_RISK_MAX_BONUS = 0.20

# Raised from 1.6 -> 1.9 -> 2.1 -> 2.5 to make room for the seismic bonus
# terms above; a victim hit by structural aftershock risk on top of every
# other hazard would otherwise hit the old cap and become indistinguishable
# in urgency from a lower-risk victim.
# NOTE: the sum of all max bonuses (depth 0.15 + secondary 0.30 + exposure
# 0.10 + water_level 0.25 + water_rising 0.20 + water_flow 0.20 + rain 0.15
# + soil 0.25 + vibration 0.20 + aftershock/soil compound 0.15 + tilt 0.30
# + cold exposure 0.20 + heat/humidity compound 0.20 + kit IMU 0.10 + pressure drop 0.20 = 2.95,
# on top of the 1.0 base) already exceeds this cap - that's intentional
# headroom, multiplier() always clamps via min(raw, CAP) so a victim hit by
# every hazard simultaneously still saturates cleanly at 2.5 rather than
# needing the cap raised every time a new bonus term is added.
HAZARD_MULTIPLIER_CAP = 2.5


# --------------------------------------------------------------------------- #
# Hazard context
# --------------------------------------------------------------------------- #

@dataclass
class HazardContext:
    """Situational hazard factors that affect rescue URGENCY, not medical class."""
    burial_depth_m: float = 0.0
    secondary_hazard: bool = False    # e.g. active avalanche path, unstable seracs, crevasse risk
    exposure_minutes: float = 0.0     # estimated time since burial/exposure began
    water_level_cm: float = 0.0                  # current flood water depth at victim location
    water_rising_rate_cm_per_cycle: float = 0.0   # how fast that water is climbing
    water_flow_ms: float = 0.0                    # current velocity/flow speed at victim location
    rainfall_mm_hr: float = 0.0                    # site-wide current rain intensity
    soil_moisture_pct: float = 0.0                  # site-wide current soil saturation
    vibration_mm_s: float = 0.0                      # site-wide current ground vibration (PGV)
    aftershock_active: bool = False                   # site-wide: an aftershock is actively decaying
    tilt_deg: float = 0.0                              # site-wide current ground/structure tilt (does not decay)
    ambient_temp_c: float = 15.0                        # site-wide current air temperature (deg C)
    humidity_pct: float = 50.0                          # site-wide current relative humidity (0-100)
    barometric_pressure_hpa: float = 1013.25            # site-wide barometric pressure (hPa)
    kit_disturbed: bool = False                          # this victim's own kit IMU just registered a tilt shift or vibration spike this cycle

    def multiplier_breakdown(self, scenario_id: Optional[str] = None) -> dict:
        """
        Same computation as multiplier() below, but returns every individual
        bonus term instead of just the final scalar - purely a read-only
        diagnostic for the admin/judge-facing explainability page (Step 15).
        Does NOT change triage classification or SPS math; multiplier()
        calls this and sums it, so the two can never drift out of sync.
        Supports scenario_id filtering so inactive hazard channels yield 0.0.
        """
        profile = get_scenario_sensor_profile(scenario_id) if scenario_id else None

        depth_bonus = HAZARD_DEPTH_MAX_BONUS * min(self.burial_depth_m, HAZARD_DEPTH_REF_M) / HAZARD_DEPTH_REF_M
        secondary_bonus = HAZARD_SECONDARY_BONUS if self.secondary_hazard else 0.0
        exposure_bonus = HAZARD_EXPOSURE_MAX_BONUS * min(self.exposure_minutes, HAZARD_EXPOSURE_REF_MIN) / HAZARD_EXPOSURE_REF_MIN
        
        # Hydrological bonuses
        water_level_bonus = WATER_RISK_MAX_BONUS * min(self.water_level_cm, WATER_RISK_REF_CM) / WATER_RISK_REF_CM
        water_rising_bonus = (
            WATER_RISING_URGENCY_MAX_BONUS
            * min(self.water_rising_rate_cm_per_cycle, WATER_RISING_REF_CM_PER_CYCLE)
            / WATER_RISING_REF_CM_PER_CYCLE
        )
        water_flow_bonus = (
            WATER_FLOW_RISK_MAX_BONUS
            * min(self.water_flow_ms, WATER_FLOW_REF_MS)
            / WATER_FLOW_REF_MS
        )
        rain_bonus = RAIN_RISK_MAX_BONUS * min(self.rainfall_mm_hr, RAIN_RISK_REF_MM_HR) / RAIN_RISK_REF_MM_HR

        if profile:
            if not profile.is_active(SensorType.WATER_LEVEL):
                water_level_bonus = 0.0
                water_rising_bonus = 0.0
            if not profile.is_active(SensorType.WATER_FLOW):
                water_flow_bonus = 0.0
            if not profile.is_active(SensorType.RAINFALL_INTENSITY):
                rain_bonus = 0.0

        soil_bonus = 0.0
        if self.secondary_hazard and self.soil_moisture_pct >= SOIL_SATURATION_LANDSLIDE_THRESHOLD_PCT:
            over_threshold = self.soil_moisture_pct - SOIL_SATURATION_LANDSLIDE_THRESHOLD_PCT
            soil_bonus = SOIL_RISK_MAX_BONUS * min(over_threshold / (100.0 - SOIL_SATURATION_LANDSLIDE_THRESHOLD_PCT), 1.0)
        vibration_bonus = VIBRATION_RISK_MAX_BONUS * min(self.vibration_mm_s, VIBRATION_RISK_REF_MM_S) / VIBRATION_RISK_REF_MM_S

        # Compound risk: an aftershock striking soil already past the
        # landslide threshold (Step 7) is worse than either alone
        compound_bonus = 0.0
        if self.aftershock_active and self.soil_moisture_pct >= SOIL_SATURATION_LANDSLIDE_THRESHOLD_PCT:
            compound_bonus = AFTERSHOCK_SOIL_COMPOUND_BONUS

        # Tilt (Step 9): structural/slope instability
        tilt_bonus = 0.0
        if self.secondary_hazard and self.tilt_deg >= TILT_DANGER_THRESHOLD_DEG:
            tilt_bonus = TILT_RISK_MAX_BONUS * min(
                (self.tilt_deg - TILT_DANGER_THRESHOLD_DEG) / (TILT_RISK_REF_DEG - TILT_DANGER_THRESHOLD_DEG),
                1.0,
            )

        if profile:
            if not profile.is_active(SensorType.SOIL_MOISTURE):
                soil_bonus = 0.0
                compound_bonus = 0.0
            if not profile.is_active(SensorType.IMU_VIBRATION):
                vibration_bonus = 0.0
            if not profile.is_active(SensorType.IMU_TILT):
                tilt_bonus = 0.0

        # Cold exposure
        cold_bonus = 0.0
        if self.ambient_temp_c <= COLD_EXPOSURE_THRESHOLD_C:
            over_threshold = COLD_EXPOSURE_THRESHOLD_C - self.ambient_temp_c
            span = COLD_EXPOSURE_THRESHOLD_C - COLD_EXPOSURE_REF_C
            cold_bonus = COLD_EXPOSURE_MAX_BONUS * min(over_threshold / span, 1.0)

        # Heat + humidity (compound)
        heat_humidity_bonus = 0.0
        if (
            self.ambient_temp_c >= HEAT_HUMIDITY_TEMP_THRESHOLD_C
            and self.humidity_pct >= HEAT_HUMIDITY_PCT_THRESHOLD
        ):
            over_threshold = self.ambient_temp_c - HEAT_HUMIDITY_TEMP_THRESHOLD_C
            span = HEAT_HUMIDITY_TEMP_REF_C - HEAT_HUMIDITY_TEMP_THRESHOLD_C
            heat_humidity_bonus = HEAT_HUMIDITY_MAX_BONUS * min(over_threshold / span, 1.0)

        if profile and not profile.is_active(SensorType.TEMPERATURE):
            cold_bonus = 0.0
            heat_humidity_bonus = 0.0

        # Kit-level IMU
        kit_bonus = KIT_IMU_RISK_BONUS if self.kit_disturbed else 0.0

        # Barometric pressure drop
        pressure_bonus = 0.0
        if self.barometric_pressure_hpa <= PRESSURE_DROP_RISK_THRESHOLD_HPA:
            over_drop = PRESSURE_DROP_RISK_THRESHOLD_HPA - self.barometric_pressure_hpa
            span = PRESSURE_DROP_RISK_THRESHOLD_HPA - PRESSURE_DROP_RISK_REF_HPA
            pressure_bonus = PRESSURE_DROP_RISK_MAX_BONUS * min(over_drop / span, 1.0)

        if profile and not profile.is_active(SensorType.BAROMETRIC_PRESSURE):
            pressure_bonus = 0.0

        return {
            "base": 1.0,
            "depth": depth_bonus,
            "secondary_hazard": secondary_bonus,
            "exposure": exposure_bonus,
            "water_level": water_level_bonus,
            "water_rising": water_rising_bonus,
            "water_flow": water_flow_bonus,
            "rain": rain_bonus,
            "soil": soil_bonus,
            "vibration": vibration_bonus,
            "aftershock_soil_compound": compound_bonus,
            "tilt": tilt_bonus,
            "cold_exposure": cold_bonus,
            "heat_humidity_compound": heat_humidity_bonus,
            "kit_imu": kit_bonus,
            "pressure_drop": pressure_bonus,
        }

    def multiplier(self, scenario_id: Optional[str] = None) -> float:
        breakdown = self.multiplier_breakdown(scenario_id=scenario_id)
        return min(sum(breakdown.values()), HAZARD_MULTIPLIER_CAP)


DEFAULT_HAZARD = HazardContext()


# --------------------------------------------------------------------------- #
# Fusion result
# --------------------------------------------------------------------------- #

@dataclass
class FusionResult:
    victim_id: Optional[str]
    confidence_pct: float
    triage_class: TriageClass
    sps: float
    hazard_multiplier: float
    tapping_detected: bool
    reliability: float
    score_breakdown: dict            # sensor_type.value -> normalized sub-score (0-1)
    contributing_sensors: list       # sensor_type.value list actually present in the input
    hazard_breakdown: dict = field(default_factory=dict)   # HazardContext.multiplier_breakdown() output, for the explainability page (Step 15)
    location: Optional[GPSCoordinate] = None
    notes: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = {
            "victim_id": self.victim_id,
            "confidence_pct": round(self.confidence_pct, 2),
            "triage_class": self.triage_class.value,
            "sps": round(self.sps, 2),
            "hazard_multiplier": round(self.hazard_multiplier, 3),
            "tapping_detected": self.tapping_detected,
            "reliability": round(self.reliability, 2),
            "score_breakdown": {k: round(v, 3) for k, v in self.score_breakdown.items()},
            "contributing_sensors": self.contributing_sensors,
            "hazard_breakdown": {k: round(v, 4) for k, v in self.hazard_breakdown.items()},
            "notes": self.notes,
            "timestamp": self.timestamp,
        }
        if self.location is not None:
            d["location"] = {
                "latitude": self.location.latitude,
                "longitude": self.location.longitude,
                "altitude_m": self.location.altitude_m,
            }
        return d


# --------------------------------------------------------------------------- #
# Internal scoring helpers
# --------------------------------------------------------------------------- #

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _average_by_sensor(readings: Iterable[SensorReading]) -> dict:
    """
    Average multiple readings of the same sensor type, accounting for sensor
    health state (ONLINE, DEGRADED, OFFLINE, ERROR).
    """
    buckets: dict = {}
    for r in readings:
        buckets.setdefault(r.sensor_type, []).append(r)
    averaged = {}
    for stype, rs in buckets.items():
        # Exclude readings explicitly marked OFFLINE or ERROR from providing positive values
        active_rs = [
            r for r in rs
            if getattr(r, "status", SensorHealthStatus.ONLINE) not in (
                SensorHealthStatus.OFFLINE,
                SensorHealthStatus.ERROR,
                "OFFLINE",
                "ERROR",
            )
        ]
        if not active_rs:
            # All readings for this modality are offline/errored
            averaged[stype] = (0.0, 0.0)
            continue

        total_weight = 0.0
        weighted_val = 0.0
        weighted_conf = 0.0
        for r in active_rs:
            st = getattr(r, "status", SensorHealthStatus.ONLINE)
            health_factor = 0.5 if st in (SensorHealthStatus.DEGRADED, "DEGRADED") else 1.0
            conf = max(0.0, min(1.0, getattr(r, "confidence", 1.0))) * health_factor
            weighted_val += r.value * conf
            weighted_conf += conf
            total_weight += conf

        if total_weight > 0.0:
            avg_value = weighted_val / total_weight
            avg_conf = weighted_conf / len(active_rs)
        else:
            avg_value = sum(r.value for r in active_rs) / len(active_rs)
            avg_conf = sum(r.confidence for r in active_rs) / len(active_rs)

        averaged[stype] = (avg_value, avg_conf)
    return averaged


def _radar_score(bpm: float) -> float:
    if bpm < HR_NOISE_FLOOR_BPM:
        return 0.0
    return _clamp01((bpm - HR_NOISE_FLOOR_BPM) / HR_SCORE_SPAN_BPM)


def _thermal_score(temp_c: float) -> float:
    raw = (temp_c - AMBIENT_TEMP_C) / (BODY_TEMP_NORMAL_C - AMBIENT_TEMP_C)
    if raw < THERMAL_SCORE_FLOOR_RAW:
        return 0.0
    return _clamp01(raw)


def _acoustic_score(db: float, motion: float) -> float:
    db_component = _clamp01((db - ACOUSTIC_DB_FLOOR) / ACOUSTIC_DB_SPAN)
    motion_component = _clamp01(motion / MOTION_SPAN)
    return max(db_component, motion_component)


def _co2_score(ppm: float) -> float:
    return _clamp01((ppm - AMBIENT_CO2_PPM) / CO2_SCORE_SPAN_PPM)


def _camera_score(conf: float) -> float:
    return _clamp01(conf)


# --------------------------------------------------------------------------- #
# Core fusion function
# --------------------------------------------------------------------------- #

def fuse_victim(
    readings: list,
    hazard: Optional[HazardContext] = None,
    victim_id: Optional[str] = None,
    location: Optional[GPSCoordinate] = None,
    scenario_id: Optional[str] = None,
) -> FusionResult:
    """
    Fuse one victim's sensor readings (a single cycle, or several cycles for
    smoothing - same-type readings are averaged) into a FusionResult
    containing Confidence %, triage class, and hazard-adjusted SPS.

    Passing an empty list represents "no sensor data for this location"
    (e.g. empty rubble scanned with nothing detected) and always resolves
    to NO_VITAL_SIGNS with 0% confidence.
    """
    hazard = hazard or DEFAULT_HAZARD

    if not readings:
        result = FusionResult(
            victim_id=victim_id,
            confidence_pct=0.0,
            triage_class=TriageClass.NO_VITAL_SIGNS,
            sps=0.0,
            hazard_multiplier=hazard.multiplier(scenario_id=scenario_id),
            tapping_detected=False,
            reliability=0.0,
            score_breakdown={},
            contributing_sensors=[],
            hazard_breakdown=hazard.multiplier_breakdown(scenario_id=scenario_id),
            location=location,
            notes="No sensor data received - no survivor indicators detected.",
        )
        return result

    by_sensor = _average_by_sensor(readings)
    contributing = [st.value for st in by_sensor.keys()]

    def value_of(stype: SensorType, default: float) -> float:
        return by_sensor[stype][0] if stype in by_sensor else default

    thermal_c = value_of(SensorType.THERMAL_IMAGING, AMBIENT_TEMP_C)
    hr_bpm = value_of(SensorType.HEART_RATE_RADAR, 0.0)
    acoustic_db = value_of(SensorType.ACOUSTIC, 0.0)
    motion = value_of(SensorType.PIR_MOTION, 0.0)
    co2_ppm = value_of(SensorType.CO2, AMBIENT_CO2_PPM)
    camera_conf = value_of(SensorType.RGB_CAMERA, 0.0)
    kit_vibration_g = value_of(SensorType.IMU_VIBRATION, 0.0)

    radar_score = _radar_score(hr_bpm)
    thermal_score = _thermal_score(thermal_c)
    acoustic_score = _acoustic_score(acoustic_db, motion)
    co2_score = _co2_score(co2_ppm)
    camera_score = _camera_score(camera_conf)

    has_uwb = SensorType.UWB_BIORADAR in by_sensor
    uwb_val = value_of(SensorType.UWB_BIORADAR, 0.0)
    uwb_score = _clamp01(uwb_val / 100.0)

    is_landslide = bool(scenario_id and ("landslide" in str(scenario_id).lower() or "mudslide" in str(scenario_id).lower() or "debris" in str(scenario_id).lower()))

    if is_landslide or has_uwb:
        # Landslide / Subsurface SAR fusion equation incorporating UWB Bioradar evidence
        # NOTE: Weight coefficients are configurable simulation parameters.
        raw_fused = (
            WEIGHT_UWB_LANDSLIDE * uwb_score
            + 0.20 * acoustic_score
            + 0.15 * thermal_score
            + 0.15 * co2_score
            + 0.10 * camera_score
        )
    else:
        raw_fused = (
            WEIGHT_RADAR * radar_score
            + WEIGHT_THERMAL * thermal_score
            + WEIGHT_ACOUSTIC * acoustic_score
            + WEIGHT_CO2 * co2_score
            + WEIGHT_CAMERA * camera_score
        )

    # measurement reliability = average sensor self-reported confidence
    # (this is where battery/signal degradation from sensor_simulator.py
    # feeds in - a technically "strong" reading from a nearly-dead battery
    # should not be trusted as much as the same reading from a fresh unit)
    active_confs = [conf for _, conf in by_sensor.values() if conf > 0.0]
    reliability = (sum(active_confs) / len(active_confs)) if active_confs else 0.0

    confidence_pct = 100.0 * raw_fused * reliability

    tapping_detected = (
        acoustic_db > ACOUSTIC_TAP_THRESHOLD_DB
        or motion > MOTION_TAP_THRESHOLD
        or kit_vibration_g > KIT_VIBRATION_TAP_THRESHOLD_G
    )
    visually_confirmed_safe = (
        camera_score >= CAMERA_SAFE_THRESHOLD
        and motion >= MOTION_SAFE_THRESHOLD
        and thermal_c >= THERMAL_SAFE_MIN_C
    )

    # Check for Animal vs Human classification in metadata
    is_confirmed_animal = False
    has_human_classification = False
    for r in readings:
        raw = getattr(r, "raw_data", {}) or {}
        cls_str = str(raw.get("classification", "")).upper()
        det_str = str(raw.get("detection_type", "")).upper()
        if "ANIMAL" in cls_str or "ANIMAL" in det_str:
            is_confirmed_animal = True
        if "HUMAN" in cls_str or "HUMAN" in det_str:
            has_human_classification = True

    if is_confirmed_animal and not has_human_classification and hr_bpm < HR_NOISE_FLOOR_BPM:
        confidence_pct = 0.0
        triage_class = TriageClass.NO_VITAL_SIGNS
        notes = "Animal signature detected (non-human); survivor classification suppressed."
    else:
        triage_class, notes = _classify(confidence_pct, tapping_detected, visually_confirmed_safe)

    hazard_breakdown = hazard.multiplier_breakdown(scenario_id=scenario_id)
    hazard_multiplier = hazard.multiplier(scenario_id=scenario_id)
    sps = confidence_pct * hazard_multiplier

    score_breakdown = {
        SensorType.HEART_RATE_RADAR.value: radar_score,
        SensorType.THERMAL_IMAGING.value: thermal_score,
        SensorType.ACOUSTIC.value: acoustic_score,
        SensorType.CO2.value: co2_score,
        SensorType.RGB_CAMERA.value: camera_score,
    }
    if SensorType.UWB_BIORADAR in by_sensor or is_landslide:
        score_breakdown[SensorType.UWB_BIORADAR.value] = uwb_score
    if SensorType.WATER_LEVEL in by_sensor:
        # Display-only: water level is surfaced here so the UI/API can show
        # it alongside the other sensor readings, but it is intentionally
        # NOT part of raw_fused / Confidence % above - it's an urgency
        # signal (see HazardContext.multiplier()), not a life-sign score.
        # Don't fold it into the weighted sum without re-deriving the
        # WEIGHT_* constants; it would silently change Confidence % math.
        score_breakdown[SensorType.WATER_LEVEL.value] = _clamp01(
            by_sensor[SensorType.WATER_LEVEL][0] / WATER_RISK_REF_CM
        )
    if SensorType.WATER_FLOW in by_sensor:
        # Same rationale as WATER_LEVEL above: display-only, not part of
        # Confidence % - current speed is an urgency signal (hazard
        # multiplier), not evidence of life.
        score_breakdown[SensorType.WATER_FLOW.value] = _clamp01(
            by_sensor[SensorType.WATER_FLOW][0] / WATER_FLOW_REF_MS
        )

    return FusionResult(
        victim_id=victim_id,
        confidence_pct=confidence_pct,
        triage_class=triage_class,
        sps=sps,
        hazard_multiplier=hazard_multiplier,
        tapping_detected=tapping_detected,
        reliability=reliability,
        score_breakdown=score_breakdown,
        contributing_sensors=contributing,
        hazard_breakdown=hazard_breakdown,
        location=location,
        notes=notes,
    )


def _classify(confidence_pct: float, tapping_detected: bool, visually_confirmed_safe: bool):
    if visually_confirmed_safe:
        return TriageClass.SAFE, "Visually confirmed, ambulatory - self-evacuating."

    if tapping_detected and confidence_pct >= TAP_HIGH_MIN_PCT:
        return TriageClass.HIGH, "Deliberate tapping/calling detected with corroborating vitals."

    if confidence_pct >= HIGH_THRESHOLD_PCT:
        return TriageClass.HIGH, "Strong multi-sensor corroboration of life signs."

    if confidence_pct >= MEDIUM_THRESHOLD_PCT:
        return TriageClass.MEDIUM, "Probable life signs, moderate confidence."

    if confidence_pct >= LOW_THRESHOLD_PCT:
        return TriageClass.LOW, "Weak or unreliable signal - recommend re-scan."

    return TriageClass.NO_VITAL_SIGNS, "No corroborated life signs detected."


# --------------------------------------------------------------------------- #
# Multi-victim helpers
# --------------------------------------------------------------------------- #

def group_readings_by_victim(readings: list) -> dict:
    """Group a flat list of SensorReadings (e.g. one simulator cycle) by victim_id."""
    grouped: dict = {}
    for r in readings:
        grouped.setdefault(r.victim_id, []).append(r)
    return grouped


def fuse_all(
    readings_by_victim: dict,
    hazard_by_victim: Optional[dict] = None,
    locations_by_victim: Optional[dict] = None,
    scenario_id: Optional[str] = None,
) -> dict:
    """Run fuse_victim() for every victim_id in readings_by_victim. Returns dict[id]->FusionResult."""
    hazard_by_victim = hazard_by_victim or {}
    locations_by_victim = locations_by_victim or {}
    results = {}
    for victim_id, readings in readings_by_victim.items():
        hazard = hazard_by_victim.get(victim_id)
        location = locations_by_victim.get(victim_id) or (readings[0].location if readings else None)
        results[victim_id] = fuse_victim(
            readings,
            hazard=hazard,
            victim_id=victim_id,
            location=location,
            scenario_id=scenario_id,
        )
    return results


def rank_victims(results: Iterable[FusionResult]) -> list:
    """
    Priority queue: order ALL currently-detected victims by real triage doctrine.

        HIGH (0) < MEDIUM (1) < LOW (2) < NO_VITAL_SIGNS (3) < SAFE (4)

    i.e. urgent survivable cases first, confirmed-fatality recovery next,
    safe/self-evacuating victims last. Within the same class, higher
    hazard-adjusted SPS is rescued first.
    """
    return sorted(
        results,
        key=lambda r: (TRIAGE_DOCTRINE_ORDER[r.triage_class], -r.sps),
    )


# --------------------------------------------------------------------------- #
# Geospatial Distance & Nearest-Entity Helpers
# --------------------------------------------------------------------------- #

def calculate_geospatial_distance(
    loc1: GPSCoordinate | dict | tuple,
    loc2: GPSCoordinate | dict | tuple,
) -> float:
    """Calculate geodesic distance in meters between two coordinates."""
    def _to_coord(loc):
        if isinstance(loc, GPSCoordinate):
            return loc
        if isinstance(loc, dict):
            return GPSCoordinate(latitude=loc.get("latitude", 0.0), longitude=loc.get("longitude", 0.0), altitude_m=loc.get("altitude_m"))
        if isinstance(loc, (list, tuple)) and len(loc) >= 2:
            return GPSCoordinate(latitude=loc[0], longitude=loc[1])
        return GPSCoordinate(latitude=0.0, longitude=0.0)

    c1 = _to_coord(loc1)
    c2 = _to_coord(loc2)
    return c1.haversine_distance_to(c2)


def find_nearest_survivor(
    reference_coord: GPSCoordinate | dict,
    survivors: dict | list,
) -> tuple[Optional[str], float]:
    """Find the closest survivor to a given reference coordinate. Returns (victim_id, distance_m)."""
    nearest_id = None
    min_dist = float("inf")

    if isinstance(survivors, dict):
        for vid, loc in survivors.items():
            dist = calculate_geospatial_distance(reference_coord, loc)
            if dist < min_dist:
                min_dist = dist
                nearest_id = vid
    elif isinstance(survivors, (list, tuple)):
        for item in survivors:
            vid = item.get("victim_id") if isinstance(item, dict) else getattr(item, "victim_id", None)
            loc = item.get("location") if isinstance(item, dict) else getattr(item, "location", None)
            if loc:
                dist = calculate_geospatial_distance(reference_coord, loc)
                if dist < min_dist:
                    min_dist = dist
                    nearest_id = vid

    return nearest_id, (min_dist if nearest_id is not None else 0.0)


def find_nearest_rescue_team(
    target_coord: GPSCoordinate | dict,
    teams: dict | list,
) -> tuple[Optional[str], float]:
    """Find the closest rescue team to a target coordinate. Returns (team_id, distance_m)."""
    nearest_id = None
    min_dist = float("inf")

    if isinstance(teams, dict):
        for tid, loc in teams.items():
            dist = calculate_geospatial_distance(target_coord, loc)
            if dist < min_dist:
                min_dist = dist
                nearest_id = tid
    elif isinstance(teams, (list, tuple)):
        for item in teams:
            tid = item.get("team_id") or item.get("id") if isinstance(item, dict) else getattr(item, "team_id", None)
            loc = item.get("location") if isinstance(item, dict) else getattr(item, "location", None)
            if loc:
                dist = calculate_geospatial_distance(target_coord, loc)
                if dist < min_dist:
                    min_dist = dist
                    nearest_id = tid

    return nearest_id, (min_dist if nearest_id is not None else 0.0)
