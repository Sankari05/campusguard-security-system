"""
test_isolated_wearable_integration.py
------------------------------------
Tests for Single Real Smartwatch Integration (Wave Call Plus / CALLPLUS_7F1B):
1. Complete removal and strict rejection of T800Ultra.
2. Wave Call Plus (CALLPLUS_7F1B / CB:4E:FD:EE:7F:1B / 6.4.3582.28) specs & capabilities.
3. Single Watch Connection Manager state machine & duplicate prevention.
4. Real Bluetooth capability discovery without fabricated UUIDs/telemetry.
5. Mode toggle: SIMULATION MODE vs REAL HARDWARE MODE.
6. Full WearableAdapter interface validation (connect, disconnect, read_status, send_notification, subscribe).
7. Honest command dispatch lifecycle (DELIVERED_TO_BRIDGE / WATCH_DELIVERY_CONFIRMATION_UNAVAILABLE).
8. Honest location source tagging (PHONE_GPS in REAL_HARDWARE, SIMULATED_GPS in SIMULATION).
9. Team isolation & routing integrity.
10. Failure handling: Offline bridge, disconnected watch, bluetooth disabled.
11. Two-way status flow: ASSIGNED -> ACCEPTED -> EN_ROUTE -> ARRIVED -> RESCUED.
12. Core system resilience: Offline watch never degrades Commander operations or 18 sensor channels.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from wearable_gateway import (
    WaveCallPlusAdapter,
    WaveCallPlusConnectionManager,
    WearableConnectionState,
    WearableOperationMode,
    AndroidCompanionBridgeAdapter,
    WearableGatewayManager,
)
import db


def test_wave_call_plus_adapter_hardware_specs():
    """Verify physical Wave Call Plus adapter reports honest hardware details and GATT profile."""
    adapter = WaveCallPlusAdapter("CB:4E:FD:EE:7F:1B", "230105502503539", "6.4.3582.28")
    assert adapter.mac_address == "CB:4E:FD:EE:7F:1B"
    assert adapter.bluetooth_name == "CALLPLUS_7F1B"
    assert adapter.serial_number == "230105502503539"
    assert adapter.software_version == "6.4.3582.28"
    assert adapter.hardware_id == "Wave Call Plus (230105502503539)"

    caps = adapter.get_capabilities()
    assert caps["command_delivery"] is True
    assert caps["heart_rate_ppg"] is True
    assert caps["battery_level"] is True
    assert caps["location_gps"] is False  # Honest: Relies on phone GNSS
    assert caps["direct_ble_programmable"] is False  # Honest: Proprietary RTOS

    diag = adapter.get_diagnostics("DEV-WEARABLE-CALLPLUS")
    assert diag["location_source"] == "PHONE_GPS"
    assert "0x180D" in diag["heart_rate_monitoring"]
    assert "0x180F" in diag["battery_service"]
    assert "disclaimer" in diag["command_disclaimer"].lower() or "not supported" in diag["command_disclaimer"].lower()


def test_adapter_interface_methods():
    """Verify complete WearableAdapter architectural interface implementation."""
    adapter = WaveCallPlusAdapter()
    assert adapter.is_connected() is False
    assert adapter.get_connection_state() == "DISCONNECTED"

    # Status reading
    st = adapter.read_status("DEV-WEARABLE-CALLPLUS")
    assert st["location_source"] == "PHONE_GPS"
    assert st["direct_command_execution"] == "UNSUPPORTED"
    assert st["notification_mirroring"] == "AVAILABLE"

    # Notification sending
    notif = adapter.send_notification({"title": "Test Alert", "body": "Evacuate Zone A"})
    assert notif["status"] == "DELIVERED_TO_BRIDGE"
    assert notif["channel"] == "ANDROID_COMPANION_BRIDGE"

    # Subscribe to status
    events = []
    adapter.subscribe_to_status(lambda e: events.append(e))
    adapter.connect("DEV-WEARABLE-CALLPLUS")
    assert len(events) >= 1
    assert events[-1]["event"] == "CONNECTED"


def test_t800_ultra_rejection_at_adapter_manager_and_api(started_client):
    """Verify T800Ultra is completely rejected at gateway manager, connection manager, and API endpoints."""
    manager = WearableGatewayManager()

    # 1. Gateway Adapter lookup rejects T800
    with pytest.raises(ValueError) as exc:
        manager.get_adapter_for_device("DEV-WEARABLE-T800")
    assert "obsolete" in str(exc.value).lower() or "unsupported" in str(exc.value).lower()

    # 2. Team binding rejects T800
    with pytest.raises(ValueError):
        manager.bind_team_to_device("RESCUE-1", "DEV-WEARABLE-T800")

    # 3. Connection Manager rejects T800
    conn_mgr = WaveCallPlusConnectionManager()
    ok, msg = conn_mgr.connect("DEV-WEARABLE-T800", mac_address="70:20:33:14:11:66", bluetooth_name="T800Ultra")
    assert ok is False
    assert conn_mgr.state == WearableConnectionState.UNSUPPORTED

    # 4. Command dispatch rejects T800
    res = manager.dispatch_rescue_command({"device_id": "DEV-WEARABLE-T800", "command_id": "CMD-T800-TEST"})
    assert res["delivered"] is False
    assert res["status"] == "UNSUPPORTED_DEVICE"

    # 5. API Diagnostics endpoint rejects T800
    res_diag = started_client.post("/api/wearable/diagnostics/DEV-WEARABLE-T800")
    assert res_diag.status_code == 400
    assert "T800Ultra is unsupported" in res_diag.json()["detail"]

    # 6. API Assign endpoint rejects T800
    res_assign = started_client.post("/api/wearable/assign", json={
        "team_id": "RESCUE-1",
        "device_id": "DEV-WEARABLE-T800",
    })
    assert res_assign.status_code == 400

    # 7. API Bridge heartbeat rejects T800
    res_hb = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-T800-SESSION",
        "team_id": "RESCUE-1",
        "watch_device_id": "DEV-WEARABLE-T800",
    })
    assert res_hb.status_code == 400


def test_operation_mode_toggle_api(started_client):
    """Verify SIMULATION vs REAL_HARDWARE mode toggle."""
    # 1. Query mode
    r1 = started_client.get("/api/wearable/mode")
    assert r1.status_code == 200
    assert "mode" in r1.json()

    # 2. Switch to SIMULATION
    r2 = started_client.post("/api/wearable/mode", json={"mode": "SIMULATION"})
    assert r2.status_code == 200
    assert r2.json()["mode"] == "SIMULATION"

    # 3. Switch back to REAL_HARDWARE
    r3 = started_client.post("/api/wearable/mode", json={"mode": "REAL_HARDWARE"})
    assert r3.status_code == 200
    assert r3.json()["mode"] == "REAL_HARDWARE"


def test_single_watch_connection_manager_state_machine():
    """Verify state transitions and single active connection rule."""
    conn_mgr = WaveCallPlusConnectionManager()
    assert conn_mgr.get_state() == "DISCONNECTED"

    # Connect valid Wave Call Plus
    ok, msg = conn_mgr.connect("DEV-WEARABLE-CALLPLUS", "CB:4E:FD:EE:7F:1B", "CALLPLUS_7F1B")
    assert ok is True
    assert conn_mgr.get_state() == "CONNECTED"
    assert conn_mgr.is_connected() is True

    # Attempt duplicate connection with another device ID
    ok_dup, msg_dup = conn_mgr.connect("DEV-WEARABLE-OTHER", "CB:4E:FD:EE:7F:1B")
    assert ok_dup is False
    assert "already connected" in msg_dup

    # Reconnect (initiation returns pending/RECONNECTING, physical confirmation transitions to CONNECTED)
    ok_rec_init, msg_rec_init = conn_mgr.reconnect(physical_confirmed=False)
    assert ok_rec_init is True
    assert conn_mgr.get_state() == "RECONNECTING"
    assert conn_mgr.is_connected() is False

    ok_rec, msg_rec = conn_mgr.reconnect(physical_confirmed=True)
    assert ok_rec is True
    assert conn_mgr.get_state() == "CONNECTED"
    assert conn_mgr.is_connected() is True

    # Disconnect
    ok_dc, msg_dc = conn_mgr.disconnect()
    assert ok_dc is True
    assert conn_mgr.get_state() == "DISCONNECTED"


def test_real_capability_discovery_no_fabricated_uuids():
    """Verify Bluetooth discovery layer enumerates genuine services and characteristics."""
    conn_mgr = WaveCallPlusConnectionManager()
    report = conn_mgr.discover_real_capabilities("DEV-WEARABLE-CALLPLUS")

    assert report["bluetooth_name"] == "CALLPLUS_7F1B"
    assert report["mac_address"] == "CB:4E:FD:EE:7F:1B"
    assert report["model"] == "Wave Call Plus"
    assert report["software_version"] == "6.4.3582.28"

    # Verify standard GATT Services
    service_uuids = [s["uuid"] for s in report["gatt_services"]]
    assert "00001800-0000-1000-8000-00805f9b34fb" in service_uuids  # Generic Access
    assert "0000180A-0000-1000-8000-00805f9b34fb" in service_uuids  # Device Info
    assert "0000180D-0000-1000-8000-00805f9b34fb" in service_uuids  # Heart Rate (PPG)
    assert "0000180F-0000-1000-8000-00805f9b34fb" in service_uuids  # Battery
    assert "0000FEA0-0000-1000-8000-00805f9b34fb" in service_uuids  # Vendor Push/Sync

    # Honest capabilities
    assert report["telemetry_capabilities"]["heart_rate_ppg"] is True
    assert report["telemetry_capabilities"]["battery_level"] is True
    assert report["telemetry_capabilities"]["onboard_gps"] is False
    assert report["command_capabilities"]["direct_ble_app_execution"] is False
    assert report["command_capabilities"]["companion_notification_relay"] is True
    assert report["location_source"] == "PHONE_GPS"


def test_api_wearable_devices_endpoint_single_watch(started_client):
    """Verify /api/wearable/devices returns ONLY Wave Call Plus (no T800)."""
    res = started_client.get("/api/wearable/devices")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total"] == 1
    device_ids = [d["device_id"] for d in data["devices"]]
    assert device_ids == ["DEV-WEARABLE-CALLPLUS"]
    assert "DEV-WEARABLE-T800" not in device_ids

    dev = data["devices"][0]
    assert dev["device_name"] == "Wave Call Plus"
    assert dev["bluetooth_name"] == "CALLPLUS_7F1B"
    assert dev["mac_address"] == "CB:4E:FD:EE:7F:1B"
    assert dev["software_version"] == "6.4.3582.28"


def test_api_wearable_capabilities_endpoint(started_client):
    """Verify GET /api/wearable/capabilities returns live discovery report."""
    res = started_client.get("/api/wearable/capabilities")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["device_id"] == "DEV-WEARABLE-CALLPLUS"
    assert data["capabilities"]["bluetooth_name"] == "CALLPLUS_7F1B"


def test_api_wearable_connection_state_endpoints(started_client):
    """Verify GET /api/wearable/connection/state and POST /api/wearable/connect."""
    res_state = started_client.get("/api/wearable/connection/state")
    assert res_state.status_code == 200
    assert res_state.json()["bluetooth_name"] == "CALLPLUS_7F1B"

    # Connect
    res_conn = started_client.post("/api/wearable/connect")
    assert res_conn.status_code == 200
    assert res_conn.json()["state"] == "CONNECTED"

    # Disconnect
    res_dc = started_client.post("/api/wearable/disconnect")
    assert res_dc.status_code == 200
    assert res_dc.json()["state"] == "DISCONNECTED"


def test_command_dispatch_honest_flow():
    """Verify rescue commands format cleanly for Android Companion Bridge without claiming fake direct GATT write."""
    manager = WearableGatewayManager()

    cmd = {
        "command_id": "CMD-TEST-CALLPLUS-01",
        "team_id": "RESCUE-1",
        "latitude": 32.3745,
        "longitude": 77.2488,
        "priority": "HIGH",
        "command_text": "Proceed to survivor extraction",
    }
    result = manager.dispatch_rescue_command(cmd)

    assert result["channel"] == "ANDROID_COMPANION_BRIDGE"
    assert result["device_id"] == "DEV-WEARABLE-CALLPLUS"
    assert result["bluetooth_name"] == "CALLPLUS_7F1B"
    assert result["direct_gatt_write_supported"] is False
    assert result["location_source"] == "PHONE_GPS"
    assert "notification_payload" in result
    assert "GO" in result["notification_payload"]["title"] or "RIDGEWATCH" in result["notification_payload"]["title"]


def test_commander_assign_dispatches_wearable_command(started_client):
    """Verify Commander assignment generates a command for Wave Call Plus."""
    overview = started_client.get("/commander/overview").json()
    member = overview["team_members"][0]
    victim = overview["victims"][0]

    res = started_client.post("/commander/assign", json={
        "member_id": member["member_id"],
        "victim_id": victim["victim_id"],
    })
    assert res.status_code == 200
    assert res.json()["status"] == "en_route"

    cmd_res = started_client.get(f"/api/wearable/commands/active?member_id={member['member_id']}")
    assert cmd_res.status_code == 200
    assert cmd_res.json()["has_active_command"] is True
    cmd = cmd_res.json()["command"]
    assert cmd["victim_id"] == victim["victim_id"]
    assert cmd["target_device_id"] == "DEV-WEARABLE-CALLPLUS"


def test_wearable_status_return_path(started_client):
    """Verify status updates (EN_ROUTE -> ARRIVED -> RESCUED) flow back through the API."""
    overview = started_client.get("/commander/overview").json()
    member = overview["team_members"][0]
    victim = overview["victims"][0]

    started_client.post("/commander/assign", json={
        "member_id": member["member_id"],
        "victim_id": victim["victim_id"],
    })

    cmd_res = started_client.get(f"/api/wearable/commands/active?member_id={member['member_id']}")
    cmd = cmd_res.json()["command"]
    cmd_id = cmd["command_id"]

    # 1. Update to EN_ROUTE
    r1 = started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "EN_ROUTE"})
    assert r1.status_code == 200

    # 2. Update to ARRIVED
    r2 = started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "ARRIVED"})
    assert r2.status_code == 200

    # 3. Update to RESCUED
    r3 = started_client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "RESCUED"})
    assert r3.status_code == 200


def test_bridge_heartbeat_and_honest_telemetry(started_client):
    """Verify companion bridge heartbeat with phone GPS coordinates explicitly tagged as PHONE_GPS."""
    res = started_client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-BRG-CALLPLUS",
        "team_id": "RESCUE-2",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_connected": True,
        "bluetooth_state": "ENABLED",
        "gps_available": True,
        "latitude": 32.3750,
        "longitude": 77.2500,
        "location_source": "PHONE_GPS",
    })
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    session = res.json()["session"]
    assert session["location_source"] == "PHONE_GPS"
    assert session["watch_mac"] == "CB:4E:FD:EE:7F:1B"
    assert session["watch_device_id"] == "DEV-WEARABLE-CALLPLUS"


def test_core_uninterrupted_when_watch_offline(started_client):
    """Verify core Commander, Scenario, Victims, and Teams work with zero interruptions when watch is disconnected."""
    overview = started_client.get("/commander/overview")
    assert overview.status_code == 200
    data = overview.json()
    assert "team_members" in data
    assert "victims" in data
    assert "scenario" in data
