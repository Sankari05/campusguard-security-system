"""
test_sms_emergency_layer.py
----------------------------
Integration and regression test suite for RidgeWatch SMS Emergency Alert Layer.

Verifies:
1. Dual-channel alert dispatch: Android notification + SMS emergency alerting.
2. Truthful state isolation: SMS_SENT and PHONE_NOTIFICATION_POSTED do NOT forge physical WATCH_ACKNOWLEDGED.
3. Fault tolerance: SMS failures are isolated from core rescue dispatching.
4. Idempotency: Multiple reports for the same command ID are safe and idempotent.
5. Heartbeat synchronization receives active commands with full notification payload.
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


def test_sms_emergency_alert_status_reporting():
    """Verify companion can report PHONE_NOTIFICATION_POSTED_AND_SMS_SENT status truthfully."""
    client = TestClient(app)
    session_id = f"BRG-AND-{uuid.uuid4().hex[:6].upper()}"

    # 1. Trigger test rescue alert
    alert_res = client.post("/api/wearable/commands/test_alert", json={
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "target_id": "Survivor-Alpha",
        "location_label": "Sector North-1",
        "distance_m": 62.0,
        "priority": "CRITICAL"
    })
    assert alert_res.status_code == 200
    cmd_data = alert_res.json()
    cmd_id = cmd_data.get("command_id") or cmd_data.get("command", {}).get("command_id")
    assert cmd_id is not None

    # 2. Companion heartbeat receives command
    sync_res = client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "device_name": "RidgeWatch Native Android Companion",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_model": "Wave Call Plus",
        "watch_connected": False,
        "status": "ONLINE"
    })
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data["active_command"] is not None
    assert sync_data["active_command"]["command_id"] == cmd_id

    # 3. Companion reports dual notification + SMS sent status
    status_res = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "PHONE_NOTIFICATION_POSTED_AND_SMS_SENT",
        "delivery_error": None
    })
    assert status_res.status_code == 200

    # 4. Strict Non-Forgery Verification: Neither SMS nor Android notification forges hardware ACK
    live_res = client.get(f"/api/wearable/commands/{cmd_id}/live_state")
    assert live_res.status_code == 200
    live_data = live_res.json()
    assert live_data["command_status"] in ("PHONE_NOTIFICATION_POSTED_AND_SMS_SENT", "PHONE_NOTIFICATION_POSTED", "SENT_TO_BRIDGE", "ASSIGNED")
    assert live_data["phone_notification_posted"] is True
    assert live_data["hardware_ack_received"] is False


def test_sms_failure_isolation():
    """Verify that reporting an SMS failure does not crash or invalidate the rescue command."""
    client = TestClient(app)

    # 1. Trigger test alert
    alert_res = client.post("/api/wearable/commands/test_alert", json={
        "team_id": "ALPHA",
        "member_id": "ALPHA-M002",
        "target_id": "Survivor-Beta",
        "location_label": "Sector South-2"
    })
    cmd_data = alert_res.json()
    cmd_id = cmd_data.get("command_id") or cmd_data.get("command", {}).get("command_id")

    # 2. Companion reports notification posted first
    client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "PHONE_NOTIFICATION_POSTED"
    })

    # 3. Companion reports SMS failure (e.g. SIM missing or network timeout)
    fail_res = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
        "status": "SMS_FAILED",
        "delivery_error": "No SIM card installed or carrier rejected"
    })
    assert fail_res.status_code == 200

    # 4. Command remains active in system
    live_res = client.get(f"/api/wearable/commands/{cmd_id}/live_state")
    assert live_res.status_code == 200
    live_data = live_res.json()
    assert live_data["hardware_ack_received"] is False


def test_dual_dispatch_idempotency():
    """Verify duplicate status updates for the same command ID are safe and idempotent."""
    client = TestClient(app)

    alert_res = client.post("/api/wearable/commands/test_alert", json={
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001"
    })
    cmd_id = alert_res.json().get("command_id") or alert_res.json().get("command", {}).get("command_id")

    # Report same status multiple times
    for _ in range(3):
        res = client.post(f"/api/wearable/commands/{cmd_id}/status", json={
            "status": "PHONE_NOTIFICATION_POSTED_AND_SMS_SENT"
        })
        assert res.status_code == 200

    live_res = client.get(f"/api/wearable/commands/{cmd_id}/live_state")
    assert live_res.status_code == 200
    assert live_res.json()["phone_notification_posted"] is True
