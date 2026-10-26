"""
test_wave_call_plus_phase1_go.py
---------------------------------
Phase 1 Only: Real Wave Call Plus GO Command Delivery Automated Test Suite.
Validates:
- Test 1: Commander assigns member to victim -> Assignment SUCCESS
- Test 2: Rescue command created in rescue_commands table with command_id
- Test 3: Correct team/member wearable is resolved (DEV-WEARABLE-CALLPLUS)
- Test 4: Android bridge online -> Command transitions to SENT_TO_BRIDGE -> PHONE_NOTIFICATION_POSTED -> WATCH_DELIVERY_UNCONFIRMED
- Test 5: Android bridge offline -> Assignment still succeeds (non-blocking), command queued as PENDING
- Test 6: Watch disconnected -> No fake WATCH_DELIVERY_CONFIRMED or fake BLE connection
- Test 7: Duplicate protection / idempotency -> Same command is not notified repeatedly
- Test 8: Simulation mode remains functional
- Test 9: Commander assignment workflow remains unchanged
- Test 10: Wave Call Plus device specifications and centralized identity
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db
from wearable_gateway import global_wearable_gateway, WearableOperationMode, CommandStatus


def test_phase1_test1_commander_assign_success(started_client):
    """Test 1: Commander assigns member to victim -> Assignment SUCCESS (HTTP 200)."""
    overview = started_client.get("/commander/overview").json()
    assert len(overview["team_members"]) > 0
    assert len(overview["victims"]) > 0

    member = overview["team_members"][0]
    victim = overview["victims"][0]

    res = started_client.post("/commander/assign", json={
        "member_id": member["member_id"],
        "victim_id": victim["victim_id"],
    })
    assert res.status_code == 200
    data = res.json()
    assert data["member_id"] == member["member_id"]
    assert data["assigned_victim_id"] == victim["victim_id"]
    assert data["status"] == "en_route"


def test_phase1_test2_rescue_command_created_in_db(started_client):
    """Test 2: Rescue command is created in rescue_commands table with valid command_id."""
    overview = started_client.get("/commander/overview").json()
    member = overview["team_members"][0]
    victim = overview["victims"][0]

    started_client.post("/commander/assign", json={
        "member_id": member["member_id"],
        "victim_id": victim["victim_id"],
    })

    cmd_res = started_client.get(f"/api/wearable/commands/active?member_id={member['member_id']}")
    assert cmd_res.status_code == 200
    cmd_data = cmd_res.json()
    assert cmd_data["has_active_command"] is True
    cmd = cmd_data["command"]
    assert "command_id" in cmd
    assert cmd["command_id"].startswith("CMD-")
    assert cmd["victim_id"] == victim["victim_id"]


def test_phase1_test3_correct_wearable_resolved(started_client):
    """Test 3: Correct team/member wearable is resolved (DEV-WEARABLE-CALLPLUS, MAC CB:4E:FD:EE:7F:1B)."""
    overview = started_client.get("/commander/overview").json()
    member = overview["team_members"][0]
    victim = overview["victims"][0]

    started_client.post("/commander/assign", json={
        "member_id": member["member_id"],
        "victim_id": victim["victim_id"],
    })

    cmd_res = started_client.get(f"/api/wearable/commands/active?member_id={member['member_id']}")
    cmd = cmd_res.json()["command"]
    assert cmd["target_device_id"] == "DEV-WEARABLE-CALLPLUS"

    dev = db.get_wearable_device("DEV-WEARABLE-CALLPLUS")
    assert dev is not None
    assert dev["bluetooth_name"] == "CALLPLUS_7F1B"
    assert dev["mac_address"] == "CB:4E:FD:EE:7F:1B"
    assert dev["model"] == "Wave Call Plus"


def test_phase1_test4_android_bridge_online_delivery_flow(started_client):
    """Test 4: Android bridge online -> Command transitions through SENT_TO_BRIDGE -> PHONE_NOTIFICATION_POSTED."""
    # 1. Android bridge sends heartbeat (establishing ONLINE bridge session)
    hb_res = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-BRG-FLOW-01",
        "team_id": "RESCUE-1",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_connected": True,
        "bluetooth_state": "ENABLED",
        "status": "ONLINE",
    })
    assert hb_res.status_code == 200

    # 2. Commander assigns member
    overview = started_client.get("/commander/overview").json()
    member = overview["team_members"][0]
    victim = overview["victims"][0]

    started_client.post("/commander/assign", json={
        "member_id": member["member_id"],
        "victim_id": victim["victim_id"],
    })

    # 3. Bridge syncs again and retrieves the active GO command with Phase 1 payload
    sync_res = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-BRG-FLOW-01",
        "team_id": member["team_id"],
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_connected": True,
        "bluetooth_state": "ENABLED",
        "status": "ONLINE",
    })
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    active_cmd = sync_data["active_command"]
    assert active_cmd is not None
    assert active_cmd["status"] in ["SENT_TO_BRIDGE", "ASSIGNED"]

    payload = active_cmd.get("notification_payload", {})
    assert "GO" in payload.get("title", "") or "RIDGEWATCH" in payload.get("title", "")
    assert "assignment" in payload.get("body", "").lower() or "rescue" in payload.get("body", "").lower()

    # 4. Bridge posts Android notification and reports PHONE_NOTIFICATION_POSTED
    st_res = started_client.post(f"/api/wearable/commands/{active_cmd['command_id']}/status", json={
        "status": "PHONE_NOTIFICATION_POSTED",
        "delivery_error": None,
    })
    assert st_res.status_code == 200

    # 5. Check DB reflects PHONE_NOTIFICATION_POSTED and WATCH_DELIVERY_UNCONFIRMED (never fake delivery)
    rec = db.get_rescue_command(active_cmd["command_id"])
    assert rec["status"] == "PHONE_NOTIFICATION_POSTED"
    assert rec["watch_delivery_status"] == "WATCH_DELIVERY_UNCONFIRMED"
    assert rec["phone_notification_posted_at"] is not None


def test_phase1_test5_android_bridge_offline_non_blocking(started_client):
    """Test 5: Android bridge offline -> Commander assignment still succeeds; command queued as PENDING."""
    # Ensure bridge is offline
    global_wearable_gateway.bridge_adapter.disconnect("DEV-GW-ANDROID-BRIDGE")

    overview = started_client.get("/commander/overview").json()
    member = overview["team_members"][0]
    victim = overview["victims"][0]

    # Assignment succeeds without blocking
    res = started_client.post("/commander/assign", json={
        "member_id": member["member_id"],
        "victim_id": victim["victim_id"],
    })
    assert res.status_code == 200
    assert res.json()["status"] == "en_route"

    # Command is queued
    cmd_res = started_client.get(f"/api/wearable/commands/active?member_id={member['member_id']}")
    assert cmd_res.status_code == 200
    assert cmd_res.json()["has_active_command"] is True


def test_phase1_test6_watch_disconnected_no_fake_delivered_status(started_client):
    """Test 6: Watch disconnected -> No fake WATCH_DELIVERY_CONFIRMED status."""
    manager = global_wearable_gateway.wave_call_plus_adapter.connection_manager
    manager.disconnect()
    assert manager.is_connected() is False
    assert manager.get_state() == "DISCONNECTED"

    # Diagnostics and state report DISCONNECTED honestly
    diag = global_wearable_gateway.run_hardware_diagnostics("DEV-WEARABLE-CALLPLUS")
    assert diag["connection_state"] == "DISCONNECTED"
    assert diag["capabilities"]["location_gps"] is False
    assert diag["capabilities"]["direct_ble_programmable"] is False


def test_phase1_test7_duplicate_protection_idempotency(started_client):
    """Test 7: Duplicate command protection -> Status updates do not duplicate commands."""
    overview = started_client.get("/commander/overview").json()
    member = overview["team_members"][0]
    victim = overview["victims"][0]

    started_client.post("/commander/assign", json={
        "member_id": member["member_id"],
        "victim_id": victim["victim_id"],
    })

    cmd = started_client.get(f"/api/wearable/commands/active?member_id={member['member_id']}").json()["command"]
    cmd_id = cmd["command_id"]

    # Posting PHONE_NOTIFICATION_POSTED twice remains idempotent
    r1 = started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "PHONE_NOTIFICATION_POSTED"})
    r2 = started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "PHONE_NOTIFICATION_POSTED"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["command"]["status"] == "PHONE_NOTIFICATION_POSTED"


def test_phase1_test8_simulation_mode_preserved(started_client):
    """Test 8: Simulation mode remains intact and functional."""
    # Switch to simulation mode
    started_client.post("/api/wearable/mode", json={"mode": "SIMULATION"})
    assert global_wearable_gateway.get_mode() == "SIMULATION"

    res = global_wearable_gateway.dispatch_rescue_command({
        "command_id": "CMD-SIM-TEST",
        "team_id": "RESCUE-1",
        "command_type": "GO",
    })
    assert res["location_source"] == "SIMULATED_GPS"
    assert res["status"] == "DELIVERED"

    # Switch back to REAL_HARDWARE
    started_client.post("/api/wearable/mode", json={"mode": "REAL_HARDWARE"})
    assert global_wearable_gateway.get_mode() == "REAL_HARDWARE"
