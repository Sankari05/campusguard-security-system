"""
test_barometric_pressure_foundation.py
---------------------------------------
Unit and database persistence tests for Barometric Pressure configuration,
data models, strict validation, and database operations.
"""

import math
import tempfile
import os
import pytest
from backend.models import (
    SensorType,
    SensorHealthStatus,
    PressureTrend,
    PressureDropSeverity,
    PressureAnomalyLevel,
    PressureConfig,
    PRESSURE_CONFIG,
    BarometricPressureReading,
    BarometricPressureInterface,
    GPSCoordinate,
    SensorHealth,
)
import backend.db as db


class DummyPressureAdapter(BarometricPressureInterface):
    """Test implementation of BarometricPressureInterface."""
    def __init__(self, pressure: float = 1013.25, status: SensorHealthStatus = SensorHealthStatus.ONLINE):
        self._pressure = pressure
        self._status = status
        self._interval = 4.0

    def read_sensor(self) -> BarometricPressureReading:
        return BarometricPressureReading(
            sensor_id="ENV-BARO-01",
            device_id="DEV-BARO-01",
            pressure_hpa=self._pressure,
            status=self._status,
        )

    def get_health(self) -> SensorHealth:
        return SensorHealth(
            sensor_id="ENV-BARO-01",
            sensor_type=SensorType.BAROMETRIC_PRESSURE,
            status=self._status,
        )

    def set_sampling_interval(self, seconds: float) -> None:
        self._interval = seconds


def test_pressure_config_defaults():
    """Verify centralized PRESSURE_CONFIG has configured application/simulation thresholds."""
    assert PRESSURE_CONFIG.min_pressure_hpa == 850.0
    assert PRESSURE_CONFIG.max_pressure_hpa == 1100.0
    assert PRESSURE_CONFIG.nominal_baseline_hpa == 1013.25
    assert PRESSURE_CONFIG.falling_threshold_hpa_per_cycle == 2.0
    assert PRESSURE_CONFIG.rapid_falling_threshold_hpa_per_cycle == 4.0
    assert PRESSURE_CONFIG.rising_threshold_hpa_per_cycle == 2.0
    assert PRESSURE_CONFIG.rapid_rising_threshold_hpa_per_cycle == 4.0
    assert PRESSURE_CONFIG.history_window_size == 60
    assert PRESSURE_CONFIG.rate_calculation_unit == "cycle"
    assert PRESSURE_CONFIG.severe_cyclone_threshold_hpa == 990.0
    assert PRESSURE_CONFIG.critical_plunge_threshold_hpa == 975.0


def test_sensor_type_barometric_pressure_enum():
    """Verify SensorType.BAROMETRIC_PRESSURE exists and has value 'barometric_pressure'."""
    assert SensorType.BAROMETRIC_PRESSURE == "barometric_pressure"
    assert SensorType.BAROMETRIC_PRESSURE.value == "barometric_pressure"


def test_pressure_enums():
    """Verify PressureTrend, PressureDropSeverity, PressureAnomalyLevel enum values."""
    assert PressureTrend.STABLE == "STABLE"
    assert PressureTrend.RISING == "RISING"
    assert PressureTrend.FALLING == "FALLING"
    assert PressureTrend.RAPIDLY_FALLING == "RAPIDLY_FALLING"
    assert PressureTrend.RAPIDLY_RISING == "RAPIDLY_RISING"

    assert PressureDropSeverity.NORMAL == "NORMAL"
    assert PressureDropSeverity.SIGNIFICANT_DROP == "SIGNIFICANT_DROP"
    assert PressureDropSeverity.RAPID_DROP == "RAPID_DROP"
    assert PressureDropSeverity.CRITICAL_DROP == "CRITICAL_DROP"

    assert PressureAnomalyLevel.NORMAL == "NORMAL"
    assert PressureAnomalyLevel.ABNORMAL == "ABNORMAL"
    assert PressureAnomalyLevel.CRITICAL == "CRITICAL"


def test_barometric_reading_validation_valid():
    """Verify valid readings pass validation."""
    reading = BarometricPressureReading(
        sensor_id="ENV-BARO-01",
        pressure_hpa=1010.5,
        unit="hPa",
        status=SensorHealthStatus.ONLINE,
        location=GPSCoordinate(latitude=19.076, longitude=72.877),
    )
    assert reading.validate() is True
    d = reading.to_dict()
    assert d["pressure_hpa"] == 1010.5
    assert d["unit"] == "hPa"
    assert d["status"] == "ONLINE"
    assert d["location"] == (19.076, 72.877)


def test_barometric_reading_validation_invalid_nan_inf():
    """Verify validation strictly rejects NaN and Infinity without converting to 0."""
    r_nan = BarometricPressureReading(pressure_hpa=float("nan"))
    assert r_nan.validate() is False

    r_inf = BarometricPressureReading(pressure_hpa=float("inf"))
    assert r_inf.validate() is False

    r_neg_inf = BarometricPressureReading(pressure_hpa=float("-inf"))
    assert r_neg_inf.validate() is False


def test_barometric_reading_validation_out_of_bounds():
    """Verify validation rejects negative or out-of-range pressures."""
    r_low = BarometricPressureReading(pressure_hpa=500.0)  # below min 850
    assert r_low.validate() is False

    r_high = BarometricPressureReading(pressure_hpa=1250.0)  # above max 1100
    assert r_high.validate() is False

    r_zero = BarometricPressureReading(pressure_hpa=0.0)  # 0 is physically impossible atmosphere
    assert r_zero.validate() is False


def test_barometric_reading_validation_invalid_metadata():
    """Verify validation rejects invalid timestamps or empty sensor IDs."""
    r_empty_id = BarometricPressureReading(sensor_id="")
    assert r_empty_id.validate() is False

    r_empty_ts = BarometricPressureReading(timestamp="")
    assert r_empty_ts.validate() is False


def test_barometric_interface_adapter():
    """Verify BarometricPressureInterface abstraction works with adapters."""
    adapter = DummyPressureAdapter(pressure=985.0, status=SensorHealthStatus.ONLINE)
    reading = adapter.read_sensor()
    assert reading.pressure_hpa == 985.0
    assert reading.validate() is True

    health = adapter.get_health()
    assert health.sensor_type == SensorType.BAROMETRIC_PRESSURE
    assert health.status == SensorHealthStatus.ONLINE


def test_barometric_db_persistence():
    """Verify SQLite persistence for single and batch barometric pressure readings."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        db.init_db(db_path=db_path)
        session_id = "test-baro-session-01"
        db.create_session(session_id=session_id, seed=42, enable_degradation=False, victim_count=4, db_path=db_path)

        reading1 = BarometricPressureReading(
            sensor_id="ENV-BARO-01",
            device_id="DEV-BARO-01",
            pressure_hpa=1012.0,
            rate_of_change=-1.5,
            trend=PressureTrend.FALLING,
            drop_severity=PressureDropSeverity.NORMAL,
            anomaly_level=PressureAnomalyLevel.NORMAL,
            location=GPSCoordinate(latitude=28.61, longitude=77.20),
            timestamp="2026-08-19T08:00:00Z",
        )
        db.log_barometric_reading(reading1, session_id=session_id, db_path=db_path)

        latest = db.get_latest_barometric_reading(session_id=session_id, db_path=db_path)
        assert latest is not None
        assert latest["pressure_hpa"] == 1012.0
        assert latest["unit"] == "hPa"
        assert latest["trend"] == "FALLING"
        assert latest["latitude"] == 28.61

        # Batch write
        batch = [
            BarometricPressureReading(
                sensor_id="ENV-BARO-01",
                pressure_hpa=1008.0,
                trend=PressureTrend.FALLING,
                timestamp="2026-08-19T08:01:00Z",
            ),
            BarometricPressureReading(
                sensor_id="ENV-BARO-01",
                pressure_hpa=1000.0,
                trend=PressureTrend.RAPIDLY_FALLING,
                timestamp="2026-08-19T08:02:00Z",
            ),
        ]
        db.log_barometric_readings_batch(batch, session_id=session_id, db_path=db_path)

        history = db.get_barometric_history(session_id=session_id, limit=10, db_path=db_path)
        assert len(history) == 3
        # Chronologically ordered (oldest to newest)
        assert history[0]["pressure_hpa"] == 1012.0
        assert history[1]["pressure_hpa"] == 1008.0
        assert history[2]["pressure_hpa"] == 1000.0
        assert history[2]["trend"] == "RAPIDLY_FALLING"

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
