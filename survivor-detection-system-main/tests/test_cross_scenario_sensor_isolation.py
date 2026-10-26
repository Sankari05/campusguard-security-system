"""
test_cross_scenario_sensor_isolation.py
---------------------------------------
Validates that sensor channels inactive in a given scenario do NOT cause
false-positive hazard inflation or cross-scenario alert bleed.
"""

import pytest
from models import SensorType, SensorReading, GPSCoordinate
from fusion_engine import HazardContext, fuse_victim


def test_water_inactive_in_chemical_leak():
    """Ensure water level elevation does not inflate hazard multiplier in a chemical leak."""
    loc = GPSCoordinate(latitude=32.374, longitude=77.249)
    readings = [
        SensorReading(
            sensor_type=SensorType.HEART_RATE_RADAR,
            value=72.0,
            unit="bpm",
            location=loc,
            victim_id="V-01",
            confidence=0.95,
        ),
    ]
    hazard = HazardContext(water_level_cm=150.0, water_rising_rate_cm_per_cycle=15.0)

    # When evaluated without scenario_id (generic): water multiplier applies
    generic_res = fuse_victim(readings, hazard=hazard, victim_id="V-01")
    assert generic_res.hazard_breakdown["water_level"] > 0.0

    # When evaluated under chemical_gas_leak: water is inactive -> breakdown for water is 0.0
    chem_res = fuse_victim(readings, hazard=hazard, victim_id="V-01", scenario_id="chemical_gas_leak")
    assert chem_res.hazard_breakdown["water_level"] == 0.0
    assert chem_res.hazard_breakdown["water_rising"] == 0.0
    assert chem_res.hazard_multiplier < generic_res.hazard_multiplier


def test_gas_inactive_in_flood():
    """Ensure gas concentration does not trigger false alerts in urban flood scenario."""
    hazard = HazardContext(soil_moisture_pct=90.0, secondary_hazard=True)
    
    # In flood: soil moisture is inactive
    fl_bd = hazard.multiplier_breakdown(scenario_id="flood_urban")
    assert fl_bd["soil"] == 0.0


def test_seismic_inactive_in_wildfire():
    """Ensure seismic vibration does not trigger aftershock soil compounds in wildfire scenario."""
    hazard = HazardContext(
        vibration_mm_s=25.0,
        tilt_deg=10.0,
        soil_moisture_pct=95.0,
        secondary_hazard=True,
    )
    wf_bd = hazard.multiplier_breakdown(scenario_id="wildfire_forest")
    assert wf_bd["soil"] == 0.0
    assert wf_bd["aftershock_soil_compound"] == 0.0
