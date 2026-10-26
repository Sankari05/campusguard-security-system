"""
test_flash_flood_intelligence_suite.py
--------------------------------------
Comprehensive test suite for Nepal-style flash-flood early warning,
non-contact hydrostatic pressure estimation (P = rho * g * h),
geotechnical hazard coupling, safe evacuation routing, multi-bearer comms,
and sensor fleet health monitoring in RIDGEWATCH.
"""

import math
import pytest
from fastapi.testclient import TestClient

from api import app
from non_contact_pressure import (
    NonContactPressureConfig,
    NonContactSensorReading,
    NonContactPressureEngine,
    get_non_contact_pressure_engine,
)
from flood_intelligence_engine import (
    FloodIntelligenceEngine,
    get_flood_intelligence_engine,
    FloodRiskLevel,
    FloodRiskThresholds,
)
from landslide_detector import LandslideDetector, get_landslide_detector
from debris_flow_detector import DebrisFlowDetector, get_debris_flow_detector
from evacuation_engine import (
    EvacuationEngine,
    get_evacuation_engine,
    ZoneDangerLevel,
    RouteSafetyConfidence,
    InundationDangerZone,
    SafeAssemblyPoint,
)
from communication_fallback import (
    CommunicationManager,
    get_communication_manager,
    BearerType,
    MessagePriority,
    MessageStatus,
)
from sensor_health_monitor import (
    SensorHealthMonitor,
    get_sensor_health_monitor,
    SensorHealthStatus,
)
import db


@pytest.fixture
def client():
    return TestClient(app)


# --------------------------------------------------------------------------- #
# 1. Non-Contact Hydrostatic Pressure Tests (P = rho * g * h)
# --------------------------------------------------------------------------- #

def test_non_contact_hydrostatic_pressure_physics():
    """Validates physical formula P = rho * g * h where h = mount_height - distance."""
    engine = NonContactPressureEngine(NonContactPressureConfig(sensor_mount_height_m=6.0))
    reading = NonContactSensorReading(
        sensor_id="DEV-WATER-NC01",
        sensor_mount_height_m=6.0,
        measured_surface_distance_m=4.5,  # Depth = 6.0 - 4.5 = 1.5 m
        timestamp=None,
    )
    est = engine.estimate_pressure(reading)

    assert est.water_depth_m == 1.5
    expected_pa = 1000.0 * 9.80665 * 1.5  # 14709.975 Pa
    assert abs(est.estimated_pressure_pa - expected_pa) < 0.1
    assert abs(est.estimated_pressure_kpa - 14.71) < 0.05
    assert est.pressure_source == "non_contact_sensor_estimation"
    assert est.reading_quality == "VALID"


def test_sensor_distance_out_of_range_rejection():
    """Verifies that impossible or negative surface distance is marked INVALID."""
    engine = NonContactPressureEngine(NonContactPressureConfig(sensor_mount_height_m=6.0))
    # Distance greater than mount height
    reading_sub = NonContactSensorReading(
        sensor_id="DEV-WATER-NC01",
        sensor_mount_height_m=6.0,
        measured_surface_distance_m=7.5,
        timestamp=None,
    )
    est_sub = engine.estimate_pressure(reading_sub)
    assert est_sub.reading_quality in ("INVALID", "UNAVAILABLE", "CALIBRATION_REQUIRED")
    assert est_sub.estimated_pressure_kpa == 0.0

    # Negative distance (sensor submerged or broken)
    reading_neg = NonContactSensorReading(
        sensor_id="DEV-WATER-NC01",
        sensor_mount_height_m=6.0,
        measured_surface_distance_m=-0.5,
        timestamp=None,
    )
    est_neg = engine.estimate_pressure(reading_neg)
    assert est_neg.reading_quality in ("INVALID", "DEGRADED", "UNAVAILABLE")


# --------------------------------------------------------------------------- #
# 2. Flash-Flood Intelligence & Risk Classification
# --------------------------------------------------------------------------- #

def test_flood_risk_classification_tiers():
    """Verifies risk classification: NORMAL (0-25), WATCH (26-50), WARNING (51-75), CRITICAL (76-100)."""
    engine = FloodIntelligenceEngine()

    # Nominal baseline
    norm_rep = engine.process_cycle(water_depth_m=0.3, rainfall_rate_mmh=5.0, flow_velocity_mps=0.3)
    assert norm_rep.current_assessment.risk_level == FloodRiskLevel.NORMAL
    assert norm_rep.current_assessment.risk_score < 25.0

    # Critical surge (deep water, extreme rainfall, high velocity)
    crit_rep = engine.process_cycle(water_depth_m=2.2, rainfall_rate_mmh=60.0, flow_velocity_mps=2.5, upstream_surge_active=True)
    assert crit_rep.current_assessment.risk_level == FloodRiskLevel.CRITICAL
    assert crit_rep.current_assessment.risk_score >= 75.0
    assert crit_rep.current_assessment.warning_issued is True
    assert crit_rep.current_assessment.evacuation_recommended is True
    assert crit_rep.current_assessment.swiftwater_rescue_flag is True


def test_early_warning_surge_acceleration_and_time_to_inundation():
    """Verifies surge rate acceleration and time-to-inundation calculations."""
    engine = FloodIntelligenceEngine()
    # Cycle 1: 0.8m depth
    engine.evaluate_flood_risk(water_depth_m=0.8, timestamp_str="2026-09-13T10:00:00Z")
    # Cycle 2: 1.4m depth 60 seconds later -> rise rate = 0.6 m/min = 60 cm/min
    res2 = engine.evaluate_flood_risk(water_depth_m=1.4, timestamp_str="2026-09-13T10:01:00Z")

    assert res2.rise_rate_cm_min >= 30.0
    assert res2.early_warning_status in ("SURGE_DETECTED", "RAPID_ACCELERATION")
    assert res2.time_to_inundation_minutes is not None
    assert res2.time_to_inundation_minutes < 10.0


# --------------------------------------------------------------------------- #
# 3. Geotechnical Landslide & Debris Flow Coupling
# --------------------------------------------------------------------------- #

def test_landslide_detector_soil_and_tilt():
    """Verifies slope shear trigger when soil saturation and inclinometer tilt exceed thresholds."""
    detector = get_landslide_detector()

    # Normal conditions
    safe_res = detector.detect_landslide(soil_moisture_pct=35.0, tilt_angle_deg=1.5, cumulative_rainfall_mm=10.0)
    assert safe_res.risk_level == "LOW"
    assert safe_res.landslide_detected is False

    # Severe saturation and slope shift
    crit_res = detector.detect_landslide(soil_moisture_pct=85.0, tilt_angle_deg=18.5, cumulative_rainfall_mm=85.0)
    assert crit_res.risk_level in ("HIGH", "CRITICAL")
    assert crit_res.landslide_detected is True


def test_debris_flow_detector_velocity_and_rumble():
    """Verifies debris flow detection on fast torrent current and acoustic ground vibration."""
    df_detector = get_debris_flow_detector()

    # High flow speed + ground acoustic rumble + damming
    res = df_detector.detect_debris_flow(
        water_flow_velocity_mps=4.2,
        water_depth_m=1.8,
        acoustic_rumble_db=72.0,
        upstream_channel_blocked=True,
    )
    assert res.threat_level == "CRITICAL"
    assert res.debris_flow_detected is True
    assert res.channel_damming_detected is True


# --------------------------------------------------------------------------- #
# 4. Evacuation Routing & High-Ground Assembly Points
# --------------------------------------------------------------------------- #

def test_evacuation_engine_danger_zones_and_safety_margin():
    """Verifies evacuation route recommendation, time-to-inundation, and safety margin computation."""
    evac_engine = get_evacuation_engine()
    flood_engine = get_flood_intelligence_engine()

    # Create a critical flood report
    crit_rep = flood_engine.process_cycle(water_depth_m=1.8, rainfall_rate_mmh=55.0, flow_velocity_mps=2.0)

    recs = evac_engine.evaluate_evacuation_plan(
        flood_report=crit_rep,
        landslide_active=True,
        debris_flow_active=True,
    )

    assert len(recs) > 0
    high_urgency = [r for r in recs if r.urgency in ("IMMEDIATE_EVACUATION", "HIGH_PRIORITY_EVACUATION")]
    assert len(high_urgency) > 0

    first_rec = recs[0]
    assert first_rec.recommended_assembly_point.altitude_m > 4000.0  # Safe high ground
    assert len(first_rec.tactical_instructions) > 0
    assert first_rec.route_safety_confidence in (
        RouteSafetyConfidence.HIGH,
        RouteSafetyConfidence.MODERATE,
        RouteSafetyConfidence.ROUTE_SAFETY_UNVERIFIED,
    )


# --------------------------------------------------------------------------- #
# 5. Multi-Bearer Resilient Communications
# --------------------------------------------------------------------------- #

def test_communication_manager_failover_and_deduplication():
    """Verifies multi-bearer automatic failover and idempotent message deduplication."""
    comm = get_communication_manager()
    comm.clear_queue()

    # Test 1: Normal dispatch via primary bearer (Internet)
    msg1 = comm.queue_message(
        recipient="+977-9801234567",
        payload="EMERGENCY: Melamchi River stage rising rapidly. Move to upper ridge!",
        priority=MessagePriority.CRITICAL,
    )
    assert msg1.status == MessageStatus.DELIVERED
    assert msg1.active_bearer == BearerType.INTERNET_API

    # Test 2: Idempotent duplicate suppression
    msg2 = comm.queue_message(
        recipient="+977-9801234567",
        payload="EMERGENCY: Melamchi River stage rising rapidly. Move to upper ridge!",
        priority=MessagePriority.CRITICAL,
        idempotency_key=msg1.idempotency_key,
    )
    assert msg2.message_id == msg1.message_id

    # Test 3: Failover when Internet and GSM are offline -> Fallback to LoRa Mesh
    comm.set_bearer_availability(BearerType.INTERNET_API, False)
    comm.set_bearer_availability(BearerType.GSM_SMS, False)

    msg3 = comm.queue_message(
        recipient="SAR_TEAM_ALPHA",
        payload="CRITICAL: Debris flow detected upstream. Evacuate valley bridge.",
        priority=MessagePriority.CRITICAL,
    )
    assert msg3.active_bearer == BearerType.LORA_MESH_ADAPTER
    assert msg3.status == MessageStatus.DELIVERED

    # Restore connectivity
    comm.set_bearer_availability(BearerType.INTERNET_API, True)
    comm.set_bearer_availability(BearerType.GSM_SMS, True)


# --------------------------------------------------------------------------- #
# 6. Sensor Health & Fleet Diagnostics
# --------------------------------------------------------------------------- #

def test_sensor_health_monitoring_and_fleet_summary():
    """Verifies sensor heartbeat, battery audit, and offline detection."""
    monitor = get_sensor_health_monitor()

    # Record healthy heartbeat
    rec_ok = monitor.record_heartbeat("DEV-WATER-NC01", value=1.25, battery_volts=3.95, rssi_dbm=-65)
    assert rec_ok.health_status == SensorHealthStatus.HEALTHY
    assert rec_ok.battery_percentage >= 70

    # Record low-battery condition
    rec_bat = monitor.record_heartbeat("DEV-TEST-LOWBAT", value=0.5, battery_volts=3.1, rssi_dbm=-70)
    assert rec_bat.health_status == SensorHealthStatus.CRITICAL_BATTERY
    assert rec_bat.battery_percentage < 15

    # Get fleet summary
    summary = monitor.get_fleet_summary()
    assert summary["total_sensors"] >= 6
    assert summary["fleet_health_index_pct"] > 50


# --------------------------------------------------------------------------- #
# 7. FastAPI REST API Endpoint Tests
# --------------------------------------------------------------------------- #

def test_api_hydrostatic_pressure_endpoint(client):
    """GET /hydrostatic-pressure/estimate returns mathematically exact P = rho * g * h."""
    resp = client.get("/hydrostatic-pressure/estimate?measured_distance_m=4.0&sensor_mount_height_m=6.0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["water_depth_m"] == 2.0
    expected_kpa = (1000.0 * 9.80665 * 2.0) / 1000.0  # 19.613 kPa
    assert abs(data["estimated_pressure_kpa"] - expected_kpa) < 0.05
    assert data["pressure_source"] == "non_contact_sensor_estimation"


def test_api_flood_intelligence_current(client):
    """GET /flood-intelligence/current returns comprehensive multi-sensor flood report."""
    resp = client.get("/flood-intelligence/current")
    assert resp.status_code == 200
    data = resp.json()
    assert "current_assessment" in data
    ca = data["current_assessment"]
    assert "water_depth_m" in ca
    assert "risk_score" in ca
    assert "risk_level" in ca
    assert "hydrostatic_pressure_kpa" in ca
    assert "mode" in ca


def test_api_flood_intelligence_evaluate(client):
    """POST /flood-intelligence/evaluate accepts arbitrary field inputs."""
    payload = {
        "water_depth_m": 2.1,
        "rainfall_rate_mmh": 65.0,
        "flow_velocity_mps": 2.8,
        "upstream_surge_active": True,
        "soil_moisture_pct": 82.0,
        "slope_tilt_deg": 16.0,
        "acoustic_rumble_db": 75.0,
    }
    resp = client.post("/flood-intelligence/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    ca = data["current_assessment"]
    assert ca["risk_level"] == "CRITICAL"
    assert ca["warning_issued"] is True
    assert ca["evacuation_recommended"] is True


def test_api_evacuation_recommendations(client):
    """GET /evacuation/recommendations returns population zone routing plans."""
    resp = client.get("/evacuation/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_zones" in data
    assert "assembly_points" in data
    assert "recommendations" in data
    assert len(data["recommendations"]) > 0


def test_api_sensor_health_summary(client):
    """GET /sensors/health/summary returns fleet overview."""
    resp = client.get("/sensors/health/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_sensors" in data
    assert "fleet_health_index_pct" in data
    assert "sensors" in data


def test_api_communication_status_and_send(client):
    """GET /communication/status and POST /communication/send test multi-bearer message dispatch."""
    stat_resp = client.get("/communication/status")
    assert stat_resp.status_code == 200
    stat_data = stat_resp.json()
    assert "bearer_status" in stat_data

    send_payload = {
        "recipient": "BROADCAST",
        "payload": "ALERT: Flash flood surge warning active in Melamchi Basin.",
        "priority": "CRITICAL",
    }
    send_resp = client.post("/communication/send", json=send_payload)
    assert send_resp.status_code == 200
    send_data = send_resp.json()
    assert send_data["status"] in ("DELIVERED", "OFFLINE_QUEUED")
    assert send_data["priority"] == "CRITICAL"


def test_api_flood_intelligence_current_with_running_scenario(client):
    """Regression test: GET /flood-intelligence/current during active simulation scenario without AttributeError."""
    start_resp = client.post("/scenario/start", json={"scenario": "flood_urban", "operation_id": "op-flood-test-01"})
    assert start_resp.status_code == 200

    try:
        resp = client.get("/flood-intelligence/current")
        assert resp.status_code == 200
        data = resp.json()
        assert "current_assessment" in data
        ca = data["current_assessment"]
        assert ca is not None
        assert "water_depth_m" in ca
        assert isinstance(ca["water_depth_m"], (int, float))
        assert "risk_score" in ca
        assert "risk_level" in ca
        assert "mode" in ca

        # Also test scoped route
        scoped_resp = client.get("/operations/op-flood-test-01/flood-intelligence/current")
        assert scoped_resp.status_code == 200
        scoped_data = scoped_resp.json()
        assert "current_assessment" in scoped_data
    finally:
        client.post("/operations/op-flood-test-01/stop")


def test_api_flood_intelligence_current_fallback_without_non_contact_method(client, monkeypatch):
    """Regression test: verify fallback to water_report() and water_flow_report() when simulator lacks non_contact_pressure_report."""
    import api

    class DummySimulatorWithoutNonContact:
        def water_report(self):
            return {"NODE-01": 250.0}  # 250 cm = 2.5 m

        def water_flow_report(self):
            return {"NODE-01": 3.2}  # 3.2 m/s

        def rain_report(self):
            return {"rainfall_mm_hr": 45.0, "accumulated_rain_mm": 90.0}

        def soil_report(self):
            return {"soil_moisture_pct": 65.0}

        def tilt_report(self):
            return {"tilt_deg": 5.0}

        def seismic_report(self):
            return {"vibration_mm_s": 2.5}

    class DummyOp:
        running = True
        simulator = DummySimulatorWithoutNonContact()
        session_id = None

    monkeypatch.setattr(api, "_get_operation_optional", lambda op_id: DummyOp())

    resp = client.get("/flood-intelligence/current")
    assert resp.status_code == 200
    data = resp.json()
    assert "current_assessment" in data
    ca = data["current_assessment"]
    assert ca["water_depth_m"] == 2.5
    assert ca["river_flow_mps"] == 3.2

