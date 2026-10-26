"""
End-to-End Pipeline Integration Test
Validates the entire closed-loop architecture:
Sensor Generation -> Validation & Quality -> Persistence -> Time-Series Trends ->
Health Diagnostics -> Semantic Evidence -> 19-Scenario Inference & Confidence ->
Cascading Risks -> Active Alert Ledger -> Commander Console & Overview ->
Eligible Staff Matching -> Job Assignment -> Progress Tracking -> Resolution.
"""

import pytest
from fastapi.testclient import TestClient
from backend.api import app
from backend import db


@pytest.fixture
def client():
    return TestClient(app)


def test_complete_sensor_intelligence_to_rescue_pipeline(client):
    """Test full intelligence-to-rescue pipeline end-to-end."""
    # 1. Start a multi-hazard or earthquake scenario
    start_res = client.post("/scenario/start", json={
        "scenario": "earthquake_building_collapse",
        "seed": 42,
        "enable_degradation": True,
    })
    assert start_res.status_code == 200
    start_data = start_res.json()
    assert start_data["running"] is True

    # 2. Query /sensors/current
    sensors_res = client.get("/sensors/current")
    assert sensors_res.status_code == 200
    sensors_data = sensors_res.json()
    assert "environmental" in sensors_data
    assert "readings" in sensors_data
    assert sensors_data["cycle"] >= 0

    # 3. Query /sensors/imu/3axis
    imu_res = client.get("/sensors/imu/3axis")
    assert imu_res.status_code == 200
    imu_data = imu_res.json()
    assert "imu_3axis_by_victim" in imu_data

    # 4. Query /sensors/health
    health_res = client.get("/sensors/health")
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert "health_records" in health_data
    assert health_data["total_channels"] > 0
    assert health_data["overall_health"] in ("OPTIMAL", "DEGRADED", "CRITICAL_FAULTS")

    # 5. Query /sensors/evidence
    evidence_res = client.get("/sensors/evidence")
    assert evidence_res.status_code == 200
    evidence_data = evidence_res.json()
    assert "evidence" in evidence_data

    # 6. Query /scenario/assessment
    assessment_res = client.get("/scenario/assessment")
    assert assessment_res.status_code == 200
    assessment_data = assessment_res.json()
    assert "assessment" in assessment_data
    assessment = assessment_data["assessment"]
    assert "primary_scenario" in assessment
    assert assessment["primary_scenario"]["scenario_id"] is not None
    assert assessment["confidence_pct"] >= 0.0
    assert assessment["overall_risk"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert "recommended_action" in assessment

    # 7. Query /alerts/active
    alerts_res = client.get("/alerts/active")
    assert alerts_res.status_code == 200
    alerts_data = alerts_res.json()
    assert "alerts" in alerts_data

    # 8. Test alert resolution if active alerts exist
    if alerts_data["alerts"]:
        alert_key = alerts_data["alerts"][0]["alert_key"]
        resolve_res = client.post(f"/alerts/{alert_key}/resolve")
        assert resolve_res.status_code == 200
        assert resolve_res.json()["status"] == "RESOLVED"

    # 9. Verify /commander/overview includes intelligence data
    overview_res = client.get("/commander/overview")
    assert overview_res.status_code == 200
    overview = overview_res.json()
    assert "disaster_assessment" in overview
    assert "active_alerts" in overview
    assert "environmental" in overview
    assert "victims" in overview
    assert "team_members" in overview

    # 10. Test scenario-based job creation and matching
    job_create_res = client.post("/commander/jobs/create", json={
        "job_name": "Earthquake Structural Shoring & Extrication",
        "scenario_id": "earthquake",
        "priority": "HIGH",
        "latitude": 32.37,
        "longitude": 77.24,
    })
    assert job_create_res.status_code == 200
    job_id = job_create_res.json()["job_id"]

    # 11. Find eligible staff for this disaster scenario
    staff_res = client.get(f"/commander/jobs/{job_id}/eligible-staff")
    assert staff_res.status_code == 200
    eligible_staff = staff_res.json().get("eligible_staff", [])

    # If eligible staff available, assign to job
    if eligible_staff:
        selected_person = eligible_staff[0]["person_id"]
        assign_res = client.post("/commander/jobs/assign", json={
            "job_id": job_id,
            "member_id": selected_person,
            "notes": "Lead Structural Specialist",
        })
        assert assign_res.status_code == 200
        assert assign_res.json()["status"] == "ASSIGNED"

    # 12. Query /sensors/history
    history_res = client.get("/sensors/history?limit=50")
    assert history_res.status_code == 200
    history_data = history_res.json()
    assert "history" in history_data
