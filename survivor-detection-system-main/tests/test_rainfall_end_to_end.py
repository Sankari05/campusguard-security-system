"""
test_rainfall_end_to_end.py
----------------------------
End-to-end full operational pipeline verification for the Rainfall environmental sensor.
Verifies the complete cycle:
Simulation -> Validation -> DB Logging -> Scenario Intelligence & Evidence ->
Alert Decision -> Alert Persistence -> Active Alert Ledger -> REST APIs -> Analytics.

Includes complete regression coverage for the 10 canonical test cases:
1. Extreme rainfall creates an active alert.
2. Heavy rainfall creates the correct alert severity if threshold requires it.
3. Normal rainfall does not create a critical alert.
4. Extreme rainfall alert contains rainfall evidence.
5. Active rainfall alert is persisted.
6. GET /alerts/active returns rainfall alert.
7. Repeated extreme rainfall does not create unlimited duplicate alerts.
8. When rainfall condition clears, alert lifecycle behaves correctly (resolves).
9. Restart does not create duplicate rainfall alerts.
10. Existing non-rainfall alerts still work.
"""

import pytest
from fastapi.testclient import TestClient
# pyrefly: ignore [missing-import]
from api import app
# pyrefly: ignore [missing-import]
import db
# pyrefly: ignore [missing-import]
from models import RainfallClassification, RiskLevel, SensorType


@pytest.fixture
def client():
    return TestClient(app)


def test_rainfall_end_to_end_pipeline(client):
    """Full operational pipeline test for rainfall telemetry, evidence, and alerts."""
    # Step 1: Start cloudburst / flood scenario
    res_start = client.post("/scenario/start", json={"scenario_id": "cloudburst"})
    assert res_start.status_code == 200
    res_assessment = client.get("/alerts/active").json()
    session_id = res_assessment["session_id"]
    assert session_id is not None

    # Step 2: Set Rainfall Simulation Profile to EXTREME
    res_sim = client.post("/sensors/rainfall/simulate", json={"profile": "EXTREME", "rainfall_rate_mm_h": 145.0})
    assert res_sim.status_code == 200
    assert res_sim.json()["profile"] == "EXTREME"

    # Step 3: Advance cycles and fetch live victims / triage ranking
    res_victims = client.get("/victims")
    assert res_victims.status_code == 200
    victims = res_victims.json()["victims"]
    assert len(victims) > 0

    # Step 4: Verify live rainfall current endpoint
    res_rain = client.get("/sensors/rainfall/current")
    assert res_rain.status_code == 200
    rain_data = res_rain.json()["rainfall"]
    assert rain_data["rainfall_rate_mm_h"] > 100.0
    assert rain_data["classification"] == "EXTREME"
    assert rain_data["severity"] == "CRITICAL"

    # Step 5: Check scenario evidence generation
    res_ev = client.get("/sensors/evidence")
    assert res_ev.status_code == 200
    ev_data = res_ev.json()
    ev_labels = [e["evidence_label"] for e in ev_data.get("evidence", [])]
    assert any("RAINFALL" in lbl or "TORRENTIAL" in lbl or "CLOUDBURST" in lbl for lbl in ev_labels)

    # Step 6: Verify Active Alerts in DB ledger & REST endpoint
    active_alerts = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    assert len(active_alerts) > 0
    rain_alerts = [a for a in active_alerts if a.get("hazard_type") == "rainfall_cloudburst"]
    assert len(rain_alerts) == 1
    assert rain_alerts[0]["severity"] == "CRITICAL"
    assert rain_alerts[0]["status"] == "ACTIVE"

    # Step 7: Verify rainfall history audit logging
    res_hist = client.get("/sensors/rainfall/history")
    assert res_hist.status_code == 200
    assert res_hist.json()["count"] > 0

    # Step 8: Verify aggregated analytics computation
    res_an = client.get("/analytics/rainfall")
    assert res_an.status_code == 200
    analytics = res_an.json()["analytics"]
    assert analytics["total_readings"] > 0
    assert analytics["max_rainfall_rate_mm_h"] >= 100.0
    assert analytics["uptime_pct"] == 100.0


# --------------------------------------------------------------------------- #
# Canonical Regression Test Cases (1 to 10)
# --------------------------------------------------------------------------- #

def test_case_1_extreme_rainfall_creates_active_alert(client):
    """1. Extreme rainfall creates an active alert."""
    client.post("/scenario/start", json={"scenario_id": "flood"})
    session_id = client.get("/alerts/active").json()["session_id"]

    client.post("/sensors/rainfall/simulate", json={"profile": "EXTREME", "rainfall_rate_mm_h": 120.0})
    client.get("/victims")

    active = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    rain_alert = next((a for a in active if a["hazard_type"] == "rainfall_cloudburst"), None)
    assert rain_alert is not None, "Expected active rainfall_cloudburst alert"
    assert rain_alert["severity"] == "CRITICAL"
    assert rain_alert["status"] == "ACTIVE"


def test_case_2_heavy_rainfall_creates_correct_severity(client):
    """2. Heavy rainfall creates the correct alert severity if threshold requires it."""
    client.post("/scenario/start", json={"scenario_id": "flood"})
    session_id = client.get("/alerts/active").json()["session_id"]

    client.post("/sensors/rainfall/simulate", json={"profile": "HEAVY", "rainfall_rate_mm_h": 35.0})
    client.get("/victims")

    active = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    rain_alert = next((a for a in active if a["hazard_type"] == "rainfall_heavy"), None)
    assert rain_alert is not None, "Expected active rainfall_heavy alert"
    assert rain_alert["severity"] == "HIGH"
    assert rain_alert["status"] == "ACTIVE"


def test_case_3_normal_rainfall_does_not_create_critical_alert(client):
    """3. Normal rainfall does not create a critical alert."""
    client.post("/scenario/start", json={"scenario_id": "flood"})
    session_id = client.get("/alerts/active").json()["session_id"]

    client.post("/sensors/rainfall/simulate", json={"profile": "NORMAL", "rainfall_rate_mm_h": 3.0})
    client.get("/victims")

    active = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    rain_alerts = [a for a in active if "rain" in a["hazard_type"]]
    assert len(rain_alerts) == 0, f"Expected no active rainfall alerts for normal rain, got: {rain_alerts}"


def test_case_4_extreme_rainfall_alert_contains_rainfall_evidence(client):
    """4. Extreme rainfall alert contains rainfall evidence."""
    client.post("/scenario/start", json={"scenario_id": "cloudburst"})
    session_id = client.get("/alerts/active").json()["session_id"]

    client.post("/sensors/rainfall/simulate", json={"profile": "EXTREME", "rainfall_rate_mm_h": 135.0})
    client.get("/victims")

    active = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    rain_alert = next((a for a in active if a["hazard_type"] == "rainfall_cloudburst"), None)
    assert rain_alert is not None
    assert rain_alert["evidence_summary"] is not None
    assert "135" in rain_alert["evidence_summary"] or "cloudburst" in rain_alert["evidence_summary"].lower() or "precipitation" in rain_alert["evidence_summary"].lower()


def test_case_5_active_rainfall_alert_is_persisted_in_db(client):
    """5. Active rainfall alert is persisted in DB."""
    client.post("/scenario/start", json={"scenario_id": "cloudburst"})
    session_id = client.get("/alerts/active").json()["session_id"]

    client.post("/sensors/rainfall/simulate", json={"profile": "EXTREME", "rainfall_rate_mm_h": 115.0})
    client.get("/victims")

    db_alerts = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    rain_keys = [a["alert_key"] for a in db_alerts if a["hazard_type"] == "rainfall_cloudburst"]
    assert len(rain_keys) == 1
    assert rain_keys[0] == f"{session_id}-rainfall-cloudburst"


def test_case_6_get_alerts_active_endpoint_returns_rainfall_alert(client):
    """6. GET /alerts/active returns rainfall alert."""
    client.post("/scenario/start", json={"scenario_id": "cloudburst"})
    client.post("/sensors/rainfall/simulate", json={"profile": "EXTREME", "rainfall_rate_mm_h": 125.0})
    client.get("/victims")

    res = client.get("/alerts/active")
    assert res.status_code == 200
    alerts = res.json()["alerts"]
    rain_alert = next((a for a in alerts if a["hazard_type"] == "rainfall_cloudburst"), None)
    assert rain_alert is not None
    assert rain_alert["severity"] == "CRITICAL"
    assert rain_alert["status"] == "ACTIVE"


def test_case_7_repeated_extreme_rainfall_deduplication(client):
    """7. Repeated extreme rainfall does not create unlimited duplicate alerts."""
    client.post("/scenario/start", json={"scenario_id": "cloudburst"})
    session_id = client.get("/alerts/active").json()["session_id"]

    client.post("/sensors/rainfall/simulate", json={"profile": "EXTREME", "rainfall_rate_mm_h": 130.0})
    
    # Tick cycle 1
    client.get("/victims")
    alerts_1 = [a for a in db.list_active_alerts(session_id=session_id, status="ACTIVE") if a["hazard_type"] == "rainfall_cloudburst"]
    assert len(alerts_1) == 1
    first_detected = alerts_1[0]["first_detected_at"]

    # Tick cycle 2, 3, 4 with extreme rain
    for _ in range(3):
        client.get("/victims")

    alerts_final = [a for a in db.list_active_alerts(session_id=session_id, status="ACTIVE") if a["hazard_type"] == "rainfall_cloudburst"]
    assert len(alerts_final) == 1, "Should deduplicate to exactly 1 active alert record"
    assert alerts_final[0]["first_detected_at"] == first_detected, "first_detected_at timestamp must remain constant"


def test_case_8_rainfall_condition_clears_resolves_alert(client):
    """8. When rainfall condition clears, alert lifecycle behaves correctly (resolves)."""
    client.post("/scenario/start", json={"scenario_id": "cloudburst"})
    session_id = client.get("/alerts/active").json()["session_id"]

    # Trigger extreme rainfall
    client.post("/sensors/rainfall/simulate", json={"profile": "EXTREME", "rainfall_rate_mm_h": 140.0})
    client.get("/victims")
    active_during = [a for a in db.list_active_alerts(session_id=session_id, status="ACTIVE") if a["hazard_type"] == "rainfall_cloudburst"]
    assert len(active_during) == 1

    # Clear rainfall to normal
    client.post("/sensors/rainfall/simulate", json={"profile": "NORMAL", "rainfall_rate_mm_h": 2.0})
    client.get("/victims")

    active_after = [a for a in db.list_active_alerts(session_id=session_id, status="ACTIVE") if "rain" in a["hazard_type"]]
    assert len(active_after) == 0, f"Expected no active rain alerts, got: {active_after}"

    resolved = [a for a in db.list_active_alerts(session_id=session_id, status="RESOLVED") if a["hazard_type"] == "rainfall_cloudburst"]
    assert len(resolved) == 1, "Cleared alert must transition to RESOLVED in database"
    assert resolved[0]["status"] == "RESOLVED"
    assert resolved[0]["resolved_at"] is not None


def test_case_9_restart_does_not_create_duplicate_rainfall_alerts(client):
    """9. Restart does not create duplicate rainfall alerts."""
    # Run first session
    client.post("/scenario/start", json={"scenario_id": "flood"})
    sess_1 = client.get("/alerts/active").json()["session_id"]
    client.post("/sensors/rainfall/simulate", json={"profile": "EXTREME", "rainfall_rate_mm_h": 120.0})
    client.get("/victims")

    # Restart session
    client.post("/scenario/start", json={"scenario_id": "flood"})
    sess_2 = client.get("/alerts/active").json()["session_id"]
    client.post("/sensors/rainfall/simulate", json={"profile": "EXTREME", "rainfall_rate_mm_h": 120.0})
    client.get("/victims")

    alerts_sess2 = [a for a in db.list_active_alerts(session_id=sess_2, status="ACTIVE") if a["hazard_type"] == "rainfall_cloudburst"]
    assert len(alerts_sess2) == 1


def test_case_10_existing_non_rainfall_alerts_still_work(client):
    """10. Existing non-rainfall alerts still work."""
    # Test earthquake / building collapse scenario
    client.post("/scenario/start", json={"scenario_id": "earthquake"})
    sess = client.get("/alerts/active").json()["session_id"]
    client.get("/victims")

    active = db.list_active_alerts(session_id=sess, status="ACTIVE")
    # Verify primary or cascading scenario alerts exist
    assert len(active) > 0
    hazard_types = [a["hazard_type"] for a in active]
    assert any("earthquake" in ht or "collapse" in ht or "avalanche" in ht or "landslide" in ht for ht in hazard_types)
