"""
test_rainfall_sensor_foundation.py
----------------------------------
Unit tests for Rainfall data models, validation constraints, interface contracts,
and database persistence/analytics functions.
"""

import math
import pytest
from backend.models import (
    RainfallClassification,
    RainfallTrend,
    RainfallConfig,
    RAINFALL_CONFIG,
    RainfallReading,
    RainfallSensorInterface,
    GPSCoordinate,
    SensorHealthStatus,
    RiskLevel,
)
import backend.db as db


def test_rainfall_classification_enums():
    assert RainfallClassification.NO_RAIN.value == "NO_RAIN"
    assert RainfallClassification.LIGHT.value == "LIGHT"
    assert RainfallClassification.MODERATE.value == "MODERATE"
    assert RainfallClassification.HEAVY.value == "HEAVY"
    assert RainfallClassification.VERY_HEAVY.value == "VERY_HEAVY"
    assert RainfallClassification.EXTREME.value == "EXTREME"


def test_rainfall_trend_enums():
    assert RainfallTrend.STABLE.value == "STABLE"
    assert RainfallTrend.INCREASING.value == "INCREASING"
    assert RainfallTrend.RAPIDLY_INCREASING.value == "RAPIDLY_INCREASING"
    assert RainfallTrend.DECREASING.value == "DECREASING"
    assert RainfallTrend.UNKNOWN.value == "UNKNOWN"


def test_rainfall_config_thresholds():
    cfg = RainfallConfig()
    assert cfg.no_rain_threshold == 0.0
    assert cfg.light_threshold_mm_h == 5.0
    assert cfg.moderate_threshold_mm_h == 20.0
    assert cfg.heavy_threshold_mm_h == 50.0
    assert cfg.very_heavy_threshold_mm_h == 100.0
    assert cfg.extreme_threshold_mm_h == 100.0
    assert cfg.flash_flood_trigger_mm_h == 30.0
    assert cfg.landslide_trigger_mm_h == 25.0
    assert cfg.critical_accumulation_mm == 100.0


def test_rainfall_reading_validation_success():
    loc = GPSCoordinate(latitude=32.37, longitude=77.24, altitude_m=3950.0)
    reading = RainfallReading(
        sensor_id="ENV-RAIN-01",
        device_id="DEV-RAIN-01",
        rainfall_rate_mm_h=28.5,
        rainfall_mm_hr=28.5,
        cumulative_rainfall_mm=14.2,
        location=loc,
        classification=RainfallClassification.HEAVY,
        severity=RiskLevel.HIGH,
        trend=RainfallTrend.INCREASING,
    )
    assert reading.validate() is True
    d = reading.to_dict()
    assert d["sensor_id"] == "ENV-RAIN-01"
    assert d["rainfall_rate_mm_h"] == 28.5
    assert d["cumulative_rainfall_mm"] == 14.2
    assert d["classification"] == "HEAVY"
    assert d["severity"] == "HIGH"
    assert d["trend"] == "INCREASING"
    assert tuple(d["location"]) == (32.37, 77.24)


def test_rainfall_reading_validation_rejections():
    # Negative rate
    r1 = RainfallReading(sensor_id="ENV-RAIN-01", rainfall_rate_mm_h=-5.0)
    assert r1.validate() is False

    # Negative cumulative
    r2 = RainfallReading(sensor_id="ENV-RAIN-01", rainfall_rate_mm_h=10.0, cumulative_rainfall_mm=-1.0)
    assert r2.validate() is False

    # NaN rate
    r3 = RainfallReading(sensor_id="ENV-RAIN-01", rainfall_rate_mm_h=float("nan"))
    assert r3.validate() is False

    # Inf rate
    r4 = RainfallReading(sensor_id="ENV-RAIN-01", rainfall_rate_mm_h=float("inf"))
    assert r4.validate() is False

    # Out-of-bounds (> 500 mm/h)
    r5 = RainfallReading(sensor_id="ENV-RAIN-01", rainfall_rate_mm_h=550.0)
    assert r5.validate() is False

    # Empty sensor_id
    r6 = RainfallReading(sensor_id="", rainfall_rate_mm_h=10.0)
    assert r6.validate() is False


def test_rainfall_sensor_interface_contract():
    class DummyRainfallSensor(RainfallSensorInterface):
        def read_sensor(self):
            return self.read_rainfall()

        def read_rainfall(self):
            return RainfallReading(sensor_id="DUMMY", rainfall_rate_mm_h=12.0)

        def get_cumulative_rainfall(self) -> float:
            return 24.0

        def reset_cumulative(self) -> None:
            pass

        def get_health(self) -> dict:
            return {"status": "ONLINE"}

        def set_simulation_profile(self, profile: str) -> None:
            pass

    probe = DummyRainfallSensor()
    res = probe.read_rainfall()
    assert res.rainfall_rate_mm_h == 12.0
    assert probe.get_cumulative_rainfall() == 24.0


def test_db_rainfall_logging_and_analytics():
    db.init_db()
    session_id = "test_rainfall_sess_001"

    # Log individual reading
    reading1 = RainfallReading(
        sensor_id="ENV-RAIN-01",
        device_id="DEV-RAIN-01",
        rainfall_rate_mm_h=35.0,
        cumulative_rainfall_mm=10.0,
        classification=RainfallClassification.HEAVY,
        severity=RiskLevel.HIGH,
        status=SensorHealthStatus.ONLINE,
    )
    res_id = db.log_rainfall_reading(reading1, session_id=session_id, cycle=1)
    assert res_id is not None

    # Log another reading
    reading2 = RainfallReading(
        sensor_id="ENV-RAIN-01",
        device_id="DEV-RAIN-01",
        rainfall_rate_mm_h=120.0,
        cumulative_rainfall_mm=35.0,
        classification=RainfallClassification.EXTREME,
        severity=RiskLevel.CRITICAL,
        status=SensorHealthStatus.ONLINE,
    )
    db.log_rainfall_reading(reading2, session_id=session_id, cycle=2)

    # Fetch latest reading
    latest = db.get_latest_rainfall_reading(session_id=session_id)
    assert latest is not None
    assert latest["rainfall_rate_mm_h"] == 120.0
    assert latest["classification"] == "EXTREME"
    assert latest["severity"] == "CRITICAL"

    # Fetch history (chronological order)
    history = db.get_rainfall_history(session_id=session_id, limit=10)
    assert len(history) >= 2
    assert history[-1]["rainfall_rate_mm_h"] == 120.0
    assert history[-2]["rainfall_rate_mm_h"] == 35.0

    # Fetch analytics
    analytics = db.get_rainfall_analytics(session_id=session_id)
    assert analytics["total_readings"] >= 2
    assert analytics["max_rainfall_rate_mm_h"] == 120.0
    assert analytics["cumulative_rainfall_mm"] == 35.0
    assert analytics["uptime_pct"] == 100.0
    assert analytics["classification_distribution"]["EXTREME"] >= 1
    assert analytics["classification_distribution"]["HEAVY"] >= 1
