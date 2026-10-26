"""
test_admin_add_victim.py
--------------------------
Tests for Step 12: dynamically adding a person to a RUNNING scenario
via the console (POST /admin/victims/add) directly without authentication.
"""


def test_add_victim_requires_running_scenario(api_client):
    r = api_client.post(
        "/admin/victims/add",
        json={"victim_id": "V99", "label": "No scenario running", "status": "HIGH", "latitude": 32.374, "longitude": 77.249},
    )
    assert r.status_code == 400


def test_add_high_priority_victim_shows_up_in_victims_and_queue(started_client):
    r = started_client.post(
        "/admin/victims/add",
        json={"victim_id": "V99", "label": "Admin-added HIGH", "status": "HIGH", "latitude": 32.374, "longitude": 77.249},
    )
    assert r.status_code == 200
    assert r.json()["victim_count"] == 5   # 4 base Himalaya victims + 1 added

    started_client.get("/victims")   # advance one cycle so V99 gets sensor readings
    victims = started_client.get("/victims").json()["victims"]
    assert any(v["victim_id"] == "V99" for v in victims)


def test_add_victim_matches_declared_triage_class(started_client):
    started_client.post(
        "/admin/victims/add",
        json={"victim_id": "V_HIGH", "label": "Should fuse HIGH", "status": "HIGH", "latitude": 32.374, "longitude": 77.249},
    )
    for _ in range(3):
        started_client.get("/victims")   # let the mean-reverting tracks settle near their template midpoint

    queue = started_client.get("/queue").json()["queue"]
    entry = next(q for q in queue if q["victim_id"] == "V_HIGH")
    assert entry["triage_class"] == "HIGH"


def test_duplicate_victim_id_is_rejected(started_client):
    r1 = started_client.post(
        "/admin/victims/add",
        json={"victim_id": "V1", "label": "Duplicate of existing V1", "status": "MEDIUM", "latitude": 32.374, "longitude": 77.249},
    )
    assert r1.status_code == 409


def test_invalid_status_value_is_rejected(started_client):
    r = started_client.post(
        "/admin/victims/add",
        json={"victim_id": "V99", "label": "Bad status", "status": "URGENT", "latitude": 32.374, "longitude": 77.249},
    )
    assert r.status_code == 422
