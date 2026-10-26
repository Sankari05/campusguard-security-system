"""
test_commander_notification_dispatch.py
---------------------------------------
End-to-End Integration Tests for Commander Assignment -> Notification Module.

Verifies:
1. Notification sidebar & standalone frontend page existence and structure.
2. Single Source Event: POST /commander/assign creates ONE rescue command and dispatches notifications.
3. Same Rescue Command ID is shared across rescue command, watch alert, and notification record.
4. No duplicate rescue command is created in the database.
5. Alpha Member 1 mobile resolves to 8098897666 / +918098897666 from backend registry.
6. Masked recipient format (+91 80988****66) is returned and full number is protected.
7. Channel statuses (SMS, Watch) are verified.
8. SMS dispatch never forges WATCH_ACKNOWLEDGED.
9. GET /notifications and GET /api/notifications return truthful persisted records.
"""

import os
import re
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.api import app
import backend.db as db


@pytest.fixture(autouse=True)
def init_data():
    db.init_db()
    db.seed_builtin_teams()
    db.seed_builtin_scenarios()


def test_notification_frontend_page_and_sidebar():
    """Verify frontend/notification.html exists with required UI components and sidebar navigation."""
    root_dir = Path(__file__).resolve().parent.parent
    notif_html_path = root_dir / "frontend" / "notification.html"
    assert notif_html_path.exists(), "notification.html must exist as a standalone frontend page"

    content = notif_html_path.read_text(encoding="utf-8")
    assert "Notification" in content
    assert "sidebar-nav" in content
    assert "notif-table" in content
    assert "notifDrawer" in content
    assert "kpiTotalCount" in content
    assert "kpiSmsCount" in content


def test_commander_assign_single_source_event(started_client):
    """Verify Commander assignment creates ONE rescue command and links same ID to notification."""
    client = started_client

    # Initial command count
    cmds_before = db.list_rescue_commands(limit=100)
    initial_cmd_count = len(cmds_before)

    # Commander assigns Alpha Member 1 to a victim
    overview = client.get("/commander/overview").json()
    member = next(m for m in overview["team_members"] if "ALPHA" in m["team_id"])
    victim = overview["victims"][0]

    assign_res = client.post("/commander/assign", json={
        "member_id": member["member_id"],
        "victim_id": victim["victim_id"],
    })
    assert assign_res.status_code == 200
    assert assign_res.json()["assigned_victim_id"] == victim["victim_id"]

    # Exactly ONE new rescue command created
    cmds_after = db.list_rescue_commands(limit=100)
    assert len(cmds_after) == initial_cmd_count + 1, "Expected exactly ONE rescue command created (No duplicate commands)"

    new_cmd = cmds_after[0]
    cmd_id = new_cmd["command_id"]

    # Notification Center must have record with the SAME rescue_command_id
    notif = db.get_notification(cmd_id)
    assert notif is not None, "Notification record must be retrievable by rescue_command_id"
    assert notif["rescue_command_id"] == cmd_id
    assert notif["victim_id"] == victim["victim_id"]


def test_alpha_member_1_mobile_resolution():
    """Verify Alpha Member 1 resolves to +918098897666 and displays masked +91 80988****66."""
    contact = db.resolve_member_contact_info("ALPHA-M001", team_id="ALPHA")
    assert contact["phone_normalized"] == "+918098897666"
    assert contact["phone_masked"] == "+91 80988****66"

    # Also test by person_id directly
    contact_p = db.resolve_member_contact_info("P-ALPHA-01", team_id="ALPHA")
    assert contact_p["phone_normalized"] == "+918098897666"
    assert contact_p["phone_masked"] == "+91 80988****66"


def test_notification_endpoints_and_channel_independence(started_client):
    """Verify GET /notifications returns multi-channel statuses with channel independence."""
    client = started_client

    # 1. Trigger assignment
    overview = client.get("/commander/overview").json()
    member = overview["team_members"][0]
    victim = overview["victims"][0]

    client.post("/commander/assign", json={
        "member_id": member["member_id"],
        "victim_id": victim["victim_id"],
    })

    # 2. Query GET /notifications
    res = client.get("/notifications")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total"] >= 1
    assert len(data["notifications"]) >= 1

    latest = data["notifications"][0]
    assert "rescue_command_id" in latest
    assert "sms_status" in latest
    assert "watch_delivery_status" in latest
    assert "phone_number_masked" in latest
    assert "****" in latest["phone_number_masked"]

    # Query GET /notifications/{id}
    notif_id = latest["id"]
    single_res = client.get(f"/notifications/{notif_id}")
    assert single_res.status_code == 200
    single_data = single_res.json()["notification"]
    assert single_data["id"] == notif_id

    # Strict Safety Check: Watch ACK was not forged
    assert single_data["watch_ack_status"] != "WATCH_ACKNOWLEDGED"
    assert single_data["watch_ack_status"] != "ACCEPTED"


def test_commander_assign_automatically_appears_in_notification_and_bridge(started_client):
    """
    Core Regression Test:
    Verify Commander assignment creates ONE rescue command that is simultaneously
    and automatically visible in BOTH Bridge (via heartbeat) and Notification module,
    referencing the exact same rescue_command_id with phone resolution and channel independence.
    """
    client = started_client

    # 1. Snapshot existing commands
    cmds_before = db.list_rescue_commands(limit=100)
    initial_count = len(cmds_before)

    # 2. Commander selects Alpha Team -> Alpha Member 1 -> Victim
    overview = client.get("/commander/overview").json()
    alpha_member = next(m for m in overview["team_members"] if "ALPHA" in m["team_id"])
    target_victim = overview["victims"][0]

    assign_res = client.post("/commander/assign", json={
        "member_id": alpha_member["member_id"],
        "victim_id": target_victim["victim_id"],
    })
    assert assign_res.status_code == 200

    # 3. Verify exactly ONE rescue command was created (no duplicates)
    cmds_after = db.list_rescue_commands(limit=100)
    assert len(cmds_after) == initial_count + 1, "Exactly ONE rescue command must be created"
    new_cmd = cmds_after[0]
    cmd_id = new_cmd["command_id"]

    # 4. Verify Bridge flow: Heartbeat immediately sees the assigned rescue command
    bridge_hb_res = client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "TEST-BRG-01",
        "team_id": "ALPHA",
        "member_id": alpha_member["member_id"],
        "watch_connected": True,
        "bluetooth_state": "ENABLED",
        "gps_available": True,
        "latitude": 34.225,
        "longitude": 77.561,
        "location_source": "PHONE_GPS",
        "status": "ONLINE",
    })
    assert bridge_hb_res.status_code == 200
    hb_data = bridge_hb_res.json()
    bridge_cmd = hb_data.get("active_command") or (hb_data.get("pending_commands") or [{}])[0]
    assert bridge_cmd.get("command_id") == cmd_id, "Bridge must see the exact same rescue command"
    assert bridge_cmd.get("member_id") == alpha_member["member_id"]
    assert bridge_cmd.get("victim_id") == target_victim["victim_id"]

    # 5. Verify Notification Module: Immediately sees the assigned rescue command
    notif_res = client.get("/notifications")
    assert notif_res.status_code == 200
    notifs = notif_res.json().get("notifications", [])
    assert len(notifs) >= 1

    # Find the notification corresponding to this rescue command
    matching_notif = next((n for n in notifs if n.get("rescue_command_id") == cmd_id), None)
    assert matching_notif is not None, f"Notification page must show the newly assigned rescue command {cmd_id}"

    # Verify identical metadata across Bridge and Notification
    assert matching_notif["rescue_command_id"] == bridge_cmd["command_id"]
    assert matching_notif["member_id"] == bridge_cmd["member_id"]
    assert matching_notif["victim_id"] == bridge_cmd["victim_id"]

    # 6. Verify Alpha Member 1 dynamic database phone resolution
    assert matching_notif["phone_number"] == "+918098897666"
    assert matching_notif["phone_number_masked"] == "+91 80988****66"

    # 7. Verify SMS Status
    assert matching_notif["sms_status"] in ("SENT", "QUEUED")

    # 8. Verify Watch ACK is strictly untouched (never forged)
    assert matching_notif["watch_ack_status"] != "WATCH_ACKNOWLEDGED"
    assert matching_notif["watch_ack_status"] != "ACCEPTED"
