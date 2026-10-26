"""
test_scenario_sensor_fusion.py
------------------------------
Validates end-to-end multi-sensor fusion, priority scoring, and API endpoints
under scenario-aware profiles.
"""

import pytest
from fastapi.testclient import TestClient
# pyrefly: ignore [missing-import]
from api import app, operations, ScenarioState
# pyrefly: ignore [missing-import]
from models import SensorType, SensorReading, GPSCoordinate
# pyrefly: ignore [missing-import]
from fusion_engine import fuse_victim, fuse_all, HazardContext, TriageClass


@pytest.fixture
def client():
    return TestClient(app)


def test_fuse_all_with_scenario_profile():
    """Verify fuse_all passes through scenario_id to all victims properly."""
    loc = GPSCoordinate(latitude=32.374, longitude=77.249)
    readings_by_victim = {
        "V-01": [
            SensorReading(
                sensor_type=SensorType.HEART_RATE_RADAR,
                value=75.0,
                unit="bpm",
                location=loc,
                victim_id="V-01",
                confidence=0.9,
            ),
        ],
        "V-02": [
            SensorReading(
                sensor_type=SensorType.HEART_RATE_RADAR,
                value=0.0,
                unit="bpm",
                location=loc,
                victim_id="V-02",
                confidence=0.9,
            ),
        ],
    }
    hazard_by_victim = {
        "V-01": HazardContext(water_level_cm=100.0),
        "V-02": HazardContext(water_level_cm=100.0),
    }

    results = fuse_all(
        readings_by_victim,
        hazard_by_victim=hazard_by_victim,
        scenario_id="flood_urban",
    )
    assert len(results) == 2
    assert results["V-01"].hazard_breakdown["water_level"] > 0.0
    assert results["V-01"].triage_class in (TriageClass.HIGH, TriageClass.MEDIUM)


def test_api_scenario_sensor_profile_endpoint(client):
    """Verify GET /scenario/sensor-profile returns valid sensor classifications and matrix."""
    res = client.get("/scenario/sensor-profile?scenario_id=flood_urban")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["scenario_id"] == "flood_urban"
    assert "water_level" in data["primary_sensors"]
    assert "gas_concentration" in data["inactive_sensors"]
    assert len(data["sensor_matrix"]) >= 18


def test_api_scenario_start_populates_profile_meta(client):
    """Verify POST /scenario/start includes scenario sensor profile metadata."""
    res = client.post("/scenario/start", json={"scenario": "chemical_gas_leak"})
    assert res.status_code == 200
    data = res.json()
    assert "sensor_profile" in data
    assert "gas_concentration" in data["sensor_profile"]["primary_sensors"]
    assert "water_level" in data["sensor_profile"]["inactive_sensors"]
