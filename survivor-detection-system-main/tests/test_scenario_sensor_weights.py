"""
test_scenario_sensor_weights.py
-------------------------------
Validates scenario-specific sensor weight distributions and hazard multipliers.
"""

import pytest
from models import SensorType
from scenario_sensor_profiles import get_scenario_sensor_profile
from fusion_engine import HazardContext


def test_scenario_weight_distributions():
    """Verify that primary sensors receive highest weights in each scenario profile."""
    # Earthquake
    eq = get_scenario_sensor_profile("earthquake_building_collapse")
    assert eq.sensor_weights[SensorType.IMU_VIBRATION] >= 0.15
    assert eq.sensor_weights[SensorType.HEART_RATE_RADAR] >= 0.20
    assert eq.get_weight(SensorType.WATER_LEVEL) == 0.0

    # Flood
    fl = get_scenario_sensor_profile("flood_urban")
    assert fl.sensor_weights[SensorType.WATER_LEVEL] >= 0.20
    assert fl.sensor_weights[SensorType.RAINFALL_INTENSITY] >= 0.10
    assert fl.get_weight(SensorType.GAS_CONCENTRATION) == 0.0

    # Chemical leak
    ch = get_scenario_sensor_profile("chemical_gas_leak")
    assert ch.sensor_weights[SensorType.GAS_CONCENTRATION] >= 0.25
    assert ch.sensor_weights[SensorType.SMOKE_DENSITY] >= 0.15
    assert ch.get_weight(SensorType.WATER_LEVEL) == 0.0


def test_hazard_multiplier_with_scenario_filtering():
    """Verify that HazardContext multiplier filters inactive bonuses according to scenario profile."""
    # Create a hazard context with high water and vibration
    hazard = HazardContext(
        water_level_cm=80.0,
        water_rising_rate_cm_per_cycle=10.0,
        vibration_mm_s=15.0,
    )
    
    # In flood: water is primary (active), vibration is supporting (active)
    fl_mult = hazard.multiplier(scenario_id="flood_urban")
    fl_bd = hazard.multiplier_breakdown(scenario_id="flood_urban")
    assert fl_bd["water_level"] > 0.0
    assert fl_bd["water_rising"] > 0.0
    assert fl_mult > 1.0

    # In earthquake: water is INACTIVE -> water bonuses must be zeroed out
    eq_bd = hazard.multiplier_breakdown(scenario_id="earthquake_building_collapse")
    assert eq_bd["water_level"] == 0.0
    assert eq_bd["water_rising"] == 0.0
    assert eq_bd["vibration"] > 0.0
