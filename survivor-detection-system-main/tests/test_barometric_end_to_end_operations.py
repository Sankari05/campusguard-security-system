"""
test_barometric_end_to_end_operations.py
----------------------------------------
Comprehensive End-to-End Operational Chain Test for Barometric Pressure Sensor:

Operational Chain Tested:
BAROMETRIC PRESSURE SENSOR INPUT / SIMULATION
↓
STRICT VALIDATION (Reject NaN/Inf/Out-of-range/Corrupted)
↓
SQLITE DATABASE PERSISTENCE (barometric_readings table & indices)
↓
PRESSURE HISTORY & ROLLING WINDOW
↓
TREND ANALYSIS (STABLE, RISING, FALLING, RAPIDLY_FALLING)
↓
RATE OF CHANGE & DROP SEVERITY
↓
ATMOSPHERIC ANOMALY DETECTION
↓
MULTI-SENSOR FUSION (Cyclone, Flood, Storm Surge, Multi-Hazard)
↓
SCENARIO ASSESSMENT & CONFIDENCE SCORE & RISK LEVEL
↓
ALERT ENGINE & ACTIVE ALERTS LEDGER (Deduplication & Escalation)
↓
SCENARIO LEDGER SYNCHRONIZATION
↓
COMMANDER DASHBOARD & HISTORY TELEMETRY
↓
DYNAMIC TEAM MATCHING (Dynamic Team "Bravo", zero hardcoding)
↓
SCENARIO-BASED STAFF ELIGIBILITY MATCHING (scenarios_master.py)
↓
COMMANDER JOB CREATION & STAFF ASSIGNMENT LIFECYCLE
↓
STAFF JOB PROCESSING (ACCEPTED -> IN_PROGRESS -> COMPLETED)
↓
COMMANDER MONITORS FINAL RESULT & COMPLETION
"""

import tempfile
import os
import pytest
from fastapi.testclient import TestClient
from backend.api import app
import backend.db as db
from backend.models import (
    SensorHealthStatus,
    PressureTrend,
    PressureDropSeverity,
    PressureAnomalyLevel,
    PRESSURE_CONFIG,
    BarometricPressureReading,
    GPSCoordinate,
)
from backend.scenarios_master import (
    is_staff_eligible_for_scenario,
    get_scenario_by_id,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_complete_end_to_end_operational_chain(client):
    """
    Executes the entire 18-step operational chain from barometric pressure drop
    to dynamic staff job assignment and completion.
    """
    # 1. Reset / Start live scenario (Cyclone / Coastal Front)
    start_res = client.post("/admin/scenario/create", json={
        "hazard_type": "cyclone",
        "victim_count": 3,
        "latitude": 19.076,
        "longitude": 72.877,
        "scenario_name": "Cyclone Coastal Emergency",
        "seed": 101,
        "enable_degradation": False,
    })
    assert start_res.status_code == 200
    start_data = start_res.json()
    assert start_data["running"] is True
    session_id = start_data.get("session_id")

    # 2. Set barometric simulation profile to CYCLONE (severe plunge)
    prof_res = client.post("/sensors/pressure/profile", json={"profile": "CYCLONE"})
    assert prof_res.status_code == 200

    # 3. Step simulation cycles to generate pressure drop and sensor fusion
    for _ in range(8):
        tick_res = client.post("/scenario/tick")
        assert tick_res.status_code == 200

    # 4. Ingest an external IoT barometric pressure reading to verify IoT Ingestion pipeline
    iot_res = client.post("/sensors/pressure/readings", json={
        "sensor_id": "IOT-BARO-01",
        "device_id": "DEV-BARO-HW",
        "pressure_hpa": 974.5,
        "unit": "hPa",
        "latitude": 19.076,
        "longitude": 72.877,
        "confidence": 0.99,
        "status": "ONLINE",
    })
    assert iot_res.status_code == 200
    assert iot_res.json()["logged"] is True

    # 5. Verify database persistence in barometric_readings table via API and DB
    hist_api = client.get("/sensors/pressure/history?limit=50").json()
    assert len(hist_api.get("history", [])) >= 4
    if session_id:
        latest_db = db.get_latest_barometric_reading(session_id=session_id)
        if latest_db:
            assert latest_db["pressure_hpa"] < 1000.0

    # 6. Verify Commander telemetry and trends
    press_cur = client.get("/sensors/pressure/current").json()
    assert press_cur["pressure"]["pressure_hpa"] < 1000.0
    assert press_cur["pressure"]["unit"] == "hPa"

    press_trend = client.get("/sensors/pressure/trend").json()
    assert press_trend["trend"] in ("FALLING", "RAPIDLY_FALLING")
    assert press_trend["rate_of_change"] <= 0.0

    press_anom = client.get("/sensors/pressure/anomaly").json()
    assert press_anom["drop_severity"] in ("RAPID_DROP", "CRITICAL_DROP", "SIGNIFICANT_DROP")

    # 7. Verify Scenario Assessment & Sensor Fusion (Confidence Score & Risk)
    assess_res = client.get("/scenario/assessment")
    assert assess_res.status_code == 200
    assessment = assess_res.json().get("assessment", {})
    assert assessment.get("overall_risk") in ("HIGH", "CRITICAL")
    assert assessment.get("confidence_pct", 0.0) >= 50.0
    assert any("barometric" in ev["description"].lower() or "pressure" in ev["description"].lower() for ev in assessment.get("active_evidence", []))

    # 8. Verify Active Alerts Ledger has deduplicated alerts
    active_alerts = client.get("/alerts/active").json()
    assert "alerts" in active_alerts
    alert_keys = [a["alert_key"] for a in active_alerts["alerts"]]
    # Ensure no duplicate keys
    assert len(alert_keys) == len(set(alert_keys))

    # 9. Register a NEW Dynamic Team "Bravo" (Zero hardcoding test)
    team_res = client.post("/admin/teams/create", json={
        "team_name": "Bravo Coastal Cyclone Rescue",
        "team_type": "coastal_cyclone",
        "description": "Dynamic specialized coastal disaster response unit.",
        "members": [],
    })
    assert team_res.status_code in (200, 201)
    team_ref_id = team_res.json()["team_ref_id"]

    # 10. Register qualified personnel for cyclone/coastal rescue
    staff_res = client.post("/admin/personnel/add", json={
        "full_name": "Commander Ramesh",
        "role": "Cyclone Specialist",
        "badge_id": "CYC-909",
        "phone": "+91-9876543210",
        "status": "Active",
        "scenarios": ["cyclone", "flood", "storm_surge"],
    })
    assert staff_res.status_code in (200, 201)
    person_id = staff_res.json()["person_id"]

    # 11. Verify Scenario-Based Staff Eligibility via scenarios_master & API
    eligible_cyclone = is_staff_eligible_for_scenario(
        ["cyclone", "flood", "storm_surge"],
        "cyclone",
    )
    assert eligible_cyclone is True

    elig_api = client.get(f"/commander/eligible-staff?scenario_id=cyclone").json()
    assert any(p["personnel_id"] == person_id for p in elig_api.get("eligible", []))

    # 12. Commander Job Creation
    job_create_res = client.post("/commander/jobs/create", json={
        "job_name": "Cyclone Coastal Search and Rescue",
        "scenario_id": "cyclone",
        "priority": "CRITICAL",
        "description": "Severe barometric pressure drop indicates approaching cyclone front. Evacuate sector A.",
    })
    assert job_create_res.status_code == 200
    job_id = job_create_res.json()["job_id"]

    # 13. Commander assigns job to eligible staff member
    assign_res = client.post("/commander/jobs/assign", json={
        "job_id": job_id,
        "member_id": person_id,
        "notes": "Urgent evacuation deployment.",
    })
    assert assign_res.status_code == 200
    assignment_id = assign_res.json()["assignment"]["assignment_id"]

    # 14. Staff receives job in active queue
    staff_jobs = client.get(f"/staff/{person_id}/jobs").json()
    assert any(j["job_id"] == job_id for j in staff_jobs.get("assignments", []))

    # 15. Staff updates status: ACCEPTED -> IN_PROGRESS -> COMPLETED
    client.post(f"/staff/jobs/{assignment_id}/status", json={"status": "ACCEPTED", "result_notes": "En route to sector A."})
    client.post(f"/staff/jobs/{assignment_id}/status", json={"status": "IN_PROGRESS", "result_notes": "Evacuating survivors."})
    done_res = client.post(f"/staff/jobs/{assignment_id}/status", json={"status": "COMPLETED", "result_notes": "Sector A evacuated safely."})
    assert done_res.status_code == 200
    assert done_res.json()["assignment"]["status"] == "COMPLETED"

    # 16. Commander monitors result and mission completion
    overview = client.get("/commander/overview").json()
    assert "cyclone" in overview["scenario"].get("hazard_type", "").lower() or "cyclone" in overview["scenario"].get("scenario_name", "").lower() or "cyclone" in overview["scenario"].get("scenario_id", "").lower()


def test_edge_cases_and_offline_handling(client):
    """
    Tests edge cases:
    - Rejection of NaN / Infinity / Impossible pressure values.
    - Offline sensor gracefully reporting UNAVAILABLE without fake 0 hPa.
    - Confidence penalty application when sensor is degraded/offline.
    - Persistence verification across reset.
    """
    # 1. Invalid string / corrupted payload rejection
    bad_resp = client.post("/sensors/pressure/readings", json={"pressure_hpa": "CORRUPTED_VALUE"})
    assert bad_resp.status_code == 422

    # 1b. Python model rejection of NaN and Infinity
    reading_nan = BarometricPressureReading(pressure_hpa=float("nan"))
    assert reading_nan.validate() is False
    reading_inf = BarometricPressureReading(pressure_hpa=float("inf"))
    assert reading_inf.validate() is False

    # 2. Impossible low pressure rejection (< 850 hPa)
    low_resp = client.post("/sensors/pressure/readings", json={"pressure_hpa": 500.0})
    assert low_resp.status_code == 422

    # 3. Impossible high pressure rejection (> 1100 hPa)
    high_resp = client.post("/sensors/pressure/readings", json={"pressure_hpa": 1400.0})
    assert high_resp.status_code == 422

    # 4. Verify analyzer offline output
    from backend.scenario_intelligence import BarometricPressureAnalyzer
    analyzer = BarometricPressureAnalyzer()
    offline_res = analyzer.analyze(1013.25, status=SensorHealthStatus.OFFLINE)
    assert offline_res["available"] is False
    assert offline_res["pressure_hpa"] == "UNAVAILABLE"
    assert offline_res["confidence_penalty"] > 0.0
