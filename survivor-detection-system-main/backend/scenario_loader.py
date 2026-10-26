"""
scenario_loader.py
--------------------
Loads disaster-scenario configuration (victim profiles, hazard context,
site origin, and rescue-team templates) from JSON files under
backend/scenarios/.

This is what makes the system "multi-disaster": the Himalaya avalanche
scenario used to be hardcoded directly into models.py and api.py. It's
now just one config file (scenarios/himalaya_avalanche.json) alongside
others (earthquake, flood, ...). Adding a new disaster scenario to the
report/demo is a matter of dropping in a new JSON file - no code changes
required - as long as it follows the schema documented below.

Schema (top-level JSON object)
-------------------------------
{
  "scenario_id":   str,   required, MUST match the filename (without .json)
  "name":          str,   required, human-readable scenario name
  "description":   str,   optional, longer blurb for docs/UI
  "site_label":    str,   optional, short label shown in the dashboard header
  "site_origin":   {"latitude": float, "longitude": float, "altitude_m": float},
                    required - reference point for rescue-team placement

  "rescue_teams": [        optional, defaults to [] (no auto-dispatch teams)
    {
      "team_id":    str,   required
      "team_name":  str,   required
      "lat_offset": float, optional, default 0.0 - team start position is
      "lon_offset": float, optional, default 0.0    site_origin + offset
      "members":    int,   optional, default 2
    }, ...
  ],

  "victims": [              required, at least 1
    {
      "victim_id":  str,    required
      "label":      str,    required
      "status":     str,    required, one of models.VictimStatus values
                             (safe | minor_injury | critical | deceased | unknown)
      "location":   {"latitude": float, "longitude": float, "altitude_m": float},
      "burial_depth_m": float, optional, default 0.0
      "signature_range": {    required - expected (min, max) sensor output
        "thermal_imaging_c":     [min, max],
        "pir_motion":            [min, max],
        "acoustic_db":           [min, max],
        "co2_ppm":               [min, max],
        "heart_rate_radar_bpm":  [min, max],
        "rgb_camera_conf":       [min, max]
      },
      "notes": str, optional,
      "hazard": {              optional, defaults to no hazard bonus
        "burial_depth_m":    float, optional, default 0.0
        "secondary_hazard":  bool,  optional, default false
        "exposure_minutes":  float, optional, default 0.0
      }
    }, ...
  ],

  "site_environment": {    optional, defaults to no rainfall (dry scenario)
    "initial_rainfall_mm_hr":       float, optional, default 0.0
    "rainfall_volatility_mm_hr":    float, optional, default 3.0
    "rain_to_water_rise_amplifier": float, optional, default 0.06
    "initial_soil_moisture_pct":              float, optional, default 0.0
    "soil_moisture_volatility_pct":           float, optional, default 1.5
    "soil_saturation_from_rain_pct_per_mm_hr": float, optional, default 0.35,
    "baseline_vibration_mm_s":       float, optional, default 0.5 - ambient microtremor (mm/s PGV)
    "aftershock_prob_per_cycle":     float, optional, default 0.0 - 0 = quiet site, no aftershocks
    "aftershock_peak_min_mm_s":      float, optional, default 8.0
    "aftershock_peak_max_mm_s":      float, optional, default 25.0
    "aftershock_decay_cycles":       int,   optional, default 6 - cycles for a spike to decay back
    "baseline_tilt_deg":             float, optional, default 0.0 - starting ground/structure tilt
    "tilt_creep_rate_deg_per_cycle": float, optional, default 0.015 - ambient slow drift per cycle
    "tilt_shift_probability":        float, optional, default 0.015 - baseline chance of a sudden
                                      shift/settling event per cycle (boosted by saturated soil /
                                      fresh vibration spikes - see sensor_simulator._step_tilt())
    "tilt_shift_range_deg":          [min, max], optional, default [0.5, 2.0] - how much tilt jumps
                                      when a shift fires
    "kit_vibration_baseline_g":      float, optional, default 0.02 - per-kit ambient micro-vibration
                                      baseline (g) when a victim's kit is undisturbed
    "kit_vibration_spike_probability": float, optional, default 0.01 - baseline chance per cycle that
                                      any one kit's own accelerometer registers a disturbance event
                                      (debris movement, animal, rescuer activity, victim knocking the
                                      unit) - see sensor_simulator._step_kit_vibration()
    "kit_tilt_creep_rate_deg_per_cycle": float, optional, default 0.01 - ambient slow drift of a
                                      kit's own inclinometer per cycle
    "kit_tilt_shift_probability":    float, optional, default 0.01 - baseline chance per cycle that
                                      a kit tips/shifts (boosted when that kit's own vibration just
                                      spiked - see sensor_simulator._step_kit_tilt())
    "initial_ambient_temp_c":        float, optional, default 15.0 - starting site-wide air temperature
    "ambient_temp_volatility_c":     float, optional, default 1.0 - cycle-to-cycle temperature noise
    "temp_diurnal_swing_c":          float, optional, default 5.0 - how much warmer the site gets at
                                      "solar noon" vs. baseline (uses the same day/night phase as the
                                      solar-charging model)
    "initial_humidity_pct":          float, optional, default 50.0 - starting site-wide relative humidity
    "humidity_volatility_pct":       float, optional, default 3.0 - cycle-to-cycle humidity noise
    "humidity_rain_amplifier_pct_per_mm_hr": float, optional, default 1.2 - how much extra relative
                                      humidity each mm/hr of rain drives toward
  }
}

Public surface
--------------
available_scenarios()        -> list of lightweight metadata dicts, one per
                                 valid *.json file in scenarios/
load_scenario(scenario_id)   -> ScenarioConfig (raises ScenarioNotFoundError
                                 / ScenarioConfigError on bad input)
"""

from __future__ import annotations

import json
import os
import random
import uuid
from dataclasses import dataclass, field
from typing import Optional

from models import (
    GPSCoordinate,
    VictimProfile,
    VictimStatus,
    SensorSignatureRange,
)
from fusion_engine import HazardContext


SCENARIOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios")


class ScenarioNotFoundError(LookupError):
    """Raised when a requested scenario_id has no matching config file."""


class ScenarioConfigError(ValueError):
    """Raised when a scenario config file exists but is malformed."""


# --------------------------------------------------------------------------- #
# Parsed config
# --------------------------------------------------------------------------- #

@dataclass
class RescueTeamTemplate:
    team_id: str
    team_name: str
    lat_offset: float = 0.0
    lon_offset: float = 0.0
    members: int = 2


@dataclass
class SiteEnvironment:
    """Site-wide environmental sensors — NOT per-victim (one physical gauge for the whole zone)."""
    initial_rainfall_mm_hr: float = 0.0
    rainfall_volatility_mm_hr: float = 3.0   # burstiness of the showers (0 = steady drizzle)
    rain_to_water_rise_amplifier: float = 0.06   # how much extra water-rise-per-cycle each mm/hr of rain adds
    initial_soil_moisture_pct: float = 0.0     # 0-100, volumetric water content of the slope soil
    soil_moisture_volatility_pct: float = 1.5  # cycle-to-cycle drift/noise
    soil_saturation_from_rain_pct_per_mm_hr: float = 0.35   # how fast soil saturates per mm/hr of rain
    baseline_vibration_mm_s: float = 0.5        # ambient microtremor (rescue equipment, wind, settling)
    aftershock_prob_per_cycle: float = 0.0      # 0 = quiet site, no aftershock risk modeled
    aftershock_peak_min_mm_s: float = 8.0       # PGV (peak ground velocity) range for a triggered event
    aftershock_peak_max_mm_s: float = 25.0
    aftershock_decay_cycles: int = 6            # cycles for a spike to decay back to baseline
    baseline_tilt_deg: float = 0.0              # starting site-wide ground/structure tilt
    tilt_creep_rate_deg_per_cycle: float = 0.015   # ambient slow drift — a slope always inches slightly
    tilt_shift_probability: float = 0.015          # baseline chance of a sudden shift/settling event per cycle
    tilt_shift_range_deg: tuple = (0.5, 2.0)        # how much tilt jumps when a shift fires
    # Kit-level IMU (Step 10) per-scenario tuning knobs
    kit_vibration_baseline_g: float = 0.02          # ambient micro-vibration when a kit is undisturbed (g)
    kit_vibration_spike_probability: float = 0.01   # chance per cycle any one kit registers a disturbance event
    kit_tilt_creep_rate_deg_per_cycle: float = 0.01 # ambient slow drift of a kit's own inclinometer
    kit_tilt_shift_probability: float = 0.01        # baseline chance per cycle a kit tips/shifts
    initial_ambient_temp_c: float = 15.0           # starting site-wide air temperature (deg C)
    ambient_temp_volatility_c: float = 1.0         # cycle-to-cycle temperature noise
    temp_diurnal_swing_c: float = 5.0              # how much warmer the site gets at "solar noon"
    initial_humidity_pct: float = 50.0             # starting site-wide relative humidity (0-100)
    humidity_volatility_pct: float = 3.0           # cycle-to-cycle humidity noise
    humidity_rain_amplifier_pct_per_mm_hr: float = 1.2   # extra humidity driven by each mm/hr of rain
    initial_gas_concentration_ppm: float = 0.0     # ambient baseline toxic/combustible gas
    gas_volatility_ppm: float = 2.0                # cycle-to-cycle gas fluctuation
    initial_smoke_density_pct: float = 0.0         # ambient smoke density (%)
    smoke_volatility_pct: float = 1.0              # cycle-to-cycle smoke fluctuation
    initial_barometric_pressure_hpa: float = 1013.25 # standard sea-level atmosphere (hPa)
    pressure_volatility_hpa: float = 0.5           # barometric jitter
    pressure_drop_rate_hpa_per_cycle: float = 0.0  # cyclone pressure plunge rate


# --------------------------------------------------------------------------- #
# Custom scenario generation (Step 13 — admin console "create scenario")
# --------------------------------------------------------------------------- #
HAZARD_TYPE_PRESETS: dict = {
    "earthquake": {
        "name_suffix": "Earthquake - Building Collapse (Admin-Generated)",
        "secondary_hazard": True,   # aftershock / further-collapse risk
        "enable_water": False,
        "site_environment_kwargs": {
            "baseline_vibration_mm_s": 0.8,
            "aftershock_prob_per_cycle": 0.05,
            "aftershock_peak_min_mm_s": 4.0,
            "aftershock_peak_max_mm_s": 14.0,
            "baseline_tilt_deg": 2.0,
            "tilt_shift_probability": 0.025,
        },
    },
    "flood": {
        "name_suffix": "Urban Flood (Admin-Generated)",
        "secondary_hazard": False,
        "enable_water": True,
        "site_environment_kwargs": {
            "initial_rainfall_mm_hr": 22.0,
            "rainfall_volatility_mm_hr": 4.0,
        },
    },
    "avalanche": {
        "name_suffix": "Avalanche (Admin-Generated)",
        "secondary_hazard": True,   # secondary slide risk
        "enable_water": False,
        "site_environment_kwargs": {
            "initial_soil_moisture_pct": 45.0,
            "baseline_tilt_deg": 1.5,
            "tilt_shift_probability": 0.02,
        },
    },
    "urban_fire": {
        "name_suffix": "Urban Fire / Structural Inferno (Admin-Generated)",
        "secondary_hazard": True,
        "enable_water": False,
        "site_environment_kwargs": {
            "initial_ambient_temp_c": 55.0,
            "ambient_temp_volatility_c": 3.0,
            "initial_smoke_density_pct": 45.0,
            "initial_gas_concentration_ppm": 120.0,
        },
    },
    "chemical_leak": {
        "name_suffix": "Chemical / Toxic Gas Leak (Admin-Generated)",
        "secondary_hazard": True,
        "enable_water": False,
        "site_environment_kwargs": {
            "initial_gas_concentration_ppm": 280.0,
            "gas_volatility_ppm": 15.0,
            "initial_smoke_density_pct": 20.0,
        },
    },
    "landslide": {
        "name_suffix": "Landslide / Debris Flow (Admin-Generated)",
        "secondary_hazard": True,
        "enable_water": False,
        "site_environment_kwargs": {
            "initial_rainfall_mm_hr": 35.0,
            "initial_soil_moisture_pct": 78.0,
            "baseline_tilt_deg": 6.5,
            "tilt_shift_probability": 0.05,
        },
    },
    "cyclone": {
        "name_suffix": "Cyclone / Severe Storm Surge (Admin-Generated)",
        "secondary_hazard": True,
        "enable_water": True,
        "site_environment_kwargs": {
            "initial_rainfall_mm_hr": 48.0,
            "initial_humidity_pct": 95.0,
            "initial_barometric_pressure_hpa": 975.0,
            "pressure_drop_rate_hpa_per_cycle": 1.5,
        },
    },
    "multi_hazard": {
        "name_suffix": "Multi-Hazard Cascading Disaster (Admin-Generated)",
        "secondary_hazard": True,
        "enable_water": True,
        "site_environment_kwargs": {
            "baseline_vibration_mm_s": 2.5,
            "aftershock_prob_per_cycle": 0.08,
            "baseline_tilt_deg": 4.0,
            "initial_ambient_temp_c": 42.0,
            "initial_smoke_density_pct": 35.0,
            "initial_gas_concentration_ppm": 85.0,
            "initial_rainfall_mm_hr": 18.0,
        },
    },
}

# Generic 4-severity spread, cycled round-robin across however many victims
# the admin requests - same pattern as HIMALAYA_VICTIMS (1 deceased, 1
# critical, 1 minor, 1 safe) but hazard-type-agnostic.
_SEVERITY_TEMPLATES: list = [
    {
        "status": VictimStatus.DECEASED,
        "burial_depth_m": 1.8,
        "signature_range": SensorSignatureRange(
            thermal_imaging_c=(10.0, 16.0), pir_motion=(0.0, 0.02), acoustic_db=(0.0, 5.0),
            co2_ppm=(400.0, 420.0), heart_rate_radar_bpm=(0.0, 0.0), rgb_camera_conf=(0.0, 0.1),
        ),
        "notes": "Admin-generated — no vital signs detected on any channel.",
    },
    {
        "status": VictimStatus.CRITICAL,
        "burial_depth_m": 1.2,
        "signature_range": SensorSignatureRange(
            thermal_imaging_c=(20.0, 27.0), pir_motion=(0.01, 0.08), acoustic_db=(5.0, 15.0),
            co2_ppm=(600.0, 900.0), heart_rate_radar_bpm=(35.0, 55.0), rgb_camera_conf=(0.1, 0.3),
        ),
        "notes": "Admin-generated — faint vitals, highest rescue priority.",
    },
    {
        "status": VictimStatus.MINOR_INJURY,
        "burial_depth_m": 0.4,
        "signature_range": SensorSignatureRange(
            thermal_imaging_c=(28.0, 34.0), pir_motion=(0.15, 0.45), acoustic_db=(25.0, 45.0),
            co2_ppm=(900.0, 1500.0), heart_rate_radar_bpm=(80.0, 110.0), rgb_camera_conf=(0.4, 0.7),
        ),
        "notes": "Admin-generated — conscious and responsive, stable but needs extraction.",
    },
    {
        "status": VictimStatus.SAFE,
        "burial_depth_m": 0.0,
        "signature_range": SensorSignatureRange(
            thermal_imaging_c=(30.0, 34.0), pir_motion=(0.5, 1.0), acoustic_db=(40.0, 70.0),
            co2_ppm=(1500.0, 2500.0), heart_rate_radar_bpm=(70.0, 100.0), rgb_camera_conf=(0.8, 1.0),
        ),
        "notes": "Admin-generated — ambulatory, self-evacuating.",
    },
]

# Water-exposure spread for admin-generated FLOOD scenarios only, indexed
# 1:1 against _SEVERITY_TEMPLATES (deceased/critical/minor/safe). Mirrors
# the hand-authored flood_urban.json pattern (see backend/scenarios/
# flood_urban.json "water_exposure" blocks) - deceased/critical victims
# are deepest and most exposed to current, the safe/ambulatory victim is
# dry. Fixes Step 17 finding: build_custom_scenario() previously left
# VictimProfile.initial_water_level_cm at its 0.0 default even when
# hazard_type="flood", so api.py's `enable_water_sensor` scenario-gate
# (ScenarioState.start()) never turned on and hazard_breakdown's
# water_level/water_rising bonuses stayed 0.0 for the life of the
# scenario, no matter how many cycles elapsed.
_FLOOD_WATER_EXPOSURE: list = [
    {"initial_water_level_cm": 150.0, "water_rising_rate_cm_per_cycle": 1.2, "initial_water_flow_ms": 1.6, "water_flow_volatility_ms": 0.4},
    {"initial_water_level_cm": 80.0,  "water_rising_rate_cm_per_cycle": 3.0, "initial_water_flow_ms": 2.0, "water_flow_volatility_ms": 0.5},
    {"initial_water_level_cm": 15.0,  "water_rising_rate_cm_per_cycle": 1.0, "initial_water_flow_ms": 0.4, "water_flow_volatility_ms": 0.2},
    {"initial_water_level_cm": 0.0,   "water_rising_rate_cm_per_cycle": 0.0, "initial_water_flow_ms": 0.0, "water_flow_volatility_ms": 0.0},
]


@dataclass
class ScenarioConfig:
    scenario_id: str
    name: str
    description: str
    site_label: str
    site_origin: GPSCoordinate
    victims: list                      # list[VictimProfile]
    hazards: dict                      # victim_id -> HazardContext
    rescue_team_templates: list        # list[RescueTeamTemplate]
    site_environment: SiteEnvironment = field(default_factory=SiteEnvironment)

    @property
    def victim_count(self) -> int:
        return len(self.victims)

    def meta(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "site_label": self.site_label,
            "victim_count": self.victim_count,
        }


# --------------------------------------------------------------------------- #
# JSON -> model object parsing helpers
# --------------------------------------------------------------------------- #

def _coord(d: dict, ctx: str) -> GPSCoordinate:
    try:
        return GPSCoordinate(
            latitude=float(d["latitude"]),
            longitude=float(d["longitude"]),
            altitude_m=float(d["altitude_m"]) if d.get("altitude_m") is not None else None,
        )
    except (KeyError, TypeError, ValueError) as e:
        raise ScenarioConfigError(f"Invalid coordinate in {ctx}: {d!r} ({e})") from e


def _range_pair(d: dict, key: str, ctx: str) -> tuple:
    try:
        lo, hi = d[key]
        return (float(lo), float(hi))
    except (KeyError, TypeError, ValueError) as e:
        raise ScenarioConfigError(f"Invalid signature_range.{key} in {ctx}: {e}") from e


def _signature_range(d: dict, ctx: str) -> SensorSignatureRange:
    # water_level_cm is optional - most scenarios (earthquake, avalanche) have
    # no flood exposure at all, so absence must default to (0.0, 0.0) rather
    # than raising, or every non-flood scenario JSON would break.
    if "water_level_cm" in d:
        water_range = _range_pair(d, "water_level_cm", ctx)
    else:
        water_range = (0.0, 0.0)

    # water_flow_ms is likewise optional - absent -> (0.0, 0.0) so
    # non-flood scenarios don't need to know this key exists.
    if "water_flow_ms" in d:
        water_flow_range = _range_pair(d, "water_flow_ms", ctx)
    else:
        water_flow_range = (0.0, 0.0)

    gas_range = _range_pair(d, "gas_concentration_ppm", ctx) if "gas_concentration_ppm" in d else (0.0, 0.0)
    smoke_range = _range_pair(d, "smoke_density_pct", ctx) if "smoke_density_pct" in d else (0.0, 0.0)

    return SensorSignatureRange(
        thermal_imaging_c=_range_pair(d, "thermal_imaging_c", ctx),
        pir_motion=_range_pair(d, "pir_motion", ctx),
        acoustic_db=_range_pair(d, "acoustic_db", ctx),
        co2_ppm=_range_pair(d, "co2_ppm", ctx),
        heart_rate_radar_bpm=_range_pair(d, "heart_rate_radar_bpm", ctx),
        rgb_camera_conf=_range_pair(d, "rgb_camera_conf", ctx),
        water_level_cm=water_range,
        water_flow_ms=water_flow_range,
        gas_concentration_ppm=gas_range,
        smoke_density_pct=smoke_range,
    )


def _victim(d: dict) -> VictimProfile:
    victim_id = d.get("victim_id") or "?"
    ctx = f"victim '{victim_id}'"
    try:
        status = VictimStatus(d["status"])
    except KeyError as e:
        raise ScenarioConfigError(f"{ctx} is missing required field: {e}") from e
    except ValueError as e:
        valid = ", ".join(s.value for s in VictimStatus)
        raise ScenarioConfigError(
            f"{ctx} has unknown status {d['status']!r}; must be one of: {valid}"
        ) from e

    # water_exposure is optional (flood scenarios only); absent -> a
    # dry/non-flood victim with no water level and no rising rate.
    water_exposure = d.get("water_exposure") or {}

    try:
        return VictimProfile(
            victim_id=d["victim_id"],
            label=d["label"],
            status=status,
            location=_coord(d["location"], ctx),
            burial_depth_m=float(d.get("burial_depth_m", 0.0)),
            signature_range=_signature_range(d["signature_range"], ctx),
            notes=d.get("notes", ""),
            initial_water_level_cm=float(water_exposure.get("initial_water_level_cm", 0.0)),
            water_rising_rate_cm_per_cycle=float(water_exposure.get("rising_rate_cm_per_cycle", 0.0)),
            initial_water_flow_ms=float(water_exposure.get("initial_water_flow_ms", 0.0)),
            water_flow_volatility_ms=float(water_exposure.get("water_flow_volatility_ms", 0.3)),
        )
    except KeyError as e:
        raise ScenarioConfigError(f"{ctx} is missing required field: {e}") from e


def _hazard(d: dict) -> HazardContext:
    d = d or {}
    return HazardContext(
        burial_depth_m=float(d.get("burial_depth_m", 0.0)),
        secondary_hazard=bool(d.get("secondary_hazard", False)),
        exposure_minutes=float(d.get("exposure_minutes", 0.0)),
    )


def _rescue_team_template(d: dict) -> RescueTeamTemplate:
    try:
        return RescueTeamTemplate(
            team_id=d["team_id"],
            team_name=d["team_name"],
            lat_offset=float(d.get("lat_offset", 0.0)),
            lon_offset=float(d.get("lon_offset", 0.0)),
            members=int(d.get("members", 2)),
        )
    except KeyError as e:
        raise ScenarioConfigError(f"rescue_teams entry is missing required field: {e}") from e


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def _scenario_path(scenario_id: str) -> str:
    # scenario_id is used to build a filesystem path - keep it to a safe
    # charset so it can't be used to escape SCENARIOS_DIR.
    if not scenario_id or not all(c.isalnum() or c in "_-" for c in scenario_id):
        raise ScenarioNotFoundError(f"Invalid scenario id: {scenario_id!r}")
    return os.path.join(SCENARIOS_DIR, f"{scenario_id}.json")


def available_scenarios() -> list:
    """
    Scan SCENARIOS_DIR and return lightweight metadata for every syntactically
    valid scenario config file (id, name, description, site_label,
    victim_count) without fully constructing VictimProfile/HazardContext
    objects. Used by GET /scenarios to populate a scenario picker.
    Files that fail to parse are silently skipped (they'll raise a clear
    error if actually loaded via load_scenario()).
    """
    if not os.path.isdir(SCENARIOS_DIR):
        return []
    out = []
    for fname in sorted(os.listdir(SCENARIOS_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(SCENARIOS_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            out.append({
                "scenario_id": raw["scenario_id"],
                "name": raw.get("name", raw["scenario_id"]),
                "description": raw.get("description", ""),
                "site_label": raw.get("site_label", ""),
                "victim_count": len(raw.get("victims", [])),
            })
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return out


CANONICAL_SCENARIO_ALIASES: dict[str, str] = {
    "earthquake": "earthquake_building_collapse",
    "flood": "flood_urban",
    "wildfire": "wildfire_forest",
    "chemical_leak": "chemical_gas_leak",
    "avalanche": "himalaya_avalanche",
    "building_collapse": "earthquake_building_collapse",
    "landslide": "earthquake_building_collapse",
    "wayanad_landslide": "earthquake_building_collapse",
    "tsunami": "flood_urban",
    "cloudburst": "flood_urban",
    "landslide_slope": "earthquake_building_collapse",
    "coastal_tsunami": "flood_urban",
}


def load_scenario(scenario_id: str) -> ScenarioConfig:
    """
    Load and fully parse a scenario config by id, building the same
    VictimProfile / HazardContext / GPSCoordinate objects the rest of the
    backend (sensor_simulator, fusion_engine, api) already knows how to
    work with.

    Raises:
        ScenarioNotFoundError - no config file for scenario_id
        ScenarioConfigError   - config file exists but is invalid/incomplete
    """
    resolved_id = CANONICAL_SCENARIO_ALIASES.get(scenario_id, scenario_id)
    path = _scenario_path(resolved_id)
    if not os.path.isfile(path):
        known = ", ".join(s["scenario_id"] for s in available_scenarios())
        raise ScenarioNotFoundError(
            f"Unknown scenario '{scenario_id}'. "
            f"Available scenarios: {known or '(none configured)'}"
        )

    with open(path, "r", encoding="utf-8") as f:
        try:
            raw = json.load(f)
        except json.JSONDecodeError as e:
            raise ScenarioConfigError(f"{path} is not valid JSON: {e}") from e

    try:
        site_origin = _coord(raw["site_origin"], "site_origin")
    except KeyError as e:
        raise ScenarioConfigError(f"Scenario '{scenario_id}' is missing required field: {e}") from e

    raw_victims = raw.get("victims") or []
    if not raw_victims:
        raise ScenarioConfigError(f"Scenario '{scenario_id}' defines no victims")

    victims = [_victim(v) for v in raw_victims]

    seen_ids = set()
    for v in victims:
        if v.victim_id in seen_ids:
            raise ScenarioConfigError(f"Scenario '{scenario_id}' has duplicate victim_id '{v.victim_id}'")
        seen_ids.add(v.victim_id)

    hazards = {v["victim_id"]: _hazard(v.get("hazard")) for v in raw_victims}

    rescue_team_templates = [_rescue_team_template(t) for t in raw.get("rescue_teams", [])]

    env_raw = raw.get("site_environment", {})
    site_environment = SiteEnvironment(
        initial_rainfall_mm_hr=env_raw.get("initial_rainfall_mm_hr", 0.0),
        rainfall_volatility_mm_hr=env_raw.get("rainfall_volatility_mm_hr", 3.0),
        rain_to_water_rise_amplifier=env_raw.get("rain_to_water_rise_amplifier", 0.06),
        initial_soil_moisture_pct=env_raw.get("initial_soil_moisture_pct", 0.0),
        soil_moisture_volatility_pct=env_raw.get("soil_moisture_volatility_pct", 1.5),
        soil_saturation_from_rain_pct_per_mm_hr=env_raw.get("soil_saturation_from_rain_pct_per_mm_hr", 0.35),
        baseline_vibration_mm_s=env_raw.get("baseline_vibration_mm_s", 0.5),
        aftershock_prob_per_cycle=env_raw.get("aftershock_prob_per_cycle", 0.0),
        aftershock_peak_min_mm_s=env_raw.get("aftershock_peak_min_mm_s", 8.0),
        aftershock_peak_max_mm_s=env_raw.get("aftershock_peak_max_mm_s", 25.0),
        aftershock_decay_cycles=env_raw.get("aftershock_decay_cycles", 6),
        baseline_tilt_deg=env_raw.get("baseline_tilt_deg", 0.0),
        tilt_creep_rate_deg_per_cycle=env_raw.get("tilt_creep_rate_deg_per_cycle", 0.015),
        tilt_shift_probability=env_raw.get("tilt_shift_probability", 0.015),
        tilt_shift_range_deg=tuple(env_raw.get("tilt_shift_range_deg", (0.5, 2.0))),
        kit_vibration_baseline_g=env_raw.get("kit_vibration_baseline_g", 0.02),
        kit_vibration_spike_probability=env_raw.get("kit_vibration_spike_probability", 0.01),
        kit_tilt_creep_rate_deg_per_cycle=env_raw.get("kit_tilt_creep_rate_deg_per_cycle", 0.01),
        kit_tilt_shift_probability=env_raw.get("kit_tilt_shift_probability", 0.01),
        initial_ambient_temp_c=env_raw.get("initial_ambient_temp_c", 15.0),
        ambient_temp_volatility_c=env_raw.get("ambient_temp_volatility_c", 1.0),
        temp_diurnal_swing_c=env_raw.get("temp_diurnal_swing_c", 5.0),
        initial_humidity_pct=env_raw.get("initial_humidity_pct", 50.0),
        humidity_volatility_pct=env_raw.get("humidity_volatility_pct", 3.0),
        humidity_rain_amplifier_pct_per_mm_hr=env_raw.get("humidity_rain_amplifier_pct_per_mm_hr", 1.2),
    )

    return ScenarioConfig(
        scenario_id=scenario_id,
        name=raw.get("name", scenario_id),
        description=raw.get("description", ""),
        site_label=raw.get("site_label", ""),
        site_origin=site_origin,
        victims=victims,
        hazards=hazards,
        rescue_team_templates=rescue_team_templates,
        site_environment=site_environment,
    )


def build_custom_scenario(
    hazard_type: str,
    victim_count: int,
    site_origin: GPSCoordinate,
    scenario_name: Optional[str] = None,
    seed: Optional[int] = None,
) -> ScenarioConfig:
    """
    Build a ScenarioConfig entirely in memory - no JSON file involved.
    Used by the admin console (Step 13, POST /admin/scenario/create) to
    let a judge/admin spin up a fresh disaster scenario on the fly.

    victim_count victims are procedurally generated, cycling round-robin
    through _SEVERITY_TEMPLATES (deceased/critical/minor/safe spread),
    scattered ~30-70m around site_origin (matching the hand-authored
    scenarios' spread) using a seeded RNG for reproducibility.
    """
    preset = HAZARD_TYPE_PRESETS.get(hazard_type)
    if preset is None:
        raise ScenarioConfigError(
            f"Unknown hazard_type {hazard_type!r}; must be one of {list(HAZARD_TYPE_PRESETS.keys())}"
        )
    if victim_count < 1:
        raise ScenarioConfigError("victim_count must be at least 1")

    rng = random.Random(seed)
    scenario_id = f"admin_custom_{uuid.uuid4().hex[:8]}"

    victims: list = []
    hazards: dict = {}
    for i in range(victim_count):
        template = _SEVERITY_TEMPLATES[i % len(_SEVERITY_TEMPLATES)]
        victim_id = f"V{i + 1}"
        # ~30-70m scatter around site_origin, same spread as the
        # hand-authored scenarios (see models.py HIMALAYA_VICTIMS comment)
        lat_offset = rng.uniform(-0.0006, 0.0006)
        lon_offset = rng.uniform(-0.0006, 0.0006)

        # Only flood scenarios carry water exposure - keeps earthquake/
        # avalanche victims at the VictimProfile water defaults (0.0), so
        # their water sensor stays scenario-gated off, same as before.
        water_kwargs = (
            _FLOOD_WATER_EXPOSURE[i % len(_FLOOD_WATER_EXPOSURE)]
            if preset.get("enable_water")
            else {}
        )

        victim = VictimProfile(
            victim_id=victim_id,
            label=f"Victim {i + 1} - {template['status'].value.replace('_', ' ').title()}",
            status=template["status"],
            location=GPSCoordinate(
                latitude=site_origin.latitude + lat_offset,
                longitude=site_origin.longitude + lon_offset,
                altitude_m=site_origin.altitude_m,
            ),
            burial_depth_m=template["burial_depth_m"],
            signature_range=template["signature_range"],
            notes=template["notes"],
            **water_kwargs,
        )
        victims.append(victim)
        hazards[victim_id] = HazardContext(
            burial_depth_m=template["burial_depth_m"],
            secondary_hazard=preset["secondary_hazard"],
            exposure_minutes=rng.uniform(60.0, 200.0),
        )

    site_environment = SiteEnvironment(**preset["site_environment_kwargs"])

    return ScenarioConfig(
        scenario_id=scenario_id,
        name=scenario_name or preset["name_suffix"],
        description=f"Admin-generated {hazard_type} scenario, {victim_count} victims.",
        site_label=f"Admin custom site ({hazard_type})",
        site_origin=site_origin,
        victims=victims,
        hazards=hazards,
        rescue_team_templates=[
            RescueTeamTemplate(team_id="TEAM-A", team_name="Rescue Team Alpha", lat_offset=-0.001, lon_offset=0.0, members=2),
            RescueTeamTemplate(team_id="TEAM-B", team_name="Rescue Team Bravo", lat_offset=0.001, lon_offset=0.0, members=2),
        ],
        site_environment=site_environment,
    )


if __name__ == "__main__":
    # quick self-test / demo when run directly: python scenario_loader.py
    for meta in available_scenarios():
        print(meta)
        cfg = load_scenario(meta["scenario_id"])
        print(f"  -> loaded {cfg.victim_count} victims, "
              f"{len(cfg.rescue_team_templates)} rescue team templates")
