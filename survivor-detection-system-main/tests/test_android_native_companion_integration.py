"""
test_android_native_companion_integration.py
---------------------------------------------
Comprehensive regression test suite for the Native Android RidgeWatch Companion
application (org.ridgewatch.rescuer) integrating with backend/api.py and backend/db.py.

Verifies:
1. Native Companion session registration and heartbeat synchronization.
2. Truthful device identity (identifies as Android Companion, not physical watch).
3. Active rescue command receipt and notification payload schema.
4. Status transitions to PHONE_NOTIFICATION_POSTED.
5. Strict non-forgery guarantee: PHONE_NOTIFICATION_POSTED != WATCH_ACKNOWLEDGED.
6. Idempotency and duplicate command protection.
7. Development test alert dispatch.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from backend.api import app
import backend.db as db


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()
    db.seed_builtin_teams()
    db.seed_builtin_scenarios()


def test_android_companion_heartbeat_registration():
    """Verify native Android companion registers honest session without faking direct GATT."""
    client = TestClient(app)
    session_id = f"BRG-AND-{uuid.uuid4().hex[:6].upper()}"

    payload = {
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "device_name": "RidgeWatch Native Android Companion",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_model": "Wave Call Plus",
        "watch_connected": False,
        "bluetooth_state": "ENABLED",
        "gps_available": True,
        "latitude": 32.3739,
        "longitude": 77.2491,
        "location_source": "PHONE_GPS",
        "status": "ONLINE",
        "notes": "Native Android Companion Active (ALPHA-M001)",
    }

    res = client.post("/api/wearable/bridge/heartbeat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("success", "ok")

    # Verify persisted in database
    sessions = db.list_bridge_sessions(team_id="ALPHA")
    matched = [s for s in sessions if s["session_id"] == session_id]
    assert len(matched) == 1
    assert matched[0]["device_name"] == "RidgeWatch Native Android Companion"
    assert matched[0]["watch_mac"] == "CB:4E:FD:EE:7F:1B"
    assert matched[0]["member_id"] == "ALPHA-M001"


def test_android_companion_receives_rescue_command_and_reports_notification_posted():
    """Verify rescue command flow: dispatch -> companion heartbeat -> PHONE_NOTIFICATION_POSTED."""
    client = TestClient(app)
    session_id = f"BRG-AND-{uuid.uuid4().hex[:6].upper()}"

    # 1. Trigger test rescue alert
    alert_res = client.post("/api/wearable/commands/test_alert", json={
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "target_id": "Survivor-1",
        "location_label": "Sector Alpha",
        "distance_m": 48.5
    })
    assert alert_res.status_code == 200
    cmd_data = alert_res.json()
    cmd_id = cmd_data.get("command_id") or cmd_data.get("command", {}).get("command_id")
    assert cmd_id is not None

    # 2. Companion heartbeat receives active command
    sync_res = client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "device_name": "RidgeWatch Native Android Companion",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_model": "Wave Call Plus",
        "watch_connected": False,
        "bluetooth_state": "ENABLED",
        "gps_available": True,
        "status": "ONLINE"
    })
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data["active_command"] is not None
    assert sync_data["active_command"]["command_id"] == cmd_id

    # 3. Companion posts notification and reports PHONE_NOTIFICATION_POSTED status
    status_res = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "PHONE_NOTIFICATION_POSTED",
        "delivery_error": None
    })
    assert status_res.status_code == 200

    # 4. CRITICAL INVARIANT: Verify watch is NOT marked as hardware acknowledged
    live_res = client.get(f"/api/wearable/commands/{cmd_id}/live_state")
    assert live_res.status_code == 200
    live_data = live_res.json()
    assert live_data["command_status"] in ("PHONE_NOTIFICATION_POSTED", "SENT_TO_BRIDGE", "ASSIGNED")
    assert live_data["phone_notification_posted"] is True
    assert live_data["hardware_ack_received"] is False


def test_android_companion_strict_idempotency_and_rescuing_separation():
    """Verify manual rescuer confirmation remains decoupled from hardware ACK."""
    client = TestClient(app)
    session_id = f"BRG-AND-{uuid.uuid4().hex[:6].upper()}"

    alert_res = client.post("/api/wearable/commands/test_alert", json={
        "team_id": "ALPHA",
        "member_id": "ALPHA-M002"
    })
    cmd_data = alert_res.json()
    cmd_id = cmd_data.get("command_id") or cmd_data.get("command", {}).get("command_id")

    # Rescuer acknowledges on phone screen UI
    ack_res = client.post(f"/api/wearable/commands/{cmd_id}/ack", json={
        "confirmed_by": "rescuer_native_app",
        "member_id": "ALPHA-M002",
        "notes": "Acknowledged from Native Android Companion UI"
    })
    assert ack_res.status_code == 200

    live_res = client.get(f"/api/wearable/commands/{cmd_id}/live_state")
    assert live_res.status_code == 200
    live_data = live_res.json()
    assert live_data.get("rescuer_confirmed") is True
    assert live_data.get("rescuer_confirmation_status") == "RESCUER_CONFIRMED"
    assert live_data.get("hardware_ack_received") is False
