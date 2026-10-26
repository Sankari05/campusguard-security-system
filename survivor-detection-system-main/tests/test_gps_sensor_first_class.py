"""
tests/test_gps_sensor_first_class.py
------------------------------------
Comprehensive First-Class Sensor Pipeline Test Suite for
Multi-Constellation GNSS / GPS Sensor and Geospatial Intelligence.

Validates all 25 required engineering criteria:
1. SensorType registration (GPS = "gps")
2. GPSConfig and GPS_CONFIG singleton validation
3. GPSCoordinate Haversine distance calculations
4. GPSReading validation with nominal values
5. GPSReading invalid latitude rejection (-90 to +90)
6. GPSReading invalid longitude rejection (-180 to +180)
7. GPSReading invalid accuracy, speed, and satellites rejection
8. GPSReading heading normalization (0 to 360 degrees)
9. GPSSimulationAdapter: STATIONARY profile
10. GPSSimulationAdapter: NORMAL_MOVEMENT profile & kinematic advancement
11. GPSSimulationAdapter: RESCUE_TEAM_MOVEMENT profile
12. GPSSimulationAdapter: GPS_SIGNAL_LOSS / OFFLINE profile
13. GPSSimulationAdapter: GPS_DEGRADED geometry profile
14. GPSSimulationAdapter: GPS_JUMP impossible kinematic anomaly detection
15. GPSSimulationAdapter: Health and diagnostic reporting
16. SensorSimulator integration & environmental cycle generation
17. SQLite database persistence, history, and breadcrumb trail logging
18. SQLite database GPS analytics & kinematic statistics
19. Sensor Fusion: Geospatial distance, nearest survivor, nearest rescue team
20. Scenario Intelligence: GPSAnalyzer telemetry & proximity analysis
21. Scenario Intelligence: Sensor evidence extraction (Tokens: AVAILABLE, DEGRADED, OFFLINE, ANOMALY)
22. Scenario Intelligence: Alert lifecycle management for GPS alerts
23. REST API: GET /sensors/gps/current, history, health, and trail
24. REST API: POST /sensors/gps/simulate and POST /sensors/gps/readings
25. REST API: GET /geospatial/distance, /geospatial/nearest-team, and /geospatial/entities
"""

import math
import pytest
import sqlite3
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from models import (
    SensorType,
    SensorReading,
    SensorHealthStatus,
    GPSMovementState,
    GPSConfig,
    GPS_CONFIG,
    GPSCoordinate,
    GPSReading,
    VictimProfile,
    RescueTeamStatus,
    TeamAvailability,
    HIMALAYA_SITE_ORIGIN,
)
from sensor_simulator import (
    SensorSimulator,
    GPSSimulationAdapter,
)
from fusion_engine import (
    calculate_geospatial_distance,
    find_nearest_survivor,
    find_nearest_rescue_team,
)
from scenario_intelligence import (
    GPSAnalyzer,
    SensorEvidenceExtractor,
    DisasterScenarioInferenceEngine,
    ScenarioIntelligenceEngine,
    AlertLifecycleManager,
)
import db
from api import app, operations, ScenarioState


# --------------------------------------------------------------------------- #
# 1. SensorType Registration
# --------------------------------------------------------------------------- #
def test_sensor_type_gps_registration():
    """Verify GPS is registered as a first-class member in SensorType."""
    assert hasattr(SensorType, "GPS")
    assert SensorType.GPS == "gps"
    assert SensorType.GPS.value == "gps"


# --------------------------------------------------------------------------- #
# 2. GPSConfig and Singleton Defaults
# --------------------------------------------------------------------------- #
def test_gps_config_defaults():
    """Verify GPSConfig parameters, defaults, and the global GPS_CONFIG singleton."""
    cfg = GPSConfig()
    assert cfg.default_accuracy_m == 2.5
    assert cfg.min_satellites_online == 4
    assert cfg.stationary_speed_threshold_mps == 0.2
    assert cfg.rapid_speed_threshold_mps == 10.0
    assert cfg.jump_distance_threshold_m == 1000.0
    assert cfg.max_speed_mps == 50.0

    assert GPS_CONFIG is not None
    assert isinstance(GPS_CONFIG, GPSConfig)


# --------------------------------------------------------------------------- #
# 3. GPSCoordinate Haversine Distance
# --------------------------------------------------------------------------- #
def test_gps_coordinate_distance():
    """Verify geodesic distance calculation on GPSCoordinate."""
    c1 = GPSCoordinate(latitude=32.3739, longitude=77.2491, altitude_m=3950.0)
    c2 = GPSCoordinate(latitude=32.3739, longitude=77.2491, altitude_m=3950.0)
    assert c1.haversine_distance_to(c2) == 0.0

    # 1 degree latitude is approx 111.1 - 111.3 km
    c3 = GPSCoordinate(latitude=33.3739, longitude=77.2491, altitude_m=3950.0)
    dist = c1.haversine_distance_to(c3)
    assert 111000.0 <= dist <= 111500.0

    d_dict = c1.to_dict()
    assert d_dict["latitude"] == 32.3739
    assert d_dict["longitude"] == 77.2491
    assert d_dict["altitude_m"] == 3950.0


# --------------------------------------------------------------------------- #
# 4. GPSReading Validation (Valid Values)
# --------------------------------------------------------------------------- #
def test_gps_reading_valid():
    """Verify GPSReading passes validation with nominal sensor values."""
    r = GPSReading(
        sensor_id="DEV-GPS-01",
        latitude=32.3739,
        longitude=77.2491,
        altitude_m=3950.0,
        accuracy_m=2.5,
        speed_mps=1.2,
        heading_deg=180.0,
        satellites=12,
        movement_state=GPSMovementState.MOVING,
    )
    assert r.validate() is True
    coord = r.to_coordinate()
    assert coord.latitude == 32.3739
    assert coord.longitude == 77.2491

    r_dict = r.to_dict()
    assert r_dict["sensor_type"] == "gps"
    assert r_dict["latitude"] == 32.3739
    assert r_dict["longitude"] == 77.2491
    assert r_dict["movement_state"] == "MOVING"


# --------------------------------------------------------------------------- #
# 5. GPSReading Validation: Invalid Latitude
# --------------------------------------------------------------------------- #
def test_gps_reading_invalid_latitude():
    """Verify out-of-bounds latitude values are rejected."""
    r_high = GPSReading(latitude=91.0, longitude=77.0)
    assert r_high.validate() is False

    r_low = GPSReading(latitude=-90.1, longitude=77.0)
    assert r_low.validate() is False

    r_nan = GPSReading(latitude=float("nan"), longitude=77.0)
    assert r_nan.validate() is False


# --------------------------------------------------------------------------- #
# 6. GPSReading Validation: Invalid Longitude
# --------------------------------------------------------------------------- #
def test_gps_reading_invalid_longitude():
    """Verify out-of-bounds longitude values are rejected."""
    r_high = GPSReading(latitude=32.0, longitude=180.5)
    assert r_high.validate() is False

    r_low = GPSReading(latitude=32.0, longitude=-181.0)
    assert r_low.validate() is False

    r_inf = GPSReading(latitude=32.0, longitude=float("inf"))
    assert r_inf.validate() is False


# --------------------------------------------------------------------------- #
# 7. GPSReading Validation: Invalid Accuracy, Speed & Satellites
# --------------------------------------------------------------------------- #
def test_gps_reading_invalid_accuracy_and_satellites():
    """Verify negative accuracy, negative speed, or negative satellites are rejected."""
    r_neg_acc = GPSReading(latitude=32.0, longitude=77.0, accuracy_m=-1.0)
    assert r_neg_acc.validate() is False

    r_neg_spd = GPSReading(latitude=32.0, longitude=77.0, speed_mps=-5.0)
    assert r_neg_spd.validate() is False

    r_neg_sat = GPSReading(latitude=32.0, longitude=77.0, satellites=-2)
    assert r_neg_sat.validate() is False


# --------------------------------------------------------------------------- #
# 8. GPSReading Heading Normalization
# --------------------------------------------------------------------------- #
def test_gps_reading_heading_normalization():
    """Verify heading angles are normalized within 0 to 360 degrees."""
    r1 = GPSReading(latitude=32.0, longitude=77.0, heading_deg=450.0)
    assert r1.validate() is True
    assert r1.heading_deg == 90.0

    r2 = GPSReading(latitude=32.0, longitude=77.0, heading_deg=-30.0)
    assert r2.validate() is True
    assert r2.heading_deg == 330.0


# --------------------------------------------------------------------------- #
# 9. GPSSimulationAdapter: STATIONARY Profile
# --------------------------------------------------------------------------- #
def test_gps_simulation_adapter_stationary():
    """Verify STATIONARY profile keeps coordinate stable with near-zero speed."""
    adapter = GPSSimulationAdapter(initial_lat=32.3739, initial_lon=77.2491)
    adapter.set_simulation_profile("STATIONARY")

    r1 = adapter.read_sensor()
    assert r1.movement_state == GPSMovementState.STATIONARY
    assert r1.speed_mps < 0.2
    assert r1.satellites >= 10
    assert r1.is_valid_fix is True
    assert r1.status == SensorHealthStatus.ONLINE


# --------------------------------------------------------------------------- #
# 10. GPSSimulationAdapter: NORMAL_MOVEMENT Profile
# --------------------------------------------------------------------------- #
def test_gps_simulation_adapter_normal_movement():
    """Verify NORMAL_MOVEMENT profile advances coordinates and updates kinematics."""
    adapter = GPSSimulationAdapter(initial_lat=32.3739, initial_lon=77.2491)
    adapter.set_simulation_profile("NORMAL_MOVEMENT")

    r1 = adapter.read_sensor()
    r2 = adapter.step()

    assert r2.speed_mps > 0.0
    assert r2.movement_state == GPSMovementState.MOVING
    assert adapter.total_distance_m >= 0.0


# --------------------------------------------------------------------------- #
# 11. GPSSimulationAdapter: RESCUE_TEAM_MOVEMENT Profile
# --------------------------------------------------------------------------- #
def test_gps_simulation_adapter_rescue_movement():
    """Verify RESCUE_TEAM_MOVEMENT profile advances toward designated target."""
    adapter = GPSSimulationAdapter(initial_lat=32.3739, initial_lon=77.2491, target_lat=32.3800, target_lon=77.2550)
    adapter.set_simulation_profile("RESCUE_TEAM_MOVEMENT")

    r = adapter.step()
    assert r.movement_state == GPSMovementState.MOVING
    assert r.speed_mps > 0.5
    assert r.is_valid_fix is True


# --------------------------------------------------------------------------- #
# 12. GPSSimulationAdapter: GPS_SIGNAL_LOSS / OFFLINE Profile
# --------------------------------------------------------------------------- #
def test_gps_simulation_adapter_signal_loss():
    """Verify GPS_SIGNAL_LOSS drops satellites to 0 and fix status to NO_FIX."""
    adapter = GPSSimulationAdapter()
    adapter.set_simulation_profile("GPS_SIGNAL_LOSS")

    r = adapter.read_sensor()
    assert r.movement_state == GPSMovementState.SIGNAL_LOSS
    assert r.satellites == 0
    assert r.is_valid_fix is False
    assert r.status == SensorHealthStatus.OFFLINE
    assert r.fix_quality == "NO_FIX"


# --------------------------------------------------------------------------- #
# 13. GPSSimulationAdapter: GPS_DEGRADED Profile
# --------------------------------------------------------------------------- #
def test_gps_simulation_adapter_degraded():
    """Verify GPS_DEGRADED profile inflates error margin and reduces locked satellites."""
    adapter = GPSSimulationAdapter()
    adapter.set_simulation_profile("GPS_DEGRADED")

    r = adapter.read_sensor()
    assert r.accuracy_m > 15.0
    assert r.satellites <= 3
    assert r.status == SensorHealthStatus.DEGRADED
    assert r.fix_quality == "DEGRADED_FIX"


# --------------------------------------------------------------------------- #
# 14. GPSSimulationAdapter: GPS_JUMP Impossible Kinematic Anomaly
# --------------------------------------------------------------------------- #
def test_gps_simulation_adapter_jump_anomaly():
    """Verify GPS_JUMP flags impossible position displacement."""
    adapter = GPSSimulationAdapter(initial_lat=32.3739, initial_lon=77.2491)
    adapter.read_sensor()
    adapter.set_simulation_profile("GPS_JUMP")

    r = adapter.step()
    assert r.movement_state == GPSMovementState.JUMP_ANOMALY
    assert r.speed_mps >= 50.0


# --------------------------------------------------------------------------- #
# 15. GPSSimulationAdapter Health Reporting
# --------------------------------------------------------------------------- #
def test_gps_simulation_adapter_health():
    """Verify GPSSimulationAdapter.get_health() returns standard SensorHealth report."""
    adapter = GPSSimulationAdapter()
    health = adapter.get_health()
    assert health.sensor_type == SensorType.GPS
    assert health.status == SensorHealthStatus.ONLINE
    assert health.battery_pct > 0.0


# --------------------------------------------------------------------------- #
# 16. SensorSimulator Integration
# --------------------------------------------------------------------------- #
def test_sensor_simulator_integration():
    """Verify SensorSimulator includes GPS adapter in lifecycle and reports."""
    sim = SensorSimulator(victims=[])
    assert hasattr(sim, "gps_adapter")
    assert sim.gps_adapter is not None

    gps_rep = sim.gps_report()
    assert "latitude" in gps_rep
    assert "longitude" in gps_rep
    assert "satellites" in gps_rep
    assert "status" in gps_rep

    env_readings = sim.generate_environmental_readings()
    gps_readings = [r for r in env_readings if r.sensor_type == SensorType.GPS]
    assert len(gps_readings) >= 1
    assert gps_readings[0].sensor_type == SensorType.GPS

    health_report = sim.get_sensor_health_report()
    assert any(h.sensor_type == SensorType.GPS for h in health_report)


# --------------------------------------------------------------------------- #
# 17. SQLite Database Persistence & Breadcrumb Trail
# --------------------------------------------------------------------------- #
def test_database_gps_persistence_and_trail():
    """Verify logging and trail retrieval from SQLite database."""
    session_id = "test-gps-session-01"
    r = GPSReading(
        sensor_id="DEV-GPS-01",
        device_id="RESCUE-KIT-01",
        latitude=32.3740,
        longitude=77.2495,
        altitude_m=3955.0,
        accuracy_m=2.1,
        speed_mps=1.5,
        heading_deg=90.0,
        satellites=14,
        movement_state=GPSMovementState.MOVING,
    )
    db.log_gps_reading(r, session_id=session_id, cycle=1)

    latest = db.get_latest_gps_reading(session_id=session_id)
    assert latest is not None
    assert latest["latitude"] == 32.3740
    assert latest["longitude"] == 77.2495
    assert latest["satellites"] == 14

    history = db.get_gps_history(session_id=session_id)
    assert len(history) >= 1
    assert history[0]["sensor_id"] == "DEV-GPS-01"

    trail = db.get_gps_trail(session_id=session_id)
    assert len(trail) >= 1
    assert "latitude" in trail[0] and "longitude" in trail[0]


# --------------------------------------------------------------------------- #
# 18. SQLite Database GPS Analytics
# --------------------------------------------------------------------------- #
def test_database_gps_analytics():
    """Verify statistical analytics aggregated from GPS history."""
    session_id = "test-gps-session-analytics"
    r1 = GPSReading(latitude=32.3700, longitude=77.2400, speed_mps=2.0, accuracy_m=2.0, satellites=12)
    r2 = GPSReading(latitude=32.3710, longitude=77.2410, speed_mps=4.0, accuracy_m=3.0, satellites=10)
    db.log_gps_reading(r1, session_id=session_id, cycle=1)
    db.log_gps_reading(r2, session_id=session_id, cycle=2)

    analytics = db.get_gps_analytics(session_id=session_id)
    assert analytics["total_readings"] >= 2
    assert analytics["avg_accuracy_m"] is not None
    assert analytics["max_speed_mps"] >= 4.0
    assert analytics["fix_availability_pct"] == 100.0


# --------------------------------------------------------------------------- #
# 19. Sensor Fusion: Geospatial Helpers
# --------------------------------------------------------------------------- #
def test_fusion_geospatial_helpers():
    """Verify distance calculation, nearest survivor, and nearest rescue team."""
    c1 = GPSCoordinate(latitude=32.3739, longitude=77.2491)
    c2 = GPSCoordinate(latitude=32.3750, longitude=77.2500)
    d = calculate_geospatial_distance(c1, c2)
    assert d > 0.0

    # Nearest survivor
    survivors = {
        "V1": GPSCoordinate(latitude=32.3740, longitude=77.2492),
        "V2": GPSCoordinate(latitude=32.4000, longitude=77.3000),
    }
    nearest_vid, dist_v = find_nearest_survivor(c1, survivors)
    assert nearest_vid == "V1"
    assert dist_v < 100.0

    # Nearest team
    teams = {
        "TEAM-A": GPSCoordinate(latitude=32.3745, longitude=77.2495),
        "TEAM-B": GPSCoordinate(latitude=32.5000, longitude=77.4000),
    }
    nearest_tid, dist_t = find_nearest_rescue_team(c1, teams)
    assert nearest_tid == "TEAM-A"
    assert dist_t < 150.0


# --------------------------------------------------------------------------- #
# 20. Scenario Intelligence: GPSAnalyzer
# --------------------------------------------------------------------------- #
def test_scenario_intelligence_gps_analyzer():
    """Verify GPSAnalyzer validation, telemetry analysis, and proximity computation."""
    analyzer = GPSAnalyzer()
    r = GPSReading(latitude=32.3739, longitude=77.2491, satellites=12, accuracy_m=2.0)
    assert analyzer.validate_reading(r) is True

    analysis = analyzer.analyze(r, victim_locations={"VIC-01": GPSCoordinate(latitude=32.3740, longitude=77.2492)})
    assert analysis["is_valid_fix"] is True
    assert analysis["fix_quality"] == "3D_FIX_PRECISION"
    assert "GPS_SIGNAL_AVAILABLE" in analysis["evidence_tokens"]
    assert analysis["nearest_victim_id"] == "VIC-01"


# --------------------------------------------------------------------------- #
# 21. Scenario Intelligence: Evidence Extraction
# --------------------------------------------------------------------------- #
def test_scenario_intelligence_gps_evidence():
    """Verify SensorEvidenceExtractor generates appropriate GPS evidence tokens."""
    extractor = SensorEvidenceExtractor()

    # High precision fix
    r_good = SensorReading(
        sensor_type=SensorType.GPS,
        victim_id="SITE",
        value=12.0,
        unit="sats",
        location=GPSCoordinate(latitude=32.3739, longitude=77.2491),
        status=SensorHealthStatus.ONLINE,
        raw_data={"satellites": 12, "accuracy_m": 2.5, "speed_mps": 0.0, "movement_state": "STATIONARY"},
    )
    ev_good = extractor.extract_evidence([r_good], [], {})
    labels_good = [e.evidence_label for e in ev_good]
    assert "GPS_SIGNAL_AVAILABLE" in labels_good

    # Offline fix
    r_off = SensorReading(
        sensor_type=SensorType.GPS,
        victim_id="SITE",
        value=0.0,
        unit="sats",
        location=GPSCoordinate(latitude=32.3739, longitude=77.2491),
        status=SensorHealthStatus.OFFLINE,
        raw_data={"satellites": 0, "accuracy_m": 99.0, "speed_mps": 0.0, "movement_state": "SIGNAL_LOSS"},
    )
    ev_off = extractor.extract_evidence([r_off], [], {})
    labels_off = [e.evidence_label for e in ev_off]
    assert "GPS_SIGNAL_OFFLINE" in labels_off


# --------------------------------------------------------------------------- #
# 22. Alert Lifecycle Manager: GPS Alerts
# --------------------------------------------------------------------------- #
def test_alert_manager_gps_alerts():
    """Verify AlertLifecycleManager syncs GPS signal loss and anomaly alerts."""
    manager = AlertLifecycleManager()
    extractor = SensorEvidenceExtractor()
    session_id = "test-gps-alerts-session"

    # Signal loss alert trigger
    r_loss = SensorReading(
        sensor_type=SensorType.GPS,
        victim_id="SITE",
        value=0.0,
        unit="sats",
        location=GPSCoordinate(latitude=32.3739, longitude=77.2491),
        status=SensorHealthStatus.OFFLINE,
        raw_data={"satellites": 0, "accuracy_m": 99.0, "movement_state": "SIGNAL_LOSS"},
    )
    ev_loss = extractor.extract_evidence([r_loss], [], {})
    alerts = manager.sync_alerts(session_id=session_id, evidence=ev_loss)
    assert any(a["hazard_type"] == "gps_signal_loss" for a in alerts)


# --------------------------------------------------------------------------- #
# 23. REST API: GET /sensors/gps/* Endpoints
# --------------------------------------------------------------------------- #
def test_api_gps_current_and_history():
    """Verify REST endpoints for live GPS telemetry, history, health, and trail."""
    client = TestClient(app)

    # Start a scenario
    start_res = client.post("/scenario/start", json={"scenario_id": "avalanche"})
    assert start_res.status_code == 200

    # Current telemetry
    cur_res = client.get("/sensors/gps/current")
    assert cur_res.status_code == 200
    cur_json = cur_res.json()
    assert "gps" in cur_json
    assert "latitude" in cur_json["gps"]
    assert "satellites" in cur_json["gps"]

    # History
    hist_res = client.get("/sensors/gps/history")
    assert hist_res.status_code == 200
    assert "history" in hist_res.json()

    # Health
    health_res = client.get("/sensors/gps/health")
    assert health_res.status_code == 200
    assert "health" in health_res.json()

    # Trail
    trail_res = client.get("/sensors/gps/trail")
    assert trail_res.status_code == 200
    assert "trail" in trail_res.json()


# --------------------------------------------------------------------------- #
# 24. REST API: POST /sensors/gps/simulate & POST /sensors/gps/readings
# --------------------------------------------------------------------------- #
def test_api_gps_simulate_and_ingest():
    """Verify GPS profile simulation and hardware ingestion REST endpoints."""
    client = TestClient(app)
    client.post("/scenario/start", json={"scenario_id": "avalanche"})

    # Simulate profile
    sim_res = client.post("/sensors/gps/simulate", json={"profile": "GPS_DEGRADED", "accuracy_m": 25.0, "satellites": 3})
    assert sim_res.status_code == 200
    assert sim_res.json()["profile"] == "GPS_DEGRADED"

    # Ingest hardware reading
    ingest_res = client.post("/sensors/gps/readings", json={
        "sensor_id": "DEV-GPS-01",
        "latitude": 32.3740,
        "longitude": 77.2490,
        "altitude_m": 3950.0,
        "accuracy_m": 2.5,
        "speed_mps": 0.0,
        "heading_deg": 0.0,
        "satellites": 12,
        "movement_state": "STATIONARY",
    })
    assert ingest_res.status_code == 200
    assert ingest_res.json()["logged"] is True

    # Ingest invalid reading (out-of-bounds latitude)
    invalid_res = client.post("/sensors/gps/readings", json={
        "latitude": 95.0,
        "longitude": 77.0,
    })
    assert invalid_res.status_code == 422


# --------------------------------------------------------------------------- #
# 25. REST API: GET /geospatial/* Endpoints
# --------------------------------------------------------------------------- #
def test_api_geospatial_endpoints():
    """Verify /geospatial/distance, /geospatial/nearest-team, /geospatial/entities."""
    client = TestClient(app)
    client.post("/scenario/start", json={"scenario_id": "avalanche"})

    # Geodesic distance calculation
    dist_res = client.get("/geospatial/distance?lat1=32.3739&lon1=77.2491&lat2=32.3750&lon2=77.2500")
    assert dist_res.status_code == 200
    dist_json = dist_res.json()
    assert "distance_m" in dist_json
    assert dist_json["distance_m"] > 0.0

    # Nearest rescue team
    team_res = client.get("/geospatial/nearest-team?target_lat=32.3740&target_lon=77.2490")
    assert team_res.status_code == 200
    team_json = team_res.json()
    assert "nearest_team_id" in team_json
    assert "distance_m" in team_json

    # Geospatial entities
    entities_res = client.get("/geospatial/entities")
    assert entities_res.status_code == 200
    ent_json = entities_res.json()
    assert "site_origin" in ent_json
    assert "device_gps" in ent_json
    assert "victims" in ent_json
    assert "teams" in ent_json
    assert "members" in ent_json
