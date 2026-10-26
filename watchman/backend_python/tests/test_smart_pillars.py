# tests/test_smart_pillars.py
from fastapi.testclient import TestClient

from app.main import create_application

app = create_application()
client = TestClient(app)


def test_maintenance_lifecycle():
    # 1. Create maintenance ticket
    payload = {
        "category": "ELECTRICAL",
        "title": "North Gate Floodlight Not Working",
        "description": "Short circuit after light rain. Floodlight flickering.",
        "location": "North Gate Bay 1",
        "urgency": "HIGH",
        "reported_by": "Ramasamy (Main Gate Security)"
    }
    resp = client.post("/api/v1/maintenance/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["ticket_number"].startswith("MNT-")
    assert data["status"] == "OPEN"
    report_id = data["id"]

    # 2. Update status to IN_PROGRESS
    update_resp = client.patch(f"/api/v1/maintenance/{report_id}/status", json={
        "status": "IN_PROGRESS",
        "assigned_to": "Campus Electrician Team"
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "IN_PROGRESS"
    assert update_resp.json()["assigned_to"] == "Campus Electrician Team"


def test_parking_management():
    # 1. Get summary
    sum_resp = client.get("/api/v1/parking/summary")
    assert sum_resp.status_code == 200
    summary = sum_resp.json()
    assert summary["total_slots"] >= 10

    # 2. Get slots
    slots_resp = client.get("/api/v1/parking/slots")
    assert slots_resp.status_code == 200
    slots = slots_resp.json()
    assert len(slots) > 0
    target_slot = slots[0]
    slot_id = target_slot["id"]

    # 3. Vacate slot
    vacate_resp = client.post(f"/api/v1/parking/slots/{slot_id}/vacate")
    assert vacate_resp.status_code == 200
    assert vacate_resp.json()["is_occupied"] is False

    # 4. Occupy slot
    occupy_resp = client.post(f"/api/v1/parking/slots/{slot_id}/occupy", json={
        "vehicle_number": "TN09ZZ9999",
        "driver_name": "Guest Lecturer",
        "phone_number": "9876543210",
        "is_unauthorized": False
    })
    assert occupy_resp.status_code == 200
    assert occupy_resp.json()["is_occupied"] is True
    assert occupy_resp.json()["vehicle_number"] == "TN09ZZ9999"


def test_patrol_checkpoints_and_scan():
    # 1. Get checkpoints
    cp_resp = client.get("/api/v1/patrol/checkpoints")
    assert cp_resp.status_code == 200
    cps = cp_resp.json()
    assert len(cps) >= 5

    # 2. Get status
    status_resp = client.get("/api/v1/patrol/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["total_checkpoints"] >= 5

    # 3. Scan QR token
    target_qr = cps[0]["qr_token"]
    scan_resp = client.post("/api/v1/patrol/scan", json={
        "qr_token": target_qr,
        "guard_id": "watchman1",
        "guard_name": "Ramasamy",
        "remarks": "Gate perimeter verified and secure."
    })
    assert scan_resp.status_code == 201
    assert scan_resp.json()["status"] == "COMPLETED"


def test_lost_and_found_and_matching():
    # 1. Report lost item
    lost_resp = client.post("/api/v1/lost-found/lost", json={
        "item_name": "Blue Dell Laptop Bag",
        "category": "ELECTRONICS",
        "description": "Dell Inspiron with charger inside",
        "lost_location": "Central Library 2nd Floor",
        "reported_by_name": "Vigneshwaran K",
        "contact_phone": "9845612342"
    })
    assert lost_resp.status_code == 201
    lost_data = lost_resp.json()
    assert lost_data["status"] == "LOST"

    # 2. Register found item
    found_resp = client.post("/api/v1/lost-found/found", json={
        "item_name": "Blue Dell Laptop Charger & Pouch",
        "category": "ELECTRONICS",
        "description": "Found near table 14 in library",
        "found_location": "Central Library",
        "stored_at": "Main Gate Locker #3"
    })
    assert found_resp.status_code == 201
    found_data = found_resp.json()
    assert found_data["status"] == "UNCLAIMED"
    found_id = found_data["id"]

    # 3. Smart matching check
    match_resp = client.get("/api/v1/lost-found/matches")
    assert match_resp.status_code == 200
    matches = match_resp.json()
    assert isinstance(matches, list)

    # 4. Claim item
    claim_resp = client.post(f"/api/v1/lost-found/found/{found_id}/claim", json={
        "claimed_by_name": "Vigneshwaran K",
        "claimed_by_phone": "9845612342"
    })
    assert claim_resp.status_code == 200
    assert claim_resp.json()["status"] == "RETURNED"


def test_duty_attendance():
    # 1. Clock in
    clock_in_resp = client.post("/api/v1/duty/clock-in", json={
        "guard_id": "watchman1",
        "guard_name": "Ramasamy (Main Gate)",
        "shift_name": "Morning Shift (06:00 AM - 02:00 PM)",
        "gate_assigned": "Campus North Barrier"
    })
    assert clock_in_resp.status_code == 201
    assert clock_in_resp.json()["is_active"] is True

    # 2. Check current duty
    cur_resp = client.get("/api/v1/duty/current/watchman1")
    assert cur_resp.status_code == 200
    assert cur_resp.json()["is_active"] is True

    # 3. Clock out
    clock_out_resp = client.post("/api/v1/duty/clock-out", json={
        "guard_id": "watchman1",
        "supervisor_notes": "Shift successfully handed over to Night Shift Guard Murugan."
    })
    assert clock_out_resp.status_code == 200
    assert clock_out_resp.json()["is_active"] is False


def test_zone_monitoring_and_weather_risk():
    # 1. Get zones
    zones_resp = client.get("/api/v1/zone-risk/zones")
    assert zones_resp.status_code == 200
    zones = zones_resp.json()
    assert len(zones) >= 4

    # 2. Inspect high risk zone
    high_risk_zone = next(z for z in zones if z["risk_level"] in ["HIGH", "MODERATE"])
    insp_resp = client.post(f"/api/v1/zone-risk/zones/{high_risk_zone['id']}/inspect?resolved_issues=true")
    assert insp_resp.status_code == 200

    # 3. Weather telemetry
    weather_resp = client.get("/api/v1/zone-risk/weather-telemetry")
    assert weather_resp.status_code == 200
    telemetry = weather_resp.json()
    assert "hazard_level" in telemetry
    assert len(telemetry["safety_checklist"]) > 0
