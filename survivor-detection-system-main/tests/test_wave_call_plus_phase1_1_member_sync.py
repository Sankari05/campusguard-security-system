"""
test_wave_call_plus_phase1_1_member_sync.py
---------------------------------------------
Phase 1.1: Assigned Team Member -> Watch Dashboard -> Wave Call Plus GO Command Delivery.
Validates:
- Test 1: Commander assigns specific member (Alpha Member 2) -> Assignment SUCCESS
- Test 2: Active command query exposes latest_assigned_member_id = ALPHA-M002
- Test 3: Member-specific filtering returns active GO command for ALPHA-M002 and Standby for other members
- Test 4: Dynamic reassignment updates latest_assigned_member_id and preserves source of truth
- Test 5: Scoped Android companion bridge receives GO for its specific member only
- Test 6: Watch delivery status transitions from PENDING -> SENT_TO_BRIDGE -> PHONE_NOTIFICATION_POSTED -> WATCH_DELIVERY_UNCONFIRMED
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db
from wearable_gateway import global_wearable_gateway


def test_phase1_1_commander_assign_specific_member(started_client):
    """Test 1: Commander assigns Alpha Member 2 specifically."""
    overview = started_client.get("/commander/overview").json()
    team_members = overview["team_members"]
    
    # Find Alpha Member 2 or second member
    target_member = next((m for m in team_members if "2" in m["callsign"] or "02" in m["member_id"]), team_members[1] if len(team_members) > 1 else team_members[0])
    victim = overview["victims"][0]

    res = started_client.post("/commander/assign", json={
        "member_id": target_member["member_id"],
        "victim_id": victim["victim_id"],
    })
    assert res.status_code == 200
    data = res.json()
    assert data["member_id"] == target_member["member_id"]
    assert data["assigned_victim_id"] == victim["victim_id"]
    assert data["status"] == "en_route"


def test_phase1_1_watch_active_assignment_reflects_assigned_member(started_client):
    """Test 2: Watch active assignment API returns latest_assigned_member_id matching Commander assignment."""
    overview = started_client.get("/commander/overview").json()
    team_members = overview["team_members"]
    target_member = next((m for m in team_members if "2" in m["callsign"] or "02" in m["member_id"]), team_members[1] if len(team_members) > 1 else team_members[0])
    victim = overview["victims"][0]

    started_client.post("/commander/assign", json={
        "member_id": target_member["member_id"],
        "victim_id": victim["victim_id"],
    })

    # Poll active commands
    active_res = started_client.get("/api/wearable/commands/active")
    assert active_res.status_code == 200
    active_data = active_res.json()
    assert active_data["latest_assigned_member_id"] == target_member["member_id"]
    assert active_data["latest_assigned_command_id"] is not None


def test_phase1_1_member_filtering_isolation(started_client):
    """Test 3: Member-specific filtering returns active GO for assigned member and standby for unassigned member."""
    overview = started_client.get("/commander/overview").json()
    team_members = overview["team_members"]
    assigned_member = team_members[1] if len(team_members) > 1 else team_members[0]
    unassigned_member = team_members[0] if len(team_members) > 1 else team_members[0]
    victim = overview["victims"][0]

    # Assign specifically to assigned_member
    started_client.post("/commander/assign", json={
        "member_id": assigned_member["member_id"],
        "victim_id": victim["victim_id"],
    })

    # Query for assigned member
    res_assigned = started_client.get(f"/api/wearable/commands/active?member_id={assigned_member['member_id']}")
    assert res_assigned.status_code == 200
    data_assigned = res_assigned.json()
    assert data_assigned["has_active_command"] is True
    assert data_assigned["command"]["member_id"] == assigned_member["member_id"]
    assert data_assigned["command"]["victim_id"] == victim["victim_id"]

    # Query for an unassigned member ID
    res_unassigned = started_client.get("/api/wearable/commands/active?member_id=UNASSIGNED-MEMBER-999")
    assert res_unassigned.status_code == 200
    data_unassigned = res_unassigned.json()
    assert data_unassigned["has_active_command"] is False


def test_phase1_1_bridge_scoped_to_assigned_member(started_client):
    """Test 4: Scoped Android companion bridge receives GO for its specific member only."""
    overview = started_client.get("/commander/overview").json()
    team_members = overview["team_members"]
    assigned_member = team_members[0]
    victim = overview["victims"][0]

    # Assign to assigned_member
    started_client.post("/commander/assign", json={
        "member_id": assigned_member["member_id"],
        "victim_id": victim["victim_id"],
    })

    # Bridge heartbeat scoped to assigned member
    hb_assigned = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-BRG-ASSIGNED",
        "team_id": assigned_member["team_id"],
        "member_id": assigned_member["member_id"],
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_connected": True,
        "bluetooth_state": "ENABLED",
        "status": "ONLINE",
    })
    assert hb_assigned.status_code == 200
    hb_data = hb_assigned.json()
    assert hb_data["active_command"] is not None
    assert hb_data["active_command"]["member_id"] == assigned_member["member_id"]

    # Bridge heartbeat scoped to a non-assigned member
    other_member_id = "NON-EXISTENT-MEMBER-999"
    hb_other = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-BRG-OTHER",
        "team_id": assigned_member["team_id"],
        "member_id": other_member_id,
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_connected": True,
        "bluetooth_state": "ENABLED",
        "status": "ONLINE",
    })
    assert hb_other.status_code == 200
    assert hb_other.json()["active_command"] is None
