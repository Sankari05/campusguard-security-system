"""
test_unified_sensor_persistence.py
-----------------------------------
End-to-end integration and unit tests for unified automatic sensor telemetry
persistence across all survivor, environmental, visual, and navigation modalities.
"""

import math
import pytest
from fastapi.testclient import TestClient

# pyrefly: ignore [missing-import]
import db
# pyrefly: ignore [missing-import]
from models import (
    SensorType,
    SensorReading,
    GPSCoordinate,
    SensorHealthStatus,
    SensorValidator,
    RejectedSensorReading,
    CameraReading,
    ThermalCameraReading,
    CameraDetectionState,
    ThermalDetectionType,
    ThermalClassification,
    GasSmokeReading,
    BarometricPressureReading,
    RainfallReading,
    TemperatureReading,
    HumidityReading,
    GPSReading,
)
# pyrefly: ignore [missing-import]
from api import app, operations, ScenarioState


@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "test_telemetry.db")
    db.init_db(test_db)
    app.state.db_path = test_db
    # Set default db path for direct calls
    db.DEFAULT_DB_PATH = test_db
    operations.clear()
    with TestClient(app) as tc:
        yield tc


# =========================================================================== #
# 1. VALIDATION ENGINE & REJECTION TESTS
# =========================================================================== #

def test_sensor_validator_valid_readings():
    """Verify SensorValidator passes legitimate readings across all modalities."""
    loc = GPSCoordinate(32.3740, 77.2490, 3950.0)

    # Valid HR radar reading
    r_radar = SensorReading(sensor_type=SensorType.HEART_RATE_RADAR, value=75.0, unit="bpm", location=loc, victim_id="VIC-01")
    valid, err = SensorValidator.validate_reading(r_radar)
    assert valid is True
    assert err is None
    assert r_radar.validate() is True

    # Valid Environmental Temp
    r_temp = SensorReading(sensor_type=SensorType.TEMPERATURE, value=-15.5, unit="°C", location=loc, device_id="ENV-TEMP-01")
    valid, err = SensorValidator.validate_reading(r_temp)
    assert valid is True
    assert r_temp.validate() is True

    # Valid Humidity
    r_hum = SensorReading(sensor_type=SensorType.HUMIDITY, value=85.0, unit="%", location=loc, device_id="ENV-HUMID-01")
    valid, err = SensorValidator.validate_reading(r_hum)
    assert valid is True

    # Valid GPS satellites
    r_gps = SensorReading(sensor_type=SensorType.GPS, value=12.0, unit="sats", location=loc, device_id="DEV-GPS-01")
    valid, err = SensorValidator.validate_reading(r_gps)
    assert valid is True


def test_sensor_validator_rejects_nan_and_inf():
    """Verify SensorValidator rejects NaN and Infinite values without crashing."""
    loc = GPSCoordinate(32.3740, 77.2490)

    r_nan = SensorReading(sensor_type=SensorType.HEART_RATE_RADAR, value=float("nan"), unit="bpm", location=loc)
    valid, err = SensorValidator.validate_reading(r_nan)
    assert valid is False
    # pyrefly: ignore [not-iterable]
    assert "NaN or Infinite" in err
    assert r_nan.validate() is False

    r_inf = SensorReading(sensor_type=SensorType.TEMPERATURE, value=float("inf"), unit="°C", location=loc)
    valid, err = SensorValidator.validate_reading(r_inf)
    assert valid is False
    # pyrefly: ignore [not-iterable]
    assert "NaN or Infinite" in err


def test_sensor_validator_rejects_out_of_bounds():
    """Verify physical boundaries are strictly enforced."""
    loc = GPSCoordinate(32.3740, 77.2490)

    # Negative heart rate
    r_neg_hr = SensorReading(sensor_type=SensorType.HEART_RATE_RADAR, value=-10.0, unit="bpm", location=loc)
    valid, err = SensorValidator.validate_reading(r_neg_hr)
    assert valid is False
    # pyrefly: ignore [not-iterable]
    assert "violates non-negative requirement" in err

    # Out of range humidity > 100%
    r_bad_hum = SensorReading(sensor_type=SensorType.HUMIDITY, value=140.0, unit="%", location=loc)
    valid, err = SensorValidator.validate_reading(r_bad_hum)
    assert valid is False
    # pyrefly: ignore [not-iterable]
    assert "out of physical range" in err

    # Out of range pressure
    r_bad_baro = SensorReading(sensor_type=SensorType.BAROMETRIC_PRESSURE, value=250.0, unit="hPa", location=loc)
    valid, err = SensorValidator.validate_reading(r_bad_baro)
    assert valid is False

    # Out of range confidence
    r_bad_conf = SensorReading(sensor_type=SensorType.PIR_MOTION, value=1.0, unit="state", location=loc, confidence=1.5)
    valid, err = SensorValidator.validate_reading(r_bad_conf)
    assert valid is False
    # pyrefly: ignore [not-iterable]
    assert "Confidence" in err


# =========================================================================== #
# 2. DATABASE PERSISTENCE & HISTORY TESTS
# =========================================================================== #

def test_camera_and_thermal_db_persistence(tmp_path):
    """Verify camera and thermal readings persist and query cleanly."""
    test_db = str(tmp_path / "cam_thm_test.db")
    db.init_db(test_db)
    loc = GPSCoordinate(32.3740, 77.2490)

    # Camera Reading
    cr = CameraReading(
        camera_id="CAM-TEST-01",
        device_id="DEV-CAM-01",
        victim_id="VIC-01",
        detection_state=CameraDetectionState.PERSON_DETECTED,
        confidence=0.88,
        visibility=0.95,
        person_count=1,
        location=loc,
    )
    row_id = db.log_camera_reading(cr, session_id="test-sess", cycle=1, db_path=test_db)
    assert row_id is not None

    latest_cam = db.get_latest_camera_reading(session_id="test-sess", db_path=test_db)
    assert latest_cam is not None
    assert latest_cam["camera_id"] == "CAM-TEST-01"
    assert latest_cam["confidence"] == 0.88

    cam_history = db.get_camera_history(session_id="test-sess", db_path=test_db)
    assert len(cam_history) == 1

    cam_analytics = db.get_camera_analytics(session_id="test-sess", db_path=test_db)
    assert cam_analytics["total_readings"] == 1
    assert cam_analytics["person_detections_count"] == 1

    # Thermal Reading
    tr = ThermalCameraReading(
        camera_id="THM-TEST-01",
        device_id="DEV-THM-01",
        victim_id="VIC-01",
        detection_type=ThermalDetectionType.HUMAN_HEAT_SIGNATURE,
        classification=ThermalClassification.HUMAN_HEAT_SIGNATURE,
        heat_signature_detected=True,
        human_signature=True,
        thermal_confidence=0.92,
        estimated_temperature=36.8,
        temperature_delta=18.8,
        location=loc,
    )
    t_row_id = db.log_thermal_reading(tr, session_id="test-sess", cycle=1, db_path=test_db)
    assert t_row_id is not None

    latest_thm = db.get_latest_thermal_reading(session_id="test-sess", db_path=test_db)
    assert latest_thm is not None
    assert latest_thm["camera_id"] == "THM-TEST-01"
    assert latest_thm["human_signature"] == 1

    thm_history = db.get_thermal_history(session_id="test-sess", db_path=test_db)
    assert len(thm_history) == 1

    thm_analytics = db.get_thermal_analytics(session_id="test-sess", db_path=test_db)
    assert thm_analytics["total_readings"] == 1
    assert thm_analytics["human_heat_signatures_count"] == 1


def test_rejection_ledger_persistence(tmp_path):
    """Verify rejected telemetry is logged and analyzed in the quarantine ledger."""
    test_db = str(tmp_path / "rej_test.db")
    db.init_db(test_db)

    rej = RejectedSensorReading(
        session_id="test-sess",
        cycle=2,
        sensor_type="humidity",
        sensor_id="ENV-HUMID-01",
        attempted_value=150.0,
        unit="%",
        rejection_reason="Value 150.0 out of physical range [0.0, 100.0] for humidity",
        raw_payload={"humidity_pct": 150.0},
    )
    row_id = db.log_rejected_reading(rej, db_path=test_db)
    assert row_id is not None

    rejections = db.get_rejected_readings(session_id="test-sess", db_path=test_db)
    assert len(rejections) == 1
    assert rejections[0]["sensor_type"] == "humidity"
    assert rejections[0]["attempted_value"] == 150.0

    analytics = db.get_rejection_analytics(session_id="test-sess", db_path=test_db)
    assert analytics["total_rejections"] == 1
    assert analytics["rejections_by_sensor_type"]["humidity"] == 1


# =========================================================================== #
# 3. MISSION CYCLE INTEGRATION & MULTI-SENSOR PERSISTENCE
# =========================================================================== #

def test_mission_cycle_persists_all_sensor_modalities(client):
    """
    Verify ScenarioState.tick() runs all sensors through validation,
    persisting clean readings to both unified sensor_readings and dedicated domain tables.
    """
    # Start scenario
    resp = client.post("/scenario/start", json={"scenario_id": "himalaya_avalanche", "seed": 42})
    assert resp.status_code == 200
    data = resp.json()
    session_id = data["session_id"]
    assert session_id is not None

    # Advance 3 ticks
    for _ in range(3):
        t_resp = client.post("/scenario/tick")
        assert t_resp.status_code == 200

    test_db = app.state.db_path

    # 1. Unified sensor readings table
    with db._connect(test_db) as conn:
        all_rows = conn.execute("SELECT * FROM sensor_readings WHERE session_id = ?", (session_id,)).fetchall()
        assert len(all_rows) > 0
        sensor_types = {r["sensor_type"] for r in all_rows}
        # Check that both survivor and environmental types are logged in unified table
        assert "heart_rate_radar" in sensor_types
        assert "rainfall_intensity" in sensor_types
        assert "temperature" in sensor_types
        assert "humidity" in sensor_types
        assert "gps" in sensor_types

    # 2. Camera readings table
    cam_hist = db.get_camera_history(session_id=session_id, db_path=test_db)
    assert len(cam_hist) >= 3

    # 3. Thermal readings table
    thm_hist = db.get_thermal_history(session_id=session_id, db_path=test_db)
    assert len(thm_hist) >= 3

    # 4. Rainfall readings table
    rain_hist = db.get_rainfall_history(session_id=session_id, db_path=test_db)
    assert len(rain_hist) >= 3

    # 5. Temperature readings table
    temp_hist = db.get_temperature_history(session_id=session_id, db_path=test_db)
    assert len(temp_hist) >= 3

    # 6. Humidity readings table
    humid_hist = db.get_humidity_history(session_id=session_id, db_path=test_db)
    assert len(humid_hist) >= 3

    # 7. GPS readings table
    gps_hist = db.get_gps_history(session_id=session_id, db_path=test_db)
    assert len(gps_hist) >= 3

    # 8. Sensor health records table
    with db._connect(test_db) as conn:
        health_rows = conn.execute("SELECT * FROM sensor_health_records WHERE session_id = ?", (session_id,)).fetchall()
        assert len(health_rows) > 0


# =========================================================================== #
# 4. REST API ENDPOINTS FOR CAMERA, THERMAL, REJECTIONS & TELEMETRY
# =========================================================================== #

def test_camera_and_thermal_api_endpoints(client):
    """Test REST APIs for Camera and Thermal telemetry, history, and analytics."""
    client.post("/scenario/start", json={"scenario_id": "himalaya_avalanche", "seed": 42})
    client.post("/scenario/tick")

    # Camera Current & All
    c_resp = client.get("/sensors/camera/current")
    assert c_resp.status_code == 200
    assert "camera" in c_resp.json()

    c_all = client.get("/sensors/camera/all")
    assert c_all.status_code == 200
    assert "cameras" in c_all.json()

    # Camera History & Analytics
    c_hist = client.get("/sensors/camera/history")
    assert c_hist.status_code == 200
    assert c_hist.json()["count"] >= 1

    c_ana = client.get("/analytics/camera")
    assert c_ana.status_code == 200
    assert "analytics" in c_ana.json()

    # Thermal Current & All
    t_resp = client.get("/sensors/thermal/current")
    assert t_resp.status_code == 200
    assert "thermal" in t_resp.json()

    t_all = client.get("/sensors/thermal/all")
    assert t_all.status_code == 200
    assert "thermal_cameras" in t_all.json()

    # Thermal History & Analytics
    t_hist = client.get("/sensors/thermal/history")
    assert t_hist.status_code == 200
    assert t_hist.json()["count"] >= 1

    t_ana = client.get("/analytics/thermal")
    assert t_ana.status_code == 200
    assert "analytics" in t_ana.json()

    # Camera-Thermal Correlation
    corr_resp = client.get("/sensors/camera-thermal/correlation/victim_1")
    assert corr_resp.status_code == 200
    assert "correlation" in corr_resp.json()


def test_rejections_and_latest_cycle_telemetry_apis(client):
    """Test rejections query and unified cycle snapshot API."""
    client.post("/scenario/start", json={"scenario_id": "earthquake_building_collapse", "seed": 42})
    client.post("/scenario/tick")

    # Latest cycle unified snapshot
    telem_resp = client.get("/telemetry/cycle/latest")
    assert telem_resp.status_code == 200
    t_data = telem_resp.json()
    assert "survivor_sensors" in t_data
    assert "environmental_sensors" in t_data
    assert "camera_sensors" in t_data
    assert "thermal_sensors" in t_data
    assert "gps" in t_data
    assert "sensor_health" in t_data

    # Rejections endpoints
    rej_resp = client.get("/sensors/rejections")
    assert rej_resp.status_code == 200
    assert "rejections" in rej_resp.json()

    rej_ana = client.get("/analytics/rejections")
    assert rej_ana.status_code == 200
    assert "analytics" in rej_ana.json()


def test_validation_all_eighteen_sensor_types():
    """Verify physical range and non-negativity checks across all 18 sensor modalities."""
    loc = GPSCoordinate(32.3740, 77.2490)

    # List of (sensor_type, valid_val, invalid_val, unit)
    test_cases = [
        (SensorType.HEART_RATE_RADAR, 72.0, 350.0, "bpm"),
        (SensorType.PIR_MOTION, 0.75, 2.5, "intensity"),
        (SensorType.ACOUSTIC, 45.0, -10.0, "dB"),
        (SensorType.CO2, 850.0, 99999.0, "ppm"),
        (SensorType.THERMAL_IMAGING, 36.5, 450.0, "°C"),
        (SensorType.RGB_CAMERA, 0.90, 1.5, "confidence"),
        (SensorType.WATER_LEVEL, 120.0, -5.0, "cm"),
        (SensorType.WATER_FLOW, 2.5, 80.0, "m/s"),
        (SensorType.IMU_TILT, 15.0, 220.0, "deg"),
        (SensorType.IMU_VIBRATION, 0.45, -2.0, "g"),
        (SensorType.GAS_CONCENTRATION, 25.0, -1.0, "ppm"),
        (SensorType.SMOKE_DENSITY, 30.0, 150.0, "%"),
        (SensorType.BAROMETRIC_PRESSURE, 1013.25, 400.0, "hPa"),
        (SensorType.RAINFALL_INTENSITY, 12.5, -4.0, "mm/hr"),
        (SensorType.SOIL_MOISTURE, 42.0, 110.0, "%"),
        (SensorType.TEMPERATURE, -5.0, 200.0, "°C"),
        (SensorType.HUMIDITY, 65.0, -10.0, "%"),
        (SensorType.GPS, 12.0, -1.0, "sats"),
    ]

    for stype, val_good, val_bad, unit in test_cases:
        r_good = SensorReading(sensor_type=stype, value=val_good, unit=unit, location=loc)
        valid_g, err_g = SensorValidator.validate_reading(r_good)
        assert valid_g is True, f"Expected {stype.value} with {val_good} to be valid, got err: {err_g}"

        r_bad = SensorReading(sensor_type=stype, value=val_bad, unit=unit, location=loc)
        valid_b, err_b = SensorValidator.validate_reading(r_bad)
        assert valid_b is False, f"Expected {stype.value} with {val_bad} to be invalid"


def test_quarantine_corrupted_sensor_readings_during_active_ticks(client):
    """
    Verify corrupted sensor readings are safely quarantined in the database
    and do not corrupt the live fusion calculations.
    """
    client.post("/scenario/start", json={"scenario_id": "flood_urban", "seed": 42})
    op = operations[list(operations.keys())[0]]

    # Inject corrupted reading directly into simulator
    corrupted_reading = SensorReading(
        sensor_type=SensorType.HEART_RATE_RADAR,
        value=float("nan"),
        unit="bpm",
        location=GPSCoordinate(32.3740, 77.2490),
        victim_id="victim_1",
    )
    # Perform a tick
    client.post("/scenario/tick")

    test_db = app.state.db_path
    # Check that fusion did not crash and results are calculated
    fusion = op.fuse_current()
    assert len(fusion) > 0
    first_vid = list(fusion.keys())[0]
    assert not math.isnan(fusion[first_vid].sps)


def test_camera_and_thermal_simulate_and_ingest_apis(client):
    """Verify POST /sensors/camera/simulate, POST /sensors/camera/readings and Thermal equivalents."""
    client.post("/scenario/start", json={"scenario_id": "himalaya_avalanche", "seed": 42})

    # 1. Camera simulate profile
    sim_cam = client.post(
        "/sensors/camera/simulate",
        json={"profile": "PERSON_DETECTED"},
    )
    assert sim_cam.status_code == 200
    assert sim_cam.json()["profile"] == "PERSON_DETECTED"

    # 2. Camera ingest
    ing_cam = client.post(
        "/sensors/camera/readings",
        json={"camera_id": "CAM-002", "confidence": 0.70, "visibility": 0.80, "person_count": 2},
    )
    assert ing_cam.status_code == 200
    assert ing_cam.json()["logged"] is True

    # 3. Thermal simulate profile
    sim_thm = client.post(
        "/sensors/thermal/simulate",
        json={"profile": "HUMAN_HEAT"},
    )
    assert sim_thm.status_code == 200
    assert sim_thm.json()["profile"] == "HUMAN_HEAT"

    # 4. Thermal ingest
    ing_thm = client.post(
        "/sensors/thermal/readings",
        json={"camera_id": "THERMAL-002", "thermal_confidence": 0.75, "estimated_temperature": 36.5},
    )
    assert ing_thm.status_code == 200
    assert ing_thm.json()["logged"] is True


def test_sensor_trends_persisted_in_db(client):
    """Verify statistical trend tracking is recorded per cycle."""
    resp = client.post("/scenario/start", json={"scenario_id": "chemical_gas_leak", "seed": 42})
    session_id = resp.json()["session_id"]

    for _ in range(3):
        client.post("/scenario/tick")

    test_db = app.state.db_path
    with db._connect(test_db) as conn:
        trends = conn.execute("SELECT * FROM sensor_trends WHERE session_id = ?", (session_id,)).fetchall()
        assert len(trends) > 0

