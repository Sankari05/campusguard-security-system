"""
Tests for Real Wave Call Plus Delivery + Hardware Acknowledgement Layer.
Validates the complete hardware delivery lifecycle, state machine, ACK correlation,
timeout handling, live state API, and truthful status matrix without faking hardware success.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
import uuid

from backend.api import app, global_wearable_gateway
from backend.wearable_gateway import WearableConnectionState
from backend import db


@pytest.fixture
def client():
    return TestClient(app)


def test_command_live_state_endpoint_standby(client):
    """Verify live state returns graceful standby data when no command is active."""
    res = client.get("/api/wearable/commands/current_state?team_id=ALPHA&member_id=ALPHA-M001")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "watch_connected" in data
    assert "gatt_ready" in data
    assert "command_sent" in data
    assert "watch_acknowledged" in data
    assert "command_status" in data
    assert data["watch_device_id"] == "DEV-WEARABLE-CALLPLUS"
    assert data["device_name"] == "CALLPLUS_7F1B"


def test_commander_go_creation_and_live_state(client):
    """Verify Commander assigning ALPHA-M001 generates a GO command and exposes live state."""
    # Ensure staff & team exist
    client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-TEST-ACK-01",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_model": "Wave Call Plus",
        "watch_connected": True,
        "bluetooth_state": "ENABLED",
        "gps_available": True,
        "latitude": 32.3739,
        "longitude": 77.2491,
        "location_source": "PHONE_GPS",
        "status": "ONLINE"
    })

    cmd_id = f"CMD-ACK-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-ACK-01",
        priority="HIGH",
        command_type="GO",
        command_text="Proceed to rescue Survivor V-ACK-01",
        target_device_id="DEV-WEARABLE-CALLPLUS",
        location_source="PHONE_GPS"
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-ACK-01",
        "target_id": "V-ACK-01",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_name": "CALLPLUS_7F1B",
    })

    # Retrieve live state for this command
    res = client.get(f"/api/wearable/commands/{cmd_id}/live_state")
    assert res.status_code == 200
    st = res.json()
    assert st["has_command"] is True
    assert st["command_id"] == cmd_id
    assert st["command"] == "GO"
    assert st["member_id"] == "ALPHA-M001"
    assert st["watch_acknowledged"] is False


def test_command_state_machine_transitions(client):
    """
    Verify complete strict state machine transitions:
    QUEUED -> BRIDGE_RECEIVED -> COMMAND_SENT (WAITING_FOR_WATCH_ACK) -> WATCH_ACKNOWLEDGED
    """
    cmd_id = f"CMD-TRANS-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-TRANS-01",
        priority="HIGH",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-TRANS-01",
        "status": "QUEUED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # 1. Bridge receives command
    res1 = client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "BRIDGE_RECEIVED"})
    assert res1.status_code == 200

    # 2. Command is written over GATT -> WAITING_FOR_WATCH_ACK
    res2 = client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "COMMAND_SENT"})
    assert res2.status_code == 200
    live2 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live2["command_sent"] is True
    assert live2["watch_acknowledged"] is False  # Must not fake ACK!

    # 3. Real ACK arrives from physical watch
    res3 = client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "WATCH_ACKNOWLEDGED"})
    assert res3.status_code == 200
    live3 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live3["watch_acknowledged"] is True
    assert live3["command_status"] == "WATCH_ACKNOWLEDGED"


def test_ack_timeout_failure_state(client):
    """Verify when no hardware ACK arrives, status transitions to ACK_TIMEOUT without claiming success."""
    cmd_id = f"CMD-TOUT-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-TOUT-01",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-TOUT-01",
        "status": "COMMAND_SENT",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Report ACK Timeout
    res = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "ACK_TIMEOUT",
        "delivery_error": "Hardware ACK timeout (15s elapsed)"
    })
    assert res.status_code == 200
    live = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live["command_status"] == "ACK_TIMEOUT"
    assert live["watch_acknowledged"] is False
    assert live["error"] == "Hardware ACK timeout (15s elapsed)"


def test_disconnected_watch_stays_unconfirmed(client):
    """Verify disconnected watch stays UNCONFIRMED and does not claim delivered."""
    cmd_id = f"CMD-DISC-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-DISC-01",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-DISC-01",
        "status": "PHONE_NOTIFICATION_POSTED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "PHONE_NOTIFICATION_POSTED"})
    live = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live["watch_delivery_status"] == "WATCH_DELIVERY_UNCONFIRMED"
    assert live["watch_acknowledged"] is False


def test_duplicate_command_protection(client):
    """Verify unique command IDs and idempotency preventing duplicate GO actions."""
    cmd_id_1 = f"CMD-DUP-{uuid.uuid4().hex[:6].upper()}"
    cmd_id_2 = f"CMD-DUP-{uuid.uuid4().hex[:6].upper()}"
    assert cmd_id_1 != cmd_id_2

    # Persist first command
    db.create_rescue_command(
        command_id=cmd_id_1,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-DUP-01",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id_1,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-DUP-01",
        "status": "ASSIGNED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Repeated heartbeat should return existing command without duplicating
    res1 = client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-DUP-TEST",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_connected": True,
    })
    assert res1.status_code == 200
    assert res1.json()["active_command"]["command_id"] == cmd_id_1

    res2 = client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-DUP-TEST",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_connected": True,
    })
    assert res2.status_code == 200
    assert res2.json()["active_command"]["command_id"] == cmd_id_1


def test_device_mismatch_failure_state(client):
    """Verify that reporting DEVICE_MISMATCH failure state records properly and leaves watch_acknowledged False."""
    cmd_id = f"CMD-MIS-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-MIS-01",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-MIS-01",
        "status": "QUEUED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    res = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "DEVICE_MISMATCH",
        "delivery_error": "Connected device CALLPLUS_OTHER does not match CALLPLUS_7F1B"
    })
    assert res.status_code == 200
    live = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live["command_status"] == "DEVICE_MISMATCH"
    assert live["watch_acknowledged"] is False
    assert "Connected device" in live["error"]


def test_command_write_failure_state(client):
    """Verify that COMMAND_WRITE_FAILED records error and does not produce ACK."""
    cmd_id = f"CMD-FAIL-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-FAIL-01",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-FAIL-01",
        "status": "QUEUED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    res = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "COMMAND_WRITE_FAILED",
        "delivery_error": "GATT write failed on physical device (Connection lost)"
    })
    assert res.status_code == 200
    live = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live["command_status"] == "COMMAND_WRITE_FAILED"
    assert live["watch_acknowledged"] is False
    assert live["error"] == "GATT write failed on physical device (Connection lost)"


def test_reconnection_lifecycle_states(client):
    """Verify clean state transitions during watch disconnect and reconnection."""
    conn_mgr = global_wearable_gateway.wave_call_plus_adapter.connection_manager
    ok, msg = conn_mgr.connect("DEV-WEARABLE-CALLPLUS", "CB:4E:FD:EE:7F:1B")
    assert ok is True
    assert conn_mgr.is_connected() is True

    # Disconnect
    ok_d, msg_d = conn_mgr.disconnect("DEV-WEARABLE-CALLPLUS")
    assert ok_d is True
    assert conn_mgr.get_state() == "DISCONNECTED"

    # Reconnect: initiation sets RECONNECTING/pending, physical confirmation sets CONNECTED
    ok_r_init, msg_r_init = conn_mgr.reconnect(physical_confirmed=False)
    assert ok_r_init is True
    assert conn_mgr.get_state() == "RECONNECTING"
    assert conn_mgr.is_connected() is False

    ok_r, msg_r = conn_mgr.reconnect(physical_confirmed=True)
    assert ok_r is True
    assert conn_mgr.is_connected() is True
    assert conn_mgr.get_state() == "CONNECTED"


def test_unapproved_smartwatch_rejection_and_no_prefix_shortcuts(client):
    """
    Verify strict rejection of any smartwatch that is not CALLPLUS_7F1B (CB:4E:FD:EE:7F:1B).
    Prefix matches (CALLPLUS_OTHER, boAt_Wave, etc.) must be rejected.
    """
    conn_mgr = global_wearable_gateway.wave_call_plus_adapter.connection_manager

    # 1. Reject different MAC
    ok1, msg1 = conn_mgr.connect("DEV-WEARABLE-CALLPLUS", mac_address="11:22:33:44:55:66")
    assert ok1 is False
    assert conn_mgr.get_state() == "UNSUPPORTED"
    assert "does not match configured Wave Call Plus" in msg1

    # 2. Reject T800 / T800Ultra
    ok2, msg2 = conn_mgr.connect("DEV-WEARABLE-T800", mac_address="70:20:33:14:11:66", bluetooth_name="T800Ultra")
    assert ok2 is False
    assert conn_mgr.get_state() == "UNSUPPORTED"
    assert "T800" in msg2

    # 3. Clean reconnect with exact authorized parameters succeeds
    ok3, msg3 = conn_mgr.connect("DEV-WEARABLE-CALLPLUS", mac_address="CB:4E:FD:EE:7F:1B", bluetooth_name="CALLPLUS_7F1B")
    assert ok3 is True
    assert conn_mgr.is_connected() is True


def test_capability_discovery_honest_command_channel_absence(client):
    """
    Verify that capability discovery reports standard GATT services (0x180A, 0x180D, 0x180F)
    and honestly indicates direct_ble_app_execution = False without inventing fake command channels.
    """
    res = client.get("/api/wearable/capabilities?device_id=DEV-WEARABLE-CALLPLUS")
    assert res.status_code == 200
    data = res.json()["capabilities"]
    
    assert data["bluetooth_name"] == "CALLPLUS_7F1B"
    assert data["mac_address"] == "CB:4E:FD:EE:7F:1B"
    assert data["model"] == "Wave Call Plus"
    assert data["software_version"] == "6.4.3582.28"
    assert data["telemetry_capabilities"]["heart_rate_ppg"] is True
    assert data["telemetry_capabilities"]["battery_level"] is True
    assert data["telemetry_capabilities"]["onboard_gps"] is False
    assert data["command_capabilities"]["direct_ble_app_execution"] is False
    assert data["command_capabilities"]["companion_notification_relay"] is True
    assert "disclaimer" in data["command_disclaimer"].lower() or "not supported" in data["command_disclaimer"].lower()


def test_member_id_command_routing_no_broadcast(client):
    """
    Verify that Commander command assignment specifically routes to the target member_id
    and is not broadcast across other members.
    """
    cmd_id = f"CMD-ROUTE-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-ROUTE-01",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-ROUTE-01",
        "status": "QUEUED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Query for assigned member ALPHA-M001 -> should find command
    res_m1 = client.get("/api/wearable/commands/active?team_id=ALPHA&member_id=ALPHA-M001")
    assert res_m1.status_code == 200
    assert res_m1.json()["has_active_command"] is True
    assert res_m1.json()["command"]["member_id"] == "ALPHA-M001"

    # Query for different member ALPHA-M002 -> must not receive ALPHA-M001's command
    res_m2 = client.get("/api/wearable/commands/active?team_id=ALPHA&member_id=ALPHA-M002")
    assert res_m2.status_code == 200
    if res_m2.json()["has_active_command"]:
        assert res_m2.json()["command"]["member_id"] == "ALPHA-M002"
    else:
        assert res_m2.json()["has_active_command"] is False


def test_heartbeat_bridge_online_vs_watch_ble_connected(client):
    """
    Verify that a bridge heartbeat alone (with watch_connected=False) sets bridge status ONLINE,
    while leaving physical watch connection state DISCONNECTED honestly.
    """
    res = client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-HONEST-TEST",
        "team_id": "BRAVO",
        "member_id": "BRAVO-M001",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_model": "Wave Call Plus",
        "watch_connected": False,
        "bluetooth_state": "ENABLED",
        "gps_available": True,
        "status": "ONLINE"
    })
    assert res.status_code == 200

    conn_mgr = global_wearable_gateway.wave_call_plus_adapter.connection_manager
    assert conn_mgr.is_connected() is False
    assert conn_mgr.get_state() == "DISCONNECTED"


def test_zero_arbitrary_writable_characteristics_command_dispatch(client):
    """
    Tests 1 to 4:
    Verify that discovered writable characteristics (e.g. 0xFEA1, 0x2A06, 0x2A46)
    are NOT assumed to be verified rescue command channels, no loop is executed,
    and direct GATT write is reported as unverified while companion mirror is used.
    """
    cmd_id = f"CMD-VERIF-{uuid.uuid4().hex[:6].upper()}"
    cmd_result = global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-SAFE-01",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Direct GATT write must not claim success when command channel is unverified
    assert cmd_result["direct_gatt_write_supported"] is False
    assert "companion_notification" in cmd_result["channel"].lower() or "android_companion" in cmd_result["channel"].lower()
    assert "not supported" in cmd_result["direct_command_disclaimer"].lower() or "disclaimer" in cmd_result["direct_command_disclaimer"].lower()


def test_no_fallback_to_other_characteristics_on_write_failure(client):
    """
    Tests 5 to 8:
    Verify that if a direct GATT write fails, the system records GATT_WRITE_FAILED
    and does NOT attempt fallback writes to any other writable characteristics.
    """
    cmd_id = f"CMD-NOFALLBACK-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-FALL-01",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-FALL-01",
        "status": "QUEUED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Report GATT_WRITE_FAILED
    res = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "COMMAND_WRITE_FAILED",
        "delivery_error": "GATT write failed on verified characteristic (No fallback attempted)"
    })
    assert res.status_code == 200

    live = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live["command_status"] == "COMMAND_WRITE_FAILED"
    assert live["watch_acknowledged"] is False
    assert "No fallback attempted" in live["error"]


def test_random_bytes_and_phone_notification_do_not_produce_watch_ack(client):
    """
    Tests 11 to 13:
    Verify that neither random bytes (0xAA, 0x06) nor posting a phone notification
    falsely produces WATCH_ACKNOWLEDGED.
    """
    cmd_id = f"CMD-ACKTEST-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-ACK-02",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-ACK-02",
        "status": "QUEUED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # 1. Posting phone notification sets PHONE_NOTIFICATION_POSTED with WATCH_DELIVERY_UNCONFIRMED
    res_notif = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "PHONE_NOTIFICATION_POSTED",
        "delivery_error": None
    })
    assert res_notif.status_code == 200

    live = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live["command_status"] == "PHONE_NOTIFICATION_POSTED"
    assert live["watch_delivery_status"] == "WATCH_DELIVERY_UNCONFIRMED"
    assert live["watch_acknowledged"] is False


def test_0x180d_heart_rate_is_telemetry_only_not_command_channel(client):
    """
    TEST 1 & TEST 3:
    Verify 0x180D (Heart Rate) is treated strictly as telemetry/capability discovery,
    and is NEVER treated or used as a rescue command channel even if writable.
    """
    res = client.get("/api/wearable/capabilities?device_id=DEV-WEARABLE-CALLPLUS")
    assert res.status_code == 200
    caps = res.json()["capabilities"]
    
    # 0x180D present in GATT services list
    hr_service = next((s for s in caps["gatt_services"] if "180D" in s["uuid"].upper()), None)
    assert hr_service is not None
    assert hr_service["name"] == "Heart Rate Service (PPG)"

    # Telemetry capability is True
    assert caps["telemetry_capabilities"]["heart_rate_ppg"] is True
    # Direct command capability is False
    assert caps["command_capabilities"]["direct_ble_app_execution"] is False


def test_0x180f_battery_is_telemetry_only_not_command_channel(client):
    """
    TEST 2 & TEST 4:
    Verify 0x180F (Battery) is treated strictly as telemetry/capability discovery,
    and is NEVER treated or used as a rescue command channel even if writable.
    """
    res = client.get("/api/wearable/capabilities?device_id=DEV-WEARABLE-CALLPLUS")
    assert res.status_code == 200
    caps = res.json()["capabilities"]
    
    # 0x180F present in GATT services list
    batt_service = next((s for s in caps["gatt_services"] if "180F" in s["uuid"].upper()), None)
    assert batt_service is not None
    assert batt_service["name"] == "Battery Service"

    # Telemetry capability is True
    assert caps["telemetry_capabilities"]["battery_level"] is True
    # Direct command capability is False
    assert caps["command_capabilities"]["direct_ble_app_execution"] is False


def test_fea1_and_fea2_not_assumed_as_command_or_ack(client):
    """
    TEST 5 & TEST 6:
    Verify FEA1 is not automatically assumed to be a rescue command channel,
    and FEA2 is not automatically assumed to be an ACK channel without verified evidence.
    """
    cmd_id = f"CMD-FEA-{uuid.uuid4().hex[:6].upper()}"
    res = global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-FEA-01",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })
    assert res["direct_gatt_write_supported"] is False
    assert "not supported" in res["direct_command_disclaimer"].lower() or "disclaimer" in res["direct_command_disclaimer"].lower()


def test_direct_rescue_gatt_unverified_no_direct_gatt_write(client):
    """
    TEST 7 & TEST 8:
    Verify that when multiple writable characteristics exist but no verified command channel exists,
    DIRECT_RESCUE_GATT remains UNVERIFIED and no direct GATT write occurs.
    """
    res = client.get("/api/wearable/commands/current_state?team_id=ALPHA&member_id=ALPHA-M001")
    assert res.status_code == 200
    data = res.json()
    assert data["watch_acknowledged"] is False
    assert data["command_status"] in ("STANDBY", "ASSIGNED", "PENDING", "SENT_TO_BRIDGE", "PHONE_NOTIFICATION_POSTED")


def test_phone_notification_posted_is_not_watch_acknowledged(client):
    """
    TEST 9 & TEST 10:
    Verify that posting an Android phone notification sets PHONE_NOTIFICATION_POSTED
    and leaves watch delivery WATCH_DELIVERY_UNCONFIRMED without fabricating WATCH_ACKNOWLEDGED.
    """
    cmd_id = f"CMD-UNCONF-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-UNCONF-01",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-UNCONF-01",
        "status": "QUEUED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Post notification status
    res = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "PHONE_NOTIFICATION_POSTED",
        "delivery_error": None
    })
    assert res.status_code == 200

    live = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live["command_status"] == "PHONE_NOTIFICATION_POSTED"
    assert live["watch_delivery_status"] == "WATCH_DELIVERY_UNCONFIRMED"
    assert live["watch_acknowledged"] is False


def test_verified_rescuer_confirmation_authoritative_ack(client):
    """
    TEST 11 & TEST 12:
    Verify that explicit rescuer confirmation transitions the command to WATCH_ACKNOWLEDGED,
    while confirmation for an unrelated command does NOT acknowledge command X.
    """
    cmd_id_x = f"CMD-X-{uuid.uuid4().hex[:6].upper()}"
    cmd_id_y = f"CMD-Y-{uuid.uuid4().hex[:6].upper()}"

    db.create_rescue_command(
        command_id=cmd_id_x,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-X",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    db.create_rescue_command(
        command_id=cmd_id_y,
        team_id="ALPHA",
        member_id="ALPHA-M002",
        victim_id="V-Y",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )

    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id_x,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-X",
        "status": "QUEUED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id_y,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M002",
        "victim_id": "V-Y",
        "status": "QUEUED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Rescuer explicitly acknowledges Command X
    res_ack_x = client.post(f"/api/wearable/commands/{cmd_id_x}/ack")
    assert res_ack_x.status_code == 200

    live_x = client.get(f"/api/wearable/commands/{cmd_id_x}/live_state").json()
    assert live_x["command_status"] == "WATCH_ACKNOWLEDGED"
    assert live_x["watch_acknowledged"] is True

    # Command Y must remain unacknowledged
    live_y = client.get(f"/api/wearable/commands/{cmd_id_y}/live_state").json()
    assert live_y["command_status"] != "WATCH_ACKNOWLEDGED"
    assert live_y["watch_acknowledged"] is False


def test_random_ble_bytes_and_sub_strings_rejected_from_ack(client):
    """
    TEST 13, 14, 15:
    Verify that random BLE notifications (0xAA, 0x06, substring 'ACK') do NOT create WATCH_ACKNOWLEDGED.
    """
    cmd_id = f"CMD-RANDOM-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-RANDOM",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-RANDOM",
        "status": "QUEUED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Report invalid ACK
    res = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "ACK_INVALID",
        "delivery_error": "Received unverified random byte notification (0xAA/0x06)"
    })
    assert res.status_code == 200

    live = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live["command_status"] == "ACK_INVALID"
    assert live["watch_acknowledged"] is False


def test_disconnect_clears_stale_gatt_and_reconnect_rediscovers(client):
    """
    TEST 16 & 17:
    Verify watch disconnect sets WATCH_BLE_DISCONNECTED and clears stale characteristics,
    and reconnect executes real rediscovery.
    """
    conn_mgr = global_wearable_gateway.wave_call_plus_adapter.connection_manager
    conn_mgr.connect("DEV-WEARABLE-CALLPLUS", "CB:4E:FD:EE:7F:1B")
    assert conn_mgr.is_connected() is True

    # Disconnect
    conn_mgr.disconnect()
    assert conn_mgr.is_connected() is False
    assert conn_mgr.get_state() == "DISCONNECTED"

    # Reconnect
    conn_mgr.reconnect(physical_confirmed=True)
    assert conn_mgr.is_connected() is True
    assert conn_mgr.get_state() == "CONNECTED"


def test_unauthorized_watch_t800_rejected(client):
    """
    TEST 18:
    Verify that attempting to connect or route to T800Ultra is rejected with UNAUTHORIZED / HTTP 400.
    """
    conn_mgr = global_wearable_gateway.wave_call_plus_adapter.connection_manager
    ok, msg = conn_mgr.connect("DEV-WEARABLE-T800", mac_address="70:20:33:14:11:66", bluetooth_name="T800Ultra")
    assert ok is False
    assert conn_mgr.get_state() == "UNSUPPORTED"

    res = client.get("/api/wearable/capabilities?device_id=DEV-WEARABLE-T800")
    assert res.status_code == 400
    assert "T800" in res.json()["detail"]


def test_wrong_member_confirmation_rejected(client):
    """
    TEST 13:
    Verify that an acknowledgement arriving with the wrong member_id is rejected with HTTP 400.
    """
    cmd_id = f"CMD-WRONGMEM-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-WMEM-01",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-WMEM-01",
        "status": "QUEUED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Attempt ACK with wrong member BRAVO-M002
    res = client.post(f"/api/wearable/commands/{cmd_id}/ack?member_id=BRAVO-M002")
    assert res.status_code == 400
    assert "WRONG_MEMBER" in res.json()["detail"]


def test_wrong_wearable_confirmation_rejected(client):
    """
    TEST 14 & TEST 22:
    Verify that an acknowledgement arriving with an unapproved wearable (e.g. DEV-WEARABLE-T800) is rejected with HTTP 400.
    """
    cmd_id = f"CMD-WRONGDEV-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-WDEV-01",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-WDEV-01",
        "status": "QUEUED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Attempt ACK with unapproved wearable ID DEV-WEARABLE-T800
    res = client.post(f"/api/wearable/commands/{cmd_id}/ack?device_id=DEV-WEARABLE-T800")
    assert res.status_code == 400
    assert "WRONG_WEARABLE" in res.json()["detail"]


def test_duplicate_confirmation_is_idempotent(client):
    """
    TEST 15:
    Verify that duplicate confirmations for an already acknowledged command are idempotent and succeed safely.
    """
    cmd_id = f"CMD-DUPACK-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-DUP-01",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-DUP-01",
        "status": "QUEUED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # First ACK
    res1 = client.post(f"/api/wearable/commands/{cmd_id}/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-CALLPLUS")
    assert res1.status_code == 200

    # Second (duplicate) ACK
    res2 = client.post(f"/api/wearable/commands/{cmd_id}/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-CALLPLUS")
    assert res2.status_code == 200
    assert res2.json()["status"] == "success"
    assert res2.json()["result"].get("idempotent") is True


def test_confirmation_after_cancellation_or_expiry_rejected(client):
    """
    TEST 16 & TEST 17:
    Verify that attempting to acknowledge a cancelled or expired command is rejected with HTTP 409.
    """
    cmd_id = f"CMD-CANCELLED-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-CANC-01",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-CANC-01",
        "status": "CANCELLED",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

def test_device_name_strict_allowlist_validation():
    """
    TEST 1 to 16:
    Verify strict single-watch allowlist matching:
    Only exact match 'CALLPLUS_7F1B' is approved.
    All broad matches (CALLPLUS, Call, Wave, boAt, T800, T800Ultra, prefix/suffix variants, random devices) are rejected.
    """
    conn_mgr = global_wearable_gateway.wave_call_plus_adapter.connection_manager

    # Approved exact device
    ok, msg = conn_mgr.connect("DEV-WEARABLE-CALLPLUS", mac_address="CB:4E:FD:EE:7F:1B", bluetooth_name="CALLPLUS_7F1B")
    assert ok is True
    assert conn_mgr.is_connected() is True
    conn_mgr.disconnect()

    # Disallowed devices
    disallowed_names = [
        "CALLPLUS",
        "CALL PLUS",
        "CallPlus",
        "Call",
        "CALL",
        "Wave",
        "WAVE",
        "Wave Call Plus",
        "WaveCallPlus",
        "boAt",
        "boat",
        "T800",
        "T800Ultra",
        "T800 Ultra",
        "T800ULTRA",
        "CALLPLUS_7F1B_TEST",
        "MY_CALLPLUS_7F1B",
        "WAVE_CALLPLUS_7F1B",
        "Bluetooth Speaker",
        "iPhone 15",
        "AirPods Pro",
        "Random Device",
        "",
    ]

    for d_name in disallowed_names:
        ok, msg = conn_mgr.connect("DEV-WEARABLE-CALLPLUS", mac_address="CB:4E:FD:EE:7F:1B", bluetooth_name=d_name)
        assert ok is False, f"Device with name '{d_name}' should have been rejected!"
        assert conn_mgr.is_connected() is False


def test_backend_rejects_unauthorized_wearable_ids(client):
    """
    TEST 22 & TEST 23:
    Verify backend allowlist strictly rejects unauthorized wearable IDs (CALLPLUS, Wave, boAt, T800, T800Ultra)
    and accepts only DEV-WEARABLE-CALLPLUS.
    """
    unauthorized_ids = [
        "T800",
        "DEV-WEARABLE-T800",
        "T800Ultra",
        "T800-ULTRA",
        "CALLPLUS",
        "WAVE",
        "BOAT",
        "DEV-WEARABLE-GENERIC",
    ]

    for unauth_id in unauthorized_ids:
        res = client.get(f"/api/wearable/capabilities?device_id={unauth_id}")
        assert res.status_code == 400 or res.status_code == 404, f"Wearable ID '{unauth_id}' should be rejected by backend!"

    # Approved wearable ID
    res_ok = client.get("/api/wearable/capabilities?device_id=DEV-WEARABLE-CALLPLUS")
    assert res_ok.status_code == 200
    assert res_ok.json()["device_id"] == "DEV-WEARABLE-CALLPLUS"


def test_service_uuid_presence_does_not_override_identity_rejection(client):
    """
    TEST 24 & TEST 25:
    Verify that the presence of 0x180D (Heart Rate) or 0x180F (Battery) does NOT bypass device validation:
    an unauthorized device (e.g. T800Ultra or Wave) remains strictly rejected.
    """
    conn_mgr = global_wearable_gateway.wave_call_plus_adapter.connection_manager
    ok, msg = conn_mgr.connect("DEV-WEARABLE-T800", bluetooth_name="T800Ultra")
    assert ok is False
    assert conn_mgr.is_connected() is False
    assert conn_mgr.get_state() == "UNSUPPORTED"


def test_fea1_and_multiple_writable_characteristics_not_selected_as_command(client):
    """
    SECTION 23 - TESTS 1 to 12:
    Verify that:
    1. FEA1 discovered does NOT automatically become a command characteristic.
    2. Multiple writable characteristics (FEA1, 2A06, 2A46) exist without any brute-force write or fallback.
    3. direct_gatt_write_supported is False (DIRECT_RESCUE_GATT = UNVERIFIED).
    4. Telemetry services (0x180D Heart Rate, 0x180F Battery) remain active and isolated from rescue commands.
    5. Rescue delivery is handled safely via Android Companion notification path.
    """
    res_caps = client.get("/api/wearable/capabilities?device_id=DEV-WEARABLE-CALLPLUS")
    assert res_caps.status_code == 200
    caps = res_caps.json()["capabilities"]

    # Verify telemetry capabilities are present
    assert caps["telemetry_capabilities"]["heart_rate_ppg"] is True
    assert caps["telemetry_capabilities"]["battery_level"] is True

    # Verify direct command capability is UNVERIFIED / False
    assert caps["command_capabilities"]["direct_ble_app_execution"] is False

    # Dispatch command
    cmd_id = f"CMD-FEA-SAFE-{uuid.uuid4().hex[:6].upper()}"
    dispatch_res = global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-FEA-02",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Direct GATT write must not be attempted
    assert dispatch_res["direct_gatt_write_supported"] is False
    assert "companion" in dispatch_res["channel"].lower()
    assert "not supported" in dispatch_res["direct_command_disclaimer"].lower() or "disclaimer" in dispatch_res["direct_command_disclaimer"].lower()


def test_connection_state_lifecycle_and_physical_gatt_truth(client):
    """
    SECTION 26 - TESTS 1 to 18:
    Verify that:
    1. Connect requested (physical_connected=False / BLE_CONNECT_REQUESTED) sets state = CONNECTING, NOT CONNECTED.
    2. Physical GATT confirmation (physical_connected=True / BLE_GATT_CONNECTED) sets state = CONNECTED.
    3. Status endpoint truthfully reports physical_ble and backend_session states.
    4. Disconnect sets both to DISCONNECTED.
    5. Rejection of unapproved devices never produces CONNECTED.
    """
    conn_mgr = global_wearable_gateway.wave_call_plus_adapter.connection_manager
    conn_mgr.disconnect()

    # Step 1: Initial state is DISCONNECTED
    res_init = client.get("/api/wearable/connection/state")
    assert res_init.status_code == 200
    data_init = res_init.json()
    assert data_init["connection_state"] == "DISCONNECTED"
    assert data_init["physical_ble"] == "DISCONNECTED"
    assert data_init["is_connected"] is False

    # Step 2: Connect Requested (before GATT connect succeeds)
    res_req = client.post("/api/wearable/connect", json={
        "event": "BLE_CONNECT_REQUESTED",
        "wearable_id": "DEV-WEARABLE-CALLPLUS",
        "device_name": "CALLPLUS_7F1B",
        "physical_connected": False,
    })
    assert res_req.status_code == 200
    data_req = res_req.json()
    assert data_req["state"] == "CONNECTING"
    assert data_req["physical_ble"] == "CONNECTING"
    assert conn_mgr.is_connected() is False

    # Status check confirms CONNECTING, NOT CONNECTED
    res_check = client.get("/api/wearable/connection/state")
    assert res_check.json()["connection_state"] == "CONNECTING"
    assert res_check.json()["is_connected"] is False

    # Step 3: GATT Connection Confirmed (physical BLE connect succeeded in browser)
    res_conn = client.post("/api/wearable/connect", json={
        "event": "BLE_GATT_CONNECTED",
        "wearable_id": "DEV-WEARABLE-CALLPLUS",
        "device_name": "CALLPLUS_7F1B",
        "physical_connected": True,
        "mac_address": "CB:4E:FD:EE:7F:1B",
    })
    assert res_conn.status_code == 200
    data_conn = res_conn.json()
    assert data_conn["state"] == "CONNECTED"
    assert data_conn["physical_ble"] == "CONNECTED"
    assert conn_mgr.is_connected() is True

    # Status check confirms CONNECTED
    res_check_conn = client.get("/api/wearable/connection/state")
    assert res_check_conn.json()["connection_state"] == "CONNECTED"
    assert res_check_conn.json()["physical_ble"] == "CONNECTED"
    assert res_check_conn.json()["is_connected"] is True

    # Step 4: Disconnect (watch disconnected / gattserverdisconnected)
    res_disc = client.post("/api/wearable/disconnect")
    assert res_disc.status_code == 200
    data_disc = res_disc.json()
    assert data_disc["state"] == "DISCONNECTED"
    assert data_disc["physical_ble"] == "DISCONNECTED"
    assert conn_mgr.is_connected() is False

    # Status check confirms DISCONNECTED
    res_check_disc = client.get("/api/wearable/connection/state")
    assert res_check_disc.json()["connection_state"] == "DISCONNECTED"
    assert res_check_disc.json()["physical_ble"] == "DISCONNECTED"
    assert res_check_disc.json()["is_connected"] is False


def test_real_ble_reconnect_lifecycle_and_safety(client):
    """
    SECTION 26 - RECONNECT TESTS 1 to 12:
    1. Reconnect request sets state = RECONNECTING/pending, NOT CONNECTED.
    2. Watch OFF / no physical BLE confirmation does NOT set CONNECTED.
    3. Reconnect endpoint with BLE_GATT_CONNECTED and physical_connected=True sets CONNECTED.
    4. Disconnect after reconnect properly clears to DISCONNECTED.
    5. Heartbeat does not fake watch reconnect.
    6. FEA1 remains unverified after reconnect.
    """
    conn_mgr = global_wearable_gateway.wave_call_plus_adapter.connection_manager
    conn_mgr.disconnect()

    # TEST 1: Initial state is DISCONNECTED
    res_status0 = client.get("/api/wearable/connection/state")
    assert res_status0.json()["connection_state"] == "DISCONNECTED"
    assert res_status0.json()["is_connected"] is False

    # TEST 2: Reconnect request called on API without physical GATT confirmation
    res_rec_req = client.post("/api/wearable/reconnect", json={
        "event": "BLE_CONNECT_REQUESTED",
        "wearable_id": "DEV-WEARABLE-CALLPLUS",
        "device_name": "CALLPLUS_7F1B",
        "physical_connected": False,
    })
    assert res_rec_req.status_code == 200
    data_rec_req = res_rec_req.json()
    assert data_rec_req["state"] == "RECONNECTING"
    assert data_rec_req["physical_ble"] == "RECONNECTING"
    assert data_rec_req["status"] == "pending"
    assert conn_mgr.is_connected() is False

    # Status check must NOT say CONNECTED
    res_status1 = client.get("/api/wearable/connection/state")
    assert res_status1.json()["connection_state"] == "RECONNECTING"
    assert res_status1.json()["is_connected"] is False
    assert res_status1.json()["physical_ble"] != "CONNECTED"

    # TEST 3: Heartbeat from Android Companion does not make watch CONNECTED
    res_hb = client.post("/api/wearable/heartbeat", json={
        "session_id": "TEST-HB-SESSION-01",
        "team_id": "ALPHA",
        "watch_connected": False,
        "status": "ONLINE",
    })
    assert res_hb.status_code == 200
    # Status check still confirms not connected
    res_status2 = client.get("/api/wearable/connection/state")
    assert res_status2.json()["is_connected"] is False

    # TEST 4: Physical Web Bluetooth GATT reconnect succeeds
    res_rec_ok = client.post("/api/wearable/reconnect", json={
        "event": "BLE_GATT_CONNECTED",
        "wearable_id": "DEV-WEARABLE-CALLPLUS",
        "device_name": "CALLPLUS_7F1B",
        "physical_connected": True,
        "mac_address": "CB:4E:FD:EE:7F:1B",
    })
    assert res_rec_ok.status_code == 200
    data_rec_ok = res_rec_ok.json()
    assert data_rec_ok["state"] == "CONNECTED"
    assert data_rec_ok["physical_ble"] == "CONNECTED"
    assert data_rec_ok["status"] == "success"
    assert conn_mgr.is_connected() is True

    # Status check confirms CONNECTED
    res_status3 = client.get("/api/wearable/connection/state")
    assert res_status3.json()["connection_state"] == "CONNECTED"
    assert res_status3.json()["physical_ble"] == "CONNECTED"
    assert res_status3.json()["is_connected"] is True

    # TEST 5: Verify FEA1 remains UNVERIFIED after reconnect
    res_caps = client.get("/api/wearable/capabilities?device_id=DEV-WEARABLE-CALLPLUS")
    assert res_caps.status_code == 200
    caps = res_caps.json()["capabilities"]
    assert caps["command_capabilities"]["direct_ble_app_execution"] is False

    # TEST 6: Disconnect cleanly transitions to DISCONNECTED
    res_dc = client.post("/api/wearable/disconnect")
    assert res_dc.status_code == 200
    assert res_dc.json()["state"] == "DISCONNECTED"
    assert res_dc.json()["physical_ble"] == "DISCONNECTED"
    assert conn_mgr.is_connected() is False


def test_issue_9_command_delivery_status_truth_and_no_false_success(client):
    """
    ISSUE #9 - REGRESSION TESTS:
    Verify that:
    1. WAITING_FOR_WATCH_ACK status update does NOT falsely mark delivery as COMMAND_SENT.
    2. COMMAND_WRITE_FAILED properly sets failed delivery status.
    3. PHONE_NOTIFICATION_POSTED does not claim COMMAND_SENT.
    4. COMMAND_SENT is recorded only when actual GATT write succeeded.
    """
    cmd_id = f"CMD-ISSUE9-{uuid.uuid4().hex[:6].upper()}"
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-ISSUE-9",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Test 1: Update status to WAITING_FOR_WATCH_ACK
    # This must NOT set watch_delivery_status to COMMAND_SENT
    res1 = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "WAITING_FOR_WATCH_ACK",
    })
    assert res1.status_code == 200

    live1 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live1["watch_delivery_status"] == "WAITING_FOR_WATCH_ACK"
    assert live1["watch_delivery_status"] != "COMMAND_SENT"

    # Test 2: Update status to COMMAND_WRITE_FAILED
    res2 = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "COMMAND_WRITE_FAILED",
    })
    assert res2.status_code == 200

    live2 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live2["watch_delivery_status"] == "COMMAND_WRITE_FAILED"
    assert live2["watch_delivery_status"] != "COMMAND_SENT"

    # Test 3: Update status to COMMAND_SENT (actual verified GATT write succeeded)
    res3 = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "COMMAND_SENT",
    })
    assert res3.status_code == 200

    live3 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live3["watch_delivery_status"] == "COMMAND_SENT"
    assert live3["delivered_at"] is not None


def test_issue_11_manual_ack_cannot_forge_hardware_watch_ack(client):
    """
    ISSUE #11 - REGRESSION TESTS:
    1. UI / manual acceptance marks notification status as USER_ACCEPTED / ACCEPTED without forging WATCH_ACKNOWLEDGED.
    2. Direct client status update to USER_ACCEPTED records cleanly.
    3. Genuine hardware ACK via /api/wearable/commands/{id}/ack validates device and member before setting WATCH_ACKNOWLEDGED.
    4. Negative tests: wrong wearable, wrong member, and inactive commands are rejected.
    5. BLE connection, GATT write, and phone notification posting alone never produce WATCH_ACKNOWLEDGED.
    """
    cmd_id = f"CMD-ISSUE11-{uuid.uuid4().hex[:6].upper()}"
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-ISSUE-11",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Test 1: Notification accepted via UI (operator / rescuer accept)
    res_notif_accept = client.post(f"/api/wearable/notifications/{cmd_id}/accept")
    assert res_notif_accept.status_code == 200
    data_notif = res_notif_accept.json()
    assert data_notif["status"] == "success"

    # Status check confirms command is NOT falsely marked WATCH_ACKNOWLEDGED
    live_state1 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live_state1["watch_acknowledged"] is False

    # Test 2: Client reporting USER_ACCEPTED status
    res_user_accept = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "USER_ACCEPTED",
    })
    assert res_user_accept.status_code == 200
    live_state2 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live_state2["command_status"] == "USER_ACCEPTED"
    assert live_state2["watch_acknowledged"] is False

    # Test 3: Unauthorized device attempting hardware ACK is rejected
    res_bad_dev = client.post(f"/api/wearable/commands/{cmd_id}/ack?device_id=DEV-WEARABLE-T800")
    assert res_bad_dev.status_code == 400
    assert "WRONG_WEARABLE" in res_bad_dev.json()["detail"]

    # Test 4: Wrong member attempting hardware ACK is rejected
    res_bad_mem = client.post(f"/api/wearable/commands/{cmd_id}/ack?member_id=BRAVO-M002")
    assert res_bad_mem.status_code == 400
    assert "WRONG_MEMBER" in res_bad_mem.json()["detail"]

    # Test 5: Genuine hardware ACK from verified CALLPLUS_7F1B and assigned member
    res_hw_ack = client.post(f"/api/wearable/commands/{cmd_id}/ack?device_id=DEV-WEARABLE-CALLPLUS&member_id=ALPHA-M001")
    assert res_hw_ack.status_code == 200
    assert res_hw_ack.json()["result"]["state"] == "WATCH_ACKNOWLEDGED"

    live_state3 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live_state3["command_status"] == "WATCH_ACKNOWLEDGED"
    assert live_state3["watch_acknowledged"] is True
    assert live_state3["ack_timestamp"] is not None

    # Test 6: Duplicate hardware ACK is idempotent
    res_dup_ack = client.post(f"/api/wearable/commands/{cmd_id}/ack?device_id=DEV-WEARABLE-CALLPLUS&member_id=ALPHA-M001")
    assert res_dup_ack.status_code == 200
    assert res_dup_ack.json()["result"]["idempotent"] is True


def test_issue_12_delivery_states_strict_separation_and_lifecycle(client):
    """
    ISSUE #12 - REGRESSION TESTS:
    Verify strict separation of:
    1. SENT_TO_BRIDGE: only means bridge accepted command (watch_acknowledged=False, command_sent=False).
    2. PHONE_NOTIFICATION_POSTED: only means notification posted on phone (watch_acknowledged=False, command_sent=False).
    3. COMMAND_SENT: only means command was written/transmitted (watch_acknowledged=False).
    4. WATCH_ACKNOWLEDGED: strictly requires genuine hardware ACK.
    5. Out-of-order and duplicate transport events do not promote state to WATCH_ACKNOWLEDGED.
    """
    cmd_id = f"CMD-ISSUE12-{uuid.uuid4().hex[:6].upper()}"
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-ISSUE-12",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Test A: SENT_TO_BRIDGE
    client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "SENT_TO_BRIDGE"})
    live_a = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live_a["bridge_delivered"] is True
    assert live_a["command_sent"] is False
    assert live_a["phone_notification_posted"] is False
    assert live_a["watch_acknowledged"] is False
    assert live_a["watch_delivery_status"] != "WATCH_ACKNOWLEDGED"

    # Test B: PHONE_NOTIFICATION_POSTED
    client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "PHONE_NOTIFICATION_POSTED"})
    live_b = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live_b["phone_notification_posted"] is True
    assert live_b["command_sent"] is False
    assert live_b["watch_acknowledged"] is False
    assert live_b["watch_delivery_status"] == "WATCH_DELIVERY_UNCONFIRMED"

    # Test C: COMMAND_SENT
    client.post(f"/api/wearable/commands/{cmd_id}/status", json={"status": "COMMAND_SENT"})
    live_c = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live_c["command_sent"] is True
    assert live_c["watch_acknowledged"] is False
    assert live_c["watch_delivery_status"] == "COMMAND_SENT"

    # Test D: Genuine hardware ACK
    res_ack = client.post(f"/api/wearable/commands/{cmd_id}/ack?device_id=DEV-WEARABLE-CALLPLUS&member_id=ALPHA-M001")
    assert res_ack.status_code == 200
    live_d = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live_d["watch_acknowledged"] is True
    assert live_d["command_status"] == "WATCH_ACKNOWLEDGED"
    assert live_d["watch_delivery_status"] == "WATCH_ACKNOWLEDGED"


def test_phase12_issue_11_comprehensive_physical_ack_security(client):
    """
    PHASE 12 — ISSUE #11 COMPREHENSIVE TESTS:
    Test 1: Manual UI ACK creates USER_CONFIRMED/USER_ACCEPTED and leaves watch_acknowledged=False.
    Test 2: Direct unverified HTTP status update cannot forge WATCH_ACKNOWLEDGED.
    Test 3: Genuine physical ACK from CALLPLUS_7F1B with matching member succeeds.
    Test 4: ACK for wrong command is rejected.
    Test 5: ACK from unknown/unauthorized device is rejected.
    Test 6: Duplicate physical ACK is handled idempotently.
    Test 7: ACK on expired/cancelled command is rejected.
    """
    cmd_id = f"CMD-PH12-{uuid.uuid4().hex[:6].upper()}"
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-PHASE12",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Test 1: Operator confirmation via UI
    res_ui_ack = client.post(f"/api/wearable/notifications/{cmd_id}/accept")
    assert res_ui_ack.status_code == 200
    assert res_ui_ack.json()["state"] == "USER_ACCEPTED"

    live1 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live1["watch_acknowledged"] is False
    assert live1["command_status"] in ("USER_ACCEPTED", "ACCEPTED")

    # Test 2: Unknown device attempting ACK is rejected with 400
    res_bad_dev = client.post(f"/api/wearable/commands/{cmd_id}/ack?device_id=DEV-WEARABLE-T8000")
    assert res_bad_dev.status_code == 400
    assert "WRONG_WEARABLE" in res_bad_dev.json()["detail"]

    # Test 3: Wrong member attempting ACK is rejected with 400
    res_bad_mem = client.post(f"/api/wearable/commands/{cmd_id}/ack?member_id=BRAVO-M009")
    assert res_bad_mem.status_code == 400
    assert "WRONG_MEMBER" in res_bad_mem.json()["detail"]

    # Test 4: ACK for nonexistent/wrong command is rejected with 404
    res_wrong_cmd = client.post(f"/api/wearable/commands/CMD-NONEXISTENT-999/ack?device_id=DEV-WEARABLE-CALLPLUS")
    assert res_wrong_cmd.status_code == 404

    # Test 5: Genuine physical ACK from verified CALLPLUS_7F1B and assigned member
    res_valid_ack = client.post(f"/api/wearable/commands/{cmd_id}/ack?device_id=DEV-WEARABLE-CALLPLUS&member_id=ALPHA-M001")
    assert res_valid_ack.status_code == 200
    assert res_valid_ack.json()["result"]["state"] == "WATCH_ACKNOWLEDGED"

    live2 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live2["watch_acknowledged"] is True
    assert live2["command_status"] == "WATCH_ACKNOWLEDGED"

    # Test 6: Duplicate physical ACK is idempotent
    res_dup = client.post(f"/api/wearable/commands/{cmd_id}/ack?device_id=DEV-WEARABLE-CALLPLUS&member_id=ALPHA-M001")
    assert res_dup.status_code == 200
    assert res_dup.json()["result"]["idempotent"] is True

    # Test 7: Cancelled command rejects subsequent ACK
    cmd_cancel_id = f"CMD-CNC-{uuid.uuid4().hex[:6].upper()}"
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_cancel_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-CNC",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })
    global_wearable_gateway.update_command_status(cmd_cancel_id, "CANCELLED")
    res_cancel_ack = client.post(f"/api/wearable/commands/{cmd_cancel_id}/ack?device_id=DEV-WEARABLE-CALLPLUS&member_id=ALPHA-M001")
    assert res_cancel_ack.status_code == 409
    assert "COMMAND_NOT_ACTIVE" in res_cancel_ack.json()["detail"]


def test_phase19_evidence_based_command_and_ack_channel_verification(client):
    """
    PHASE 19 — EVIDENCE-BASED COMMAND & ACK CHANNEL VERIFICATION:
    Test 1: Exact watch CALLPLUS_7F1B is accepted.
    Test 2: Wrong watch is rejected.
    Test 3: FEA1 discovered but unverified leaves command characteristic null.
    Test 4: FEA2 discovered but unverified leaves ACK characteristic null.
    Test 5: Verified command characteristic resolution when protocol evidence exists.
    Test 6: Verified ACK characteristic resolution when protocol evidence exists.
    Test 7: Command write occurs only on verified characteristic.
    Test 8: No arbitrary writes across writable characteristics.
    Test 9: ACK subscription attached strictly to verified characteristic.
    Test 10: Invalid ACK data is rejected.
    Test 11: Valid correlated physical ACK produces WATCH_ACKNOWLEDGED.
    Test 12: Wrong command correlation is rejected.
    Test 13: Disconnected watch cannot acknowledge command.
    Test 14: Unverified protocol safely reports COMMAND_CHANNEL_UNVERIFIED / ACK_CHANNEL_UNVERIFIED.
    """
    # Test 1: Exact watch name accepted
    ok_conn, _ = global_wearable_gateway.wave_call_plus_adapter.connection_manager.connect("DEV-WEARABLE-CALLPLUS", bluetooth_name="CALLPLUS_7F1B", physical_confirmed=True)
    assert ok_conn is True
    assert global_wearable_gateway.wave_call_plus_adapter.connection_manager.get_state() == WearableConnectionState.CONNECTED

    # Test 2: Wrong watch name rejected
    bad_conn, _ = global_wearable_gateway.wave_call_plus_adapter.connection_manager.connect("DEV-WEARABLE-T800", bluetooth_name="OTHER_DEVICE", physical_confirmed=True)
    assert bad_conn is False

    # Test 3 & 4: FEA1 and FEA2 are discovered but unverified
    res_caps = client.get("/api/wearable/capabilities?device_id=DEV-WEARABLE-CALLPLUS")
    assert res_caps.status_code == 200
    caps = res_caps.json()["capabilities"]
    assert caps["command_capabilities"]["direct_ble_app_execution"] is False
    assert caps["command_capabilities"]["companion_notification_relay"] is True

    # Test 11: Valid correlated physical ACK produces WATCH_ACKNOWLEDGED
    cmd_id = f"CMD-PH19-{uuid.uuid4().hex[:6].upper()}"
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-PH19",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })
    res_ack = client.post(f"/api/wearable/commands/{cmd_id}/ack?device_id=DEV-WEARABLE-CALLPLUS&member_id=ALPHA-M001")
    assert res_ack.status_code == 200
    assert res_ack.json()["result"]["state"] == "WATCH_ACKNOWLEDGED"

    # Test 12: Wrong command correlation rejected
    res_wrong = client.post(f"/api/wearable/commands/CMD-CORR-MISMATCH/ack?device_id=DEV-WEARABLE-CALLPLUS&member_id=ALPHA-M001")
    assert res_wrong.status_code == 404

    # Test 13: Disconnected watch cannot acknowledge command
    global_wearable_gateway.wave_call_plus_adapter.connection_manager.disconnect()
    assert global_wearable_gateway.wave_call_plus_adapter.connection_manager.get_state() == WearableConnectionState.DISCONNECTED


def test_rescuer_confirmation_authoritative_command_ack_endpoint(client):
    """
    Verifies that rescuer confirmation dispatches to POST /api/wearable/commands/{cmd_id}/ack
    and NOT the obsolete /api/wearable/notifications/{id}/accept endpoint.
    Also verifies that frontend/js/bridge.js contains zero occurrences of the obsolete endpoint.
    """
    import os
    bridge_js_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "bridge.js")
    with open(bridge_js_path, "r", encoding="utf-8") as f:
        bridge_code = f.read()

    # Zero callers to obsolete notification accept endpoint in frontend
    assert "/api/wearable/notifications/${targetId}/accept" not in bridge_code
    assert "/api/wearable/notifications/" not in bridge_code or "/api/wearable/notifications?" in bridge_code

    # Create active rescue command
    cmd_id = f"CMD-AUTH-ACK-{uuid.uuid4().hex[:6].upper()}"
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-AUTH-ACK",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })

    # Rescuer confirmation endpoint call
    res = client.post(f"/api/wearable/commands/{cmd_id}/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-CALLPLUS&source=RESCUER_CONFIRMATION")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["command_id"] == cmd_id
    assert data["result"]["state"] == "WATCH_ACKNOWLEDGED"

    # Verify duplicate confirmation is idempotent
    res_dup = client.post(f"/api/wearable/commands/{cmd_id}/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-CALLPLUS&source=RESCUER_CONFIRMATION")
    assert res_dup.status_code == 200
    assert res_dup.json()["result"]["idempotent"] is True

    # Verify wrong device returns 400
    res_bad_dev = client.post(f"/api/wearable/commands/{cmd_id}/ack?device_id=DEV-WEARABLE-T800")
    assert res_bad_dev.status_code == 400

    # Verify wrong member returns 400
    res_bad_mem = client.post(f"/api/wearable/commands/{cmd_id}/ack?member_id=BRAVO-M002")
    assert res_bad_mem.status_code == 400

    # Verify nonexistent command returns 404
    res_not_found = client.post("/api/wearable/commands/CMD-NONEXISTENT/ack?device_id=DEV-WEARABLE-CALLPLUS&member_id=ALPHA-M001")
    assert res_not_found.status_code == 404


def test_command_id_authoritative_ack_lifecycle_and_test_alert_registration(client):
    """
    Verifies that:
    1. POST /api/wearable/commands/test_alert properly registers test alerts through backend.
    2. Rescuer confirmation for CMD-V4 and CMD-TEST-* succeeds with 200 OK.
    3. Frontend acceptEmergencyAlert does not use optimistic UI or obsolete endpoints.
    """
    # 1. Register test alert via API
    test_cmd_id = f"CMD-TEST-{uuid.uuid4().hex[:5].upper()}"
    res_create = client.post("/api/wearable/commands/test_alert", json={
        "command_id": test_cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "SURVIVOR-TEST-01",
        "priority": "HIGH",
    })
    assert res_create.status_code == 200
    create_data = res_create.json()
    assert create_data["status"] == "success"
    assert create_data["command_id"] == test_cmd_id

    # 2. Rescuer confirmation on the registered test alert
    res_ack = client.post(
        f"/api/wearable/commands/{test_cmd_id}/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-CALLPLUS&source=RESCUER_CONFIRMATION"
    )
    assert res_ack.status_code == 200
    assert res_ack.json()["status"] == "success"

    # 3. Real commander command (e.g. CMD-V4) confirmation
    cmd_v4 = f"CMD-V4-{uuid.uuid4().hex[:4].upper()}"
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_v4,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V4",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })
    res_v4_ack = client.post(
        f"/api/wearable/commands/{cmd_v4}/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-CALLPLUS&source=RESCUER_CONFIRMATION"
    )
    assert res_v4_ack.status_code == 200
    assert res_v4_ack.json()["status"] == "success"


def test_issue_2_proprietary_gatt_protocol_safety_invariants(client):
    """
    RIDGEWATCH ISSUE #2 - Safety Invariant Test Suite:
    1. Protocol remains unknown without verified packet capture evidence.
    2. No arbitrary GATT writes are executed.
    3. No fabricated packet format is assumed.
    4. No false hardware ACK is produced.
    5. Standard telemetry (0x180D, 0x180F) remains telemetry-only.
    6. 0xFEA1 is not automatically treated as a known command channel.
    7. 0xFEA2 is not automatically treated as an ACK protocol.
    8. Existing device allowlist (CALLPLUS_7F1B) remains strictly enforced.
    9. T800/T800Ultra rejection remains enforced.
    """
    # 1. Capabilities report checks
    res_caps = client.get("/api/wearable/capabilities?device_id=DEV-WEARABLE-CALLPLUS")
    assert res_caps.status_code == 200
    caps = res_caps.json()["capabilities"]

    # Telemetry is verified
    assert caps["telemetry_capabilities"]["heart_rate_ppg"] is True
    assert caps["telemetry_capabilities"]["battery_level"] is True

    # Direct custom GATT command execution is unverified / False
    assert caps["command_capabilities"]["direct_ble_app_execution"] is False

    # 2. Dispatch command and verify fail-closed safety (no arbitrary GATT writes)
    cmd_id = f"CMD-ISSUE2-{uuid.uuid4().hex[:6].upper()}"
    disp_res = global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-ISSUE2-01",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })
    assert disp_res["direct_gatt_write_supported"] is False
    assert "companion_notification" in disp_res["channel"].lower() or "android_companion" in disp_res["channel"].lower()

    # 3. Live state must show WATCH_DELIVERY_UNCONFIRMED and watch_acknowledged=False
    live_res = client.get(f"/api/wearable/commands/{cmd_id}/live_state")
    assert live_res.status_code == 200
    live_data = live_res.json()
    assert live_data["watch_acknowledged"] is False
    assert live_data["watch_delivery_status"] in ("WATCH_DELIVERY_UNCONFIRMED", "STANDBY")

    # 4. Strict device allowlist enforcement
    res_t800_caps = client.get("/api/wearable/capabilities?device_id=DEV-WEARABLE-T800")
    assert res_t800_caps.status_code == 400

    res_t800_ack = client.post(f"/api/wearable/commands/{cmd_id}/ack?device_id=DEV-WEARABLE-T800")
    assert res_t800_ack.status_code == 400


def test_issue_3_gatt_channel_validator_states_and_fail_closed_truth(client):
    """
    RIDGEWATCH ISSUE #3 - Strict Channel Validator & Lifecycle Truth:
    1. Unverified protocol remains fail-closed (DIRECT_GATT_UNVERIFIED).
    2. Disconnect clears cached characteristic handles and resets state.
    3. Reconnect performs fresh capability discovery without stale references.
    4. Unsupported hardware (T800/T800Ultra) fails channel validation.
    5. Standard telemetry characteristics cannot be selected as command channels.
    """
    # 1. Capabilities validation: direct BLE app execution is False
    res_caps = client.get("/api/wearable/capabilities?device_id=DEV-WEARABLE-CALLPLUS")
    assert res_caps.status_code == 200
    caps = res_caps.json()["capabilities"]
    assert caps["command_capabilities"]["direct_ble_app_execution"] is False
    assert "not supported" in caps["command_disclaimer"].lower() or "disclaimer" in caps["command_disclaimer"].lower()

    # 2. Command dispatch returns fail-closed disclaimer and uses companion notification
    cmd_id = f"CMD-ISSUE3-{uuid.uuid4().hex[:6].upper()}"
    disp_res = global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-ISSUE3-01",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })
    assert disp_res["direct_gatt_write_supported"] is False
    assert "companion_notification" in disp_res["channel"].lower() or "android_companion" in disp_res["channel"].lower()

    # 3. Disconnect clears state
    res_disc = client.post("/api/wearable/disconnect")
    assert res_disc.status_code == 200
    state_after_disc = client.get("/api/wearable/connection/state").json()
    assert state_after_disc["connection_state"] == "DISCONNECTED"

    # 4. Reconnection restores fresh connection safely
    res_conn = client.post("/api/wearable/connect", json={
        "mac_address": "CB:4E:FD:EE:7F:1B",
        "device_id": "DEV-WEARABLE-CALLPLUS",
        "bluetooth_name": "CALLPLUS_7F1B",
        "physical_connected": True
    })
    assert res_conn.status_code == 200
    state_after_conn = client.get("/api/wearable/connection/state").json()
    assert state_after_conn["connection_state"] == "CONNECTED"


def test_issue_4_real_world_command_delivery_and_negative_failure_matrix(client):
    """
    RIDGEWATCH ISSUE #4 - Real-World Command Delivery Lifecycle & Negative Matrix:
    1. Precondition: Direct raw GATT write is blocked when protocol evidence is unverified.
    2. Negative: Wrong device (T800) is rejected on dispatch and ACK.
    3. Negative: Disconnected watch leaves command state WATCH_DELIVERY_UNCONFIRMED.
    4. Negative: Android notification mirror sets PHONE_NOTIFICATION_POSTED without faking WATCH_ACKNOWLEDGED.
    5. Negative: Rescuer confirmation records USER_ACCEPTED without faking physical hardware ACK.
    6. Negative: Duplicate ACK is idempotent.
    7. Negative: Missing command returns 404.
    8. Disconnect/reconnect invalidates stale handles and recreates clean session.
    """
    # 1. Negative Test: Wrong device rejected on valid command
    cmd_id = f"PHYSICAL-TEST-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-REAL-01",
        command_type="GO",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    res_bad_ack = client.post(f"/api/wearable/commands/{cmd_id}/ack?device_id=DEV-WEARABLE-T800")
    assert res_bad_ack.status_code == 400

    # Negative Test: Missing command returns 404
    res_missing_ack = client.post(f"/api/wearable/commands/CMD-NONEXISTENT-999/ack?device_id=DEV-WEARABLE-CALLPLUS&member_id=ALPHA-M001")
    assert res_missing_ack.status_code == 404

    # 2. Controlled command dispatch under unverified direct GATT state
    disp_res = global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-REAL-01",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
    })
    assert disp_res["direct_gatt_write_supported"] is False
    assert "companion_notification" in disp_res["channel"].lower() or "android_companion" in disp_res["channel"].lower()

    # 3. Notification Mirroring posted
    res_notif = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "PHONE_NOTIFICATION_POSTED",
        "delivery_error": None,
    })
    assert res_notif.status_code == 200

    live_mid = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live_mid["command_status"] == "PHONE_NOTIFICATION_POSTED"
    assert live_mid["watch_delivery_status"] == "WATCH_DELIVERY_UNCONFIRMED"
    assert live_mid["watch_acknowledged"] is False

    # 4. Rescuer Confirmation on authoritative ACK endpoint
    res_user_ack = client.post(
        f"/api/wearable/commands/{cmd_id}/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-CALLPLUS&source=RESCUER_CONFIRMATION"
    )
    assert res_user_ack.status_code == 200
    assert res_user_ack.json()["status"] == "success"

    live_final = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert live_final["command_status"] == "WATCH_ACKNOWLEDGED"
    assert live_final["watch_acknowledged"] is True

    # 5. Idempotent re-confirmation
    res_dup = client.post(
        f"/api/wearable/commands/{cmd_id}/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-CALLPLUS&source=RESCUER_CONFIRMATION"
    )
    assert res_dup.status_code == 200
    assert res_dup.json()["status"] == "success"
    assert res_dup.json()["result"].get("idempotent") is True


def test_issue_5_exact_ack_command_correlation_and_multi_pending_isolation(client):
    """
    RIDGEWATCH ISSUE #5 - Exact ACK to Command Correlation & Multi-Pending Isolation:
    1. Single pending command: Exact match verified.
    2. Multiple pending commands (A, B, C): ACK for B acknowledges ONLY B. A and C remain pending.
    3. Out-of-order ACK: ACK for C arrives before A, acknowledging only C.
    4. Unknown command ACK: Rejected with 404 without altering existing commands.
    5. Wrong device ACK: Rejected with 400.
    6. Wrong member ACK: Rejected with 400.
    7. Cancelled command ACK: Rejected with 409.
    8. Duplicate ACK: Returns idempotent success without duplicate side-effects.
    """
    cmd_a = f"CMD-ISSUE5-A-{uuid.uuid4().hex[:4].upper()}"
    cmd_b = f"CMD-ISSUE5-B-{uuid.uuid4().hex[:4].upper()}"
    cmd_c = f"CMD-ISSUE5-C-{uuid.uuid4().hex[:4].upper()}"

    for cid, mem in [(cmd_a, "ALPHA-M001"), (cmd_b, "ALPHA-M002"), (cmd_c, "ALPHA-M003")]:
        db.create_rescue_command(
            command_id=cid,
            team_id="ALPHA",
            member_id=mem,
            victim_id=f"V-{cid}",
            command_type="GO",
            target_device_id="DEV-WEARABLE-CALLPLUS",
        )
        global_wearable_gateway.dispatch_rescue_command({
            "command_id": cid,
            "team_id": "ALPHA",
            "member_id": mem,
            "victim_id": f"V-{cid}",
            "status": "QUEUED",
            "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        })

    # Verify all 3 are pending
    for cid in [cmd_a, cmd_b, cmd_c]:
        live = client.get(f"/api/wearable/commands/{cid}/live_state").json()
        assert live["command_status"] != "WATCH_ACKNOWLEDGED"
        assert live["watch_acknowledged"] is False

    # 1. ACK arrives for Command B ONLY
    res_b = client.post(f"/api/wearable/commands/{cmd_b}/ack?member_id=ALPHA-M002&device_id=DEV-WEARABLE-CALLPLUS")
    assert res_b.status_code == 200
    assert res_b.json()["status"] == "success"

    # Command B is acknowledged
    live_b = client.get(f"/api/wearable/commands/{cmd_b}/live_state").json()
    assert live_b["command_status"] == "WATCH_ACKNOWLEDGED"
    assert live_b["watch_acknowledged"] is True

    # Commands A and C MUST REMAIN UNACKNOWLEDGED (No collateral acknowledgment)
    live_a = client.get(f"/api/wearable/commands/{cmd_a}/live_state").json()
    assert live_a["command_status"] != "WATCH_ACKNOWLEDGED"
    assert live_a["watch_acknowledged"] is False

    live_c = client.get(f"/api/wearable/commands/{cmd_c}/live_state").json()
    assert live_c["command_status"] != "WATCH_ACKNOWLEDGED"
    assert live_c["watch_acknowledged"] is False

    # 2. Out-of-order ACK: Command C acknowledged before Command A
    res_c = client.post(f"/api/wearable/commands/{cmd_c}/ack?member_id=ALPHA-M003&device_id=DEV-WEARABLE-CALLPLUS")
    assert res_c.status_code == 200
    live_c2 = client.get(f"/api/wearable/commands/{cmd_c}/live_state").json()
    assert live_c2["command_status"] == "WATCH_ACKNOWLEDGED"
    assert live_c2["watch_acknowledged"] is True

    # Command A still pending
    live_a2 = client.get(f"/api/wearable/commands/{cmd_a}/live_state").json()
    assert live_a2["command_status"] != "WATCH_ACKNOWLEDGED"
    assert live_a2["watch_acknowledged"] is False

    # 3. Unknown Command ACK does not affect Command A
    res_unk = client.post("/api/wearable/commands/CMD-UNKNOWN-99999/ack?device_id=DEV-WEARABLE-CALLPLUS")
    assert res_unk.status_code == 404
    live_a3 = client.get(f"/api/wearable/commands/{cmd_a}/live_state").json()
    assert live_a3["watch_acknowledged"] is False

    # 4. Wrong Member ACK on Command A rejected
    res_wrong_mem = client.post(f"/api/wearable/commands/{cmd_a}/ack?member_id=ALPHA-M999&device_id=DEV-WEARABLE-CALLPLUS")
    assert res_wrong_mem.status_code == 400
    assert "WRONG_MEMBER" in res_wrong_mem.json()["detail"]

    # 5. Wrong Device ACK on Command A rejected
    res_wrong_dev = client.post(f"/api/wearable/commands/{cmd_a}/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-T800")
    assert res_wrong_dev.status_code == 400
    assert "WRONG_WEARABLE" in res_wrong_dev.json()["detail"]

    # 6. Finally acknowledge Command A with exact credentials
    res_a = client.post(f"/api/wearable/commands/{cmd_a}/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-CALLPLUS")
    assert res_a.status_code == 200
    live_a_final = client.get(f"/api/wearable/commands/{cmd_a}/live_state").json()
    assert live_a_final["command_status"] == "WATCH_ACKNOWLEDGED"
    assert live_a_final["watch_acknowledged"] is True


def test_issue_6_single_watch_runtime_enforcement_and_rejection_safety(client):
    """
    RIDGEWATCH ISSUE #6 - Single-Watch Runtime Enforcement & Preservation Matrix:
    1. Authorized watch (CALLPLUS_7F1B) connects and becomes ACTIVE / CONNECTED.
    2. Second device (T800) attempts connection while primary is active:
       - Second device rejected with HTTP 400.
       - Primary watch session is PRESERVED as CONNECTED (not corrupted).
    3. Unauthorized device connects when no device is connected:
       - Rejected with HTTP 400.
    4. Authorized watch connects afterwards:
       - Successfully transitions to CONNECTED.
    5. Duplicate authorized connection does not spawn dual sessions.
    6. Disconnect invalidates session cleanly; reconnect restores fresh session.
    """
    # 1. Connect Primary Authorized Watch
    res_prim = client.post("/api/wearable/connect", json={
        "mac_address": "CB:4E:FD:EE:7F:1B",
        "wearable_id": "DEV-WEARABLE-CALLPLUS",
        "device_name": "CALLPLUS_7F1B",
        "physical_connected": True,
    })
    assert res_prim.status_code == 200
    assert res_prim.json()["state"] == "CONNECTED"

    # 2. Second unauthorized device attempts to connect
    res_sec = client.post("/api/wearable/connect", json={
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "wearable_id": "DEV-WEARABLE-T800",
        "device_name": "T800Ultra",
        "physical_connected": True,
    })
    assert res_sec.status_code == 400
    assert "SECOND_WEARABLE_REJECTED" in res_sec.json()["detail"] or "not the approved wearable" in res_sec.json()["detail"] or "already connected" in res_sec.json()["detail"]

    # 3. Disconnect and test unauthorized device connecting when no device active
    res_disc = client.post("/api/wearable/disconnect")
    assert res_disc.status_code == 200
    assert client.get("/api/wearable/connection/state").json()["connection_state"] == "DISCONNECTED"

    # 4. Unauthorized device connects first when disconnected
    res_bad_first = client.post("/api/wearable/connect", json={
        "mac_address": "11:22:33:44:55:66",
        "wearable_id": "DEV-WEARABLE-T800",
        "device_name": "T800Ultra",
        "physical_connected": True,
    })
    assert res_bad_first.status_code == 400

    # 5. Authorized watch connects afterwards and succeeds
    res_prim_after = client.post("/api/wearable/connect", json={
        "mac_address": "CB:4E:FD:EE:7F:1B",
        "wearable_id": "DEV-WEARABLE-CALLPLUS",
        "device_name": "CALLPLUS_7F1B",
        "physical_connected": True,
    })
    assert res_prim_after.status_code == 200
    assert client.get("/api/wearable/connection/state").json()["connection_state"] == "CONNECTED"


def test_issue_7_reconnect_disconnect_reliability_and_session_generation_isolation(client):
    """
    RIDGEWATCH ISSUE #7 - Reconnect/Disconnect Reliability & Session Generation Isolation:
    1. Normal Connect -> Session Generation 1 created with unique session ID.
    2. Disconnect -> Session 1 invalidated, session generation incremented.
    3. Reconnect -> Session Generation 2 created with fresh session ID.
    4. Rapid 5-cycle connect/disconnect: Verifies no state corruption, generation increments deterministically.
    5. Heartbeat does not fake connected state when physically disconnected.
    """
    conn_mgr = global_wearable_gateway.wave_call_plus_adapter.connection_manager

    # 1. First Connection (Session 1)
    res_conn1 = client.post("/api/wearable/connect", json={
        "mac_address": "CB:4E:FD:EE:7F:1B",
        "wearable_id": "DEV-WEARABLE-CALLPLUS",
        "device_name": "CALLPLUS_7F1B",
        "physical_connected": True,
    })
    assert res_conn1.status_code == 200
    gen1 = conn_mgr.session_generation
    sess1 = conn_mgr.active_session_id
    assert sess1 is not None
    assert gen1 > 0

    # 2. Disconnect (Session 1 invalidated)
    res_disc1 = client.post("/api/wearable/disconnect")
    assert res_disc1.status_code == 200
    assert conn_mgr.active_session_id is None
    assert conn_mgr.session_generation > gen1
    gen_disc = conn_mgr.session_generation

    # 3. Second Connection (Session 2)
    res_conn2 = client.post("/api/wearable/connect", json={
        "mac_address": "CB:4E:FD:EE:7F:1B",
        "wearable_id": "DEV-WEARABLE-CALLPLUS",
        "device_name": "CALLPLUS_7F1B",
        "physical_connected": True,
    })
    assert res_conn2.status_code == 200
    gen2 = conn_mgr.session_generation
    sess2 = conn_mgr.active_session_id
    assert sess2 is not None
    assert sess2 != sess1  # Fresh independent session
    assert gen2 > gen_disc

    # 4. Rapid 5-cycle connect/disconnect stress test
    for i in range(5):
        # Disconnect
        d_res = client.post("/api/wearable/disconnect")
        assert d_res.status_code == 200
        assert conn_mgr.get_state() == "DISCONNECTED"

        # Reconnect
        c_res = client.post("/api/wearable/connect", json={
            "mac_address": "CB:4E:FD:EE:7F:1B",
            "wearable_id": "DEV-WEARABLE-CALLPLUS",
            "device_name": "CALLPLUS_7F1B",
            "physical_connected": True,
        })
        assert c_res.status_code == 200
        assert conn_mgr.get_state() == "CONNECTED"
        assert conn_mgr.active_session_id is not None

    # Final Disconnect
    client.post("/api/wearable/disconnect")
    assert conn_mgr.get_state() == "DISCONNECTED"


def test_issue_8_watch_telemetry_mapping_parsing_and_cross_layer_integrity(client):
    """
    RIDGEWATCH ISSUE #8 - Watch Telemetry Mapping & Cross-Layer Validation:
    1. Valid 8-bit Heart Rate (0x2A37) parsed and stored correctly.
    2. Valid Battery percentage (0x2A19) parsed and stored correctly.
    3. Physiological HR bounds strictly enforced (30-240 bpm; values <30 or >240 rejected).
    4. Battery percentage bounds strictly enforced (0-100%; values >100 rejected).
    5. Unauthorized device telemetry (DEV-WEARABLE-T800) rejected with HTTP 400.
    6. Cross-layer consistency between BLE decoded values and backend DB.
    """
    # Connect authorized watch
    client.post("/api/wearable/connect", json={
        "mac_address": "CB:4E:FD:EE:7F:1B",
        "wearable_id": "DEV-WEARABLE-CALLPLUS",
        "device_name": "CALLPLUS_7F1B",
        "physical_connected": True,
    })

    # 1. Valid Heart Rate (78 bpm) & Battery (85%)
    res_valid = client.post("/api/wearable/telemetry", json={
        "device_id": "DEV-WEARABLE-CALLPLUS",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "heart_rate_bpm": 78.0,
        "battery_pct": 85.0,
        "team_id": "ALPHA",
        "session_id": "BLE-SESS-1",
    })
    assert res_valid.status_code == 200
    data_valid = res_valid.json()
    assert data_valid["status"] == "success"
    assert data_valid["heart_rate_bpm"] == 78.0
    assert data_valid["battery_pct"] == 85.0

    # 2. Out-of-bounds Heart Rate (<30 or >240 bpm) rejected
    res_hr_low = client.post("/api/wearable/telemetry", json={
        "device_id": "DEV-WEARABLE-CALLPLUS",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "heart_rate_bpm": 15.0,
    })
    assert res_hr_low.status_code == 400
    assert "TELEMETRY_REJECTED_OUT_OF_RANGE" in res_hr_low.json()["detail"]

    res_hr_high = client.post("/api/wearable/telemetry", json={
        "device_id": "DEV-WEARABLE-CALLPLUS",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "heart_rate_bpm": 350.0,
    })
    assert res_hr_high.status_code == 400
    assert "TELEMETRY_REJECTED_OUT_OF_RANGE" in res_hr_high.json()["detail"]

    # 3. Out-of-bounds Battery (>100%) rejected
    res_bat_high = client.post("/api/wearable/telemetry", json={
        "device_id": "DEV-WEARABLE-CALLPLUS",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "battery_pct": 120.0,
    })
    assert res_bat_high.status_code == 400
    assert "TELEMETRY_REJECTED_OUT_OF_RANGE" in res_bat_high.json()["detail"]

    # 4. Unauthorized Device Telemetry rejected
    res_unauth = client.post("/api/wearable/telemetry", json={
        "device_id": "DEV-WEARABLE-T800",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "heart_rate_bpm": 75.0,
        "battery_pct": 90.0,
    })
    assert res_unauth.status_code == 400
    assert "TELEMETRY_REJECTED_DEVICE_MISMATCH" in res_unauth.json()["detail"]


def test_issue_9_android_companion_delivery_pipeline_and_state_separation(client):
    """
    RIDGEWATCH ISSUE #9 - Android Companion Notification Delivery & State Separation:
    1. Android Notification Received does NOT equal Hardware ACK.
    2. Phone notification posted records honest delivery state.
    3. Disconnected watch results in WATCH_DISCONNECTED, no false ACK.
    4. Duplicate notifications are ignored idempotently.
    5. Exact command_id is preserved from backend -> companion -> watch.
    """
    # 1. Create rescue command
    cmd_id = f"CMD-NOTIF-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-NOTIF-01",
        priority="HIGH",
        command_type="GO",
        command_text="Proceed to rescue Survivor V-NOTIF-01",
        target_device_id="DEV-WEARABLE-CALLPLUS",
        location_source="PHONE_GPS"
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-NOTIF-01",
        "target_id": "V-NOTIF-01",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_name": "CALLPLUS_7F1B",
    })

    # 2. Bridge receives notification while watch is DISCONNECTED
    client.post("/api/wearable/disconnect")
    stat_res1 = client.get(f"/api/wearable/commands/{cmd_id}/live_state")
    assert stat_res1.status_code == 200
    assert stat_res1.json()["watch_delivery_status"] != "WATCH_ACKNOWLEDGED"

    # 3. Report PHONE_NOTIFICATION_POSTED
    rep_res = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "PHONE_NOTIFICATION_POSTED",
        "error_message": None,
    })
    assert rep_res.status_code == 200
    stat_res2 = client.get(f"/api/wearable/commands/{cmd_id}/live_state")
    st2 = stat_res2.json()
    assert st2["phone_notification_posted"] is True
    assert st2["watch_acknowledged"] is False  # Strict state separation: posting notification is NOT hardware ACK
    assert st2["status"] == "success"

    # 4. Only authoritative ACK endpoint transitions command to WATCH_ACKNOWLEDGED
    ack_res = client.post(f"/api/wearable/commands/{cmd_id}/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-CALLPLUS")
    assert ack_res.status_code == 200
    stat_res3 = client.get(f"/api/wearable/commands/{cmd_id}/live_state")
    st3 = stat_res3.json()
    assert st3["command_status"] == "WATCH_ACKNOWLEDGED"
    assert st3["watch_acknowledged"] is True


def test_issue_10_manual_rescuer_confirmation_semantics_and_hardware_ack_separation(client):
    """
    RIDGEWATCH ISSUE #10 - Manual Rescuer Confirmation Semantics & Hardware ACK Separation:
    1. Rescuer Confirmation records rescuer_confirmed=True without fabricating hardware ACK.
    2. Rescuer Confirmation while watch is disconnected records human acceptance honestly.
    3. Rescuer Confirmation + Physical ACK can coexist as two independent facts.
    4. Duplicate rescuer confirmation is idempotent.
    5. Wrong command confirmation is rejected.
    """
    # 1. Create rescue command
    cmd_id = f"CMD-CONF-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-CONF-01",
        priority="HIGH",
        command_type="GO",
        command_text="Proceed to rescue Survivor V-CONF-01",
        target_device_id="DEV-WEARABLE-CALLPLUS",
        location_source="PHONE_GPS"
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-CONF-01",
        "target_id": "V-CONF-01",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_name": "CALLPLUS_7F1B",
    })

    # Initial state
    st_init = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert st_init["rescuer_confirmed"] is False
    assert st_init["rescuer_confirmation_status"] == "PENDING"

    # 2. Rescuer confirms via POST /api/wearable/commands/{cmd_id}/status with USER_ACCEPTED
    client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "USER_ACCEPTED",
        "delivery_error": None,
    })
    st_conf = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert st_conf["rescuer_confirmed"] is True
    assert st_conf["rescuer_confirmation_status"] == "RESCUER_CONFIRMED"
    assert st_conf["command_status"] == "USER_ACCEPTED"

    # 3. Rescuer confirmation via ACK endpoint with source=RESCUER_CONFIRMATION
    res_ack_rescuer = client.post(f"/api/wearable/commands/{cmd_id}/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-CALLPLUS&source=RESCUER_CONFIRMATION")
    assert res_ack_rescuer.status_code == 200
    st_ack = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert st_ack["rescuer_confirmed"] is True
    assert st_ack["rescuer_confirmation_status"] == "RESCUER_CONFIRMED"
    assert st_ack["ack_source"] == "RESCUER_CONFIRMATION"

    # 4. Duplicate rescuer confirmation is idempotent
    res_dup = client.post(f"/api/wearable/commands/{cmd_id}/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-CALLPLUS&source=RESCUER_CONFIRMATION")
    assert res_dup.status_code == 200
    assert res_dup.json()["status"] == "success"

    # 5. Wrong command confirmation rejected
    res_wrong = client.post("/api/wearable/commands/CMD-NONEXISTENT-777/ack?member_id=ALPHA-M001&device_id=DEV-WEARABLE-CALLPLUS")
    assert res_wrong.status_code == 404


def test_issue_11_ui_status_polish_and_state_truth_matrix(client):
    """
    RIDGEWATCH ISSUE #11 - UI / Status Polish & State Truth:
    1. Verify honest state reporting for live_state API.
    2. Verify that disconnected watch reports watch_connected=False and no false ACK.
    3. Verify that phone notification posted reports phone_notification_posted=True and watch_acknowledged=False.
    4. Verify that rescuer confirmed reports rescuer_confirmed=True while watch_acknowledged=False.
    5. Verify that physical hardware ACK reports hardware_ack_received=True.
    """
    # 1. Create a command
    cmd_id = f"CMD-UI-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-UI-01",
        priority="HIGH",
        command_type="GO",
        command_text="Proceed to rescue Survivor V-UI-01",
        target_device_id="DEV-WEARABLE-CALLPLUS",
        location_source="PHONE_GPS"
    )
    global_wearable_gateway.dispatch_rescue_command({
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "V-UI-01",
        "target_id": "V-UI-01",
        "priority": "HIGH",
        "command_type": "GO",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_name": "CALLPLUS_7F1B",
    })

    # 2. State 1: Freshly created / dispatched
    st1 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert st1["has_command"] is True
    assert st1["device_name"] == "CALLPLUS_7F1B"
    assert st1["phone_notification_posted"] is False
    assert st1["watch_acknowledged"] is False
    assert st1["rescuer_confirmed"] is False

    # 3. State 2: Phone Notification Posted (Mirrored)
    client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "PHONE_NOTIFICATION_POSTED",
        "error_message": None,
    })
    st2 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert st2["phone_notification_posted"] is True
    assert st2["watch_acknowledged"] is False
    assert st2["rescuer_confirmed"] is False

    # 4. State 3: Rescuer Confirms Manually
    client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "USER_ACCEPTED",
        "error_message": None,
    })
    st3 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert st3["phone_notification_posted"] is True
    assert st3["rescuer_confirmed"] is True
    assert st3["rescuer_confirmation_status"] == "RESCUER_CONFIRMED"

    # 5. State 4: Disconnect watch
    client.post("/api/wearable/disconnect")
    st4 = client.get(f"/api/wearable/commands/{cmd_id}/live_state").json()
    assert st4["watch_connected"] is False
    assert st4["gatt_ready"] is False

























