"""
test_landslide_foundation_and_models.py
---------------------------------------
Unit and database persistence tests for Soil Moisture, Tilt / Inclinometer,
Landslide risk configuration, data models, validation, and DB operations.
"""

import math
import tempfile
import os
import pytest
from backend.models import (
    SensorType,
    SensorHealthStatus,
    MoistureTrend,
    TiltTrend,
    LandslideRiskLevel,
    LandslideEventState,
    LandslideConfig,
    LANDSLIDE_CONFIG,
    SoilMoistureReading,
    TiltReading,
    LandslideRiskAssessment,
    SoilMoistureSensorInterface,
    TiltSensorInterface,
    GPSCoordinate,
    SensorHealth,
)
import backend.db as db


class DummySoilAdapter(SoilMoistureSensorInterface):
    """Test implementation of SoilMoistureSensorInterface."""
    def __init__(self, moisture: float = 40.0, status: SensorHealthStatus = SensorHealthStatus.ONLINE):
        self._moisture = moisture
        self._status = status

    def read_soil_moisture(self, node_id: str = "SLOPE-NODE-01") -> SoilMoistureReading:
        return SoilMoistureReading(
            sensor_id=f"SOIL-{node_id}",
            node_id=node_id,
            soil_moisture_pct=self._moisture,
            status=self._status,
        )

    def get_soil_health(self, node_id: str = "SLOPE-NODE-01") -> SensorHealth:
        return SensorHealth(
            sensor_id=f"SOIL-{node_id}",
            sensor_type=SensorType.SOIL_MOISTURE,
            status=self._status,
        )


class DummyTiltAdapter(TiltSensorInterface):
    """Test implementation of TiltSensorInterface."""
    def __init__(self, tilt_deg: float = 1.0, status: SensorHealthStatus = SensorHealthStatus.ONLINE):
        self._tilt = tilt_deg
        self._status = status

    def read_tilt(self, node_id: str = "SLOPE-NODE-01") -> TiltReading:
        return TiltReading(
            sensor_id=f"TILT-{node_id}",
            node_id=node_id,
            tilt_angle_deg=self._tilt,
            status=self._status,
        )

    def get_tilt_health(self, node_id: str = "SLOPE-NODE-01") -> SensorHealth:
        return SensorHealth(
            sensor_id=f"TILT-{node_id}",
            sensor_type=SensorType.IMU_TILT,
            status=self._status,
        )


def test_landslide_config_defaults():
    """Verify centralized LANDSLIDE_CONFIG has configured thresholds."""
    assert LANDSLIDE_CONFIG.min_moisture_pct == 0.0
    assert LANDSLIDE_CONFIG.max_moisture_pct == 100.0
    assert LANDSLIDE_CONFIG.nominal_baseline_moisture_pct == 38.0
    assert LANDSLIDE_CONFIG.moisture_elevated_threshold_pct == 50.0
    assert LANDSLIDE_CONFIG.moisture_high_threshold_pct == 70.0
    assert LANDSLIDE_CONFIG.moisture_critical_threshold_pct == 80.0

    assert LANDSLIDE_CONFIG.min_tilt_deg == 0.0
    assert LANDSLIDE_CONFIG.max_tilt_deg == 90.0
    assert LANDSLIDE_CONFIG.nominal_baseline_tilt_deg == 0.5
    assert LANDSLIDE_CONFIG.tilt_elevated_threshold_deg == 1.5
    assert LANDSLIDE_CONFIG.tilt_high_threshold_deg == 3.0
    assert LANDSLIDE_CONFIG.tilt_critical_threshold_deg == 4.5

    assert LANDSLIDE_CONFIG.weight_moisture == 0.25
    assert LANDSLIDE_CONFIG.weight_moisture_trend == 0.15
    assert LANDSLIDE_CONFIG.weight_tilt == 0.25
    assert LANDSLIDE_CONFIG.weight_tilt_trend == 0.25
    assert LANDSLIDE_CONFIG.weight_persistence == 0.10


def test_sensor_type_enums():
    """Verify SensorType has SOIL_MOISTURE and IMU_TILT."""
    assert SensorType.SOIL_MOISTURE == "soil_moisture"
    assert SensorType.IMU_TILT == "imu_tilt"


def test_landslide_enums():
    """Verify MoistureTrend, TiltTrend, LandslideRiskLevel, LandslideEventState."""
    assert MoistureTrend.STABLE == "STABLE"
    assert MoistureTrend.RISING == "RISING"
    assert MoistureTrend.RAPIDLY_RISING == "RAPIDLY_RISING"
    assert MoistureTrend.FALLING == "FALLING"
    assert MoistureTrend.RAPIDLY_FALLING == "RAPIDLY_FALLING"

    assert TiltTrend.STABLE == "STABLE"
    assert TiltTrend.RISING == "RISING"
    assert TiltTrend.RAPIDLY_RISING == "RAPIDLY_RISING"

    assert LandslideRiskLevel.LOW == "LOW"
    assert LandslideRiskLevel.MODERATE == "MODERATE"
    assert LandslideRiskLevel.HIGH == "HIGH"
    assert LandslideRiskLevel.CRITICAL == "CRITICAL"

    assert LandslideEventState.NORMAL == "NORMAL"
    assert LandslideEventState.WATCH == "WATCH"
    assert LandslideEventState.ELEVATED == "ELEVATED"
    assert LandslideEventState.HIGH_RISK == "HIGH_RISK"
    assert LandslideEventState.CRITICAL == "CRITICAL"
    assert LandslideEventState.RECOVERY == "RECOVERY"


def test_soil_moisture_reading_validation():
    """Verify valid and invalid soil moisture readings."""
    valid = SoilMoistureReading(soil_moisture_pct=45.5)
    assert valid.validate() is True
    assert valid.to_dict()["soil_moisture_pct"] == 45.5

    assert SoilMoistureReading(soil_moisture_pct=-1.0).validate() is False
    assert SoilMoistureReading(soil_moisture_pct=105.0).validate() is False
    assert SoilMoistureReading(soil_moisture_pct=float("nan")).validate() is False
    assert SoilMoistureReading(soil_moisture_pct=float("inf")).validate() is False


def test_tilt_reading_validation():
    """Verify valid and invalid tilt readings."""
    valid = TiltReading(tilt_angle_deg=2.5, tilt_x=0.1, tilt_y=0.2, tilt_z=0.97)
    assert valid.validate() is True
    d = valid.to_dict()
    assert d["tilt_angle_deg"] == 2.5
    assert d["tilt_x"] == 0.1

    assert TiltReading(tilt_angle_deg=-0.1).validate() is False
    assert TiltReading(tilt_angle_deg=95.0).validate() is False
    assert TiltReading(tilt_angle_deg=float("nan")).validate() is False
    assert TiltReading(tilt_angle_deg=float("inf")).validate() is False


def test_landslide_risk_assessment_model():
    """Verify LandslideRiskAssessment data model."""
    loc = GPSCoordinate(latitude=32.375, longitude=77.248)
    assess = LandslideRiskAssessment(
        node_id="SLOPE-NODE-01",
        location=loc,
        soil_moisture_pct=72.5,
        moisture_trend=MoistureTrend.RISING,
        tilt_angle_deg=3.4,
        tilt_trend=TiltTrend.RISING,
        landslide_risk_score=68.5,
        risk_level=LandslideRiskLevel.HIGH,
        event_state=LandslideEventState.HIGH_RISK,
        contributing_factors=["High soil moisture", "Increasing tilt slope shift"],
        recommended_action="Restrict slope base access.",
    )
    d = assess.to_dict()
    assert d["node_id"] == "SLOPE-NODE-01"
    assert d["soil_moisture_pct"] == 72.5
    assert d["moisture_trend"] == "RISING"
    assert d["landslide_risk_score"] == 68.5
    assert d["risk_level"] == "HIGH"
    assert d["event_state"] == "HIGH_RISK"
    assert len(d["contributing_factors"]) == 2


def test_dummy_interfaces():
    """Verify SoilMoistureSensorInterface and TiltSensorInterface dummy implementations."""
    soil_ad = DummySoilAdapter(moisture=52.0)
    r_soil = soil_ad.read_soil_moisture("SLOPE-NODE-01")
    assert r_soil.soil_moisture_pct == 52.0
    h_soil = soil_ad.get_soil_health("SLOPE-NODE-01")
    assert h_soil.status == SensorHealthStatus.ONLINE

    tilt_ad = DummyTiltAdapter(tilt_deg=4.2)
    r_tilt = tilt_ad.read_tilt("SLOPE-NODE-01")
    assert r_tilt.tilt_angle_deg == 4.2
    h_tilt = tilt_ad.get_tilt_health("SLOPE-NODE-01")
    assert h_tilt.status == SensorHealthStatus.ONLINE


def test_database_persistence_landslide():
    """Verify logging and fetching landslide readings from SQLite DB."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db.init_db(db_path)
        reading1 = SoilMoistureReading(
            sensor_id="SOIL-01",
            node_id="SLOPE-NODE-01",
            soil_moisture_pct=58.0,
            rate_of_change=1.2,
            trend=MoistureTrend.RISING,
        )
        row1 = db.log_landslide_reading(reading1, session_id="test-session-1", db_path=db_path)
        assert row1 > 0

        reading2 = TiltReading(
            sensor_id="TILT-01",
            node_id="SLOPE-NODE-01",
            tilt_angle_deg=3.8,
            tilt_rate=0.4,
            trend=TiltTrend.RISING,
        )
        row2 = db.log_landslide_reading(reading2, session_id="test-session-1", db_path=db_path)
        assert row2 > 0

        latest = db.get_latest_landslide_reading(session_id="test-session-1", db_path=db_path)
        assert latest is not None
        assert latest["node_id"] == "SLOPE-NODE-01"

        history = db.get_landslide_history(session_id="test-session-1", db_path=db_path)
        assert len(history) == 2

        # Batch logging
        batch = [
            SoilMoistureReading(soil_moisture_pct=60.0),
            SoilMoistureReading(soil_moisture_pct=62.0),
        ]
        cnt = db.log_landslide_readings_batch(batch, session_id="test-session-2", db_path=db_path)
        assert cnt == 2
        hist2 = db.get_landslide_history(session_id="test-session-2", db_path=db_path)
        assert len(hist2) == 2
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
