"""
test_rainfall_simulation_adapter.py
-----------------------------------
Unit tests for RainfallSimulationAdapter and SensorSimulator integration.
"""

import pytest
from backend.models import RainfallClassification, RainfallTrend, SensorHealthStatus
from backend.sensor_simulator import SensorSimulator, RainfallSimulationAdapter


def test_rainfall_simulation_adapter_initialization():
    adapter = RainfallSimulationAdapter(sensor_id="TEST-RAIN-01")
    assert adapter.sensor_id == "TEST-RAIN-01"
    assert adapter._simulation_profile == "AUTO"
    assert adapter._rainfall_rate_mm_h >= 0.0
    assert adapter._cumulative_rainfall_mm >= 0.0
    assert adapter.status == SensorHealthStatus.ONLINE


def test_rainfall_simulation_profiles():
    adapter = RainfallSimulationAdapter()

    # NO_RAIN
    adapter.set_simulation_profile("NO_RAIN")
    reading = adapter.step_cycle()
    assert reading.rainfall_rate_mm_h == 0.0
    assert reading.classification == RainfallClassification.NO_RAIN

    # LIGHT
    adapter.set_simulation_profile("LIGHT")
    reading = adapter.step_cycle()
    assert 0.1 <= reading.rainfall_rate_mm_h <= 5.0
    assert reading.classification == RainfallClassification.LIGHT

    # MODERATE
    adapter.set_simulation_profile("MODERATE")
    reading = adapter.step_cycle()
    assert 5.0 < reading.rainfall_rate_mm_h <= 20.0
    assert reading.classification == RainfallClassification.MODERATE

    # HEAVY
    adapter.set_simulation_profile("HEAVY")
    reading = adapter.step_cycle()
    assert 20.0 < reading.rainfall_rate_mm_h <= 50.0
    assert reading.classification == RainfallClassification.HEAVY

    # VERY_HEAVY
    adapter.set_simulation_profile("VERY_HEAVY")
    reading = adapter.step_cycle()
    assert 50.0 < reading.rainfall_rate_mm_h <= 100.0
    assert reading.classification == RainfallClassification.VERY_HEAVY

    # EXTREME
    adapter.set_simulation_profile("EXTREME")
    reading = adapter.step_cycle()
    assert reading.rainfall_rate_mm_h > 100.0
    assert reading.classification == RainfallClassification.EXTREME

    # RAIN_SENSOR_FAILURE
    adapter.set_simulation_profile("RAIN_SENSOR_FAILURE")
    reading = adapter.step_cycle()
    assert reading.status == SensorHealthStatus.OFFLINE
    health = adapter.get_health()
    assert health.status == SensorHealthStatus.OFFLINE


def test_cumulative_accumulation_and_reset():
    adapter = RainfallSimulationAdapter()
    adapter.set_simulation_profile("HEAVY")
    
    # Step cycles to accumulate rain
    for _ in range(10):
        reading = adapter.step_cycle()
        assert reading.validate() is True

    cumul = adapter.get_cumulative_rainfall()
    assert cumul > 0.0

    adapter.reset_cumulative()
    assert adapter.get_cumulative_rainfall() == 0.0


def test_sensor_simulator_rainfall_integration():
    sim = SensorSimulator()
    assert hasattr(sim, "rainfall_adapter")

    # Generate full cycle
    sim.rainfall_adapter.set_simulation_profile("HEAVY")
    readings = sim.generate_cycle()
    
    # Check that environmental full report contains rainfall metrics
    env = sim.environmental_full_report()
    assert "rainfall_rate_mm_h" in env
    assert "cumulative_rainfall_mm" in env
    assert "rainfall_classification" in env
    assert env["rainfall_rate_mm_h"] > 0.0

    # Check dedicated rainfall report
    rep = sim.rainfall_report()
    assert rep["sensor_id"] == "ENV-RAIN-01"
    assert rep["rainfall_rate_mm_h"] > 0.0
    assert rep["classification"] in ("MODERATE", "HEAVY", "VERY_HEAVY")
    assert rep["unit"] == "mm/h"
