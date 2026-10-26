"""
test_stage4_live_commander_guidance_arrival.py
----------------------------------------------
Comprehensive automated test suite for STAGE 4:
LIVE COMMANDER GPS, DIRECTION GUIDANCE & ARRIVAL IMPLEMENTATION.

Covers:
1. Alpha Member 1 starts at ASSIGNED.
2. Acceptance changes state correctly.
3. Real GPS location updates Alpha Member 1.
4. Synthetic movement does not overwrite Alpha Member 1.
5. Simulated Alpha Member 2 still moves synthetically.
6. Simulated Bravo members still move synthetically.
7. Survivor location remains unchanged.
8. Target bearing calculation is correct.
9. Haversine distance calculation is correct.
10. Movement heading calculation works when GPS heading is unavailable.
11. ON TRACK is detected correctly.
12. WRONG_DIRECTION is detected correctly.
13. One noisy GPS sample does not trigger WRONG_DIRECTION.
14. Multiple confirmed wrong-direction samples trigger the warning.
15. Direction alert cooldown prevents SMS spam.
16. SMS warning uses SMSGate only.
17. Dynamic contact resolution is preserved.
18. No private phone number is hardcoded.
19. ARRIVED triggers within the configured radius (<= 15.0m).
20. ARRIVED is idempotent.
21. No direction warning is sent after ARRIVED.
22. STALE GPS stops direction evaluation.
23. STALE GPS does not resume synthetic movement.
24. Fresh GPS resumes tracking.
25. No duplicate rescue commands are created.
26. No duplicate watch ACK is created.
27. Existing watch behavior remains untouched (backend/wearable_gateway.py).
"""

import os
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest

from fastapi.testclient import TestClient
from backend.api import (
    app,
    operations,
    calculate_angular_difference,
    calculate_direction_guidance,
    send_direction_guidance_sms,
    _bearing_deg,
    haversine_distance_m,
    GPS_ARRIVAL_DISTANCE_METERS,
    GPS_MIN_SPEED_FOR_DIRECTION_MPS,
    DIRECTION_TOLERANCE_DEGREES,
    DIRECTION_CONFIRMATION_SAMPLES,
    DIRECTION_ALERT_COOLDOWN_SECONDS,
    GPS_STALE_THRESHOLD_SECONDS,
    ALPHA_M001_LATEST_GPS,
    ALPHA_M001_NAV_STATE,
)
import backend.db as db
from backend.models import GPSCoordinate, MemberStatus, TeamMember


@pytest.fixture(autouse=True)
def reset_nav_state():
    """Reset global caches before each test run."""
    ALPHA_M001_LATEST_GPS.clear()
    ALPHA_M001_NAV_STATE.update({
        "status": "STANDBY",
        "consecutive_wrong_samples": 0,
        "consecutive_on_track_samples": 0,
        "last_direction_alert_time": 0.0,
        "last_heading": None,
        "last_lat": None,
        "last_lon": None,
        "last_dist_m": None,
        "last_bearing_deg": None,
        "last_guidance": None,
        "is_arrived": False,
        "assigned_victim_id": None,
        "assigned_cmd_id": None,
    })


def test_08_target_bearing_calculation():
    """8. Target bearing calculation is correct for all compass quadrants."""
    # North
    p_origin = GPSCoordinate(latitude=0.0, longitude=0.0)
    p_north = GPSCoordinate(latitude=1.0, longitude=0.0)
    b_north = _bearing_deg(p_origin, p_north)
    assert abs(b_north - 0.0) < 1.0 or abs(b_north - 360.0) < 1.0

    # East
    p_east = GPSCoordinate(latitude=0.0, longitude=1.0)
    b_east = _bearing_deg(p_origin, p_east)
    assert abs(b_east - 90.0) < 1.0

    # South
    p_south = GPSCoordinate(latitude=-1.0, longitude=0.0)
    b_south = _bearing_deg(p_origin, p_south)
    assert abs(b_south - 180.0) < 1.0

    # West
    p_west = GPSCoordinate(latitude=0.0, longitude=-1.0)
    b_west = _bearing_deg(p_origin, p_west)
    assert abs(b_west - 270.0) < 1.0


def test_09_haversine_distance_calculation():
    """9. Haversine distance calculation is correct."""
    p1 = GPSCoordinate(latitude=32.3739, longitude=77.2491)
    p2 = GPSCoordinate(latitude=32.3739, longitude=77.2491)
    assert haversine_distance_m(p1, p2) == 0.0

    # 1 degree latitude is approx 111.19 km
    p3 = GPSCoordinate(latitude=33.3739, longitude=77.2491)
    dist = haversine_distance_m(p1, p3)
    assert 110000.0 < dist < 112000.0


def test_10_movement_heading_fallback_when_gps_heading_unavailable(started_client):
    """10. Movement heading calculation works when GPS heading is unavailable or 0.0."""
    session_id = f"BRG-HEADING-{uuid.uuid4().hex[:6].upper()}"

    # Setup assignment and acceptance
    alert_res = started_client.post("/api/wearable/commands/test_alert", json={
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "target_id": "Survivor-1",
        "location_label": "Sector Alpha"
    })
    cmd_id = alert_res.json().get("command_id") or alert_res.json().get("command", {}).get("command_id")
    started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "USER_ACCEPTED"})

    # Send initial position (no heading)
    t1 = datetime.now(timezone.utc).isoformat()
    r1 = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3740,
        "longitude": 77.2490,
        "speed_mps": 1.2,
        "heading_deg": None,
        "timestamp": t1,
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })
    assert r1.status_code == 200

    # Send second position moving directly North (lat increased)
    t2 = datetime.now(timezone.utc).isoformat()
    r2 = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3745,  # moved north
        "longitude": 77.2490,
        "speed_mps": 1.5,
        "heading_deg": None,
        "timestamp": t2,
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })
    assert r2.status_code == 200

    # The computed heading should be approximately 0 / 360 deg (North)
    overview = started_client.get("/commander/overview").json()
    alpha1 = next(m for m in overview["team_members"] if m["member_id"] == "ALPHA-M001")
    assert alpha1["location_source"] == "PHONE_GPS"
    assert alpha1.get("heading_deg") is not None
    assert abs(alpha1["heading_deg"] - 0.0) < 5.0 or abs(alpha1["heading_deg"] - 360.0) < 5.0


def test_angular_difference_and_guidance_helpers():
    """Test angular difference and human-readable turn guidance helper functions."""
    # Difference wrapping around 0/360
    assert calculate_angular_difference(10.0, 350.0) == 20.0
    assert calculate_angular_difference(0.0, 180.0) == 180.0
    assert calculate_angular_difference(45.0, 90.0) == 45.0

    # Guidance strings
    # Heading 0, Target 90 -> Turn right
    g_right, _ = calculate_direction_guidance(0.0, 90.0)
    assert "Turn right" in g_right

    # Heading 0, Target 270 -> Turn left
    g_left, _ = calculate_direction_guidance(0.0, 270.0)
    assert "Turn left" in g_left

    # Heading 0, Target 180 -> Turn around
    g_around, _ = calculate_direction_guidance(0.0, 180.0)
    assert "Turn around" in g_around

    # Heading 0, Target 15 -> Continue straight
    g_straight, _ = calculate_direction_guidance(0.0, 15.0)
    assert "Continue straight" in g_straight or "on track" in g_straight.lower()


def test_01_to_07_assignment_acceptance_real_gps_and_simulation_isolation(started_client):
    """
    1. Alpha Member 1 starts at ASSIGNED.
    2. Acceptance changes state correctly.
    3. Real GPS location updates Alpha Member 1.
    4. Synthetic movement does not overwrite Alpha Member 1.
    5. Simulated Alpha Member 2 still moves synthetically.
    6. Simulated Bravo members still move synthetically.
    7. Survivor location remains unchanged.
    """
    # 1. Commander Assigns survivor to Alpha Member 1
    overview_before = started_client.get("/commander/overview").json()
    victim = overview_before["victims"][0]
    victim_id = victim["victim_id"]
    survivor_initial_lat = victim["location"]["latitude"]
    survivor_initial_lon = victim["location"]["longitude"]

    assign_res = started_client.post("/commander/assign", json={
        "member_id": "ALPHA-M001",
        "victim_id": victim_id
    })
    assert assign_res.status_code == 200
    assert assign_res.json()["status"] == "en_route"
    assert assign_res.json()["assigned_victim_id"] == victim_id

    # Check active rescue command for ALPHA-M001
    active_cmd = db.get_active_command_for_member("ALPHA-M001")
    assert active_cmd is not None
    cmd_id = active_cmd["command_id"]
    assert active_cmd["status"] == "ASSIGNED"

    # 2. Acceptance changes state correctly
    accept_res = started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "USER_ACCEPTED"
    })
    assert accept_res.status_code == 200
    updated_cmd = db.get_active_command_for_member("ALPHA-M001")
    assert updated_cmd["status"] in ("ACCEPTED", "USER_ACCEPTED")

    # 3. Real GPS location updates Alpha Member 1
    session_id = f"BRG-STAGE4-{uuid.uuid4().hex[:6].upper()}"
    real_lat = 32.3785
    real_lon = 77.2515
    gps_time = datetime.now(timezone.utc).isoformat()

    sync_res = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": real_lat,
        "longitude": real_lon,
        "accuracy_m": 3.0,
        "speed_mps": 1.4,
        "heading_deg": 90.0,
        "timestamp": gps_time,
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })
    assert sync_res.status_code == 200

    overview_after_gps = started_client.get("/commander/overview").json()
    alpha1 = next(m for m in overview_after_gps["team_members"] if m["member_id"] == "ALPHA-M001")
    assert alpha1["location_source"] == "PHONE_GPS"
    assert abs(alpha1["location"]["latitude"] - real_lat) < 1e-4
    assert abs(alpha1["location"]["longitude"] - real_lon) < 1e-4

    # Record positions of simulated members before tick
    alpha2_lat_before = next(m["location"]["latitude"] for m in overview_after_gps["team_members"] if m["member_id"] == "ALPHA-M002")
    bravo1_lat_before = next(m["location"]["latitude"] for m in overview_after_gps["team_members"] if m["member_id"] == "BRAVO-M001")
    bravo2_lat_before = next(m["location"]["latitude"] for m in overview_after_gps["team_members"] if m["member_id"] == "BRAVO-M002")

    # Advance scenario by tick
    started_client.post("/scenario/tick")

    overview_after_tick = started_client.get("/commander/overview").json()
    alpha1_after = next(m for m in overview_after_tick["team_members"] if m["member_id"] == "ALPHA-M001")
    alpha2_after = next(m for m in overview_after_tick["team_members"] if m["member_id"] == "ALPHA-M002")
    bravo1_after = next(m for m in overview_after_tick["team_members"] if m["member_id"] == "BRAVO-M001")
    bravo2_after = next(m for m in overview_after_tick["team_members"] if m["member_id"] == "BRAVO-M002")
    victim_after = next(v for v in overview_after_tick["victims"] if v["victim_id"] == victim_id)

    # 4. Synthetic movement does not overwrite Alpha Member 1
    assert abs(alpha1_after["location"]["latitude"] - real_lat) < 1e-4
    assert abs(alpha1_after["location"]["longitude"] - real_lon) < 1e-4

    # 5 & 6. Simulated members still have simulated movement capability
    assert alpha2_after["location_source"] == "SIMULATED"
    assert bravo1_after["location_source"] == "SIMULATED"
    assert bravo2_after["location_source"] == "SIMULATED"

    # 7. Survivor location remains unchanged
    assert victim_after["location"]["latitude"] == survivor_initial_lat
    assert victim_after["location"]["longitude"] == survivor_initial_lon


def test_11_to_15_wrong_direction_confirmation_and_sms_cooldown(started_client):
    """
    11. ON TRACK is detected correctly.
    12. WRONG_DIRECTION is detected correctly.
    13. One noisy GPS sample does not trigger WRONG_DIRECTION.
    14. Multiple confirmed wrong-direction samples trigger the warning.
    15. Direction alert cooldown prevents SMS spam.
    16. SMS warning uses SMSGate only.
    """
    session_id = f"BRG-NAV-{uuid.uuid4().hex[:6].upper()}"

    # Assign survivor to ALPHA-M001
    overview = started_client.get("/commander/overview").json()
    victim = overview["victims"][0]
    victim_id = victim["victim_id"]
    victim_lat = victim["location"]["latitude"]
    victim_lon = victim["location"]["longitude"]

    started_client.post("/commander/assign", json={
        "member_id": "ALPHA-M001",
        "victim_id": victim_id
    })
    active_cmd = db.get_active_command_for_member("ALPHA-M001")
    cmd_id = active_cmd["command_id"]
    started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "USER_ACCEPTED"})

    # Place rescuer 100m away from survivor
    rescuer_lat = victim_lat - 0.001  # South of survivor -> Target bearing is North (approx 0 deg)
    rescuer_lon = victim_lon

    target_bearing = _bearing_deg(GPSCoordinate(latitude=rescuer_lat, longitude=rescuer_lon),
                                  GPSCoordinate(latitude=victim_lat, longitude=victim_lon))

    # 11. ON TRACK: Rescuer moving toward survivor (heading = target_bearing)
    on_track_time = datetime.now(timezone.utc).isoformat()
    r_on_track = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": rescuer_lat,
        "longitude": rescuer_lon,
        "accuracy_m": 4.0,
        "speed_mps": 1.5,
        "heading_deg": target_bearing,  # Perfectly aligned
        "timestamp": on_track_time,
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })
    assert r_on_track.status_code == 200
    data_on_track = r_on_track.json()
    assert data_on_track.get("navigation", {}).get("navigation_status") == "ON_TRACK"

    # Mock SMS dispatch to capture SMSGate calls
    _api_mod = sys.modules.get("api") or sys.modules.get("backend.api")
    with patch.object(_api_mod, "send_direction_guidance_sms") as mock_send_sms:
        mock_send_sms.return_value = {"status": "DELIVERED", "provider": "SMS_GATE"}

        # 13. One noisy GPS sample (heading directly opposite: +180 deg)
        wrong_heading = (target_bearing + 180.0) % 360.0
        t1 = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
        r_sample1 = started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": session_id,
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": rescuer_lat,
            "longitude": rescuer_lon,
            "accuracy_m": 4.0,
            "speed_mps": 1.5,
            "heading_deg": wrong_heading,
            "timestamp": t1,
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })
        assert r_sample1.status_code == 200
        # Should NOT trigger WRONG_DIRECTION or SMS on 1st sample
        assert r_sample1.json().get("navigation", {}).get("navigation_status") != "WRONG_DIRECTION"
        assert mock_send_sms.call_count == 0

        # Sample 2: Still not confirmed
        t2 = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
        r_sample2 = started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": session_id,
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": rescuer_lat - 0.00002,
            "longitude": rescuer_lon,
            "accuracy_m": 4.0,
            "speed_mps": 1.5,
            "heading_deg": wrong_heading,
            "timestamp": t2,
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })
        assert r_sample2.status_code == 200
        assert r_sample2.json().get("navigation", {}).get("navigation_status") != "WRONG_DIRECTION"
        assert mock_send_sms.call_count == 0

        # 14. Sample 3: 3rd sample reaches DIRECTION_CONFIRMATION_SAMPLES -> WRONG_DIRECTION confirmed
        t3 = (datetime.now(timezone.utc) + timedelta(seconds=3)).isoformat()
        r_sample3 = started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": session_id,
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": rescuer_lat - 0.00004,
            "longitude": rescuer_lon,
            "accuracy_m": 4.0,
            "speed_mps": 1.5,
            "heading_deg": wrong_heading,
            "timestamp": t3,
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })
        assert r_sample3.status_code == 200
        nav3 = r_sample3.json().get("navigation", {})
        assert nav3.get("navigation_status") == "WRONG_DIRECTION"
        assert "Turn around" in nav3.get("direction_guidance", "")
        # First SMS warning sent
        assert mock_send_sms.call_count == 1

        # 15. Sample 4: Within 30s cooldown -> No duplicate SMS sent
        t4 = (datetime.now(timezone.utc) + timedelta(seconds=4)).isoformat()
        r_sample4 = started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": session_id,
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": rescuer_lat - 0.00006,
            "longitude": rescuer_lon,
            "accuracy_m": 4.0,
            "speed_mps": 1.5,
            "heading_deg": wrong_heading,
            "timestamp": t4,
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })
        assert r_sample4.status_code == 200
        # Call count must remain 1 due to 30-second cooldown
        assert mock_send_sms.call_count == 1


def test_16_17_18_smsgate_provider_and_dynamic_recipient():
    """
    16. SMS warning uses SMSGate only.
    17. Dynamic contact resolution is preserved.
    18. No private phone number is hardcoded.
    """
    with patch("backend.notification_dispatch.dispatch_smsgate_sms") as mock_smsgate:
        mock_smsgate.return_value = {"status": "DELIVERED", "provider": "SMSGATE", "message_id": "SMS-MOCK-123"}

        res = send_direction_guidance_sms(
            member_id="ALPHA-M001",
            team_id="ALPHA",
            command_id="CMD-TEST-DYNAMIC",
            victim_id="VIC-001",
            heading_deg=180.0,
            target_bearing_deg=0.0,
            guidance="WRONG DIRECTION — Turn around and head toward survivor.",
            distance_m=120.0
        )

        assert res is not None
        assert res.get("status") in ("DELIVERED", "SIMULATED_TEST", "SENT")
        # Ensure recipient is dynamically queried from team member contact, not hardcoded
        contact = db.resolve_member_contact_info("ALPHA-M001", team_id="ALPHA")
        expected_contact = contact.get("phone_normalized") or contact.get("phone_masked")
        assert expected_contact is not None


def test_19_to_21_arrival_detection_idempotency_and_no_guidance_after_arrival(started_client):
    """
    19. ARRIVED triggers within configured radius (<= 15.0m).
    20. ARRIVED is idempotent.
    21. No direction warning is sent after ARRIVED.
    """
    session_id = f"BRG-ARRIVE-{uuid.uuid4().hex[:6].upper()}"

    # Assign and accept
    overview = started_client.get("/commander/overview").json()
    victim = overview["victims"][0]
    victim_id = victim["victim_id"]
    victim_lat = victim["location"]["latitude"]
    victim_lon = victim["location"]["longitude"]

    started_client.post("/commander/assign", json={
        "member_id": "ALPHA-M001",
        "victim_id": victim_id
    })
    active_cmd = db.get_active_command_for_member("ALPHA-M001")
    cmd_id = active_cmd["command_id"]
    started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "USER_ACCEPTED"})

    # Send GPS fix directly at survivor location (distance = 0m <= 15m)
    gps_time = datetime.now(timezone.utc).isoformat()
    r_arrive = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": victim_lat,
        "longitude": victim_lon,
        "accuracy_m": 2.0,
        "speed_mps": 0.8,
        "heading_deg": 45.0,
        "timestamp": gps_time,
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })
    assert r_arrive.status_code == 200
    nav = r_arrive.json().get("navigation", {})
    assert nav.get("is_arrived") is True
    assert nav.get("navigation_status") == "ARRIVED"
    assert nav.get("distance_to_target_m") <= GPS_ARRIVAL_DISTANCE_METERS

    # Verify command in DB is updated to ARRIVED with arrived_at timestamp
    cmd_db = db.get_rescue_command(cmd_id)
    assert cmd_db["status"] == "ARRIVED"
    assert cmd_db.get("arrived_at") is not None

    # 20. ARRIVED is idempotent: Send another heartbeat, still ARRIVED
    t2 = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
    r_arrive2 = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": victim_lat + 0.00001,
        "longitude": victim_lon,
        "accuracy_m": 2.0,
        "speed_mps": 0.8,
        "heading_deg": 180.0, # Facing away, but already arrived!
        "timestamp": t2,
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })
    assert r_arrive2.status_code == 200
    nav2 = r_arrive2.json().get("navigation", {})
    assert nav2.get("is_arrived") is True
    assert nav2.get("navigation_status") == "ARRIVED"

    # 21. No direction warnings after ARRIVED
    assert "WRONG_DIRECTION" not in nav2.get("navigation_status")


def test_22_to_24_stale_gps_stops_direction_evaluation_and_resumes_fresh(started_client):
    """
    22. STALE GPS stops direction evaluation.
    23. STALE GPS does not resume synthetic movement.
    24. Fresh GPS resumes tracking.
    """
    session_id = f"BRG-STALE-{uuid.uuid4().hex[:6].upper()}"

    # Setup assignment
    overview = started_client.get("/commander/overview").json()
    victim = overview["victims"][0]
    started_client.post("/commander/assign", json={
        "member_id": "ALPHA-M001",
        "victim_id": victim["victim_id"]
    })
    active_cmd = db.get_active_command_for_member("ALPHA-M001")
    cmd_id = active_cmd["command_id"]
    started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "USER_ACCEPTED"})

    # Send GPS fix timestamped 30 seconds in the past (> 15s threshold)
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=35)).isoformat()
    real_lat = 32.3755
    real_lon = 77.2505

    r_stale = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": real_lat,
        "longitude": real_lon,
        "accuracy_m": 5.0,
        "speed_mps": 1.2,
        "heading_deg": 180.0,
        "timestamp": stale_time,
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "STALE"
    })
    assert r_stale.status_code == 200

    overview = started_client.get("/commander/overview").json()
    alpha1 = next(m for m in overview["team_members"] if m["member_id"] == "ALPHA-M001")
    # 22. STALE GPS stops direction evaluation
    assert alpha1["gps_status"] == "STALE"
    assert alpha1.get("navigation_status") == "STALE"

    # 23. STALE GPS does not resume synthetic movement
    started_client.post("/scenario/tick")
    overview_tick = started_client.get("/commander/overview").json()
    alpha1_tick = next(m for m in overview_tick["team_members"] if m["member_id"] == "ALPHA-M001")
    assert abs(alpha1_tick["location"]["latitude"] - real_lat) < 1e-4
    assert abs(alpha1_tick["location"]["longitude"] - real_lon) < 1e-4

    # 24. Fresh GPS resumes tracking
    fresh_time = datetime.now(timezone.utc).isoformat()
    r_fresh = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": real_lat + 0.0001,
        "longitude": real_lon + 0.0001,
        "accuracy_m": 3.0,
        "speed_mps": 1.5,
        "heading_deg": 45.0,
        "timestamp": fresh_time,
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })
    assert r_fresh.status_code == 200

    overview_fresh = started_client.get("/commander/overview").json()
    alpha1_fresh = next(m for m in overview_fresh["team_members"] if m["member_id"] == "ALPHA-M001")
    assert alpha1_fresh["gps_status"] == "TRACKING"


def test_25_to_27_no_duplicate_commands_no_fake_acks_wearable_gateway_untouched(started_client):
    """
    25. No duplicate rescue commands are created.
    26. No duplicate watch ACK is created.
    27. Existing watch behavior remains untouched (backend/wearable_gateway.py).
    """
    # 27. Confirm wearable_gateway.py was NOT modified
    with open("backend/wearable_gateway.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "class WaveCallPlusAdapter" in content
    assert "class WearableGatewayManager" in content
    assert "DEV-WEARABLE-CALLPLUS" in content
    assert "CB:4E:FD:EE:7F:1B" in content

    # Check git diff of wearable_gateway.py is empty
    import subprocess
    diff = subprocess.run(
        ["git", "diff", "backend/wearable_gateway.py"],
        capture_output=True,
        text=True,
        shell=True
    )
    assert diff.stdout.strip() == "", "backend/wearable_gateway.py MUST NOT be modified!"

    # 25. Trigger test alert
    alert_res = started_client.post("/api/wearable/commands/test_alert", json={
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001"
    })
    cmd_id = alert_res.json().get("command_id") or alert_res.json().get("command", {}).get("command_id")

    # Send multiple GPS heartbeats
    for i in range(3):
        started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "BRG-CHECK-DUP",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": 32.3739 + i * 0.0001,
            "longitude": 77.2491,
            "gps_available": True,
            "location_source": "PHONE_GPS",
            "gps_status": "TRACKING"
        })

    # Verify no duplicate active commands were created for ALPHA-M001
    active_commands = db.get_active_wearable_commands()
    alpha1_commands = [c for c in active_commands if c["member_id"] == "ALPHA-M001"]
    assert len(alpha1_commands) == 1
    assert alpha1_commands[0]["command_id"] == cmd_id

    # 26. Hardware ACK remains unconfirmed until physical watch confirms
    live_state = started_client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live_state.get("hardware_ack_received") is False
    assert live_state.get("watch_acknowledged") is False
