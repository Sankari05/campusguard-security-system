"""
tests/test_non_contact_pressure.py
----------------------------------
Comprehensive Unit Test Suite for RIDGEWATCH Non-Contact Water Level & Hydrostatic Pressure Module.

Tests:
1. Zero water depth => zero gauge pressure.
2. 1 metre water depth => ~9.80665 kPa.
3. 2 metre water depth => ~19.6133 kPa.
4. Negative distance rejected.
5. Out-of-range distance rejected.
6. Stale reading rejected.
7. Sudden impossible jump rejected.
8. Sensor above water with correct mount height produces correct depth.
9. Sensor surface distance equal to mount height produces zero depth.
10. Integration with NonContactPressureEngine stateful processing.
"""

import math
import sys
import os
from datetime import datetime, timezone, timedelta

# Ensure backend path is available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from non_contact_pressure import (
    NonContactPressureConfig,
    NonContactSensorReading,
    NonContactPressureEstimate,
    NonContactPressureEngine,
    calculate_water_depth,
    calculate_hydrostatic_pressure,
    validate_sensor_reading,
    estimate_pressure_from_sensor,
)


def test_zero_water_depth_zero_gauge_pressure():
    """Test 1: Zero water depth must produce exactly 0.0 Pa and 0.0 kPa gauge pressure."""
    pa, kpa = calculate_hydrostatic_pressure(water_depth_m=0.0)
    assert pa == 0.0
    assert kpa == 0.0

    # Negative depth guard check
    pa_neg, kpa_neg = calculate_hydrostatic_pressure(water_depth_m=-0.5)
    assert pa_neg == 0.0
    assert kpa_neg == 0.0


def test_one_meter_depth_pressure():
    """Test 2: 1.0 metre fresh water depth => approximately 9.80665 kPa (9806.65 Pa)."""
    pa, kpa = calculate_hydrostatic_pressure(
        water_depth_m=1.0,
        density_kg_m3=1000.0,
        gravity_m_s2=9.80665,
    )
    assert math.isclose(pa, 9806.65, rel_tol=1e-4)
    assert math.isclose(kpa, 9.80665, rel_tol=1e-4)


def test_two_meter_depth_pressure():
    """Test 3: 2.0 metre fresh water depth => approximately 19.6133 kPa (19613.3 Pa)."""
    pa, kpa = calculate_hydrostatic_pressure(
        water_depth_m=2.0,
        density_kg_m3=1000.0,
        gravity_m_s2=9.80665,
    )
    assert math.isclose(pa, 19613.3, rel_tol=1e-4)
    assert math.isclose(kpa, 19.6133, rel_tol=1e-4)


def test_negative_distance_rejected():
    """Test 4: Negative downward distance (d < 0) is physically impossible and must be rejected."""
    config = NonContactPressureConfig(sensor_mount_height_m=5.0, sensor_max_range_m=10.0)
    is_valid, reason = validate_sensor_reading(distance_m=-0.25, config=config)
    assert not is_valid
    assert reason == "NEGATIVE_DISTANCE_REJECTED"

    estimate = estimate_pressure_from_sensor(measured_surface_distance_m=-1.0, config=config)
    assert not estimate.is_valid
    assert estimate.reading_quality == "INVALID"
    assert estimate.water_depth_m is None
    assert estimate.estimated_pressure_kpa is None


def test_out_of_range_distance_rejected():
    """Test 5: Surface distance exceeding max configured sensor range must be rejected."""
    config = NonContactPressureConfig(sensor_mount_height_m=5.0, sensor_max_range_m=10.0)
    is_valid, reason = validate_sensor_reading(distance_m=12.5, config=config)
    assert not is_valid
    assert reason == "OUT_OF_RANGE_REJECTED"

    estimate = estimate_pressure_from_sensor(measured_surface_distance_m=10.5, config=config)
    assert not estimate.is_valid
    assert estimate.reading_quality == "INVALID"
    assert estimate.water_depth_m is None
    assert estimate.estimated_pressure_kpa is None


def test_stale_reading_rejected():
    """Test 6: Reading timestamp older than timeout window must be flagged as stale and rejected."""
    config = NonContactPressureConfig(sensor_timeout_seconds=10.0)
    now = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    stale_ts = (now - timedelta(seconds=25.0)).isoformat()

    is_valid, reason = validate_sensor_reading(
        distance_m=3.5,
        config=config,
        timestamp_str=stale_ts,
        current_time=now,
    )
    assert not is_valid
    assert reason == "STALE_READING_REJECTED"

    estimate = estimate_pressure_from_sensor(
        measured_surface_distance_m=3.5,
        config=config,
        timestamp_str=stale_ts,
        current_time=now,
    )
    assert not estimate.is_valid
    assert estimate.reading_quality == "STALE"


def test_sudden_impossible_jump_rejected():
    """Test 7: Sudden impossible displacement jump exceeding max_jump_rate_m_s must be rejected."""
    config = NonContactPressureConfig(max_jump_rate_m_s=3.0)
    now = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    prev_ts = (now - timedelta(seconds=1.0)).isoformat()
    curr_ts = now.isoformat()

    prev_reading = {
        "measured_surface_distance_m": 4.5,
        "reading_timestamp": prev_ts,
    }

    # Jump from 4.5m to 0.5m in 1.0s is 4.0 m/s delta, exceeding 3.0 m/s threshold
    is_valid, reason = validate_sensor_reading(
        distance_m=0.5,
        config=config,
        timestamp_str=curr_ts,
        previous_reading=prev_reading,
        current_time=now,
    )
    assert not is_valid
    assert reason == "IMPOSSIBLE_JUMP_REJECTED"

    estimate = estimate_pressure_from_sensor(
        measured_surface_distance_m=0.5,
        config=config,
        timestamp_str=curr_ts,
        previous_reading=prev_reading,
        current_time=now,
    )
    assert not estimate.is_valid
    assert estimate.reading_quality == "INVALID"


def test_sensor_above_water_with_correct_mount_height():
    """Test 8: Sensor mounted at 5.0m with surface distance 3.2m produces depth 1.8m and ~17.652 kPa."""
    config = NonContactPressureConfig(
        sensor_mount_height_m=5.0,
        pressure_datum_m=0.0,
        water_density_kg_m3=1000.0,
        gravity_m_s2=9.80665,
    )
    depth = calculate_water_depth(surface_distance_m=3.2, mount_height_m=5.0, datum_m=0.0)
    assert math.isclose(depth, 1.8, rel_tol=1e-4)

    estimate = estimate_pressure_from_sensor(measured_surface_distance_m=3.2, config=config)
    assert estimate.is_valid
    assert math.isclose(estimate.water_depth_m, 1.8, rel_tol=1e-4)
    expected_pa = 1000.0 * 9.80665 * 1.8
    assert math.isclose(estimate.estimated_pressure_pa, expected_pa, rel_tol=1e-3)
    assert math.isclose(estimate.estimated_pressure_kpa, expected_pa / 1000.0, rel_tol=1e-3)
    assert estimate.pressure_source == "non_contact_sensor_estimation"


def test_surface_distance_equal_mount_height_zero_depth():
    """Test 9: Distance equal to mount height (5.0m) means zero water depth & zero pressure."""
    config = NonContactPressureConfig(sensor_mount_height_m=5.0, pressure_datum_m=0.0)
    depth = calculate_water_depth(surface_distance_m=5.0, mount_height_m=5.0, datum_m=0.0)
    assert depth == 0.0

    estimate = estimate_pressure_from_sensor(measured_surface_distance_m=5.0, config=config)
    assert estimate.is_valid
    assert estimate.water_depth_m == 0.0
    assert estimate.estimated_pressure_pa == 0.0
    assert estimate.estimated_pressure_kpa == 0.0


def test_stateful_non_contact_pressure_engine():
    """Test 10: NonContactPressureEngine stateful processing, history retention, and fallback report."""
    engine = NonContactPressureEngine(NonContactPressureConfig(sensor_mount_height_m=4.0))
    
    # Process baseline dry reading (distance 4.0m)
    est1 = engine.process_reading(distance_m=4.0)
    assert est1.is_valid
    assert est1.water_depth_m == 0.0
    assert est1.estimated_pressure_kpa == 0.0

    # Process flood surge reading (distance 2.5m => depth 1.5m)
    est2 = engine.process_reading(distance_m=2.5)
    assert est2.is_valid
    assert math.isclose(est2.water_depth_m, 1.5, rel_tol=1e-4)
    assert math.isclose(est2.estimated_pressure_kpa, 1.5 * 9.80665, rel_tol=1e-3)

    # Process invalid corrupted reading (None)
    est3 = engine.process_reading(distance_m=None)
    assert not est3.is_valid
    assert est3.reading_quality == "SENSOR_OFFLINE"

    # Verify report dictionary structure
    rep = engine.get_latest_report()
    assert "sensor_type" in rep
    assert "pressure_source" in rep
    assert rep["pressure_source"] == "non_contact_sensor_estimation"
    assert len(engine.history) == 3


def test_non_contact_pressure_api_endpoints():
    """Test 11: FastAPI endpoint returns valid structured non-contact pressure telemetry."""
    from fastapi.testclient import TestClient
    from api import app

    client = TestClient(app)
    response = client.get("/sensors/non-contact-pressure/current")
    assert response.status_code == 200
    data = response.json()
    assert "non_contact_pressure" in data
    assert "pressure_source" in data["non_contact_pressure"]
    assert data["non_contact_pressure"]["pressure_source"] == "non_contact_sensor_estimation"

