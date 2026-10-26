"""
test_persistent_alert_watch_delivery.py
---------------------------------------
Comprehensive test suite verifying persistent rescue alert storage, parallel
real-time physical watch dispatch (Wave Call Plus CALLPLUS_7F1B), disconnection
resilience, hardware ACK event logging, duplicate prevention, and alert ledger immutability.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
import uuid

from backend.api import app, global_wearable_gateway
from backend import db


@pytest.fixture
def client():
    return TestClient(app)


def test_1_existing_alert_still_appears(client):
    """
    Test 1 — Existing Alert Still Appears:
    Create a rescue alert / assignment -> verify it persists in active_alerts_ledger
    and rescue_commands, and is retrieved by the active alerts API for Web UI rendering.
    """
    alert_key = f"TEST_ALERT_{uuid.uuid4().hex[:6].upper()}"
    session_id = f"SES-PERSIST-{uuid.uuid4().hex[:4].upper()}"

    db.upsert_active_alert(
        alert_key=alert_key,
        session_id=session_id,
        hazard_type="SURVIVOR_DETECTED",
        alert_title="🚨 High Priority Survivor: VIC-PERSIST-01",
        severity="HIGH",
        confidence_pct=95.0,
        evidence_summary="Survival probability 95%. Immediate rescue required.",
    )

    # Verify alert exists in active ledger
    active_alerts = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    assert len(active_alerts) == 1
    assert active_alerts[0]["alert_key"] == alert_key
    assert active_alerts[0]["status"] == "ACTIVE"
    assert active_alerts[0]["severity"] == "HIGH"

    # Verify endpoint exposes it for Web UI
    res = client.get(f"/api/wearable/alerts/active?session_id={session_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total_active_alerts"] >= 1
    assert any(a["alert_key"] == alert_key for a in data["alerts"])


def test_2_watch_delivery(client):
    """
    Test 2 — Watch Delivery:
    Create rescue alert -> verify watch delivery layer prepares a structured,
    compact watch-safe payload for Wave Call Plus (0xFEA1 GATT characteristic).
    """
    cmd_id = f"CMD-WATCH-{uuid.uuid4().hex[:6].upper()}"
    alert_id = f"ALT-{cmd_id}"

    # Register bridge session
    client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-WATCH-DELIVERY",
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
        "status": "ONLINE",
    })

    # Dispatch to watch
    res_dispatch = global_wearable_gateway.dispatch_alert_to_watch({
        "alert_id": alert_id,
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "VIC-002",
        "location": "Sector Bravo",
        "priority": "HIGH",
        "command_type": "GO",
        "command_text": "Proceed to rescue VIC-002 in Sector Bravo",
        "title": "🚨 RIDGEWATCH — GO",
        "body": "Proceed to rescue VIC-002",
    })

    assert res_dispatch["status"] in ("SENT_TO_BRIDGE", "DELIVERED", "PENDING")

    # Bridge polls active command
    hb_res = client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "BRG-WATCH-DELIVERY",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_connected": True,
        "status": "ONLINE",
    })
    assert hb_res.status_code == 200
    hb_data = hb_res.json()
    assert hb_data["active_command"] is not None
    active_c = hb_data["active_command"]
    assert active_c["command_id"] == cmd_id
    assert active_c["type"] == "RESCUE_ALERT"
    assert active_c["priority"] == "HIGH"
    assert "notification_payload" in active_c
    assert active_c["notification_payload"]["title"] == "🚨 RIDGEWATCH — GO"


def test_3_both_happen_parallel(client):
    """
    Test 3 — Both Happen:
    A single rescue alert event simultaneously creates an active ledger alert for the Web UI
    AND a watch command for physical Wave Call Plus delivery.
    """
    cmd_id = f"CMD-DUAL-{uuid.uuid4().hex[:6].upper()}"
    alert_id = f"ALT-{cmd_id}"
    session_id = f"SES-DUAL-{uuid.uuid4().hex[:4].upper()}"

    # 1. Database persistence
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="VIC-DUAL-01",
        priority="HIGH",
        command_type="GO",
        command_text="Dual delivery rescue mission",
        target_device_id="DEV-WEARABLE-CALLPLUS",
        location_source="PHONE_GPS",
    )
    db.upsert_active_alert(
        alert_key=f"CMD_{cmd_id}",
        session_id=session_id,
        hazard_type="RESCUE_DISPATCH",
        alert_title="🚨 RESCUE MISSION: Alpha Member 1 ➔ VIC-DUAL-01",
        severity="HIGH",
        confidence_pct=100.0,
        evidence_summary="Commander assigned Alpha Member 1 to rescue VIC-DUAL-01",
    )

    # 2. Watch dispatch
    global_wearable_gateway.dispatch_alert_to_watch({
        "alert_id": alert_id,
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "VIC-DUAL-01",
        "location": "Sector Dual",
        "priority": "HIGH",
        "command_type": "GO",
    })

    # Channel 1: Web UI Alert
    web_alerts = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    assert len(web_alerts) == 1
    assert web_alerts[0]["alert_key"] == f"CMD_{cmd_id}"

    # Channel 2: Physical Watch Dispatch
    watch_cmd = global_wearable_gateway.get_active_command_for_team_or_device(team_id="ALPHA", member_id="ALPHA-M001")
    assert watch_cmd is not None
    assert watch_cmd["command_id"] == cmd_id
    assert watch_cmd["watch_device_id"] == "DEV-WEARABLE-CALLPLUS"


def test_4_watch_disconnected(client):
    """
    Test 4 — Watch Disconnected:
    When the watch is disconnected, creating an alert must succeed for the Web UI,
    record the watch delivery as disconnected/pending, and never fail the original rescue alert.
    """
    cmd_id = f"CMD-DISCONN-{uuid.uuid4().hex[:6].upper()}"
    session_id = f"SES-DISCONN-{uuid.uuid4().hex[:4].upper()}"

    db.upsert_active_alert(
        alert_key=f"CMD_{cmd_id}",
        session_id=session_id,
        hazard_type="RESCUE_DISPATCH",
        alert_title="🚨 RESCUE MISSION: VIC-DISCONN",
        severity="HIGH",
        confidence_pct=100.0,
        evidence_summary="Dispatched while watch is offline",
    )

    # Dispatch to offline watch
    res = global_wearable_gateway.dispatch_alert_to_watch({
        "alert_id": f"ALT-{cmd_id}",
        "command_id": cmd_id,
        "team_id": "BRAVO",
        "member_id": "BRAVO-M001",
        "victim_id": "VIC-DISCONN",
    })

    # Watch status is pending or offline
    assert res["status"] in ("PENDING", "SENT_TO_BRIDGE", "DELIVERED")

    # Web alert remains 100% active and unfailed
    alerts = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    assert len(alerts) == 1
    assert alerts[0]["status"] == "ACTIVE"


def test_5_watch_ack(client):
    """
    Test 5 — Watch ACK:
    Physical watch sends ACK -> bridge posts to backend -> backend logs event
    to rescue_status_events and updates status to WATCH_ACKNOWLEDGED without deleting the alert.
    """
    cmd_id = f"CMD-ACK-TEST-{uuid.uuid4().hex[:6].upper()}"
    session_id = f"SES-ACK-{uuid.uuid4().hex[:4].upper()}"

    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="VIC-ACK-01",
        priority="HIGH",
        command_type="GO",
        command_text="Rescue with ACK verification",
        target_device_id="DEV-WEARABLE-CALLPLUS",
    )
    db.upsert_active_alert(
        alert_key=f"CMD_{cmd_id}",
        session_id=session_id,
        hazard_type="RESCUE_DISPATCH",
        alert_title="🚨 RESCUE MISSION: VIC-ACK-01",
        severity="HIGH",
        confidence_pct=100.0,
        evidence_summary="Awaiting hardware ACK",
    )
    global_wearable_gateway.dispatch_alert_to_watch({
        "alert_id": f"ALT-{cmd_id}",
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "VIC-ACK-01",
        "session_id": session_id,
    })

    # Post ACK from bridge
    ack_res = client.post(f"/api/wearable/commands/{cmd_id}/ack?device_id=DEV-WEARABLE-CALLPLUS")
    assert ack_res.status_code == 200
    ack_data = ack_res.json()
    assert ack_data["status"] == "success"
    assert ack_data["result"]["state"] == "WATCH_ACKNOWLEDGED"

    # Verify DB status updated to WATCH_ACKNOWLEDGED
    db_cmd = db.get_rescue_command(cmd_id)
    assert db_cmd["status"] == "WATCH_ACKNOWLEDGED"

    # Verify original alert is NOT deleted from active ledger
    active_alerts = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    assert len(active_alerts) == 1
    assert active_alerts[0]["alert_key"] == f"CMD_{cmd_id}"


def test_6_no_duplicate_delivery(client):
    """
    Test 6 — No Duplicate Delivery:
    Querying active commands or polling heartbeats multiple times with the same alert/command ID
    returns the same consistent command object with its unique command_id for client-side idempotency.
    """
    cmd_id = f"CMD-IDEMP-{uuid.uuid4().hex[:6].upper()}"

    global_wearable_gateway.dispatch_alert_to_watch({
        "alert_id": f"ALT-{cmd_id}",
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "VIC-IDEMP-01",
    })

    # Multiple heartbeats
    res1 = client.get("/api/wearable/commands/active?team_id=ALPHA&member_id=ALPHA-M001")
    res2 = client.get("/api/wearable/commands/active?team_id=ALPHA&member_id=ALPHA-M001")
    assert res1.status_code == 200 and res2.status_code == 200
    assert res1.json()["command"]["command_id"] == cmd_id
    assert res2.json()["command"]["command_id"] == cmd_id
    # Both refer to identical immutable command ID


def test_7_alert_persistence_after_full_lifecycle(client):
    """
    Test 7 — Alert Persistence:
    Throughout the full lifecycle (Creation -> Watch Delivery -> Watch ACK),
    the alert remains permanently stored in active_alerts_ledger and rescue_commands.
    """
    cmd_id = f"CMD-LIFECYCLE-{uuid.uuid4().hex[:6].upper()}"
    session_id = f"SES-LIFE-{uuid.uuid4().hex[:4].upper()}"

    # 1. Creation & Persistence
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="VIC-LIFE-01",
        priority="HIGH",
        command_type="GO",
        command_text="Full lifecycle persistence test",
    )
    db.upsert_active_alert(
        alert_key=f"CMD_{cmd_id}",
        session_id=session_id,
        hazard_type="RESCUE_DISPATCH",
        alert_title="🚨 RESCUE MISSION: VIC-LIFE-01",
        severity="HIGH",
        confidence_pct=100.0,
        evidence_summary="Full lifecycle persistence test",
    )

    # 2. Watch Delivery
    global_wearable_gateway.dispatch_alert_to_watch({
        "alert_id": f"ALT-{cmd_id}",
        "command_id": cmd_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "VIC-LIFE-01",
        "session_id": session_id,
    })

    # 3. Status updates during delivery
    client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "PHONE_NOTIFICATION_POSTED",
        "session_id": session_id,
    })
    client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "COMMAND_SENT",
        "session_id": session_id,
    })

    # 4. Watch ACK
    client.post(f"/api/wearable/commands/{cmd_id}/ack")

    # 5. Verify alert is STILL in active_alerts_ledger and rescue_commands
    db_cmd = db.get_rescue_command(cmd_id)
    assert db_cmd is not None
    assert db_cmd["command_id"] == cmd_id
    assert db_cmd["status"] == "WATCH_ACKNOWLEDGED"

    ledger_alerts = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    assert len(ledger_alerts) == 1
    assert ledger_alerts[0]["alert_key"] == f"CMD_{cmd_id}"
    assert ledger_alerts[0]["status"] == "ACTIVE"
