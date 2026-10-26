import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from api import app, state


@pytest.fixture
def client():
    c = TestClient(app)
    c.post("/scenario/start", json={"seed": 42, "enable_degradation": False})
    return c


def test_optical_camera_api_endpoints(client):
    """Verify Optical Camera REST APIs."""
    # 1. GET current
    res_cur = client.get("/sensors/camera/current")
    assert res_cur.status_code == 200
    cur_data = res_cur.json()
    assert "camera" in cur_data
    assert "camera_id" in cur_data["camera"]

    # 2. GET all cameras
    res_all = client.get("/sensors/cameras")
    assert res_all.status_code == 200
    all_data = res_all.json()
    assert all_data["camera_count"] >= 4

    # 3. POST simulate profile
    res_sim = client.post("/sensors/camera/simulate", json={"profile": "PERSON_DETECTED"})
    assert res_sim.status_code == 200
    assert res_sim.json()["profile"] == "PERSON_DETECTED"

    # 4. POST manual IoT reading (valid)
    res_ingest = client.post(
        "/sensors/camera/readings",
        json={
            "camera_id": "CAM-001",
            "confidence": 0.95,
            "person_count": 2,
            "detection_state": "MULTIPLE_PERSONS",
        },
    )
    assert res_ingest.status_code == 200
    assert res_ingest.json()["logged"] is True

    # 5. POST manual IoT reading (invalid out-of-bounds rejected with 422)
    res_bad = client.post(
        "/sensors/camera/readings",
        json={
            "camera_id": "CAM-001",
            "confidence": 2.5,
            "person_count": -3,
        },
    )
    assert res_bad.status_code == 422


def test_thermal_camera_api_endpoints(client):
    """Verify Thermal Camera REST APIs."""
    # 1. GET current
    res_cur = client.get("/sensors/thermal/current")
    assert res_cur.status_code == 200
    cur_data = res_cur.json()
    assert "thermal" in cur_data
    assert "estimated_temperature" in cur_data["thermal"]

    # 2. GET all thermal cameras
    res_all = client.get("/sensors/thermal")
    assert res_all.status_code == 200
    all_data = res_all.json()
    assert all_data["thermal_count"] >= 4

    # 3. POST simulate profile
    res_sim = client.post("/sensors/thermal/simulate", json={"profile": "HUMAN_HEAT"})
    assert res_sim.status_code == 200
    assert res_sim.json()["profile"] == "HUMAN_HEAT"

    # 4. POST manual IoT reading (valid)
    res_ingest = client.post(
        "/sensors/thermal/readings",
        json={
            "camera_id": "THERMAL-001",
            "estimated_temperature": 34.8,
            "thermal_confidence": 0.90,
            "detection_type": "HUMAN_HEAT_SIGNATURE",
        },
    )
    assert res_ingest.status_code == 200
    assert res_ingest.json()["logged"] is True

    # 5. POST manual IoT reading (invalid rejected with 422)
    res_bad = client.post(
        "/sensors/thermal/readings",
        json={
            "camera_id": "THERMAL-001",
            "estimated_temperature": -200.0,
            "thermal_confidence": 5.0,
        },
    )
    assert res_bad.status_code == 422


def test_correlation_and_analytics_endpoints(client):
    """Verify Cross-Modal Correlation and Analytics endpoints."""
    # Correlation
    res_corr = client.get("/sensors/camera-thermal/correlation?victim_id=V1")
    assert res_corr.status_code == 200
    corr_data = res_corr.json()
    assert "correlation" in corr_data
    assert "correlation_case" in corr_data["correlation"]

    # Analytics
    res_ana = client.get("/analytics/camera-thermal")
    assert res_ana.status_code == 200
    ana_data = res_ana.json()
    assert "analytics" in ana_data
    assert "total_camera_readings" in ana_data["analytics"]
    assert "total_thermal_readings" in ana_data["analytics"]
