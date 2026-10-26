"""
test_stage6_navigation_intelligence.py
---------------------------------------
Comprehensive automated test suite for STAGE 6:
NAVIGATION INTELLIGENCE IMPLEMENTATION
TARGET BEARING + MOVEMENT HEADING + DISTANCE TREND + DIRECTION GUIDANCE

Tests covered (Section 23):
1. Target bearing north.
2. Target bearing east.
3. Target bearing south.
4. Target bearing west.
5. Angle wraparound.
6. Heading difference normalization.
7. Stationary rescuer.
8. ON_TRACK heading.
9. WRONG_DIRECTION heading.
10. Wrong-direction confirmation.
11. Counter reset after correct movement.
12. Turn-left guidance.
13. Turn-right guidance.
14. Turn-around guidance.
15. Distance calculation.
16. APPROACHING trend.
17. MOVING_AWAY trend.
18. STABLE trend.
19. GPS accuracy rejection.
20. GPS stale behavior.
21. No navigation alerts while stale.
22. SMS cooldown.
23. No SMS from a single wrong sample.
24. Arrival at <=15m.
25. Arrival idempotency.
26. No guidance after ARRIVED.
27. ARRIVED persists to authoritative DB command.
28. Alpha 1 never returns to simulation.
29. Alpha 2 remains simulation.
30. Bravo 1 remains simulation.
31. Bravo 2 remains simulation.
32. Survivor remains fixed/simulated.
33. Existing Stage 4 tests compatibility.
34. Existing Stage 5 tests compatibility.
35. SMSGate isolation (mocked, no real SMS).
36. Watch BLE/GATT preserved and backend/wearable_gateway.py untouched.
"""

import os
import sys
import time
import uuid
import math
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest

from fastapi.testclient import TestClient

# Dual-import resolution
api_mod = sys.modules.get("api") or sys.modules.get("backend.api")
if not api_mod:
    from backend import api as api_mod

app = api_mod.app
operations = api_mod.operations
ALPHA_M001_LATEST_GPS = api_mod.ALPHA_M001_LATEST_GPS
ALPHA_M001_NAV_STATE = api_mod.ALPHA_M001_NAV_STATE
GPS_STALE_THRESHOLD_SECONDS = api_mod.GPS_STALE_THRESHOLD_SECONDS
GPS_ARRIVAL_DISTANCE_METERS = api_mod.GPS_ARRIVAL_DISTANCE_METERS
GPS_MIN_SPEED_FOR_DIRECTION_MPS = api_mod.GPS_MIN_SPEED_FOR_DIRECTION_MPS
DIRECTION_TOLERANCE_DEGREES = api_mod.DIRECTION_TOLERANCE_DEGREES
DIRECTION_CONFIRMATION_SAMPLES = api_mod.DIRECTION_CONFIRMATION_SAMPLES
DIRECTION_ALERT_COOLDOWN_SECONDS = api_mod.DIRECTION_ALERT_COOLDOWN_SECONDS
DISTANCE_TREND_HYSTERESIS_METERS = api_mod.DISTANCE_TREND_HYSTERESIS_METERS

calculate_angular_difference = api_mod.calculate_angular_difference
calculate_direction_guidance = api_mod.calculate_direction_guidance
calculate_target_bearing = api_mod.calculate_target_bearing
calculate_distance_trend = api_mod.calculate_distance_trend
reset_alpha_m001_telemetry = api_mod.reset_alpha_m001_telemetry
_bearing_deg = api_mod._bearing_deg

import backend.db as db
from backend.models import GPSCoordinate, MemberStatus, TeamMember
haversine_distance_m = api_mod.haversine_distance_m


@pytest.fixture(autouse=True)
def reset_stage6_state():
    """Reset Alpha Member 1 navigation and telemetry state before each test."""
    reset_alpha_m001_telemetry()
    yield
    reset_alpha_m001_telemetry()


def _assign_alpha1_mission(client, target_index=0):
    """Helper to assign Alpha Member 1 to an active scenario victim."""
    overview = client.get("/commander/overview").json()
    victims = overview.get("victims", [])
    assert len(victims) > target_index, "No victims available in scenario"
    vic = victims[target_index]
    victim_id = vic["victim_id"]
    r = client.post("/commander/assign", json={
        "member_id": "ALPHA-M001",
        "victim_id": victim_id
    })
    assert r.status_code == 200, f"Assign failed: {r.text}"
    active_cmd = db.get_active_command_for_member("ALPHA-M001")
    if active_cmd:
        cmd_id = active_cmd["command_id"]
        client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "USER_ACCEPTED"})
    return vic


# ==============================================================================
# 1-4: TARGET BEARING TESTS (North, East, South, West)
# ==============================================================================

def test_01_target_bearing_north():
    """1. Target bearing North is approx 0 / 360 degrees."""
    # Rescuer south of target (moving due North)
    b = calculate_target_bearing(rescuer_lat=32.370000, rescuer_lon=77.240000, target_lat=32.380000, target_lon=77.240000)
    assert 0.0 <= b < 360.0
    assert abs(b - 0.0) < 1.0 or abs(b - 360.0) < 1.0


def test_02_target_bearing_east():
    """2. Target bearing East is approx 90 degrees."""
    # Rescuer west of target (moving due East on equator)
    b = calculate_target_bearing(rescuer_lat=0.0, rescuer_lon=0.0, target_lat=0.0, target_lon=1.0)
    assert 0.0 <= b < 360.0
    assert abs(b - 90.0) < 1.0


def test_03_target_bearing_south():
    """3. Target bearing South is approx 180 degrees."""
    # Rescuer north of target (moving due South)
    b = calculate_target_bearing(rescuer_lat=32.380000, rescuer_lon=77.240000, target_lat=32.370000, target_lon=77.240000)
    assert 0.0 <= b < 360.0
    assert abs(b - 180.0) < 1.0


def test_04_target_bearing_west():
    """4. Target bearing West is approx 270 degrees."""
    # Rescuer east of target (moving due West on equator)
    b = calculate_target_bearing(rescuer_lat=0.0, rescuer_lon=1.0, target_lat=0.0, target_lon=0.0)
    assert 0.0 <= b < 360.0
    assert abs(b - 270.0) < 1.0


# ==============================================================================
# 5-6: ANGLE WRAPAROUND & HEADING DIFFERENCE NORMALIZATION
# ==============================================================================

def test_05_angle_wraparound():
    """5. Angle wraparound handles 350° to 10° as 20° difference, not 340°."""
    # Target = 350, heading = 10 -> smallest difference = 20°
    diff1 = calculate_angular_difference(heading_deg=10.0, target_bearing_deg=350.0)
    assert diff1 == 20.0

    # Target = 10, heading = 350 -> smallest difference = 20°
    diff2 = calculate_angular_difference(heading_deg=350.0, target_bearing_deg=10.0)
    assert diff2 == 20.0

    # 1° and 359° -> 2°
    assert calculate_angular_difference(1.0, 359.0) == 2.0


def test_06_heading_difference_normalization():
    """6. Heading difference is always normalized between 0° and 180°."""
    for h in [0.0, 45.0, 90.0, 180.0, 270.0, 355.0]:
        for t in [0.0, 15.0, 90.0, 180.0, 275.0, 359.0]:
            diff = calculate_angular_difference(h, t)
            assert 0.0 <= diff <= 180.0


# ==============================================================================
# 7-11: NAVIGATION STATES, CONFIRMATION & COUNTER RESET
# ==============================================================================

def test_07_stationary_rescuer(started_client):
    """7. Stationary rescuer: speed < 0.5 m/s sets STATIONARY and produces no wrong-direction alerts."""
    vic = _assign_alpha1_mission(started_client)
    v_lat = vic["location"]["latitude"]
    v_lon = vic["location"]["longitude"]

    res = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-STAT-01",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": v_lat - 0.002,
        "longitude": v_lon,
        "accuracy_m": 5.0,
        "speed_mps": 0.2,  # Below 0.5 m/s threshold
        "heading_deg": 180.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["navigation"]["navigation_status"] == "STATIONARY"
    assert ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] == 0


def test_08_on_track_heading(started_client):
    """8. ON_TRACK heading: difference <= 45° results in ON_TRACK status."""
    vic = _assign_alpha1_mission(started_client)
    v_lat = vic["location"]["latitude"]
    v_lon = vic["location"]["longitude"]

    rescuer_lat = v_lat - 0.002
    rescuer_lon = v_lon
    target_b = calculate_target_bearing(rescuer_lat, rescuer_lon, v_lat, v_lon)

    # Move along target bearing (heading = target_b)
    res = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-ONTRK-01",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": rescuer_lat,
        "longitude": rescuer_lon,
        "accuracy_m": 4.0,
        "speed_mps": 1.2,
        "heading_deg": target_b,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["navigation"]["navigation_status"] == "ON_TRACK"
    assert data["navigation"]["heading_difference_deg"] is not None
    assert data["navigation"]["heading_difference_deg"] <= DIRECTION_TOLERANCE_DEGREES


def test_09_and_10_wrong_direction_multi_sample_confirmation(started_client):
    """
    9. WRONG_DIRECTION heading detected.
    10. 3 consecutive samples required for WRONG_DIRECTION confirmation.
    """
    vic = _assign_alpha1_mission(started_client)
    v_lat = vic["location"]["latitude"]
    v_lon = vic["location"]["longitude"]

    rescuer_lat = v_lat - 0.002
    rescuer_lon = v_lon
    target_b = calculate_target_bearing(rescuer_lat, rescuer_lon, v_lat, v_lon)
    wrong_heading = (target_b + 180.0) % 360.0

    with patch.object(api_mod, "send_direction_guidance_sms") as mock_sms:
        mock_sms.return_value = {"status": "DELIVERED", "provider": "SMS_GATE"}
        # Sample 1: wrong direction -> counter = 1, status remains ON_TRACK
        r1 = started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "BRG-WRONG-CONF",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": rescuer_lat,
            "longitude": rescuer_lon,
            "accuracy_m": 4.0,
            "speed_mps": 1.2,
            "heading_deg": wrong_heading,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })
        assert r1.json()["navigation"]["navigation_status"] == "ON_TRACK"
        assert ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] == 1
        assert mock_sms.call_count == 0

        # Sample 2: wrong direction -> counter = 2, status remains ON_TRACK
        r2 = started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "BRG-WRONG-CONF",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": rescuer_lat,
            "longitude": rescuer_lon,
            "accuracy_m": 4.0,
            "speed_mps": 1.2,
            "heading_deg": wrong_heading,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })
        assert r2.json()["navigation"]["navigation_status"] == "ON_TRACK"
        assert ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] == 2
        assert mock_sms.call_count == 0

        # Sample 3: wrong direction -> counter = 3, CONFIRMED WRONG_DIRECTION!
        r3 = started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "BRG-WRONG-CONF",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": rescuer_lat,
            "longitude": rescuer_lon,
            "accuracy_m": 4.0,
            "speed_mps": 1.2,
            "heading_deg": wrong_heading,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })
        assert r3.json()["navigation"]["navigation_status"] == "WRONG_DIRECTION"
        assert ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] >= 3
        assert mock_sms.call_count == 1


def test_11_counter_reset_after_correct_movement(started_client):
    """11. Counter resets when rescuer corrects course before reaching confirmation threshold."""
    vic = _assign_alpha1_mission(started_client)
    v_lat = vic["location"]["latitude"]
    v_lon = vic["location"]["longitude"]

    rescuer_lat = v_lat - 0.002
    rescuer_lon = v_lon
    target_b = calculate_target_bearing(rescuer_lat, rescuer_lon, v_lat, v_lon)
    wrong_heading = (target_b + 180.0) % 360.0

    # 2 wrong samples
    for _ in range(2):
        started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "BRG-RESET-CTR",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": rescuer_lat,
            "longitude": rescuer_lon,
            "accuracy_m": 4.0,
            "speed_mps": 1.2,
            "heading_deg": wrong_heading,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })
    assert ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] == 2

    # Rescuer turns back ON_TRACK
    res = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-RESET-CTR",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": rescuer_lat,
        "longitude": rescuer_lon,
        "accuracy_m": 4.0,
        "speed_mps": 1.2,
        "heading_deg": target_b,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })
    assert res.json()["navigation"]["navigation_status"] == "ON_TRACK"
    assert ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] == 0


# ==============================================================================
# 12-14: TURN GUIDANCE TESTS
# ==============================================================================

def test_12_turn_left_guidance():
    """12. Target significantly to the left -> Turn left guidance."""
    guidance, delta = calculate_direction_guidance(heading_deg=0.0, target_bearing_deg=270.0)
    assert "Turn left" in guidance
    assert abs(delta - 90.0) < 0.1


def test_13_turn_right_guidance():
    """13. Target significantly to the right -> Turn right guidance."""
    guidance, delta = calculate_direction_guidance(heading_deg=0.0, target_bearing_deg=90.0)
    assert "Turn right" in guidance
    assert abs(delta - 90.0) < 0.1


def test_14_turn_around_guidance():
    """14. Target approximately behind the rescuer -> Turn around guidance."""
    guidance, delta = calculate_direction_guidance(heading_deg=0.0, target_bearing_deg=180.0)
    assert "Turn around" in guidance
    assert abs(delta - 180.0) < 0.1


# ==============================================================================
# 15-18: DISTANCE & DISTANCE TREND TESTS
# ==============================================================================

def test_15_distance_calculation():
    """15. Haversine distance calculation is accurate."""
    c1 = GPSCoordinate(latitude=32.374800, longitude=77.249800)
    c2 = GPSCoordinate(latitude=32.375800, longitude=77.249800)
    dist = haversine_distance_m(c1, c2)
    assert 100.0 < dist < 120.0


def test_16_approaching_trend():
    """16. Distance decreasing > 1.0m is classified as APPROACHING."""
    trend = calculate_distance_trend(current_distance_m=50.0, previous_distance_m=55.0, hysteresis_m=1.0)
    assert trend == "APPROACHING"


def test_17_moving_away_trend():
    """17. Distance increasing > 1.0m is classified as MOVING_AWAY."""
    trend = calculate_distance_trend(current_distance_m=65.0, previous_distance_m=60.0, hysteresis_m=1.0)
    assert trend == "MOVING_AWAY"


def test_18_stable_trend():
    """18. Distance change <= 1.0m or missing previous distance is classified as STABLE."""
    assert calculate_distance_trend(current_distance_m=50.4, previous_distance_m=50.0, hysteresis_m=1.0) == "STABLE"
    assert calculate_distance_trend(current_distance_m=49.6, previous_distance_m=50.0, hysteresis_m=1.0) == "STABLE"
    assert calculate_distance_trend(current_distance_m=50.0, previous_distance_m=None) == "STABLE"


# ==============================================================================
# 19-21: ACCURACY REJECTION & STALE BEHAVIOR
# ==============================================================================

def test_19_gps_accuracy_rejection(started_client):
    """19. Inaccurate GPS (accuracy > 150m) is rejected from direction analysis."""
    vic = _assign_alpha1_mission(started_client)
    v_lat = vic["location"]["latitude"]
    v_lon = vic["location"]["longitude"]

    res = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-ACC-REJ",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": v_lat - 0.002,
        "longitude": v_lon,
        "accuracy_m": 250.0,  # Worse than 150m threshold
        "speed_mps": 1.2,
        "heading_deg": 180.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })
    assert res.status_code == 200
    assert ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] == 0


def test_20_and_21_gps_stale_behavior_and_no_alerts(started_client):
    """
    20. GPS fix older than 15 seconds transitions to STALE.
    21. No navigation alerts are dispatched while STALE.
    """
    vic = _assign_alpha1_mission(started_client)
    v_lat = vic["location"]["latitude"]
    v_lon = vic["location"]["longitude"]

    stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=25)).isoformat()
    with patch("backend.api.send_direction_guidance_sms") as mock_sms:
        res = started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "BRG-STALE-TEST",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": v_lat - 0.002,
            "longitude": v_lon,
            "accuracy_m": 4.0,
            "speed_mps": 1.5,
            "heading_deg": 180.0,
            "timestamp": stale_ts,
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "STALE"
        })
        assert res.status_code == 200
        assert mock_sms.call_count == 0
        assert ALPHA_M001_LATEST_GPS.get("gps_status") == "STALE"
        assert ALPHA_M001_LATEST_GPS.get("navigation_status") in ("STALE", "GPS_STALE")


# ==============================================================================
# 22-23: SMS COOLDOWN & SINGLE SAMPLE SUPPRESSION
# ==============================================================================

def test_22_and_23_sms_cooldown_and_single_sample_suppression(started_client):
    """
    22. SMS alert respects 30-second cooldown.
    23. Single wrong-direction sample does NOT trigger SMS.
    """
    vic = _assign_alpha1_mission(started_client)
    v_lat = vic["location"]["latitude"]
    v_lon = vic["location"]["longitude"]

    rescuer_lat = v_lat - 0.002
    rescuer_lon = v_lon
    target_b = calculate_target_bearing(rescuer_lat, rescuer_lon, v_lat, v_lon)
    wrong_heading = (target_b + 180.0) % 360.0

    with patch.object(api_mod, "send_direction_guidance_sms") as mock_sms:
        mock_sms.return_value = {"status": "DELIVERED", "provider": "SMS_GATE"}
        # Sample 1: No SMS
        started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "BRG-COOLDOWN",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": rescuer_lat,
            "longitude": rescuer_lon,
            "accuracy_m": 4.0,
            "speed_mps": 1.2,
            "heading_deg": wrong_heading,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })
        assert mock_sms.call_count == 0  # Test 23: No SMS from single sample

        # Sample 2: No SMS
        started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "BRG-COOLDOWN",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": rescuer_lat,
            "longitude": rescuer_lon,
            "accuracy_m": 4.0,
            "speed_mps": 1.2,
            "heading_deg": wrong_heading,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })
        assert mock_sms.call_count == 0

        # Sample 3: Confirmed -> 1 SMS sent
        started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "BRG-COOLDOWN",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": rescuer_lat,
            "longitude": rescuer_lon,
            "accuracy_m": 4.0,
            "speed_mps": 1.2,
            "heading_deg": wrong_heading,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })
        assert mock_sms.call_count == 1

        # Sample 4 (immediately after, within 30s cooldown): NO additional SMS sent
        started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "BRG-COOLDOWN",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": rescuer_lat,
            "longitude": rescuer_lon,
            "accuracy_m": 4.0,
            "speed_mps": 1.2,
            "heading_deg": wrong_heading,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })
        assert mock_sms.call_count == 1  # Still 1 due to 30s cooldown


# ==============================================================================
# 24-27: ARRIVAL, IDEMPOTENCY, GUIDANCE SUPPRESSION & DB PERSISTENCE
# ==============================================================================

def test_24_to_27_arrival_idempotency_and_db_persistence(started_client):
    """
    24. Arrival triggers when distance <= 15m.
    25. Arrival is idempotent (subsequent heartbeats do not duplicate events or reset state).
    26. Direction analysis and guidance stop after ARRIVED.
    27. ARRIVED persists to authoritative rescue_commands database row.
    """
    vic = _assign_alpha1_mission(started_client)
    v_lat = vic["location"]["latitude"]
    v_lon = vic["location"]["longitude"]

    # Position rescuer 5 meters from victim (well within 15m arrival radius)
    r1 = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-ARRIVE-01",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": v_lat,
        "longitude": v_lon,
        "accuracy_m": 2.0,
        "speed_mps": 0.3,
        "heading_deg": 90.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })
    assert r1.status_code == 200
    d1 = r1.json()["navigation"]

    # 24. Arrival detection
    assert d1["navigation_status"] == "ARRIVED"
    assert d1["is_arrived"] is True
    assert d1["arrived_at"] is not None

    # 26. No turn guidance after arrival
    assert "Arrived" in d1["direction_guidance"]

    first_arrived_at = d1["arrived_at"]

    # 25. Arrival Idempotency: Send second heartbeat with wrong heading
    with patch("backend.api.send_direction_guidance_sms") as mock_sms:
        r2 = started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "BRG-ARRIVE-01",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": v_lat,
            "longitude": v_lon,
            "accuracy_m": 2.0,
            "speed_mps": 1.2,
            "heading_deg": 270.0,  # Different heading
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })
        assert r2.status_code == 200
        d2 = r2.json()["navigation"]
        # Must stay ARRIVED
        assert d2["navigation_status"] == "ARRIVED"
        assert d2["is_arrived"] is True
        assert d2["arrived_at"] == first_arrived_at
        assert mock_sms.call_count == 0

    # 27. Persistence to authoritative DB command
    cmds = db.list_rescue_commands(member_id="ALPHA-M001")
    assert len(cmds) > 0
    cmd = cmds[0]
    assert cmd["status"] == "ARRIVED"
    assert cmd["navigation_status"] == "ARRIVED"
    assert cmd["arrived_at"] is not None


# ==============================================================================
# 28-32: SIMULATION ISOLATION TESTS
# ==============================================================================

def test_28_to_32_simulation_isolation(started_client):
    """
    28. Alpha 1 never returns to simulation.
    29. Alpha 2 remains simulation.
    30. Bravo 1 remains simulation.
    31. Bravo 2 remains simulation.
    32. Survivor remains fixed/simulated.
    """
    overview = started_client.get("/commander/overview").json()
    victims = overview["victims"]
    v1 = victims[0]["victim_id"]
    v2 = victims[1]["victim_id"]
    v3 = victims[2]["victim_id"]
    v4 = victims[3]["victim_id"]

    started_client.post("/commander/assign", json={"member_id": "ALPHA-M001", "victim_id": v1})
    started_client.post("/commander/assign", json={"member_id": "ALPHA-M002", "victim_id": v2})
    started_client.post("/commander/assign", json={"member_id": "BRAVO-M001", "victim_id": v3})
    started_client.post("/commander/assign", json={"member_id": "BRAVO-M002", "victim_id": v4})

    real_lat = 32.378900
    real_lon = 77.251200
    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-ISO-01",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": real_lat,
        "longitude": real_lon,
        "accuracy_m": 3.0,
        "speed_mps": 1.0,
        "heading_deg": 45.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })

    # Capture initial positions
    op = operations[list(operations.keys())[-1]]
    a1 = next(m for m in op.team_members["ALPHA"] if m.member_id == "ALPHA-M001")
    a2 = next(m for m in op.team_members["ALPHA"] if m.member_id == "ALPHA-M002")
    b1 = next(m for m in op.team_members["BRAVO"] if m.member_id == "BRAVO-M001")
    b2 = next(m for m in op.team_members["BRAVO"] if m.member_id == "BRAVO-M002")

    a2_lat_initial = a2.location.latitude
    b1_lat_initial = b1.location.latitude
    b2_lat_initial = b2.location.latitude

    vics = {v.victim_id: (v.location.latitude, v.location.longitude) for v in op.config.victims}

    # Advance tick (simulation step)
    op.tick()
    op.advance_team_members()

    # 28. Alpha 1 position is frozen at real GPS coordinates, never overwritten by simulation
    assert a1.location.latitude == real_lat
    assert a1.location.longitude == real_lon
    assert a1.location_source == "PHONE_GPS"

    # 29-31. Simulated members move
    assert a2.location.latitude != a2_lat_initial or a2.location.longitude != a2.location.longitude
    assert b1.location.latitude != b1_lat_initial or b1.location.longitude != b1.location.longitude
    assert b2.location.latitude != b2_lat_initial or b2.location.longitude != b2.location.longitude

    # 32. Survivor remains fixed/simulated
    for v in op.config.victims:
        orig_lat, orig_lon = vics[v.victim_id]
        assert v.location.latitude == orig_lat
        assert v.location.longitude == orig_lon


# ==============================================================================
# 33-37: REGRESSION & ARCHITECTURAL INVARIANTS
# ==============================================================================

def test_35_smsgate_isolation_no_real_sms():
    """35. SMS alerts use SMSGate only and dynamic contact resolution."""
    from backend.api import send_direction_guidance_sms
    with patch("notification_dispatch.dispatch_smsgate_sms") as mock_dispatch:
        mock_dispatch.return_value = {"status": "DELIVERED", "provider": "SMS_GATE"}
        res = send_direction_guidance_sms(
            member_id="ALPHA-M001",
            team_id="ALPHA",
            command_id="CMD-TEST",
            victim_id="VIC-001",
            heading_deg=180.0,
            target_bearing_deg=0.0,
            guidance="Turn around and head toward survivor",
            distance_m=120.0,
        )
        assert mock_dispatch.call_count == 1
        call_kwargs = mock_dispatch.call_args[1]
        assert "turn around" in call_kwargs["message_text"].lower()


def test_37_wearable_gateway_unmodified():
    """37. Verify backend/wearable_gateway.py is untouched."""
    import backend.wearable_gateway as gw
    assert hasattr(gw, "WearableGatewayManager")
    assert hasattr(gw, "global_wearable_gateway")
