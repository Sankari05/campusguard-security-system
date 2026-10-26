# tests/test_copilot.py
from fastapi.testclient import TestClient

from app.main import create_application

app = create_application()
client = TestClient(app)


def test_situation_card_and_pattern_alert():
    # 1. First reading: Normal
    r1 = client.post("/api/v1/copilot/situation", json={
        "location": "North Parking Bay",
        "status": "NORMAL",
        "notes": "Morning inspection clear",
        "recorded_by": "Ramasamy"
    })
    assert r1.status_code == 201
    assert r1.json()["status"] == "NORMAL"

    # 2. Second reading: Attention Needed
    r2 = client.post("/api/v1/copilot/situation", json={
        "location": "North Parking Bay",
        "status": "ATTENTION_NEEDED",
        "notes": "Loose perimeter wire near bay 4",
        "recorded_by": "Ramasamy"
    })
    assert r2.status_code == 201

    # 3. Third reading: Suspicious -> Pattern trigger should fire!
    r3 = client.post("/api/v1/copilot/situation", json={
        "location": "North Parking Bay",
        "status": "SUSPICIOUS",
        "notes": "Unidentified van idling near rear boundary",
        "recorded_by": "Ramasamy"
    })
    assert r3.status_code == 201
    data3 = r3.json()
    assert data3["pattern_alert_triggered"] is True
    assert "Situation Changed" in data3["alert_message"]

    # 4. Check active pattern alerts
    p_resp = client.get("/api/v1/copilot/situation/patterns")
    assert p_resp.status_code == 200
    alerts = p_resp.json()
    assert len(alerts) > 0
    assert any("North Parking" in a["location"] for a in alerts)


def test_voice_incident_nlp_parsing():
    transcript = "Block B-la gate damage irukku, vehicle number TN09CA1234 hit panniduchu."
    resp = client.post("/api/v1/copilot/voice-incident", json={
        "transcript": transcript,
        "spoken_by": "Watchman Ramasamy"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["ticket_number"].startswith("MNT-")
    assert data["location"] == "Block B"
    assert data["detected_vehicle"] == "TN09CA1234"
    assert data["urgency"] == "HIGH"
    assert len(data["automated_actions"]) >= 2


def test_prioritized_task_queue():
    resp = client.get("/api/v1/copilot/tasks/prioritized")
    assert resp.status_code == 200
    data = resp.json()
    assert "do_first" in data
    assert "do_next" in data
    assert "routine" in data
    assert isinstance(data["do_first"], list)
    assert isinstance(data["do_next"], list)
    assert isinstance(data["routine"], list)


def test_carry_forward_tasks():
    resp = client.get("/api/v1/copilot/carry-forward")
    assert resp.status_code == 200
    data = resp.json()
    assert "has_carry_forward" in data
    assert "pending_tasks" in data
    assert isinstance(data["pending_tasks"], list)


def test_sector_profiles():
    resp = client.get("/api/v1/copilot/sectors")
    assert resp.status_code == 200
    sectors = resp.json()
    assert len(sectors) == 5
    ids = [s["sector_id"] for s in sectors]
    assert "COLLEGE" in ids
    assert "FACTORY" in ids
    assert "HOSPITAL" in ids
    assert "OFFICE" in ids
    assert "SOCIETY" in ids
    assert any("RGP" in s["gate_pass_name"] for s in sectors)


def test_gate_congestion_analytics():
    resp = client.get("/api/v1/copilot/analytics/congestion")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_ingress_rate_per_hour"] > 0
    assert len(data["peak_hours"]) >= 1
    assert "automation_efficiency_boost" in data
    assert len(data["hourly_distribution"]) > 5

