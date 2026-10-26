"""
scenario_sensor_profiles.py
----------------------------
Centralized configuration and runtime classification engine for
Scenario-Aware Sensor Activation, Sensor Role Classification (PRIMARY, SUPPORTING, INACTIVE),
and Sensor Priority/Weight Mapping.

This module is the single source of truth across the entire RidgeWatch architecture
(Simulator, Fusion Engine, Scenario Intelligence, REST APIs, and Frontends)
for mapping disaster scenarios to their active sensor profiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any, Set

from models import SensorType


# --------------------------------------------------------------------------- #
# Sensor Roles
# --------------------------------------------------------------------------- #

class SensorRole(str, Enum):
    PRIMARY = "PRIMARY"          # Mission-critical modality driving detection & triage
    SUPPORTING = "SUPPORTING"    # Contextual / environmental corroboration modality
    INACTIVE = "INACTIVE"        # Not applicable to scenario; zero hazard / risk contribution


# --------------------------------------------------------------------------- #
# Scenario Sensor Profile Model
# --------------------------------------------------------------------------- #

@dataclass
class ScenarioSensorProfile:
    scenario_id: str
    name: str
    category: str
    description: str
    primary_sensors: List[SensorType]
    supporting_sensors: List[SensorType]
    inactive_sensors: List[SensorType]
    sensor_weights: Dict[SensorType, float] = field(default_factory=dict)
    hazard_weights: Dict[str, float] = field(default_factory=dict)
    minimum_evidence_count: int = 2
    thresholds: Dict[str, Any] = field(default_factory=dict)

    def get_role(self, sensor_type: SensorType | str) -> SensorRole:
        st = SensorType(sensor_type) if isinstance(sensor_type, str) else sensor_type
        if st in self.primary_sensors:
            return SensorRole.PRIMARY
        if st in self.supporting_sensors:
            return SensorRole.SUPPORTING
        return SensorRole.INACTIVE

    def is_active(self, sensor_type: SensorType | str) -> bool:
        return self.get_role(sensor_type) != SensorRole.INACTIVE

    def get_weight(self, sensor_type: SensorType | str) -> float:
        st = SensorType(sensor_type) if isinstance(sensor_type, str) else sensor_type
        if st in self.inactive_sensors:
            return 0.0
        return self.sensor_weights.get(st, 0.10 if st in self.supporting_sensors else 0.30)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "primary_sensors": [s.value for s in self.primary_sensors],
            "supporting_sensors": [s.value for s in self.supporting_sensors],
            "inactive_sensors": [s.value for s in self.inactive_sensors],
            "sensor_weights": {s.value: w for s, w in self.sensor_weights.items()},
            "hazard_weights": self.hazard_weights,
            "minimum_evidence_count": self.minimum_evidence_count,
            "thresholds": self.thresholds,
        }

    def get_sensor_state_map(self) -> Dict[str, Dict[str, Any]]:
        """Return full runtime sensor role and activity state map for every SensorType."""
        res: Dict[str, Dict[str, Any]] = {}
        for st in SensorType:
            role = self.get_role(st)
            active = (role != SensorRole.INACTIVE)
            weight = self.get_weight(st)
            contribution = "HIGH" if role == SensorRole.PRIMARY else ("MEDIUM" if role == SensorRole.SUPPORTING else "ZERO")
            status = "ACTIVE" if role == SensorRole.PRIMARY else ("SUPPORTING" if role == SensorRole.SUPPORTING else "NOMINAL_BASELINE")
            res[st.value] = {
                "sensor_type": st.value,
                "role": role.value,
                "status": status,
                "active": active,
                "weight": round(weight, 3),
                "contribution": contribution,
            }
        return res


# --------------------------------------------------------------------------- #
# Canonical 5 Scenario Profiles
# --------------------------------------------------------------------------- #

# A. EARTHQUAKE / BUILDING COLLAPSE
EARTHQUAKE_PROFILE = ScenarioSensorProfile(
    scenario_id="earthquake_building_collapse",
    name="Earthquake & Structural Collapse",
    category="Geophysical / Structural",
    description="Structural collapse, rubble void entrapment, seismic vibrations, and acoustic distress calls.",
    primary_sensors=[
        SensorType.IMU_VIBRATION,
        SensorType.HEART_RATE_RADAR,
        SensorType.PIR_MOTION,
    ],
    supporting_sensors=[
        SensorType.RGB_CAMERA,
        SensorType.THERMAL_IMAGING,
        SensorType.GPS,
        SensorType.TEMPERATURE,
        SensorType.ACOUSTIC,
        SensorType.CO2,
        SensorType.IMU_TILT,
    ],
    inactive_sensors=[
        SensorType.WATER_LEVEL,
        SensorType.WATER_FLOW,
        SensorType.GAS_CONCENTRATION,
        SensorType.RAINFALL_INTENSITY,
        SensorType.SOIL_MOISTURE,
        SensorType.SMOKE_DENSITY,
        SensorType.BAROMETRIC_PRESSURE,
        SensorType.HUMIDITY,
    ],
    sensor_weights={
        SensorType.HEART_RATE_RADAR: 0.35,
        SensorType.IMU_VIBRATION: 0.25,
        SensorType.PIR_MOTION: 0.20,
        SensorType.ACOUSTIC: 0.10,
        SensorType.THERMAL_IMAGING: 0.05,
        SensorType.RGB_CAMERA: 0.05,
    },
    hazard_weights={
        "vibration": 0.35,
        "tilt": 0.25,
        "secondary_hazard": 0.25,
        "depth": 0.15,
    },
    minimum_evidence_count=2,
    thresholds={
        "seismic_vibration_alert_g": 0.10,
        "tilt_shift_danger_deg": 4.0,
    },
)

# B. FLOOD
FLOOD_PROFILE = ScenarioSensorProfile(
    scenario_id="flood_urban",
    name="Urban Flash Flood",
    category="Hydrological",
    description="Rapid rising water levels, swift water currents, and heavy torrential rainfall inundation.",
    primary_sensors=[
        SensorType.WATER_LEVEL,
        SensorType.WATER_FLOW,
        SensorType.RAINFALL_INTENSITY,
    ],
    supporting_sensors=[
        SensorType.GPS,
        SensorType.IMU_VIBRATION,
        SensorType.IMU_TILT,
        SensorType.HUMIDITY,
        SensorType.HEART_RATE_RADAR,
        SensorType.THERMAL_IMAGING,
        SensorType.ACOUSTIC,
        SensorType.RGB_CAMERA,
        SensorType.PIR_MOTION,
    ],
    inactive_sensors=[
        SensorType.GAS_CONCENTRATION,
        SensorType.SMOKE_DENSITY,
        SensorType.SOIL_MOISTURE,
        SensorType.BAROMETRIC_PRESSURE,
        SensorType.CO2,
    ],
    sensor_weights={
        SensorType.WATER_LEVEL: 0.40,
        SensorType.WATER_FLOW: 0.30,
        SensorType.RAINFALL_INTENSITY: 0.20,
        SensorType.GPS: 0.05,
        SensorType.HUMIDITY: 0.05,
    },
    hazard_weights={
        "water_level": 0.35,
        "water_rising": 0.25,
        "water_flow": 0.25,
        "rain": 0.15,
    },
    minimum_evidence_count=2,
    thresholds={
        "flood_warning_depth_cm": 30.0,
        "flood_critical_depth_cm": 100.0,
        "swift_current_mps": 1.5,
    },
)

# C. AVALANCHE
AVALANCHE_PROFILE = ScenarioSensorProfile(
    scenario_id="himalaya_avalanche",
    name="Himalaya Snow Avalanche",
    category="Cryospheric",
    description="Snowpack displacement, subsurface deep snow burial, hypothermia triage, and faint radar vitals.",
    primary_sensors=[
        SensorType.IMU_VIBRATION,
        SensorType.HEART_RATE_RADAR,
        SensorType.IMU_TILT,
    ],
    supporting_sensors=[
        SensorType.TEMPERATURE,
        SensorType.GPS,
        SensorType.RGB_CAMERA,
        SensorType.THERMAL_IMAGING,
        SensorType.ACOUSTIC,
        SensorType.CO2,
        SensorType.PIR_MOTION,
        SensorType.SOIL_MOISTURE,
    ],
    inactive_sensors=[
        SensorType.WATER_LEVEL,
        SensorType.WATER_FLOW,
        SensorType.GAS_CONCENTRATION,
        SensorType.SMOKE_DENSITY,
        SensorType.RAINFALL_INTENSITY,
        SensorType.BAROMETRIC_PRESSURE,
        SensorType.HUMIDITY,
    ],
    sensor_weights={
        SensorType.HEART_RATE_RADAR: 0.40,
        SensorType.IMU_VIBRATION: 0.25,
        SensorType.IMU_TILT: 0.15,
        SensorType.THERMAL_IMAGING: 0.10,
        SensorType.ACOUSTIC: 0.05,
        SensorType.TEMPERATURE: 0.05,
    },
    hazard_weights={
        "depth": 0.35,
        "cold_exposure": 0.30,
        "secondary_hazard": 0.25,
        "exposure": 0.10,
    },
    minimum_evidence_count=2,
    thresholds={
        "burial_depth_critical_m": 1.5,
        "freezing_air_temp_c": 0.0,
    },
)

# D. CHEMICAL / TOXIC GAS LEAK
CHEMICAL_LEAK_PROFILE = ScenarioSensorProfile(
    scenario_id="chemical_gas_leak",
    name="Chemical & Toxic Gas Leak",
    category="CBRN / HazMat",
    description="Atmospheric toxic gas concentration breach, chemical dispersion, and HazMat hot zone containment.",
    primary_sensors=[
        SensorType.GAS_CONCENTRATION,
        SensorType.SMOKE_DENSITY,
    ],
    supporting_sensors=[
        SensorType.TEMPERATURE,
        SensorType.HUMIDITY,
        SensorType.GPS,
        SensorType.RGB_CAMERA,
        SensorType.THERMAL_IMAGING,
        SensorType.HEART_RATE_RADAR,
        SensorType.ACOUSTIC,
        SensorType.PIR_MOTION,
        SensorType.CO2,
    ],
    inactive_sensors=[
        SensorType.WATER_LEVEL,
        SensorType.WATER_FLOW,
        SensorType.RAINFALL_INTENSITY,
        SensorType.SOIL_MOISTURE,
        SensorType.BAROMETRIC_PRESSURE,
        SensorType.IMU_VIBRATION,
        SensorType.IMU_TILT,
    ],
    sensor_weights={
        SensorType.GAS_CONCENTRATION: 0.50,
        SensorType.SMOKE_DENSITY: 0.30,
        SensorType.TEMPERATURE: 0.10,
        SensorType.HUMIDITY: 0.05,
        SensorType.GPS: 0.05,
    },
    hazard_weights={
        "gas": 0.50,
        "smoke": 0.30,
        "exposure": 0.20,
    },
    minimum_evidence_count=2,
    thresholds={
        "toxic_gas_elevated_ppm": 35.0,
        "toxic_gas_critical_ppm": 70.0,
    },
)

# E. WILDFIRE / FOREST FIRE
WILDFIRE_PROFILE = ScenarioSensorProfile(
    scenario_id="wildfire_forest",
    name="Wildfire & Forest Fire",
    category="Thermal",
    description="Elevated extreme ambient temperature, particulate smoke plumes, and infrared thermal hotspots.",
    primary_sensors=[
        SensorType.TEMPERATURE,
        SensorType.SMOKE_DENSITY,
        SensorType.THERMAL_IMAGING,
    ],
    supporting_sensors=[
        SensorType.HUMIDITY,
        SensorType.RGB_CAMERA,
        SensorType.GPS,
        SensorType.RAINFALL_INTENSITY,
        SensorType.GAS_CONCENTRATION,
        SensorType.HEART_RATE_RADAR,
        SensorType.PIR_MOTION,
        SensorType.ACOUSTIC,
    ],
    inactive_sensors=[
        SensorType.WATER_LEVEL,
        SensorType.WATER_FLOW,
        SensorType.SOIL_MOISTURE,
        SensorType.BAROMETRIC_PRESSURE,
        SensorType.IMU_VIBRATION,
        SensorType.IMU_TILT,
        SensorType.CO2,
    ],
    sensor_weights={
        SensorType.TEMPERATURE: 0.35,
        SensorType.SMOKE_DENSITY: 0.35,
        SensorType.THERMAL_IMAGING: 0.20,
        SensorType.HUMIDITY: 0.05,
        SensorType.RGB_CAMERA: 0.05,
    },
    hazard_weights={
        "temperature": 0.40,
        "smoke": 0.35,
        "heat_humidity_compound": 0.15,
        "exposure": 0.10,
    },
    minimum_evidence_count=2,
    thresholds={
        "fire_temp_threshold_c": 45.0,
        "smoke_critical_pct": 50.0,
    },
)

# F. LANDSLIDE & DEBRIS FLOW (RIDGEWATCH Subsurface SAR Module)
LANDSLIDE_PROFILE = ScenarioSensorProfile(
    scenario_id="landslide",
    name="Landslide & Mudflow Subsurface SAR",
    category="Geotechnical",
    description="Subsurface soil and mud displacement, buried survivor detection via UWB bioradar, soil saturation, and slope tilt monitoring.",
    primary_sensors=[
        SensorType.UWB_BIORADAR,
        SensorType.SOIL_MOISTURE,
        SensorType.IMU_TILT,
        SensorType.RAINFALL_INTENSITY,
    ],
    supporting_sensors=[
        SensorType.IMU_VIBRATION,
        SensorType.ACOUSTIC,
        SensorType.CO2,
        SensorType.THERMAL_IMAGING,
        SensorType.RGB_CAMERA,
        SensorType.HEART_RATE_RADAR,
        SensorType.GPS,
        SensorType.TEMPERATURE,
        SensorType.HUMIDITY,
        SensorType.BAROMETRIC_PRESSURE,
    ],
    inactive_sensors=[
        SensorType.WATER_LEVEL,
        SensorType.WATER_FLOW,
        SensorType.GAS_CONCENTRATION,
        SensorType.SMOKE_DENSITY,
    ],
    sensor_weights={
        SensorType.UWB_BIORADAR: 0.40,
        SensorType.ACOUSTIC: 0.20,
        SensorType.THERMAL_IMAGING: 0.15,
        SensorType.CO2: 0.15,
        SensorType.RGB_CAMERA: 0.10,
    },
    hazard_weights={
        "soil_moisture": 0.30,
        "tilt": 0.25,
        "rainfall": 0.20,
        "vibration": 0.15,
        "exposure": 0.10,
    },
    minimum_evidence_count=2,
    thresholds={
        "soil_moisture_critical_pct": 65.0,
        "tilt_critical_deg": 10.0,
    },
)


# --------------------------------------------------------------------------- #
# Lookup & Profile Registry
# --------------------------------------------------------------------------- #

SCENARIO_SENSOR_PROFILES: Dict[str, ScenarioSensorProfile] = {
    # Exact scenario_ids
    "earthquake_building_collapse": EARTHQUAKE_PROFILE,
    "flood_urban": FLOOD_PROFILE,
    "himalaya_avalanche": AVALANCHE_PROFILE,
    "chemical_gas_leak": CHEMICAL_LEAK_PROFILE,
    "wildfire_forest": WILDFIRE_PROFILE,
    "landslide": LANDSLIDE_PROFILE,
    "landslide_debris_flow": LANDSLIDE_PROFILE,

    # Canonical aliases matching scenarios_master.py
    "earthquake": EARTHQUAKE_PROFILE,
    "building_collapse": EARTHQUAKE_PROFILE,
    "flood": FLOOD_PROFILE,
    "avalanche": AVALANCHE_PROFILE,
    "chemical_leak": CHEMICAL_LEAK_PROFILE,
    "gas_leak": CHEMICAL_LEAK_PROFILE,
    "wildfire": WILDFIRE_PROFILE,
    "forest_fire": WILDFIRE_PROFILE,
    "urban_fire": WILDFIRE_PROFILE,
    "debris_flow": LANDSLIDE_PROFILE,
    "mudslide": LANDSLIDE_PROFILE,
}

# Generic fallback profile (used if an unknown custom scenario is evaluated)
DEFAULT_GENERIC_PROFILE = ScenarioSensorProfile(
    scenario_id="generic_disaster",
    name="Generic Multi-Sensor Emergency",
    category="General SAR",
    description="General search and rescue with balanced multi-sensor weighting.",
    primary_sensors=[
        SensorType.HEART_RATE_RADAR,
        SensorType.THERMAL_IMAGING,
        SensorType.ACOUSTIC,
        SensorType.PIR_MOTION,
    ],
    supporting_sensors=[
        SensorType.RGB_CAMERA,
        SensorType.CO2,
        SensorType.GPS,
        SensorType.TEMPERATURE,
        SensorType.HUMIDITY,
        SensorType.IMU_VIBRATION,
        SensorType.IMU_TILT,
        SensorType.WATER_LEVEL,
        SensorType.WATER_FLOW,
        SensorType.RAINFALL_INTENSITY,
        SensorType.GAS_CONCENTRATION,
        SensorType.SMOKE_DENSITY,
        SensorType.SOIL_MOISTURE,
        SensorType.BAROMETRIC_PRESSURE,
    ],
    inactive_sensors=[],
    sensor_weights={
        SensorType.HEART_RATE_RADAR: 0.35,
        SensorType.THERMAL_IMAGING: 0.25,
        SensorType.ACOUSTIC: 0.25,
        SensorType.CO2: 0.10,
        SensorType.RGB_CAMERA: 0.05,
    },
    hazard_weights={},
    minimum_evidence_count=1,
)


def normalize_scenario_id(scenario_id: Optional[str]) -> str:
    """Normalize scenario ID string for robust matching."""
    if not scenario_id:
        return "generic_disaster"
    s = str(scenario_id).strip().lower().replace("-", "_").replace(" ", "_")
    return s


def get_scenario_sensor_profile(scenario_id: Optional[str]) -> ScenarioSensorProfile:
    """
    Retrieve the ScenarioSensorProfile for a given scenario ID or alias.
    Falls back gracefully to DEFAULT_GENERIC_PROFILE if unrecognized.
    """
    norm = normalize_scenario_id(scenario_id)
    if norm in SCENARIO_SENSOR_PROFILES:
        return SCENARIO_SENSOR_PROFILES[norm]
    
    # Prefix / substring match
    for k, profile in SCENARIO_SENSOR_PROFILES.items():
        if norm.startswith(k) or k.startswith(norm):
            return profile
            
    return DEFAULT_GENERIC_PROFILE


def get_sensor_role(scenario_id: Optional[str], sensor_type: SensorType | str) -> SensorRole:
    """Return runtime SensorRole (PRIMARY, SUPPORTING, INACTIVE) for scenario and sensor."""
    profile = get_scenario_sensor_profile(scenario_id)
    return profile.get_role(sensor_type)


def get_scenario_sensor_state_map(scenario_id: Optional[str]) -> list[Dict[str, Any]]:
    """Return list of state dictionaries for each sensor type containing role, active state, weight, and contribution."""
    profile = get_scenario_sensor_profile(scenario_id)
    return list(profile.get_sensor_state_map().values())
