"""
test_admin_create_scenario.py
--------------------------------
Tests for Step 13: custom scenarios (POST /admin/scenario/create) with direct unauthenticated access.
"""


def test_create_earthquake_scenario_generates_correct_victim_count(api_client):
    r = api_client.post(
        "/admin/scenario/create",
        json={"hazard_type": "earthquake", "victim_count": 6, "latitude": 28.6, "longitude": 77.2, "seed": 1},
    )
    assert r.status_code == 200
    assert r.json()["victim_count"] == 6

    victims = api_client.get("/victims").json()["victims"]
    assert len(victims) == 6


def test_create_flood_scenario_enables_water_sensor(api_client):
    r = api_client.post(
        "/admin/scenario/create",
        json={"hazard_type": "flood", "victim_count": 4, "latitude": 19.07, "longitude": 72.87, "seed": 2},
    )
    assert r.status_code == 200

    api_client.get("/victims")   # advance one cycle
    rain = api_client.get("/rain").json()
    assert rain["rainfall_mm_hr"] > 0.0   # flood preset seeds nonzero rainfall


def test_create_scenario_rejects_unknown_hazard_type(api_client):
    r = api_client.post(
        "/admin/scenario/create",
        json={"hazard_type": "tornado", "victim_count": 4, "latitude": 28.6, "longitude": 77.2},
    )
    assert r.status_code == 422


def test_create_scenario_replaces_previous_scenario(api_client):
    api_client.post("/scenario/start", json={"scenario": "himalaya_avalanche", "seed": 1})
    r = api_client.post(
        "/admin/scenario/create",
        json={"hazard_type": "avalanche", "victim_count": 3, "latitude": 32.37, "longitude": 77.24, "seed": 1},
    )
    assert r.status_code == 200
    meta = api_client.get("/victims").json()["scenario"]
    assert meta["victim_count"] == 3   # old himalaya_avalanche's 4 victims are gone, replaced
