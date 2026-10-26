"""
test_scenario_sensor_activation.py
----------------------------------
Validates that activating a scenario enables primary/supporting sensors
and leaves inactive channels at nominal baseline in the simulation.
"""

import pytest
# pyrefly: ignore [missing-import]
from models import SensorType, HIMALAYA_VICTIMS
# pyrefly: ignore [missing-import]
from sensor_simulator import SensorSimulator


def test_sensor_simulator_scenario_activation():
    """Verify that SensorSimulator initializes with active scenario profile."""
    sim = SensorSimulator(victims=HIMALAYA_VICTIMS, scenario_id="chemical_gas_leak")
    assert sim.scenario_id == "chemical_gas_leak"
    assert sim.profile.is_active(SensorType.GAS_CONCENTRATION) is True
    assert sim.profile.is_active(SensorType.WATER_LEVEL) is False


def test_dynamic_set_scenario():
    """Verify that set_scenario dynamically transitions the simulator profile."""
    sim = SensorSimulator(victims=HIMALAYA_VICTIMS, scenario_id="earthquake_building_collapse")
    assert sim.profile.is_active(SensorType.IMU_VIBRATION) is True
    assert sim.profile.is_active(SensorType.WATER_LEVEL) is False

    # Switch to flood
    sim.set_scenario("flood_urban")
    assert sim.scenario_id == "flood_urban"
    assert sim.profile.is_active(SensorType.WATER_LEVEL) is True
    assert sim.profile.is_active(SensorType.GAS_CONCENTRATION) is False


def test_inactive_sensors_produce_nominal_baseline():
    """Verify that inactive channels in a scenario step to 0.0 or nominal baseline."""
    # Gas leak scenario -> water and rain are inactive
    sim = SensorSimulator(victims=HIMALAYA_VICTIMS, scenario_id="chemical_gas_leak")
    readings = sim.generate_cycle()
    
    # Rainfall and water level should remain nominal zero
    assert sim._rain_mm_hr == 0.0
    for r in readings:
        if r.sensor_type == SensorType.WATER_LEVEL:
            assert r.value == 0.0
        elif r.sensor_type == SensorType.WATER_FLOW:
            assert r.value == 0.0


def test_primary_sensors_dynamic_stepping():
    """Verify that primary channels exhibit dynamic scenario values."""
    # Chemical leak -> gas is active and non-zero
    sim = SensorSimulator(victims=HIMALAYA_VICTIMS, scenario_id="chemical_gas_leak")
    sim.generate_cycle()
    assert sim._gas_ppm > 0.0
    assert sim._smoke_pct > 0.0
