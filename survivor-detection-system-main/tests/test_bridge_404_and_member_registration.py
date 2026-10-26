"""
test_bridge_404_and_member_registration.py
-------------------------------------------
Tests to verify:
1. All bridge / wearable endpoints exist and return 200 (no 404s for /api/wearable/devices, /watch, /api/bridge/status, etc.)
2. Member registration in bridge heartbeat (explicit member_id stored and bound)
3. BLE watch connection state synchronization (honest true/false tracking)
4. Safe targeted rescue command routing with member resolution
"""

import sys
import os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import db
from wearable_gateway import global_wearable_gateway


def test_wearable_devices_endpoint_exists(started_client):
    """Verify GET /api/wearable/devices and /api/devices return 200 with device list."""
    res1 = started_client.get("/api/wearable/devices")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "success"
    assert len(data1["devices"]) > 0
    dev = data1["devices"][0]
    assert dev["device_id"] == "DEV-WEARABLE-CALLPLUS"

    res2 = started_client.get("/api/devices")
    assert res2.status_code == 200
    assert res2.json()["status"] == "success"


def test_wearable_device_by_id_endpoint(started_client):
    """Verify GET /api/wearable/devices/{device_id} returns 200."""
    res = started_client.get("/api/wearable/devices/DEV-WEARABLE-CALLPLUS")
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert res.json()["device"]["device_id"] == "DEV-WEARABLE-CALLPLUS"


def test_watch_endpoint_graceful_fallbacks(started_client):
    """Verify /watch, /watch/, /watch/null, and /watch/ALPHA-M001 never return unhandled 404."""
    res_default = started_client.get("/watch")
    assert res_default.status_code == 200
    assert "status" in res_default.json()

    res_slash = started_client.get("/watch/")
    assert res_slash.status_code == 200

    res_null = started_client.get("/watch/null")
    assert res_null.status_code == 200

    res_undef = started_client.get("/watch/undefined")
    assert res_undef.status_code == 200

    res_valid = started_client.get("/watch/ALPHA-M001")
    assert res_valid.status_code == 200
    assert res_valid.json()["member_id"] == "ALPHA-M001"


def test_bridge_status_aliases(started_client):
    """Verify /api/bridge/status and /api/wearable/bridge/status both return 200."""
    res1 = started_client.get("/api/wearable/bridge/status")
    assert res1.status_code == 200

    res2 = started_client.get("/api/bridge/status")
    assert res2.status_code == 200


def test_bridge_heartbeat_member_and_ble_sync(started_client):
    """Verify bridge heartbeat registers explicit member_id and syncs BLE connection state honestly."""
    # 1. Heartbeat with watch_connected = False
    hb1 = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-T01PMR3",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "watch_connected": False,
        "bluetooth_state": "ENABLED",
        "latitude": 9.4821,
        "longitude": 78.0057,
        "location_source": "PHONE_GPS",
    })
    assert hb1.status_code == 200
    data1 = hb1.json()
    assert data1["session"]["session_id"] == "BRG-T01PMR3"
    assert data1["session"]["team_id"] == "ALPHA"
    assert data1["session"]["member_id"] == "ALPHA-M001"
    assert data1["session"]["watch_connected"] == 0

    # Verify device status reflects DISCONNECTED
    dev_res1 = started_client.get("/api/wearable/devices")
    dev1 = next(d for d in dev_res1.json()["devices"] if d["device_id"] == "DEV-WEARABLE-CALLPLUS")
    assert dev1["connection_status"] == "DISCONNECTED"

    # 2. Heartbeat with watch_connected = True (Real BLE paired)
    hb2 = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-T01PMR3",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "watch_connected": True,
        "bluetooth_state": "ENABLED",
        "latitude": 9.4821,
        "longitude": 78.0057,
        "location_source": "PHONE_GPS",
    })
    assert hb2.status_code == 200
    data2 = hb2.json()
    assert data2["session"]["watch_connected"] == 1

    dev_res2 = started_client.get("/api/wearable/devices")
    dev2 = next(d for d in dev_res2.json()["devices"] if d["device_id"] == "DEV-WEARABLE-CALLPLUS")
    assert dev2["connection_status"] == "CONNECTED"


def test_commander_assign_flow_and_bridge_dispatch(started_client):
    """Verify Commander assigns member, resolves watch, and delivers command to bridge."""
    overview = started_client.get("/commander/overview").json()
    member = overview["team_members"][0]
    victim = overview["victims"][0]

    # Assign
    res = started_client.post("/commander/assign", json={
        "member_id": member["member_id"],
        "victim_id": victim["victim_id"],
    })
    assert res.status_code == 200

    # Bridge heartbeat for this member gets the command
    hb = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-T01PMR3",
        "team_id": member["team_id"],
        "member_id": member["member_id"],
        "watch_connected": True,
    }).json()

    assert hb["active_command"] is not None
    cmd = hb["active_command"]
    assert cmd["member_id"] == member["member_id"]
    assert cmd["victim_id"] == victim["victim_id"]
    assert cmd["command_type"] == "GO"
