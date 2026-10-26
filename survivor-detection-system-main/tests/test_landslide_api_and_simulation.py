"""
test_landslide_api_and_simulation.py
------------------------------------
API and simulation profile tests for the Soil Moisture, Tilt, and Landslide Early Warning module.
"""

import pytest
from fastapi.testclient import TestClient
from backend.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_soil_moisture_endpoints(client):
    """Verify GET /sensors/soil-moisture/current and /history."""
    # Start scenario
    start_resp = client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})
    assert start_resp.status_code == 200

    # Current soil moisture
    cur_resp = client.get("/sensors/soil-moisture/current")
    assert cur_resp.status_code == 200
    data = cur_resp.json()
    assert "reading" in data
    assert "soil_moisture_pct" in data["reading"]
    assert "health" in data
    assert data["health"]["status"] == "ONLINE"

    # Specific node current
    node2_resp = client.get("/sensors/soil-moisture/current?node_id=SLOPE-NODE-02")
    assert node2_resp.status_code == 200
    assert node2_resp.json()["reading"]["node_id"] == "SLOPE-NODE-02"

    # Soil moisture history
    hist_resp = client.get("/sensors/soil-moisture/history")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert "history" in hist_data


def test_api_tilt_endpoints(client):
    """Verify GET /sensors/tilt/current and /history."""
    client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})

    # Current tilt
    cur_resp = client.get("/sensors/tilt/current")
    assert cur_resp.status_code == 200
    data = cur_resp.json()
    assert "reading" in data
    assert "tilt_angle_deg" in data["reading"]
    assert "health" in data

    # Tilt history
    hist_resp = client.get("/sensors/tilt/history")
    assert hist_resp.status_code == 200
    assert "history" in hist_resp.json()


def test_api_landslide_hazard_endpoints(client):
    """Verify GET /hazards/landslide/current, /nodes, /risk, and /history."""
    client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})

    # Current aggregate landslide hazard
    cur_resp = client.get("/hazards/landslide/current")
    assert cur_resp.status_code == 200
    assert "assessment" in cur_resp.json()
    assess = cur_resp.json()["assessment"]
    assert "landslide_risk_score" in assess
    assert "risk_level" in assess

    # Slope nodes report
    nodes_resp = client.get("/hazards/landslide/nodes")
    assert nodes_resp.status_code == 200
    nodes_data = nodes_resp.json()
    assert "nodes" in nodes_data
    assert "SLOPE-NODE-01" in nodes_data["nodes"]
    assert "SLOPE-NODE-02" in nodes_data["nodes"]
    assert "SLOPE-NODE-03" in nodes_data["nodes"]
    assert "highest_risk_score" in nodes_data
    assert "overall_risk_level" in nodes_data

    # Risk score explainability breakdown
    risk_resp = client.get("/hazards/landslide/risk")
    assert risk_resp.status_code == 200
    risk_data = risk_resp.json()
    assert "score_breakdown" in risk_data
    bd = risk_data["score_breakdown"]
    assert "moisture_subscore" in bd
    assert "tilt_subscore" in bd
    assert "weights" in bd

    # Landslide history
    hist_resp = client.get("/hazards/landslide/history")
    assert hist_resp.status_code == 200
    assert "history" in hist_resp.json()


def test_api_switch_simulation_profiles(client):
    """Verify POST /hazards/landslide/profile switches profiles across 9 simulation modes."""
    client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})

    profiles = [
        "NORMAL", "WET_SOIL", "INCREASING_MOISTURE", "TILT_ANOMALY",
        "EARLY_LANDSLIDE", "CRITICAL_LANDSLIDE", "SENSOR_FAILURE", "NOISY_SENSOR", "RECOVERY"
    ]
    for p in profiles:
        resp = client.post("/hazards/landslide/profile", json={"profile": p})
        assert resp.status_code == 200
        assert resp.json()["profile"] == p


def test_api_iot_soil_ingestion_and_validation(client):
    """Verify POST /sensors/soil-moisture/readings validates and accepts IoT telemetry."""
    client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})

    # Valid ingestion
    valid_resp = client.post(
        "/sensors/soil-moisture/readings",
        json={"soil_moisture_pct": 65.5, "node_id": "SLOPE-NODE-01"}
    )
    assert valid_resp.status_code == 200
    assert valid_resp.json()["logged"] is True

    # Out of range (>100) -> 422
    inv_resp = client.post(
        "/sensors/soil-moisture/readings",
        json={"soil_moisture_pct": 125.0}
    )
    assert inv_resp.status_code == 422


def test_api_iot_tilt_ingestion_and_validation(client):
    """Verify POST /sensors/tilt/readings validates and accepts IoT telemetry."""
    client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})

    # Valid ingestion
    valid_resp = client.post(
        "/sensors/tilt/readings",
        json={"tilt_angle_deg": 3.2, "node_id": "SLOPE-NODE-01"}
    )
    assert valid_resp.status_code == 200
    assert valid_resp.json()["logged"] is True

    # Out of range (>90) -> 422
    inv_resp = client.post(
        "/sensors/tilt/readings",
        json={"tilt_angle_deg": 105.0}
    )
    assert inv_resp.status_code == 422
