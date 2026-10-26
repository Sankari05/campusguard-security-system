"""
test_scenario_sensor_profiles.py
--------------------------------
Validates that each disaster scenario profile correctly defines its primary,
supporting, and inactive sensors, normalized sensor weights sum to 1.0,
and fallback logic works gracefully.
"""

import pytest
# pyrefly: ignore [missing-import]
from models import SensorType
# pyrefly: ignore [missing-import]
from scenario_sensor_profiles import (
    SensorRole,
    ScenarioSensorProfile,
    get_scenario_sensor_profile,
    get_sensor_role,
    get_scenario_sensor_state_map,
    SCENARIO_SENSOR_PROFILES,
)


def test_scenario_profiles_exist():
    """Ensure all 5 canonical scenarios have registered profiles."""
    expected_scenarios = [
        "earthquake_building_collapse",
        "flood_urban",
        "himalaya_avalanche",
        "chemical_gas_leak",
        "wildfire_forest",
    ]
    for s_id in expected_scenarios:
        profile = get_scenario_sensor_profile(s_id)
        assert profile is not None
        assert profile.scenario_id == s_id
        assert len(profile.primary_sensors) > 0
        assert len(profile.supporting_sensors) > 0
        assert len(profile.inactive_sensors) > 0


def test_earthquake_profile_classifications():
    """Verify Earthquake / Collapse sensor classifications."""
    profile = get_scenario_sensor_profile("earthquake_building_collapse")
    
    # Primaries
    assert SensorType.IMU_VIBRATION in profile.primary_sensors
    assert SensorType.HEART_RATE_RADAR in profile.primary_sensors
    assert SensorType.PIR_MOTION in profile.primary_sensors
    
    # Inactives
    assert SensorType.WATER_LEVEL in profile.inactive_sensors
    assert SensorType.WATER_FLOW in profile.inactive_sensors
    assert SensorType.GAS_CONCENTRATION in profile.inactive_sensors
    assert SensorType.RAINFALL_INTENSITY in profile.inactive_sensors
    assert SensorType.SOIL_MOISTURE in profile.inactive_sensors
    
    assert profile.get_role(SensorType.IMU_VIBRATION) == SensorRole.PRIMARY
    assert profile.get_role(SensorType.WATER_LEVEL) == SensorRole.INACTIVE
    assert profile.is_active(SensorType.IMU_VIBRATION) is True
    assert profile.is_active(SensorType.WATER_LEVEL) is False


def test_flood_profile_classifications():
    """Verify Flood sensor classifications."""
    profile = get_scenario_sensor_profile("flood_urban")
    
    # Primaries
    assert SensorType.WATER_LEVEL in profile.primary_sensors
    assert SensorType.WATER_FLOW in profile.primary_sensors
    assert SensorType.RAINFALL_INTENSITY in profile.primary_sensors
    
    # Inactives
    assert SensorType.GAS_CONCENTRATION in profile.inactive_sensors
    assert SensorType.SMOKE_DENSITY in profile.inactive_sensors
    assert SensorType.SOIL_MOISTURE in profile.inactive_sensors
    assert SensorType.BAROMETRIC_PRESSURE in profile.inactive_sensors
    
    assert profile.get_role(SensorType.WATER_LEVEL) == SensorRole.PRIMARY
    assert profile.get_role(SensorType.GAS_CONCENTRATION) == SensorRole.INACTIVE


def test_avalanche_profile_classifications():
    """Verify Avalanche sensor classifications."""
    profile = get_scenario_sensor_profile("himalaya_avalanche")
    
    # Primaries
    assert SensorType.IMU_VIBRATION in profile.primary_sensors
    assert SensorType.HEART_RATE_RADAR in profile.primary_sensors
    assert SensorType.IMU_TILT in profile.primary_sensors
    
    # Inactives
    assert SensorType.WATER_LEVEL in profile.inactive_sensors
    assert SensorType.WATER_FLOW in profile.inactive_sensors
    assert SensorType.GAS_CONCENTRATION in profile.inactive_sensors
    assert SensorType.SMOKE_DENSITY in profile.inactive_sensors
    assert SensorType.RAINFALL_INTENSITY in profile.inactive_sensors


def test_chemical_gas_leak_profile_classifications():
    """Verify Chemical / Toxic Gas Leak sensor classifications."""
    profile = get_scenario_sensor_profile("chemical_gas_leak")
    
    # Primaries
    assert SensorType.GAS_CONCENTRATION in profile.primary_sensors
    assert SensorType.SMOKE_DENSITY in profile.primary_sensors
    
    # Inactives
    assert SensorType.WATER_LEVEL in profile.inactive_sensors
    assert SensorType.WATER_FLOW in profile.inactive_sensors
    assert SensorType.RAINFALL_INTENSITY in profile.inactive_sensors
    assert SensorType.SOIL_MOISTURE in profile.inactive_sensors


def test_wildfire_profile_classifications():
    """Verify Wildfire sensor classifications."""
    profile = get_scenario_sensor_profile("wildfire_forest")
    
    # Primaries
    assert SensorType.TEMPERATURE in profile.primary_sensors
    assert SensorType.SMOKE_DENSITY in profile.primary_sensors
    assert SensorType.THERMAL_IMAGING in profile.primary_sensors
    
    # Inactives
    assert SensorType.WATER_LEVEL in profile.inactive_sensors
    assert SensorType.WATER_FLOW in profile.inactive_sensors
    assert SensorType.SOIL_MOISTURE in profile.inactive_sensors


def test_profile_weights_sum_to_one():
    """Verify that sensor weights sum to ~1.0 across all scenarios."""
    for s_id, profile in SCENARIO_SENSOR_PROFILES.items():
        total_weight = sum(profile.sensor_weights.values())
        assert abs(total_weight - 1.0) < 1e-4, f"Scenario {s_id} weights sum to {total_weight}, expected 1.0"


def test_scenario_aliases_and_case_insensitivity():
    """Verify aliases and case insensitivity work correctly."""
    p1 = get_scenario_sensor_profile("FLOOD_URBAN")
    assert p1.scenario_id == "flood_urban"
    
    p2 = get_scenario_sensor_profile("earthquake")
    assert p2.scenario_id == "earthquake_building_collapse"
    
    p3 = get_scenario_sensor_profile("gas_leak")
    assert p3.scenario_id == "chemical_gas_leak"
    
    p4 = get_scenario_sensor_profile("wildfire")
    assert p4.scenario_id == "wildfire_forest"
    
    p5 = get_scenario_sensor_profile("avalanche")
    assert p5.scenario_id == "himalaya_avalanche"


def test_generic_fallback_profile():
    """Verify unknown scenario falls back safely to generic profile without crashing."""
    p = get_scenario_sensor_profile("unknown_apocalyptic_event_99")
    assert p is not None
    assert p.scenario_id in ("generic", "generic_disaster")
    assert len(p.primary_sensors) > 0


def test_sensor_state_map_generation():
    """Verify get_scenario_sensor_state_map returns formatted matrix for all sensors."""
    matrix = get_scenario_sensor_state_map("flood_urban")
    assert len(matrix) == len(SensorType)
    for item in matrix:
        assert "sensor_type" in item
        assert "role" in item
        assert "status" in item
        assert "weight" in item
