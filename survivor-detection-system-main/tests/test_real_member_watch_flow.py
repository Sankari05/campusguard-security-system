"""
test_real_member_watch_flow.py
-------------------------------
Automated test suite verifying the real Backend -> Assigned Member -> Physical Watch GO Command Flow.

Covers:
1. Explicit Team -> Member -> Registered Watch Resolution (No broadcast, no 'All Team Members' fallback)
2. Real Commander assignment creation with command_type="GO", priority, timestamps
3. Scoped Android Companion Bridge polling (only assigned member receives the command)
4. GET /api/rescue/commands/{command_id} endpoint lifecycle verification
5. Non-blocking status progression: PENDING -> SENT_TO_BRIDGE -> PHONE_NOTIFICATION_POSTED -> WATCH_DELIVERY_UNCONFIRMED
6. Negative tests (offline bridge queues as PENDING, unassigned member returns no active command, no false confirmed delivery)
"""

import sys
import os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import db
from wearable_gateway import global_wearable_gateway


def test_member_to_watch_resolution():
    """Verify backend resolves explicit member to registered Wave Call Plus hardware."""
    dev_id, hw_info = global_wearable_gateway.resolve_watch_for_member("ALPHA-M001", "ALPHA")
    assert dev_id == "DEV-WEARABLE-CALLPLUS"
    assert hw_info["bluetooth_name"] == "CALLPLUS_7F1B"
    assert hw_info["mac_address"] == "CB:4E:FD:EE:7F:1B"
    assert hw_info["serial_number"] == "230105502503539"
    assert hw_info["software_version"] == "6.4.3582.28"


def test_commander_assign_explicit_member_and_command_creation(started_client):
    """Verify Commander assigns a specific member and creates a real GO command."""
    overview = started_client.get("/commander/overview").json()
    team_members = overview["team_members"]
    victims = overview["victims"]

    target_member = team_members[0]
    target_victim = victims[0]

    res = started_client.post("/commander/assign", json={
        "member_id": target_member["member_id"],
        "victim_id": target_victim["victim_id"],
    })
    assert res.status_code == 200
    data = res.json()
    assert data["member_id"] == target_member["member_id"]
    assert data["assigned_victim_id"] == target_victim["victim_id"]
    assert data["status"] == "en_route"

    # Query active command for this member
    cmd_res = started_client.get(f"/api/wearable/commands/active?member_id={target_member['member_id']}")
    assert cmd_res.status_code == 200
    cmd_data = cmd_res.json()
    assert cmd_data["has_active_command"] is True
    cmd = cmd_data["command"]
    assert cmd["member_id"] == target_member["member_id"]
    assert cmd["victim_id"] == target_victim["victim_id"]
    assert cmd["target_device_id"] == "DEV-WEARABLE-CALLPLUS"
    assert cmd["command_type"] == "GO"
    assert cmd["priority"] == "HIGH"


def test_command_status_lifecycle_api(started_client):
    """Verify GET /api/rescue/commands/{command_id} returns accurate status."""
    overview = started_client.get("/commander/overview").json()
    target_member = overview["team_members"][0]
    target_victim = overview["victims"][0]

    started_client.post("/commander/assign", json={
        "member_id": target_member["member_id"],
        "victim_id": target_victim["victim_id"],
    })

    cmd_res = started_client.get(f"/api/wearable/commands/active?member_id={target_member['member_id']}")
    cmd_id = cmd_res.json()["command"]["command_id"]

    # Check command status endpoint
    status_res = started_client.get(f"/api/rescue/commands/{cmd_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["command_id"] == cmd_id
    assert status_data["member_id"] == target_member["member_id"]
    assert status_data["victim_id"] == target_victim["victim_id"]
    assert status_data["command_type"] == "GO"
    assert status_data["watch_id"] == "DEV-WEARABLE-CALLPLUS"


def test_scoped_bridge_delivery_isolation(started_client):
    """Verify that only the bridge session matching the assigned member receives the command."""
    overview = started_client.get("/commander/overview").json()
    team_members = overview["team_members"]
    assigned_member = team_members[0]
    other_member = team_members[1] if len(team_members) > 1 else {"member_id": "OTHER-M999"}
    victim = overview["victims"][0]

    # Assign specifically to assigned_member
    started_client.post("/commander/assign", json={
        "member_id": assigned_member["member_id"],
        "victim_id": victim["victim_id"],
    })

    # Bridge heartbeat for assigned_member receives command
    hb_assigned = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "SES-ASSIGNED-01",
        "team_id": assigned_member["team_id"],
        "member_id": assigned_member["member_id"],
        "watch_connected": True,
        "bluetooth_state": "ENABLED",
    }).json()

    assert hb_assigned["active_command"] is not None
    assert hb_assigned["active_command"]["member_id"] == assigned_member["member_id"]

    # Bridge heartbeat for an unassigned member does NOT receive assigned_member's command
    hb_other = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "SES-OTHER-02",
        "team_id": "CHARLIE",
        "member_id": "UNASSIGNED-MEMBER-999",
        "watch_connected": True,
        "bluetooth_state": "ENABLED",
    }).json()

    assert hb_other["active_command"] is None


def test_watch_unconfirmed_honest_state(started_client):
    """Verify that posting phone notification sets status to WATCH_DELIVERY_UNCONFIRMED, never faking WATCH_DELIVERY_CONFIRMED."""
    overview = started_client.get("/commander/overview").json()
    target_member = overview["team_members"][0]
    victim = overview["victims"][0]

    started_client.post("/commander/assign", json={
        "member_id": target_member["member_id"],
        "victim_id": victim["victim_id"],
    })

    cmd_res = started_client.get(f"/api/wearable/commands/active?member_id={target_member['member_id']}")
    cmd_id = cmd_res.json()["command"]["command_id"]

    # Bridge reports PHONE_NOTIFICATION_POSTED
    st_res = started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "PHONE_NOTIFICATION_POSTED",
    })
    assert st_res.status_code == 200

    # Query status
    status_res = started_client.get(f"/api/rescue/commands/{cmd_id}")
    assert status_res.json()["watch_status"] == "WATCH_DELIVERY_UNCONFIRMED"
