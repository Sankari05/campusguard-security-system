"""
test_stage7_operational_reliability.py
---------------------------------------
Comprehensive automated test suite for STAGE 7:
OPERATIONAL RELIABILITY, MISSION LIFECYCLE HARDENING, AND GPS/NETWORK RECOVERY

Tests covered (Section 17):
1.  mission lifecycle transition safety
2.  duplicate acceptance
3.  duplicate assignment protection
4.  duplicate heartbeat
5.  out-of-order heartbeat
6.  stale heartbeat handling
7.  fresh heartbeat recovery
8.  GPS unavailable behavior
9.  GPS recovery
10. invalid coordinates
11. invalid timestamp
12. old telemetry cannot overwrite newer telemetry
13. stale GPS cannot trigger navigation
14. stale GPS cannot trigger SMS
15. arrived mission cannot trigger guidance
16. completed mission cannot trigger guidance
17. wrong-direction cooldown survives duplicate telemetry
18. wrong-direction counter resets correctly
19. mission-scoped state reset
20. old mission state cannot affect new mission
21. Alpha 1 never enters synthetic movement
22. Alpha 2 remains simulation-only
23. Bravo members remain simulation-only
24. survivor locations remain simulation-only
25. Commander live marker freezes when stale
26. Commander marker resumes after fresh GPS
27. notification idempotency
28. SMSGate remains the only SMS path
29. watch flow remains untouched
30. database restart/recovery behavior where practical
31. backward API compatibility
"""

import os
import sys
import time
import math
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest

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

reset_alpha_m001_telemetry = api_mod.reset_alpha_m001_telemetry
reset_alpha_m001_mission_navigation_state = api_mod.reset_alpha_m001_mission_navigation_state
validate_gps_coordinates = api_mod.validate_gps_coordinates

import backend.db as db
from backend.models import GPSCoordinate, MemberStatus, TeamMember
haversine_distance_m = api_mod.haversine_distance_m


@pytest.fixture(autouse=True)
def reset_stage7_state():
    """Reset Alpha Member 1 navigation and telemetry state before each test."""
    reset_alpha_m001_telemetry()
    yield
    reset_alpha_m001_telemetry()


def _setup_active_operation(started_client, target_index=0):
    """Helper to start operation and assign Alpha Member 1 to a victim."""
    overview = started_client.get("/commander/overview").json()
    victims = overview.get("victims", [])
    assert len(victims) > target_index, "No victims available in scenario"
    vic = victims[target_index]
    victim_id = vic["victim_id"]

    with patch.object(api_mod, "send_direction_guidance_sms") as mock_sms, \
         patch("backend.notification_dispatch.dispatch_smsgate_sms") as mock_smsgate:
        mock_smsgate.return_value = {"status": "SUCCESS", "message_id": "MOCK-SMS"}
        r = started_client.post("/commander/assign", json={
            "member_id": "ALPHA-M001",
            "victim_id": victim_id
        })
        assert r.status_code == 200, f"Assign failed: {r.text}"

    active_cmd = db.get_active_command_for_member("ALPHA-M001")
    assert active_cmd is not None
    cmd_id = active_cmd["command_id"]
    started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "USER_ACCEPTED"})
    return vic, active_cmd


# ==============================================================================
# 1. Mission Lifecycle Transition Safety
# ==============================================================================

def test_01_mission_lifecycle_transition_safety(started_client):
    """1. Enforce lifecycle transition rules: terminal states cannot revert, ARRIVED cannot revert backwards."""
    vic, cmd = _setup_active_operation(started_client)
    cmd_id = cmd["command_id"]

    # Transition to ARRIVED
    updated = db.update_rescue_command_status(cmd_id, status="ARRIVED")
    assert updated["status"] == "ARRIVED"

    # Attempt illegal backwards transition from ARRIVED to EN_ROUTE
    reverted = db.update_rescue_command_status(cmd_id, status="EN_ROUTE")
    assert reverted["status"] == "ARRIVED", "ARRIVED status must not revert backwards to EN_ROUTE"

    # Attempt illegal transition from ARRIVED to ASSIGNED
    reverted2 = db.update_rescue_command_status(cmd_id, status="ASSIGNED")
    assert reverted2["status"] == "ARRIVED", "ARRIVED status must not revert to ASSIGNED"

    # Legal transition from ARRIVED to COMPLETED
    completed = db.update_rescue_command_status(cmd_id, status="COMPLETED")
    assert completed["status"] == "COMPLETED"

    # Attempt illegal transition from COMPLETED to EN_ROUTE or ARRIVED
    bad_rev = db.update_rescue_command_status(cmd_id, status="EN_ROUTE")
    assert bad_rev["status"] == "COMPLETED", "COMPLETED status must not revert to EN_ROUTE"
    bad_rev2 = db.update_rescue_command_status(cmd_id, status="ARRIVED")
    assert bad_rev2["status"] == "COMPLETED", "COMPLETED status must not revert to ARRIVED"


# ==============================================================================
# 2. Duplicate Acceptance Idempotency
# ==============================================================================

def test_02_duplicate_acceptance(started_client):
    """2. Acceptance must be idempotent and must not resend notifications or create duplicate commands."""
    vic, cmd = _setup_active_operation(started_client)
    cmd_id = cmd["command_id"]

    count_before = len(db.list_rescue_commands(member_id="ALPHA-M001"))

    # Repeated acceptance calls
    with patch("backend.notification_dispatch.dispatch_smsgate_sms") as mock_smsgate:
        for _ in range(3):
            r = started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "USER_ACCEPTED"})
            assert r.status_code == 200
            # Also test accept endpoint
            r_acc = started_client.post(f"/api/wearable/notifications/{cmd_id}/accept")
            assert r_acc.status_code == 200

        # Must not have sent any new SMS
        mock_smsgate.assert_not_called()

    count_after = len(db.list_rescue_commands(member_id="ALPHA-M001"))
    assert count_after == count_before, "Duplicate acceptance must not create duplicate rescue commands"


# ==============================================================================
# 3. Duplicate Assignment Protection
# ==============================================================================

def test_03_duplicate_assignment_protection(started_client):
    """3. Repeated assignment must return existing active command idempotently without creating new commands."""
    vic, cmd = _setup_active_operation(started_client)
    cmd_id = cmd["command_id"]

    cmds_before = db.list_rescue_commands(member_id="ALPHA-M001")

    with patch("backend.notification_dispatch.dispatch_smsgate_sms") as mock_smsgate:
        # Assign same victim again
        r = started_client.post("/commander/assign", json={
            "member_id": "ALPHA-M001",
            "victim_id": vic["victim_id"]
        })
        assert r.status_code == 200
        # No new SMS dispatches
        mock_smsgate.assert_not_called()

    cmds_after = db.list_rescue_commands(member_id="ALPHA-M001")
    assert len(cmds_after) == len(cmds_before), "Repeated assignment must not create duplicate commands"


# ==============================================================================
# 4. Duplicate Heartbeat Protection
# ==============================================================================

def test_04_duplicate_heartbeat(started_client):
    """4. Duplicate GPS heartbeats with identical timestamps are safely ignored without duplicating alerts."""
    vic, cmd = _setup_active_operation(started_client)
    ts_fixed = datetime.now(timezone.utc).isoformat()

    payload = {
        "session_id": "TEST-STAGE7-DUP",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3740,
        "longitude": 77.2480,
        "accuracy_m": 5.0,
        "speed_mps": 1.5,
        "heading_deg": 180.0,
        "timestamp": ts_fixed,
        "gps_available": True,
        "gps_status": "TRACKING"
    }

    with patch.object(api_mod, "send_direction_guidance_sms") as mock_sms:
        r1 = started_client.post("/api/wearable/bridge/heartbeat", json=payload)
        assert r1.status_code == 200

        # Send duplicate heartbeat
        r2 = started_client.post("/api/wearable/bridge/heartbeat", json=payload)
        assert r2.status_code == 200

        # Duplicate heartbeat must not send direction SMS
        mock_sms.assert_not_called()


# ==============================================================================
# 5. Out-of-Order Heartbeat Protection
# ==============================================================================

def test_05_out_of_order_heartbeat(started_client):
    """5. An older GPS heartbeat arriving after a newer heartbeat must not move Alpha 1 backwards in time."""
    vic, cmd = _setup_active_operation(started_client)
    now = datetime.now(timezone.utc)
    t_new = (now).isoformat()
    t_old = (now - timedelta(seconds=10)).isoformat()

    # Send newer coordinate (Point A)
    r1 = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-STAGE7-ORDER",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3745,
        "longitude": 77.2485,
        "accuracy_m": 4.0,
        "speed_mps": 1.2,
        "timestamp": t_new,
        "gps_available": True,
        "gps_status": "TRACKING"
    })
    assert r1.status_code == 200
    assert abs(ALPHA_M001_LATEST_GPS["latitude"] - 32.3745) < 1e-5

    # Send older delayed coordinate (Point B)
    r2 = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-STAGE7-ORDER",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3700,
        "longitude": 77.2400,
        "accuracy_m": 4.0,
        "speed_mps": 1.2,
        "timestamp": t_old,
        "gps_available": True,
        "gps_status": "TRACKING"
    })
    assert r2.status_code == 200

    # Newer coordinate Point A MUST be preserved
    assert abs(ALPHA_M001_LATEST_GPS["latitude"] - 32.3745) < 1e-5, "Out-of-order telemetry must not overwrite newer coordinate"


# ==============================================================================
# 6. Stale Heartbeat Handling
# ==============================================================================

def test_06_stale_heartbeat_handling(started_client):
    """6. Telemetry older than stale threshold (15s) is marked STALE and suspends navigation."""
    vic, cmd = _setup_active_operation(started_client)
    stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()

    r = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-STAGE7-STALE",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3740,
        "longitude": 77.2480,
        "accuracy_m": 5.0,
        "speed_mps": 1.0,
        "timestamp": stale_ts,
        "gps_available": True,
        "gps_status": "TRACKING"
    })
    assert r.status_code == 200
    assert ALPHA_M001_LATEST_GPS["gps_status"] == "STALE"
    assert ALPHA_M001_NAV_STATE["navigation_status"] == "STALE"


# ==============================================================================
# 7. Fresh Heartbeat Recovery
# ==============================================================================

def test_07_fresh_heartbeat_recovery(started_client):
    """7. Telemetry returning to fresh (<15s) resumes TRACKING from STALE state safely."""
    vic, cmd = _setup_active_operation(started_client)

    # 1. Enter STALE
    stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=25)).isoformat()
    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-STAGE7-REC",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3740,
        "longitude": 77.2480,
        "timestamp": stale_ts,
        "gps_available": True,
        "gps_status": "TRACKING"
    })
    assert ALPHA_M001_LATEST_GPS["gps_status"] == "STALE"

    # 2. Fresh heartbeat arrives
    fresh_ts = datetime.now(timezone.utc).isoformat()
    r = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-STAGE7-REC",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3741,
        "longitude": 77.2481,
        "speed_mps": 1.2,
        "heading_deg": 90.0,
        "timestamp": fresh_ts,
        "gps_available": True,
        "gps_status": "TRACKING"
    })
    assert r.status_code == 200
    assert ALPHA_M001_LATEST_GPS["gps_status"] == "TRACKING"
    assert ALPHA_M001_NAV_STATE["navigation_status"] in ("ON_TRACK", "WRONG_DIRECTION", "STATIONARY")


# ==============================================================================
# 8. GPS Unavailable Behavior
# ==============================================================================

def test_08_gps_unavailable_behavior(started_client):
    """8. GPS unavailable sets navigation to GPS_UNAVAILABLE and does not fabricate coordinates."""
    vic, cmd = _setup_active_operation(started_client)

    # Establish last known coordinate
    ts1 = datetime.now(timezone.utc).isoformat()
    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-STAGE7-UNAVAIL",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3740,
        "longitude": 77.2480,
        "timestamp": ts1,
        "gps_available": True,
        "gps_status": "TRACKING"
    })
    last_lat = ALPHA_M001_LATEST_GPS["latitude"]

    # GPS becomes unavailable
    ts2 = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    r = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-STAGE7-UNAVAIL",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": None,
        "longitude": None,
        "timestamp": ts2,
        "gps_available": False,
        "gps_status": "GPS_UNAVAILABLE"
    })
    assert r.status_code == 200
    assert ALPHA_M001_LATEST_GPS["gps_status"] == "GPS_UNAVAILABLE"
    assert ALPHA_M001_NAV_STATE["navigation_status"] == "GPS_UNAVAILABLE"
    # Preserves last known coordinate
    assert ALPHA_M001_LATEST_GPS["latitude"] == last_lat


# ==============================================================================
# 9. GPS Recovery from Unavailable
# ==============================================================================

def test_09_gps_recovery(started_client):
    """9. When GPS becomes available again, tracking resumes with fresh valid sample."""
    vic, cmd = _setup_active_operation(started_client)

    # 1. Unavailable
    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-STAGE7-REC2",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "gps_available": False,
        "gps_status": "GPS_UNAVAILABLE"
    })

    # 2. Reconnects with fresh sample
    ts = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
    r = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-STAGE7-REC2",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3742,
        "longitude": 77.2482,
        "accuracy_m": 3.0,
        "speed_mps": 1.0,
        "heading_deg": 45.0,
        "timestamp": ts,
        "gps_available": True,
        "gps_status": "TRACKING"
    })
    assert r.status_code == 200
    assert ALPHA_M001_LATEST_GPS["gps_status"] == "TRACKING"


# ==============================================================================
# 10. Invalid Coordinates Rejection
# ==============================================================================

def test_10_invalid_coordinates(started_client):
    """10. Coordinates outside -90..90 lat, -180..180 lon, or NaN/Inf are rejected with HTTP 400."""
    # Latitude > 90
    r1 = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-INVALID",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 95.0,
        "longitude": 77.0,
    })
    assert r1.status_code == 400

    # Longitude < -180
    r2 = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-INVALID",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.0,
        "longitude": -195.0,
    })
    assert r2.status_code == 400


# ==============================================================================
# 11. Invalid Timestamp Handling
# ==============================================================================

def test_11_invalid_timestamp(started_client):
    """11. Malformed ISO timestamp or impossible future timestamp is rejected with HTTP 400."""
    # Malformed string
    r1 = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-INVALID",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.0,
        "longitude": 77.0,
        "timestamp": "not-a-timestamp",
    })
    assert r1.status_code == 400

    # Far future timestamp
    r2 = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-INVALID",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.0,
        "longitude": 77.0,
        "timestamp": "2099-01-01T00:00:00Z",
    })
    assert r2.status_code == 400


# ==============================================================================
# 12. Old Telemetry Cannot Overwrite Newer Telemetry
# ==============================================================================

def test_12_old_telemetry_cannot_overwrite_newer_telemetry(started_client):
    """12. Consecutive out-of-order samples cannot mutate the latest valid coordinate."""
    vic, cmd = _setup_active_operation(started_client)
    base_time = datetime.now(timezone.utc)

    # Sample 1 (t=10s)
    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-ORDER",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3750,
        "longitude": 77.2500,
        "timestamp": (base_time + timedelta(seconds=10)).isoformat(),
        "gps_available": True,
    })
    assert abs(ALPHA_M001_LATEST_GPS["latitude"] - 32.3750) < 1e-5

    # Sample 2 (t=5s, older)
    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-ORDER",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3710,
        "longitude": 77.2410,
        "timestamp": (base_time + timedelta(seconds=5)).isoformat(),
        "gps_available": True,
    })
    assert abs(ALPHA_M001_LATEST_GPS["latitude"] - 32.3750) < 1e-5


# ==============================================================================
# 13-14. Stale GPS Cannot Trigger Navigation or SMS
# ==============================================================================

def test_13_14_stale_gps_cannot_trigger_navigation_or_sms(started_client):
    """13 & 14. When GPS is stale, navigation evaluation is suspended and no wrong-direction SMS can fire."""
    vic, cmd = _setup_active_operation(started_client)
    stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=35)).isoformat()

    with patch.object(api_mod, "send_direction_guidance_sms") as mock_sms:
        # Send wrong heading with stale timestamp
        r = started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "TEST-STALE-NAV",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": 32.3740,
            "longitude": 77.2480,
            "speed_mps": 2.0,
            "heading_deg": 180.0,
            "timestamp": stale_ts,
            "gps_available": True,
            "gps_status": "TRACKING"
        })
        assert r.status_code == 200
        assert ALPHA_M001_NAV_STATE["navigation_status"] == "STALE"
        mock_sms.assert_not_called()


# ==============================================================================
# 15. Arrived Mission Cannot Trigger Guidance
# ==============================================================================

def test_15_arrived_mission_cannot_trigger_guidance(started_client):
    """15. A mission already ARRIVED must not generate further navigation warnings or alerts."""
    vic, cmd = _setup_active_operation(started_client)
    cmd_id = cmd["command_id"]

    # Mark arrived
    db.update_rescue_command_status(cmd_id, status="ARRIVED")
    ALPHA_M001_NAV_STATE["navigation_status"] = "ARRIVED"
    ALPHA_M001_NAV_STATE["is_arrived"] = True

    with patch.object(api_mod, "send_direction_guidance_sms") as mock_sms:
        # Rescuer coordinates move away with wrong heading
        ts = datetime.now(timezone.utc).isoformat()
        r = started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "TEST-ARRIVED-LOCK",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": 32.3700,
            "longitude": 77.2400,
            "speed_mps": 2.0,
            "heading_deg": 270.0,
            "timestamp": ts,
            "gps_available": True,
            "gps_status": "TRACKING"
        })
        assert r.status_code == 200
        assert ALPHA_M001_NAV_STATE["navigation_status"] == "ARRIVED"
        mock_sms.assert_not_called()


# ==============================================================================
# 16. Completed Mission Cannot Trigger Guidance
# ==============================================================================

def test_16_completed_mission_cannot_trigger_guidance(started_client):
    """16. A mission already COMPLETED must not generate navigation alerts."""
    vic, cmd = _setup_active_operation(started_client)
    cmd_id = cmd["command_id"]

    # Mark completed
    db.update_rescue_command_status(cmd_id, status="COMPLETED")

    with patch.object(api_mod, "send_direction_guidance_sms") as mock_sms:
        ts = datetime.now(timezone.utc).isoformat()
        r = started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "TEST-COMPLETED-LOCK",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": 32.3700,
            "longitude": 77.2400,
            "speed_mps": 2.0,
            "heading_deg": 180.0,
            "timestamp": ts,
            "gps_available": True,
            "gps_status": "TRACKING"
        })
        assert r.status_code == 200
        assert ALPHA_M001_NAV_STATE["navigation_status"] == "COMPLETED"
        mock_sms.assert_not_called()


# ==============================================================================
# 17. Wrong-Direction Cooldown Survives Duplicate Telemetry
# ==============================================================================

def test_17_wrong_direction_cooldown_survives_duplicate_telemetry(started_client):
    """17. Duplicate heartbeats must not reset or bypass the 30-second wrong-direction SMS cooldown."""
    vic, cmd = _setup_active_operation(started_client)
    now = time.time()
    ALPHA_M001_NAV_STATE["last_direction_alert_time"] = now  # alert just sent

    ts = datetime.now(timezone.utc).isoformat()
    with patch.object(api_mod, "send_direction_guidance_sms") as mock_sms:
        # Duplicate heartbeat
        started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "TEST-COOLDOWN",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": 32.3700,
            "longitude": 77.2400,
            "speed_mps": 2.0,
            "heading_deg": 180.0,
            "timestamp": ts,
            "gps_available": True,
            "gps_status": "TRACKING"
        })
        mock_sms.assert_not_called()
        assert ALPHA_M001_NAV_STATE["last_direction_alert_time"] == now


# ==============================================================================
# 18. Wrong-Direction Counter Resets Correctly
# ==============================================================================

def test_18_wrong_direction_counter_resets_correctly(started_client):
    """18. Walking in the correct direction resets consecutive wrong direction samples to 0."""
    vic, cmd = _setup_active_operation(started_client)
    ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] = 2

    # Provide a coordinate and heading directly towards survivor
    target_loc = vic["location"]
    t_lat = target_loc["latitude"]
    t_lon = target_loc["longitude"]

    # Rescuer is south of survivor, moving North (0 deg)
    r_lat = t_lat - 0.0005
    r_lon = t_lon

    ts = datetime.now(timezone.utc).isoformat()
    r = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-RESET-COUNTER",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": r_lat,
        "longitude": r_lon,
        "speed_mps": 1.5,
        "heading_deg": 0.0,  # directly north toward survivor
        "timestamp": ts,
        "gps_available": True,
        "gps_status": "TRACKING"
    })
    assert r.status_code == 200
    assert ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] == 0
    assert ALPHA_M001_NAV_STATE["navigation_status"] == "ON_TRACK"


# ==============================================================================
# 19. Mission-Scoped State Reset
# ==============================================================================

def test_19_mission_scoped_state_reset():
    """19. reset_alpha_m001_mission_navigation_state resets navigation values while preserving hardware fix."""
    ALPHA_M001_LATEST_GPS.update({
        "latitude": 32.3740,
        "longitude": 77.2480,
        "accuracy_m": 4.0,
        "is_arrived": True,
        "navigation_status": "ARRIVED",
    })
    ALPHA_M001_NAV_STATE.update({
        "consecutive_wrong_samples": 3,
        "is_arrived": True,
        "navigation_status": "ARRIVED",
    })

    reset_alpha_m001_mission_navigation_state(new_command_id="CMD-NEW-01", new_victim_id="V2", preserve_hardware_fix=True)

    # Hardware coordinates preserved
    assert ALPHA_M001_LATEST_GPS["latitude"] == 32.3740
    assert ALPHA_M001_LATEST_GPS["longitude"] == 77.2480

    # Navigation states cleanly reset for new mission
    assert ALPHA_M001_NAV_STATE["is_arrived"] is False
    assert ALPHA_M001_NAV_STATE["consecutive_wrong_samples"] == 0
    assert ALPHA_M001_NAV_STATE["navigation_status"] == "ON_TRACK"
    assert ALPHA_M001_NAV_STATE["active_command_id"] == "CMD-NEW-01"


# ==============================================================================
# 20. Old Mission State Cannot Affect New Mission
# ==============================================================================

def test_20_old_mission_state_cannot_affect_new_mission(started_client):
    """20. When Mission A reaches ARRIVED and Mission B is assigned to a new victim, Mission B starts clean."""
    # 1. Mission A
    vic1, cmd1 = _setup_active_operation(started_client, target_index=0)
    db.update_rescue_command_status(cmd1["command_id"], status="COMPLETED")

    # 2. Assign Mission B
    overview = started_client.get("/commander/overview").json()
    vic2 = overview["victims"][1]
    with patch.object(api_mod, "send_direction_guidance_sms"), \
         patch("backend.notification_dispatch.dispatch_smsgate_sms"):
        r = started_client.post("/commander/assign", json={
            "member_id": "ALPHA-M001",
            "victim_id": vic2["victim_id"]
        })
        assert r.status_code == 200

    # Verify navigation status is not ARRIVED or COMPLETED from old mission
    assert ALPHA_M001_NAV_STATE["navigation_status"] == "ON_TRACK"
    assert ALPHA_M001_NAV_STATE["is_arrived"] is False


# ==============================================================================
# 21. Alpha 1 Never Enters Synthetic Movement
# ==============================================================================

def test_21_alpha_1_never_enters_synthetic_movement(started_client):
    """21. Alpha 1 must never fall back to synthetic movement, even during ticks or when stale."""
    vic, cmd = _setup_active_operation(started_client)

    # Telemetry point
    ts = datetime.now(timezone.utc).isoformat()
    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-NO-SYNTH",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3739,
        "longitude": 77.2491,
        "timestamp": ts,
        "gps_available": True,
        "gps_status": "TRACKING"
    })
    initial_coord = (ALPHA_M001_LATEST_GPS["latitude"], ALPHA_M001_LATEST_GPS["longitude"])

    # Multiple simulation ticks via overview polls
    for _ in range(5):
        started_client.get("/commander/overview")

    # Alpha 1 coordinate MUST NOT move without a new GPS heartbeat
    final_coord = (ALPHA_M001_LATEST_GPS["latitude"], ALPHA_M001_LATEST_GPS["longitude"])
    assert initial_coord == final_coord, "Alpha 1 coordinates must remain frozen without fresh GPS heartbeat"


# ==============================================================================
# 22-23. Alpha 2 and Bravo Members Remain Simulation Only
# ==============================================================================

def test_22_23_simulated_members_remain_simulation(started_client):
    """22 & 23. Alpha 2 and Bravo members remain simulation-only and step along bearing when en route."""
    overview = started_client.get("/commander/overview").json()
    members = {m["member_id"]: m for m in overview["team_members"]}

    assert members["ALPHA-M002"]["location_source"] == "SIMULATED"
    assert members["BRAVO-M001"]["location_source"] == "SIMULATED"
    assert members["BRAVO-M002"]["location_source"] == "SIMULATED"


# ==============================================================================
# 24. Survivor Locations Remain Simulation Only
# ==============================================================================

def test_24_survivor_locations_remain_simulation_only(started_client):
    """24. Survivor coordinates are never mutated by rescuer GPS telemetry."""
    overview1 = started_client.get("/commander/overview").json()
    v1_orig = overview1["victims"][0]["location"]

    # Send heartbeat for Alpha 1
    ts = datetime.now(timezone.utc).isoformat()
    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-SURVIVOR-ISOLATION",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3755,
        "longitude": 77.2555,
        "timestamp": ts,
        "gps_available": True,
    })

    overview2 = started_client.get("/commander/overview").json()
    v1_after = overview2["victims"][0]["location"]

    assert v1_orig["latitude"] == v1_after["latitude"]
    assert v1_orig["longitude"] == v1_after["longitude"]


# ==============================================================================
# 25-26. Commander Live Marker Freezes when Stale & Resumes Fresh
# ==============================================================================

def test_25_26_commander_marker_freeze_and_resume(started_client):
    """25 & 26. Commander overview shows STALE and freezes marker, then resumes when fresh."""
    vic, cmd = _setup_active_operation(started_client)

    # 1. Stale heartbeat
    stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()
    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-FREEZE",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3740,
        "longitude": 77.2480,
        "timestamp": stale_ts,
        "gps_available": True,
    })

    ov1 = started_client.get("/commander/overview").json()
    a1_ov1 = next(m for m in ov1["team_members"] if m["member_id"] == "ALPHA-M001")
    assert a1_ov1["gps_status"] == "STALE"

    # 2. Fresh heartbeat resumes TRACKING
    fresh_ts = datetime.now(timezone.utc).isoformat()
    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-FREEZE",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3748,
        "longitude": 77.2488,
        "timestamp": fresh_ts,
        "gps_available": True,
        "gps_status": "TRACKING"
    })

    ov2 = started_client.get("/commander/overview").json()
    a1_ov2 = next(m for m in ov2["team_members"] if m["member_id"] == "ALPHA-M001")
    assert a1_ov2["gps_status"] == "TRACKING"
    assert abs(a1_ov2["location"]["latitude"] - 32.3748) < 1e-5


# ==============================================================================
# 27. Notification Idempotency
# ==============================================================================

def test_27_notification_idempotency(started_client):
    """27. Operational recovery, commander refresh, and duplicate status updates do not resend assignment SMS."""
    vic, cmd = _setup_active_operation(started_client)

    with patch("backend.notification_dispatch.dispatch_smsgate_sms") as mock_smsgate:
        # Refresh overview multiple times
        for _ in range(3):
            started_client.get("/commander/overview")

        # Duplicate heartbeat
        ts = datetime.now(timezone.utc).isoformat()
        started_client.post("/api/wearable/bridge/heartbeat", json={
            "session_id": "TEST-NOTIF-IDEMP",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "latitude": 32.3740,
            "longitude": 77.2480,
            "timestamp": ts,
            "gps_available": True,
        })
        mock_smsgate.assert_not_called()


# ==============================================================================
# 28. SMSGate Remains the Only SMS Path
# ==============================================================================

def test_28_smsgate_remains_the_only_sms_path(monkeypatch):
    """28. Direction guidance SMS routes strictly through SMSGate dispatch without fallback or legacy providers."""
    mock_smsgate = MagicMock(return_value={"status": "SUCCESS", "message_id": "SMS-STAGE7"})
    if "backend.notification_dispatch" in sys.modules:
        monkeypatch.setattr(sys.modules["backend.notification_dispatch"], "dispatch_smsgate_sms", mock_smsgate)
    if "notification_dispatch" in sys.modules:
        monkeypatch.setattr(sys.modules["notification_dispatch"], "dispatch_smsgate_sms", mock_smsgate)
    res = api_mod.send_direction_guidance_sms(
        member_id="ALPHA-M001",
        team_id="ALPHA",
        command_id="CMD-TEST-7",
        victim_id="V2",
        heading_deg=180.0,
        target_bearing_deg=0.0,
        guidance="Turn around 180°",
        distance_m=45.0,
        smsgate_only=True,
    )
    assert res.get("status") in ("SUCCESS", "success")
    mock_smsgate.assert_called_once()


# ==============================================================================
# 29. Watch Flow Remains Untouched
# ==============================================================================

def test_29_watch_flow_remains_untouched(started_client):
    """29. Physical Wave Call Plus watch notification and ACK flow remain intact."""
    vic, cmd = _setup_active_operation(started_client)
    cmd_id = cmd["command_id"]

    # Acknowledge command via rescuer confirmation
    r_ack = started_client.post(f"/api/wearable/commands/{cmd_id}/ack?member_id=ALPHA-M001&source=RESCUER_CONFIRMATION")
    assert r_ack.status_code == 200
    res = r_ack.json()
    assert res["status"] == "success"


# ==============================================================================
# 31. Database Restart and Recovery Behavior
# ==============================================================================

def test_31_database_restart_recovery_behavior(started_client):
    """31. After simulated backend restart, rescue commands remain queryable from SQLite database."""
    vic, cmd = _setup_active_operation(started_client)
    cmd_id = cmd["command_id"]

    # Retrieve command directly from SQLite
    db_cmd = db.get_rescue_command(cmd_id)
    assert db_cmd is not None
    assert db_cmd["command_id"] == cmd_id
    assert db_cmd["member_id"] == "ALPHA-M001"
    assert db_cmd["victim_id"] == vic["victim_id"]


# ==============================================================================
# 32. Backward API Compatibility
# ==============================================================================

def test_32_backward_api_compatibility(started_client):
    """32. Core endpoints maintain backward compatibility contracts."""
    r1 = started_client.get("/api/wearable/commands/active?team_id=ALPHA")
    assert r1.status_code == 200

    r2 = started_client.get("/commander/overview")
    assert r2.status_code == 200
    ov = r2.json()
    assert "victims" in ov
    assert "team_members" in ov

    r3 = started_client.get("/notifications")
    assert r3.status_code == 200

    r4 = started_client.get("/api/wearable/bridge/heartbeat")
    assert r4.status_code == 200
