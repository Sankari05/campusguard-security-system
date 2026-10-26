"""
test_rainfall_api_and_analytics.py
----------------------------------
Integration tests for Rainfall REST API routes and statistical analytics.
"""

import pytest
from fastapi.testclient import TestClient
from backend.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_rainfall_current_route(client):
    # Start running scenario
    client.post("/scenario/start", json={"scenario_id": "himalaya_avalanche"})

    res = client.get("/sensors/rainfall/current")
    assert res.status_code == 200
    data = res.json()
    assert "rainfall" in data
    r = data["rainfall"]
    assert "rainfall_rate_mm_h" in r
    assert "cumulative_rainfall_mm" in r
    assert "classification" in r
    assert "unit" in r


def test_rainfall_simulate_route(client):
    client.post("/scenario/start", json={"scenario_id": "himalaya_avalanche"})

    # Simulate EXTREME profile
    res_sim = client.post("/sensors/rainfall/simulate", json={"profile": "EXTREME", "rainfall_rate_mm_h": 125.0})
    assert res_sim.status_code == 200
    assert res_sim.json()["status"] == "ok"
    assert res_sim.json()["profile"] == "EXTREME"

    # Verify updated reading
    res_cur = client.get("/sensors/rainfall/current")
    assert res_cur.status_code == 200
    assert res_cur.json()["rainfall"]["rainfall_rate_mm_h"] == 125.0


def test_rainfall_ingest_route_and_validation(client):
    # Valid reading ingestion
    valid_payload = {
        "sensor_id": "TEST-RAIN-IOT-01",
        "device_id": "DEV-IOT-01",
        "rainfall_rate_mm_h": 45.2,
        "cumulative_rainfall_mm": 20.0,
        "classification": "HEAVY",
        "severity": "HIGH",
    }
    res_valid = client.post("/sensors/rainfall/readings", json=valid_payload)
    assert res_valid.status_code == 200
    assert res_valid.json()["logged"] is True

    # Invalid negative reading (should return HTTP 422)
    invalid_payload = {
        "sensor_id": "TEST-RAIN-IOT-01",
        "rainfall_rate_mm_h": -15.0,
    }
    res_invalid = client.post("/sensors/rainfall/readings", json=invalid_payload)
    assert res_invalid.status_code == 422


def test_rainfall_history_and_analytics_routes(client):
    res_hist = client.get("/sensors/rainfall/history?limit=10")
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert "history" in hist_data
    assert "count" in hist_data

    res_an = client.get("/analytics/rainfall")
    assert res_an.status_code == 200
    an_data = res_an.json()
    assert "analytics" in an_data
    a = an_data["analytics"]
    assert "total_readings" in a
    assert "max_rainfall_rate_mm_h" in a
    assert "average_rainfall_rate_mm_h" in a
    assert "cumulative_rainfall_mm" in a
    assert "uptime_pct" in a
    assert "classification_distribution" in a
