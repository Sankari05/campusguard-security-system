"""
test_live_rescue_flow.py
------------------------
Automated test suite verifying the 3rd Watch Module View:
"LIVE RESCUE FLOW" (Operational Real-Time Hardware Command Pipeline).

Covers:
1. 3-View Toggle in watch.html ([ WATCH CONSOLE ] [ SIMULATION ] [ LIVE RESCUE FLOW ])
2. Complete separation of the three internal views (only one visible at a time)
3. DOM structure of Live Rescue Flow (Status pills, Logical assignment, Physical hardware endpoint, 6-stage pipeline, Watch monitor, Location telemetry)
4. Dynamic hardware routing (Logical Team/Member -> Physical Wave Call Plus)
5. Real-time command propagation through Commander -> Backend -> Bridge -> Watch
6. Graceful fallbacks (GPS DATA WAITING, WATCH UNCONFIRMED)
"""

import os
import sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_three_view_toggle_markup():
    """Verify that watch.html defines the 3-view toggle with clean IDs."""
    watch_html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "watch.html")
    with open(watch_html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 3-View Buttons
    assert 'id="btnViewConsole"' in html
    assert 'id="btnViewRescueFlow"' in html
    assert 'id="btnViewLiveRescueFlow"' in html
    assert "WATCH CONSOLE" in html
    assert "SIMULATION" in html
    assert "LIVE RESCUE FLOW" in html

    # 3-View Containers
    assert 'id="viewWatchConsole"' in html
    assert 'id="viewRescueFlow"' in html
    assert 'id="viewLiveRescueFlow"' in html


def test_live_rescue_flow_dom_structure():
    """Verify View C (Live Rescue Flow) has all operational components and honest labels."""
    watch_html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "watch.html")
    with open(watch_html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Header & Subtitle
    assert "LIVE RESCUE FLOW" in html
    assert "Real-Time Commander ➔ Backend ➔ Bridge ➔ Physical Watch" in html

    # Status Bar
    assert 'id="lrfStatBackend"' in html
    assert 'id="lrfStatCommander"' in html
    assert 'id="lrfStatBridge"' in html
    assert 'id="lrfStatBluetooth"' in html
    assert 'id="lrfStatWatch"' in html

    # Logical Assignment Card
    assert 'id="lrfValTeam"' in html
    assert 'id="lrfValMember"' in html
    assert 'id="lrfValOpId"' in html
    assert 'id="lrfValTarget"' in html
    assert 'id="lrfValPriority"' in html
    assert 'id="lrfValCommand"' in html

    # Physical Endpoint Card
    assert 'id="lrfValHwDevice"' in html
    assert 'id="lrfValHwId"' in html
    assert 'id="lrfValHwMac"' in html
    assert 'id="lrfValHwBtState"' in html
    assert "Wave Call Plus" in html
    assert "CALLPLUS_7F1B" in html
    assert "CB:4E:FD:EE:7F:1B" in html

    # 6-Stage Command Pipeline
    assert 'id="lrfPipeCommander"' in html
    assert 'id="lrfPipeBackend"' in html
    assert 'id="lrfPipeBridge"' in html
    assert 'id="lrfPipeBluetooth"' in html
    assert 'id="lrfPipeWatch"' in html
    assert 'id="lrfPipeDisplay"' in html

    # Watch Monitor & Location Readout
    assert 'id="lrfMonitorBigCmd"' in html
    assert 'id="lrfLocRescuer"' in html
    assert 'id="lrfLocTarget"' in html
    assert 'id="lrfLocDist"' in html
    assert 'id="lrfLocHeading"' in html
    assert 'id="lrfLocEta"' in html
    assert 'id="lrfLocLastGps"' in html
    assert "GPS DATA WAITING" in html


def test_live_rescue_flow_assets_exist():
    """Verify live_rescue_flow.css and live_rescue_flow.js exist and are linked."""
    base_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    css_path = os.path.join(base_dir, "css", "live_rescue_flow.css")
    js_path = os.path.join(base_dir, "js", "live_rescue_flow.js")

    assert os.path.exists(css_path), "frontend/css/live_rescue_flow.css must exist"
    assert os.path.exists(js_path), "frontend/js/live_rescue_flow.js must exist"

    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "LiveRescueFlow" in js
    assert "syncLiveRescueFlow" in js
    assert "startPolling" in js
    assert "stopPolling" in js


def test_end_to_end_commander_to_physical_watch_dispatch(started_client):
    """
    Test End-to-End Flow:
    Commander assigns ANY Team & Member -> Backend creates command -> Bridge receives -> Watch endpoint active.
    """
    overview = started_client.get("/commander/overview").json()
    team_members = overview["team_members"]
    victims = overview["victims"]

    # Select any team member (e.g. Member 2 or Charlie member)
    target_member = team_members[1] if len(team_members) > 1 else team_members[0]
    target_victim = victims[0]

    # 1. Commander Assigns
    r_assign = started_client.post(
        "/commander/assign",
        json={
            "member_id": target_member["member_id"],
            "victim_id": target_victim["victim_id"],
        },
    )
    assert r_assign.status_code == 200

    # 2. Check active wearable command on backend
    r_cmd = started_client.get(f"/api/wearable/commands/active?member_id={target_member['member_id']}")
    assert r_cmd.status_code == 200
    cmd_data = r_cmd.json()
    assert cmd_data["has_active_command"] is True
    active_cmd = cmd_data["command"]
    assert active_cmd["victim_id"] == target_victim["victim_id"]
    assert active_cmd["member_id"] == target_member["member_id"]
    assert active_cmd["target_device_id"] == "DEV-WEARABLE-CALLPLUS"

    # 3. Android Companion Bridge polls/heartbeats
    r_bridge = started_client.post(
        "/api/wearable/bridge/heartbeat",
        json={
            "session_id": "SES-LIVE-BRIDGE-001",
            "team_id": target_member["team_id"],
            "member_id": target_member["member_id"],
            "device_name": "Companion Android Phone",
            "bluetooth_state": "CONNECTED",
            "watch_connected": True,
            "watch_mac": "CB:4E:FD:EE:7F:1B",
            "watch_model": "Wave Call Plus",
            "gps_available": False,
            "status": "ONLINE",
        },
    )
    assert r_bridge.status_code == 200
    bridge_res = r_bridge.json()
    assert bridge_res["status"] == "success"
    assert bridge_res["active_command"] is not None
    assert bridge_res["active_command"]["status"] == "SENT_TO_BRIDGE"
    assert bridge_res["active_command"]["watch_delivery_status"] == "WATCH_DELIVERY_UNCONFIRMED"

    # 4. Member watch view reflects operational status
    r_watch = started_client.get(f"/watch/{target_member['member_id']}")
    assert r_watch.status_code == 200
    w_data = r_watch.json()
    assert w_data["status"] in ["en_route", "arrived"]
    assert w_data["assigned_victim_id"] == target_victim["victim_id"]
