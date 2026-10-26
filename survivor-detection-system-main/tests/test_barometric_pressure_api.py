"""
test_barometric_pressure_api.py
--------------------------------
Integration tests for Barometric Pressure REST endpoints in backend/api.py.
"""

import pytest
from fastapi.testclient import TestClient
from backend.api import app
import backend.db as db


@pytest.fixture
def client():
    return TestClient(app)


def test_get_pressure_config(client):
    """Test GET /sensors/pressure/config returns centralized thresholds."""
    resp = client.get("/sensors/pressure/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "config" in data
    cfg = data["config"]
    assert cfg["min_pressure_hpa"] == 850.0
    assert cfg["max_pressure_hpa"] == 1100.0
    assert cfg["nominal_baseline_hpa"] == 1013.25
    assert cfg["severe_cyclone_threshold_hpa"] == 990.0


def test_pressure_endpoints_during_running_scenario(client):
    """Test GET /sensors/pressure/* when scenario is started."""
    # 1. Start scenario
    start_resp = client.post("/scenario/start", json={"scenario_id": "himalaya_avalanche", "seed": 42})
    assert start_resp.status_code == 200

    # 2. GET current/latest
    cur_resp = client.get("/sensors/pressure/current")
    assert cur_resp.status_code == 200
    cur_data = cur_resp.json()
    assert "pressure" in cur_data
    assert cur_data["pressure"]["unit"] == "hPa"
    assert cur_data["pressure"]["pressure_hpa"] > 0

    # Alias /latest
    latest_resp = client.get("/sensors/pressure/latest")
    assert latest_resp.status_code == 200
    assert latest_resp.json()["pressure"]["pressure_hpa"] == cur_data["pressure"]["pressure_hpa"]

    # 3. GET trend
    trend_resp = client.get("/sensors/pressure/trend")
    assert trend_resp.status_code == 200
    trend_data = trend_resp.json()
    assert "trend" in trend_data
    assert "rate_of_change" in trend_data

    # 4. GET anomaly
    anom_resp = client.get("/sensors/pressure/anomaly")
    assert anom_resp.status_code == 200
    anom_data = anom_resp.json()
    assert "anomaly_level" in anom_data
    assert "drop_severity" in anom_data

    # 5. GET health
    health_resp = client.get("/sensors/pressure/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["health"]["sensor_type"] == "barometric_pressure"

    # 6. GET status
    status_resp = client.get("/sensors/pressure/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["available"] is True
    assert status_data["status"] == "ONLINE"
    assert status_data["mode"] == "SIMULATED"

    # 7. Tick and check history
    client.post("/scenario/tick")
    hist_resp = client.get("/sensors/pressure/history")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert "history" in hist_data
    assert len(hist_data["history"]) >= 1


def test_post_pressure_reading_valid(client):
    """Test POST /sensors/pressure/readings with valid payload."""
    payload = {
        "sensor_id": "ENV-BARO-TEST",
        "device_id": "DEV-BARO-TEST",
        "pressure_hpa": 1005.5,
        "unit": "hPa",
        "latitude": 19.076,
        "longitude": 72.877,
        "confidence": 0.98,
        "status": "ONLINE",
    }
    resp = client.post("/sensors/pressure/readings", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["logged"] is True
    assert data["reading"]["pressure_hpa"] == 1005.5


def test_post_pressure_reading_invalid_rejected(client):
    """Test POST /sensors/pressure/readings rejects out-of-range or corrupted values."""
    # Out of range low (500 hPa is below min 850)
    resp_low = client.post("/sensors/pressure/readings", json={"pressure_hpa": 500.0})
    assert resp_low.status_code == 422

    # Out of range high (1500 hPa is above max 1100)
    resp_high = client.post("/sensors/pressure/readings", json={"pressure_hpa": 1500.0})
    assert resp_high.status_code == 422

    # Zero pressure
    resp_zero = client.post("/sensors/pressure/readings", json={"pressure_hpa": 0.0})
    assert resp_zero.status_code == 422
