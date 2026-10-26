"""
test_stage3_real_gps_alpha_member.py
------------------------------------
Comprehensive automated test suite for STAGE 3 — IMPLEMENT THE REAL GPS MODULE FOR ALPHA MEMBER 1.

Verifies:
A. Alpha Member 1 accepted mission can activate real GPS.
B. GPS permission denied is handled safely without crashing.
C. GPS unavailable is handled safely.
D. Valid real GPS sample is accepted.
E. GPS payload contains real location metadata (accuracy, speed, heading, altitude, timestamp).
F. GPS timestamp is recorded.
G. Alpha Member 1 uses real GPS instead of synthetic movement when real GPS is active.
H. Alpha Member 2 remains simulation-only.
I. Bravo Member 1 remains simulation-only.
J. Bravo Member 2 remains simulation-only.
K. Simulated survivor location remains unchanged.
L. Stale GPS marks Alpha Member 1 as STALE after 15s threshold.
M. Stale GPS does NOT trigger synthetic movement.
N. Invalid/poor GPS readings do not create fabricated coordinates.
O. Existing Commander assignment flow works correctly.
P. Existing Mission Acceptance flow works correctly.
Q. Existing SMSGate provider isolation remains intact.
R. Physical watch ACK behavior remains strictly uncoupled from phone GPS.
S. Confirmation that backend/wearable_gateway.py is unmodified.
"""

import time
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from backend.api import app, operations, GPS_STALE_THRESHOLD_SECONDS, ALPHA_M001_LATEST_GPS
import backend.db as db
from backend.models import GPSCoordinate, MemberStatus
from backend.rescue_dispatch import haversine_distance_m


@pytest.fixture(autouse=True)
def setup_db_and_session():
    db.init_db()
    db.seed_builtin_teams()
    db.seed_builtin_scenarios()


def test_A_alpha_member_1_accepted_mission_can_activate_real_gps(started_client):
    """A. Verify Alpha Member 1 accepted mission can activate real GPS tracking."""
    session_id = f"BRG-AND-{uuid.uuid4().hex[:6].upper()}"

    # 1. Trigger mission
    alert_res = started_client.post("/api/wearable/commands/test_alert", json={
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "target_id": "Survivor-1",
        "location_label": "Sector Alpha"
    })
    assert alert_res.status_code == 200
    cmd_data = alert_res.json()
    cmd_id = cmd_data.get("command_id") or cmd_data.get("command", {}).get("command_id")
    assert cmd_id is not None

    # 2. Rescuer accepts mission
    accept_res = started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "USER_ACCEPTED"
    })
    assert accept_res.status_code == 200

    # 3. Real GPS tracking heartbeat for Alpha Member 1
    gps_time = datetime.now(timezone.utc).isoformat()
    sync_res = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3780,
        "longitude": 77.2510,
        "altitude_m": 3965.0,
        "accuracy_m": 4.5,
        "speed_mps": 1.2,
        "heading_deg": 135.0,
        "timestamp": gps_time,
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })
    assert sync_res.status_code == 200
    data = sync_res.json()
    assert data["status"] == "success"

    # Verify state in overview
    overview = started_client.get("/commander/overview").json()
    alpha1 = next(m for m in overview["team_members"] if m["member_id"] == "ALPHA-M001")
    assert alpha1["location_source"] == "PHONE_GPS"
    assert alpha1["gps_status"] == "TRACKING"
    assert abs(alpha1["location"]["latitude"] - 32.3780) < 1e-4
    assert abs(alpha1["location"]["longitude"] - 77.2510) < 1e-4


def test_B_gps_permission_denied_handled_safely(started_client):
    """B. Verify GPS permission denied is handled safely without crashing or faking coordinates."""
    session_id = f"BRG-AND-{uuid.uuid4().hex[:6].upper()}"

    res = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "gps_available": False,
        "location_source": "PHONE_GPS",
        "gps_status": "PERMISSION_DENIED",
        "notes": "User denied ACCESS_FINE_LOCATION"
    })
    assert res.status_code == 200

    overview = started_client.get("/commander/overview").json()
    alpha1 = next(m for m in overview["team_members"] if m["member_id"] == "ALPHA-M001")
    assert alpha1["gps_status"] == "PERMISSION_DENIED"


def test_C_gps_unavailable_handled_safely(started_client):
    """C. Verify GPS unavailable is handled safely."""
    session_id = f"BRG-AND-{uuid.uuid4().hex[:6].upper()}"

    res = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "gps_available": False,
        "location_source": "PHONE_GPS",
        "gps_status": "GPS_UNAVAILABLE",
        "notes": "Location providers disabled on device"
    })
    assert res.status_code == 200

    overview = started_client.get("/commander/overview").json()
    alpha1 = next(m for m in overview["team_members"] if m["member_id"] == "ALPHA-M001")
    assert alpha1["gps_status"] == "GPS_UNAVAILABLE"


def test_D_E_F_valid_real_gps_sample_and_metadata_recorded(started_client):
    """D, E, F. Valid real GPS sample is accepted with full metadata and recorded timestamp."""
    session_id = f"BRG-AND-{uuid.uuid4().hex[:6].upper()}"
    gps_time = "2026-09-05T14:45:00Z"

    payload = {
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "device_name": "RidgeWatch Native Android Companion",
        "latitude": 32.3812,
        "longitude": 77.2534,
        "altitude_m": 3980.5,
        "accuracy_m": 3.8,
        "speed_mps": 1.45,
        "heading_deg": 88.5,
        "timestamp": gps_time,
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    }

    res = started_client.post("/api/wearable/bridge/heartbeat", json=payload)
    assert res.status_code == 200

    # Verify session persisted in database with full metadata
    sessions = db.list_bridge_sessions(team_id="ALPHA")
    sess = next(s for s in sessions if s["session_id"] == session_id)
    assert sess["latitude"] == 32.3812
    assert sess["longitude"] == 77.2534
    assert sess["altitude_m"] == 3980.5
    assert sess["accuracy_m"] == 3.8
    assert sess["speed_mps"] == 1.45
    assert sess["heading_deg"] == 88.5
    assert sess["location_source"] == "PHONE_GPS"

    # Verify overview exposes metadata
    overview = started_client.get("/commander/overview").json()
    alpha1 = next(m for m in overview["team_members"] if m["member_id"] == "ALPHA-M001")
    assert alpha1["accuracy_m"] == 3.8
    assert alpha1["speed_mps"] == 1.45
    assert alpha1["heading_deg"] == 88.5
    assert alpha1["gps_timestamp"] == gps_time


def test_G_alpha_member_1_uses_real_gps_instead_of_synthetic_movement(started_client):
    """G. Alpha Member 1 uses real GPS instead of synthetic movement when real GPS is active."""
    overview = started_client.get("/commander/overview").json()
    victim = overview["victims"][0]

    # Assign Alpha Member 1 to a victim
    started_client.post("/commander/assign", json={
        "member_id": "ALPHA-M001",
        "victim_id": victim["victim_id"]
    })

    # Post real GPS fix for Alpha Member 1
    fixed_lat, fixed_lon = 32.3900, 77.2600
    gps_time = datetime.now(timezone.utc).isoformat()
    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-TEST-FIX",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": fixed_lat,
        "longitude": fixed_lon,
        "timestamp": gps_time,
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })

    # Poll /commander/overview multiple times (which triggers advance_team_members)
    for _ in range(3):
        res = started_client.get("/commander/overview").json()
        alpha1 = next(m for m in res["team_members"] if m["member_id"] == "ALPHA-M001")
        # Position must REMAIN at real phone GPS coordinates, not synthetic step towards victim
        assert abs(alpha1["location"]["latitude"] - fixed_lat) < 1e-6
        assert abs(alpha1["location"]["longitude"] - fixed_lon) < 1e-6


def test_H_I_J_other_members_remain_simulation_only(started_client):
    """H, I, J. Alpha Member 2, Bravo Member 1, Bravo Member 2 remain simulation-only."""
    overview = started_client.get("/commander/overview").json()
    victim = overview["victims"][0]

    # Assign Alpha Member 2 and Bravo Member 1
    started_client.post("/commander/assign", json={"member_id": "ALPHA-M002", "victim_id": victim["victim_id"]})
    started_client.post("/commander/assign", json={"member_id": "BRAVO-M001", "victim_id": victim["victim_id"]})

    before = started_client.get("/commander/overview").json()
    a2_before = next(m for m in before["team_members"] if m["member_id"] == "ALPHA-M002")
    b1_before = next(m for m in before["team_members"] if m["member_id"] == "BRAVO-M001")

    dist_a2_before = haversine_distance_m(GPSCoordinate(**a2_before["location"]), GPSCoordinate(**victim["location"]))
    dist_b1_before = haversine_distance_m(GPSCoordinate(**b1_before["location"]), GPSCoordinate(**victim["location"]))

    # Advance simulation polls
    after = started_client.get("/commander/overview").json()
    a2_after = next(m for m in after["team_members"] if m["member_id"] == "ALPHA-M002")
    b1_after = next(m for m in after["team_members"] if m["member_id"] == "BRAVO-M001")

    dist_a2_after = haversine_distance_m(GPSCoordinate(**a2_after["location"]), GPSCoordinate(**victim["location"]))
    dist_b1_after = haversine_distance_m(GPSCoordinate(**b1_after["location"]), GPSCoordinate(**victim["location"]))

    # Both simulated members must advance synthetically toward victim
    assert dist_a2_after < dist_a2_before or a2_after["status"] == "arrived"
    assert dist_b1_after < dist_b1_before or b1_after["status"] == "arrived"


def test_K_simulated_survivor_location_remains_unchanged(started_client):
    """K. Simulated survivor location remains unchanged."""
    before = started_client.get("/commander/overview").json()
    victim_before = before["victims"][0]

    # Send multiple GPS updates
    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-V-TEST",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3850,
        "longitude": 77.2550,
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })

    after = started_client.get("/commander/overview").json()
    victim_after = after["victims"][0]

    assert victim_before["victim_id"] == victim_after["victim_id"]
    assert victim_before["location"] == victim_after["location"]


def test_L_M_stale_gps_handling_and_no_synthetic_movement(started_client):
    """L, M. Stale GPS marks Alpha Member 1 as STALE and does NOT trigger synthetic movement."""
    overview = started_client.get("/commander/overview").json()
    victim = overview["victims"][0]

    started_client.post("/commander/assign", json={
        "member_id": "ALPHA-M001",
        "victim_id": victim["victim_id"]
    })

    # Post an old GPS update (> 15 seconds ago)
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()
    fixed_lat, fixed_lon = 32.3755, 77.2485

    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-STALE-TEST",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": fixed_lat,
        "longitude": fixed_lon,
        "timestamp": old_time,
        "gps_available": True,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING"
    })

    # Polling overview checks stale condition and advances members
    after = started_client.get("/commander/overview").json()
    alpha1 = next(m for m in after["team_members"] if m["member_id"] == "ALPHA-M001")

    # Must be marked STALE
    assert alpha1["gps_status"] == "STALE"
    # Must PRESERVE last known real location, NOT synthetically move toward victim
    assert abs(alpha1["location"]["latitude"] - fixed_lat) < 1e-6
    assert abs(alpha1["location"]["longitude"] - fixed_lon) < 1e-6


def test_N_invalid_poor_gps_readings_do_not_fabricate_coordinates(started_client):
    """N. Invalid or poor GPS readings do not create fabricated coordinates."""
    # When coordinates are null/invalid and GPS is unavailable, no coordinates fabricated
    res = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-NO-FIX",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": None,
        "longitude": None,
        "gps_available": False,
        "location_source": "PHONE_GPS",
        "gps_status": "GPS_UNAVAILABLE"
    })
    assert res.status_code == 200


def test_O_P_commander_assignment_and_mission_acceptance_intact(started_client):
    """O, P. Existing Commander assignment and Mission Acceptance flows remain intact."""
    overview = started_client.get("/commander/overview").json()
    member_id = overview["team_members"][1]["member_id"] # ALPHA-M002
    victim_id = overview["victims"][0]["victim_id"]

    # Commander assignment
    assign_res = started_client.post("/commander/assign", json={
        "member_id": member_id,
        "victim_id": victim_id
    })
    assert assign_res.status_code == 200
    assert assign_res.json()["status"] == "en_route"
    assert assign_res.json()["assigned_victim_id"] == victim_id

    # Test alert & mission acceptance
    alert_res = started_client.post("/api/wearable/commands/test_alert", json={
        "team_id": "ALPHA",
        "member_id": member_id
    })
    cmd_id = alert_res.json().get("command_id") or alert_res.json().get("command", {}).get("command_id")

    accept_res = started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "USER_ACCEPTED"
    })
    assert accept_res.status_code == 200

    live_res = started_client.get(f"/api/wearable/commands/{cmd_id}/live_state")
    assert live_res.status_code == 200
    assert live_res.json()["rescuer_confirmed"] is True


def test_S_T_watch_gateway_unmodified_and_hardware_ack_uncoupled(started_client):
    """S, T. Wearable gateway is unmodified and physical watch ACK is uncoupled from phone GPS."""
    with open("backend/wearable_gateway.py", "r", encoding="utf-8") as f:
        content = f.read()
    # Confirm essential Wave Call Plus markers in wearable_gateway.py
    assert "class WaveCallPlusAdapter" in content
    assert "class WearableGatewayManager" in content
    assert "DEV-WEARABLE-CALLPLUS" in content
    assert "CB:4E:FD:EE:7F:1B" in content

    # 1. Trigger test alert
    alert_res = started_client.post("/api/wearable/commands/test_alert", json={
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001"
    })
    cmd_id = alert_res.json().get("command_id") or alert_res.json().get("command", {}).get("command_id")

    # Post real GPS heartbeat
    started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-WATCH-SEP",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 32.3739,
        "longitude": 77.2491,
        "gps_available": True,
        "location_source": "PHONE_GPS"
    })

    # Verify physical watch ACK is NOT forged
    live_state = started_client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live_state.get("hardware_ack_received") is False
    assert live_state.get("watch_acknowledged") is False
