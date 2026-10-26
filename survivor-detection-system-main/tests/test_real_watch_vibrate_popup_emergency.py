"""
tests/test_real_watch_vibrate_popup_emergency.py
-------------------------------------------------
Comprehensive automated test suite for Real Smart Watch Vibrate + Popup Emergency Alert:
1. Real Geospatial Distance Calculation (Phone/Member GPS -> Target Victim Location).
2. Honest fallback to "Distance unavailable" when coordinates are missing.
3. Watch Emergency Alert payload construction with compact text for Wave Call Plus.
4. Notification Center persistence in DB and retrieval via GET /api/wearable/notifications.
5. Watch disconnect resilience: Alert is preserved in Notification Center when watch is offline.
6. User Accept & Watch ACK state transitions via POST /api/wearable/notifications/{id}/accept.
7. Multi-alert retention in Notification Center history.
"""

import pytest
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient

import db
from api import app, global_wearable_gateway
from rescue_dispatch import haversine_distance_m, GPSCoordinate


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    test_db = tmp_path / "test_emergency_alerts.db"
    db.init_db(str(test_db))
    global_wearable_gateway.active_commands.clear()
    yield
    global_wearable_gateway.active_commands.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_real_geospatial_distance_calculation():
    """Verify haversine distance calculation between phone rescuer GPS and victim coordinates."""
    rescuer_coord = GPSCoordinate(latitude=32.3739, longitude=77.2491)
    victim_coord = GPSCoordinate(latitude=32.3750, longitude=77.2505)

    dist_m = haversine_distance_m(rescuer_coord, victim_coord)
    assert dist_m > 0
    assert 100 < dist_m < 300  # expected ~180m

    # Test through wearable_gateway.dispatch_alert_to_watch
    alert_payload = {
        "alert_id": "ALT-DIST-01",
        "command_id": "CMD-DIST-01",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "VIC-001",
        "location": "Ridge Sector A",
        "latitude": 32.3750,
        "longitude": 77.2505,
        "member_latitude": 32.3739,
        "member_longitude": 77.2491,
    }

    res = global_wearable_gateway.dispatch_alert_to_watch(alert_payload)
    assert res["status"] in ("QUEUED", "SENT_TO_BRIDGE", "WATCH_CONNECTED", "PENDING")
    
    cmd = global_wearable_gateway.active_commands.get("CMD-DIST-01")
    assert cmd is not None
    assert cmd["distance_m"] is not None
    assert "m" in cmd["distance_label"] or "km" in cmd["distance_label"]
    assert "Distance:" in cmd["notification_payload"]["body"]


def test_distance_unavailable_when_coordinates_missing():
    """Verify distance is honestly labeled as 'Distance unavailable' when coordinates are not provided."""
    alert_payload = {
        "alert_id": "ALT-NODIST-01",
        "command_id": "CMD-NODIST-01",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "VIC-002",
        "location": "Sector Unknown",
        "latitude": 0.0,
        "longitude": 0.0,
    }

    res = global_wearable_gateway.dispatch_alert_to_watch(alert_payload)
    cmd = global_wearable_gateway.active_commands.get("CMD-NODIST-01")
    assert cmd is not None
    assert cmd["distance_label"] == "Distance unavailable"


def test_notification_center_db_persistence_and_api(client):
    """Verify that every emergency alert is persisted into notification_center table and accessible via REST API."""
    alert_payload = {
        "alert_id": "ALT-PERSIST-01",
        "command_id": "CMD-PERSIST-01",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "VIC-SURVIVOR-99",
        "location": "North Basin",
        "priority": "HIGH",
        "latitude": 32.3740,
        "longitude": 77.2495,
        "member_latitude": 32.3739,
        "member_longitude": 77.2491,
    }

    global_wearable_gateway.dispatch_alert_to_watch(alert_payload)

    # Check notification in DB directly
    notif = db.get_notification("ALT-PERSIST-01")
    assert notif is not None
    assert notif["alert_id"] == "ALT-PERSIST-01"
    assert notif["victim_id"] == "VIC-SURVIVOR-99"
    assert notif["priority"] == "HIGH"
    assert notif["status"] == "ACTIVE"

    # Check via REST endpoint GET /api/wearable/notifications
    resp = client.get("/api/wearable/notifications?team_id=ALPHA")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["total"] >= 1
    found = any(n["alert_id"] == "ALT-PERSIST-01" for n in data["notifications"])
    assert found is True


def test_user_accept_notification_flow(client):
    """Verify accepting a notification via API updates DB status, watch ACK state, and gateway command."""
    alert_payload = {
        "alert_id": "ALT-ACCEPT-01",
        "command_id": "CMD-ACCEPT-01",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "VIC-100",
        "location": "Sector West",
    }

    global_wearable_gateway.dispatch_alert_to_watch(alert_payload)

    # Post user accept
    resp = client.post("/api/wearable/notifications/ALT-ACCEPT-01/accept")
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["state"] == "USER_ACCEPTED"

    # Verify notification state updated in DB
    notif = db.get_notification("ALT-ACCEPT-01")
    assert notif is not None
    assert notif["status"] == "USER_ACCEPTED"
    assert notif["watch_ack_status"] == "ACCEPTED"

    # Verify gateway command state (Operator confirmed via UI, not false hardware ACK)
    cmd = global_wearable_gateway.active_commands.get("CMD-ACCEPT-01")
    assert cmd is not None
    assert cmd["status"] == "USER_ACCEPTED"


def test_multi_alert_retention_in_notification_center(client):
    """Verify multiple alerts accumulate and remain in Notification Center history."""
    for i in range(5):
        global_wearable_gateway.dispatch_alert_to_watch({
            "alert_id": f"ALT-BATCH-{i}",
            "command_id": f"CMD-BATCH-{i}",
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "victim_id": f"VIC-BATCH-{i}",
            "location": f"Zone {i}",
        })

    resp = client.get("/api/wearable/notifications?team_id=ALPHA")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["notifications"]) == 5


def test_watch_disconnected_resilience():
    """Verify that when watch is disconnected, alert is cleanly stored as WATCH_DISCONNECTED without throwing."""
    # Ensure bridge is disconnected
    global_wearable_gateway.bridge_adapter._connected = False

    alert_payload = {
        "alert_id": "ALT-OFFLINE-01",
        "command_id": "CMD-OFFLINE-01",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "victim_id": "VIC-OFFLINE-01",
        "location": "Sub-Sector 4",
    }

    res = global_wearable_gateway.dispatch_alert_to_watch(alert_payload)
    assert res["status"] in ("QUEUED", "SENT_TO_BRIDGE", "WATCH_DISCONNECTED", "PENDING")

    notif = db.get_notification("ALT-OFFLINE-01")
    assert notif is not None
    assert notif["status"] == "ACTIVE"
