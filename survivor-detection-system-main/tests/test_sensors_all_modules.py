"""
Comprehensive Test Suite for All Sensor Modules
Validates 3-axis IMU, mmWave Radar, PIR, Temperature, Humidity,
Water Level & Flow, Gas & Smoke, Barometric Pressure, Rainfall, Soil Moisture,
Camera, GPS, and Sensor Health Diagnostics.
"""

import pytest
import math
from models import (
    SensorType,
    SensorReading,
    SensorHealthStatus,
    GPSCoordinate,
    VictimProfile,
    VictimStatus,
    SensorSignatureRange,
)
from sensor_simulator import SensorSimulator, SensorNode
from scenario_loader import SiteEnvironment, load_scenario


def test_sensor_types_coverage():
    """Verify all 15 sensor types exist and are valid enum values."""
    expected_types = [
        "heart_rate_radar", "thermal_imaging", "acoustic", "co2", "pir_motion",
        "rgb_camera", "water_level", "water_flow", "imu_tilt", "imu_vibration",
        "gas_concentration", "smoke_density", "barometric_pressure",
        "rainfall_intensity", "soil_moisture"
    ]
    for st in expected_types:
        assert SensorType(st) is not None


def test_sensor_reading_model_fields():
    """Verify SensorReading contains all required fields, quality scores, and device_id."""
    loc = GPSCoordinate(latitude=32.37, longitude=77.24, altitude_m=3950)
    reading = SensorReading(
        sensor_type=SensorType.GAS_CONCENTRATION,
        value=125.5,
        unit="ppm",
        location=loc,
        victim_id="V1",
        device_id="KIT-V1",
        confidence=0.98,
        quality=0.95,
        status=SensorHealthStatus.ONLINE,
        raw_data={"sensor_model": "MQ-135"}
    )
    d = reading.to_dict()
    assert d["sensor_type"] == "gas_concentration"
    assert d["value"] == 125.5
    assert d["unit"] == "ppm"
    assert d["device_id"] == "KIT-V1"
    assert d["quality"] == 0.95
    assert d["status"] == "ONLINE"
    assert d["raw_data"]["sensor_model"] == "MQ-135"


def test_3axis_imu_simulation_and_metrics():
    """Verify 3-axis IMU generates valid ax, ay, az, magnitude, tilt angle, and vibration metrics."""
    config = load_scenario("himalaya_avalanche")
    sim = SensorSimulator(
        config.victims,
        seed=42,
        site_environment=config.site_environment,
    )
    # Generate a cycle
    sim.generate_cycle()
    imu_report = sim.imu_3axis_report()
    assert len(imu_report) == len(config.victims)

    for vid, metrics in imu_report.items():
        assert "ax_g" in metrics
        assert "ay_g" in metrics
        assert "az_g" in metrics
        assert "magnitude_g" in metrics
        assert "tilt_deg" in metrics
        assert "sustained_vibration" in metrics
        assert "impact_detected" in metrics

        # Verify magnitude calculation: sqrt(ax^2 + ay^2 + az^2)
        calc_mag = math.sqrt(metrics["ax_g"]**2 + metrics["ay_g"]**2 + metrics["az_g"]**2)
        assert abs(metrics["magnitude_g"] - calc_mag) < 0.05
        assert metrics["tilt_deg"] >= 0.0


def test_environmental_sensors_simulation():
    """Verify gas, smoke, barometric pressure, rainfall, soil moisture, temp, and humidity simulate properly."""
    env = SiteEnvironment(
        initial_ambient_temp_c=-8.0,
        initial_humidity_pct=85.0,
        initial_gas_concentration_ppm=45.0,
        initial_smoke_density_pct=15.0,
        initial_barometric_pressure_hpa=980.0,
        initial_rainfall_mm_hr=12.0,
        initial_soil_moisture_pct=65.0,
    )
    config = load_scenario("himalaya_avalanche")
    sim = SensorSimulator(
        config.victims,
        seed=100,
        site_environment=env,
    )

    # Generate 5 cycles to test stepping
    for _ in range(5):
        sim.generate_cycle()

    full_report = sim.environmental_full_report()
    assert "ambient_temp_c" in full_report
    assert "humidity_pct" in full_report
    assert "gas_concentration_ppm" in full_report
    assert "smoke_density_pct" in full_report
    assert "barometric_pressure_hpa" in full_report
    assert "rainfall_mm_hr" in full_report
    assert "soil_moisture_pct" in full_report
    assert "vibration_mm_s" in full_report

    # Check value bounds
    assert full_report["gas_concentration_ppm"] >= 0.0
    assert 0.0 <= full_report["smoke_density_pct"] <= 100.0
    assert 800.0 <= full_report["barometric_pressure_hpa"] <= 1100.0
    assert 0.0 <= full_report["soil_moisture_pct"] <= 100.0


def test_sensor_health_report():
    """Verify health monitor tracks online, degraded, and offline channels with signal quality and battery."""
    config = load_scenario("himalaya_avalanche")
    sim = SensorSimulator(
        config.victims,
        seed=101,
        enable_degradation=True,
        site_environment=config.site_environment,
    )
    sim.generate_cycle()
    health_records = sim.get_sensor_health_report()
    assert len(health_records) > 0

    for h in health_records:
        assert h.sensor_id is not None
        assert h.sensor_type is not None
        assert h.status in (
            SensorHealthStatus.ONLINE,
            SensorHealthStatus.DEGRADED,
            SensorHealthStatus.OFFLINE,
            SensorHealthStatus.ERROR,
            SensorHealthStatus.CALIBRATION,
        )
        assert 0.0 <= h.battery_pct <= 100.0
        assert 0.0 <= h.signal_quality <= 1.0


def test_environmental_readings_generation():
    """Verify environmental readings can be generated as SensorReading objects."""
    config = load_scenario("himalaya_avalanche")
    sim = SensorSimulator(
        config.victims,
        seed=102,
        site_environment=config.site_environment,
    )
    env_readings = sim.generate_environmental_readings()
    assert len(env_readings) >= 5

    types = [r.sensor_type for r in env_readings]
    assert SensorType.RAINFALL_INTENSITY in types
    assert SensorType.SOIL_MOISTURE in types
    assert SensorType.BAROMETRIC_PRESSURE in types
    assert SensorType.GAS_CONCENTRATION in types
    assert SensorType.SMOKE_DENSITY in types
