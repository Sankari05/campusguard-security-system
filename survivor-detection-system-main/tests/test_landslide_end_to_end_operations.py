"""
test_landslide_end_to_end_operations.py
---------------------------------------
End-to-end integration and operations tests for Landslide Hazard Detection,
Simulation Advancement, Active Alert Generation, Deduplication, Commander Visibility,
Resolution, and DB Logging.
"""

import pytest
from fastapi.testclient import TestClient
from backend.api import app
import backend.db as db


@pytest.fixture
def client():
    return TestClient(app)


def test_step1_start_landslide_scenario_no_false_critical(client):
    """TEST 1: Start Landslide scenario. Expected: No false CRITICAL alert immediately."""
    start_res = client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})
    assert start_res.status_code == 200
    session_id = start_res.json().get("session_id")

    # Initial baseline: Landslide sensor and hazard should not declare CRITICAL false alarm
    curr_res = client.get("/hazards/landslide/current")
    assert curr_res.status_code == 200
    assert curr_res.json()["assessment"]["risk_level"] in ("LOW", "MODERATE")

    alerts = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    crit_alerts = [a for a in alerts if a.get("severity") == "CRITICAL" and "landslide" in a.get("hazard_type", "").lower()]
    assert len(crit_alerts) == 0, f"False critical alert generated on startup: {crit_alerts}"


def test_step2_increase_soil_moisture_only_no_false_critical(client):
    """TEST 2: Increase soil moisture only. Expected: Landslide evidence increases, but not critical alone."""
    start_res = client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})
    assert start_res.status_code == 200
    session_id = start_res.json().get("session_id")

    # Set Saturating Soil Moisture profile (elevated moisture, but tilt remains stable)
    prof_res = client.post("/hazards/landslide/profile", json={"profile": "INCREASING_MOISTURE"})
    assert prof_res.status_code == 200

    # Tick 1 cycle
    client.post("/scenario/tick")

    assess_res = client.get("/scenario/assessment")
    assert assess_res.status_code == 200
    assess = assess_res.json()

    # Soil moisture evidence should be present, but landslide should not be CRITICAL from one sensor alone
    ev_labels = [e["evidence_label"] for e in assess.get("active_evidence", [])]
    assert any("SOIL" in l or "MOISTURE" in l for l in ev_labels)

    crit_landslide = [
        a for a in db.list_active_alerts(session_id=session_id, status="ACTIVE")
        if a.get("severity") == "CRITICAL" and "landslide" in a.get("hazard_type", "").lower()
    ]
    assert len(crit_landslide) == 0, f"False critical landslide alert from soil moisture alone: {crit_landslide}"


def test_step3_high_soil_moisture_plus_abnormal_tilt_increases_risk(client):
    """TEST 3: High soil moisture + abnormal tilt. Expected: Landslide risk increases."""
    start_res = client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})
    assert start_res.status_code == 200

    # Trigger Early Landslide profile (elevated moisture + abnormal tilt)
    client.post("/hazards/landslide/profile", json={"profile": "EARLY_LANDSLIDE"})
    client.post("/scenario/tick")
    client.post("/scenario/tick")

    curr_res = client.get("/hazards/landslide/current")
    assert curr_res.status_code == 200
    assessment = curr_res.json()["assessment"]
    assert assessment["risk_score"] >= 35.0
    assert assessment["risk_level"] in ("HIGH", "CRITICAL", "MODERATE")


def test_step4_high_moisture_abnormal_tilt_high_rainfall_strong_evidence(client):
    """TEST 4: High soil moisture + abnormal tilt + high rainfall. Expected: Strong Landslide evidence."""
    start_res = client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})
    assert start_res.status_code == 200

    # Trigger Critical Landslide profile
    client.post("/hazards/landslide/profile", json={"profile": "CRITICAL_LANDSLIDE"})
    client.post("/scenario/tick")
    client.post("/scenario/tick")

    assess_res = client.get("/scenario/assessment")
    assert assess_res.status_code == 200
    ev_labels = [e["evidence_label"] for e in assess_res.json().get("active_evidence", [])]
    assert "LANDSLIDE_HAZARD_CRITICAL" in ev_labels or "LANDSLIDE_EARLY_WARNING" in ev_labels or "RAINFALL_SOIL_COMPOUND_LANDSLIDE_TRIGGER" in ev_labels


def test_step5_persistent_critical_evidence_creates_active_alert(client):
    """TEST 5: Persistent critical evidence. Expected: Risk=CRITICAL, Scenario Assessment=CRITICAL, Active Alert=EXISTS."""
    start_res = client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]

    # Activate critical landslide profile and advance 3 cycles to confirm persistence
    client.post("/hazards/landslide/profile", json={"profile": "CRITICAL_LANDSLIDE"})
    for _ in range(3):
        client.post("/scenario/tick")

    # Verify scenario assessment
    assess_res = client.get("/scenario/assessment")
    assert assess_res.status_code == 200
    assess = assess_res.json()
    assert assess["overall_risk"] == "CRITICAL"

    # Verify active alert exists in DB ledger
    active_alerts = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    landslide_alerts = [
        a for a in active_alerts
        if "landslide" in a.get("hazard_type", "").lower() or "landslide" in a.get("alert_title", "").lower()
    ]
    assert len(landslide_alerts) > 0, f"Expected active landslide alert in DB ledger, got: {active_alerts}"
    assert any(a.get("severity") == "CRITICAL" for a in landslide_alerts)


def test_step6_multiple_critical_cycles_deduplication(client):
    """TEST 6: Run several additional critical cycles. Expected: Still one logical ACTIVE Landslide alert (deduplication)."""
    start_res = client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]

    client.post("/hazards/landslide/profile", json={"profile": "CRITICAL_LANDSLIDE"})
    for _ in range(3):
        client.post("/scenario/tick")

    initial_alerts = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    initial_crit = [a for a in initial_alerts if a.get("alert_key") == f"{session_id}-landslide-critical"]
    assert len(initial_crit) == 1
    first_detected_at = initial_crit[0]["first_detected_at"]

    # Run 5 more cycles
    for _ in range(5):
        client.post("/scenario/tick")

    subsequent_alerts = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    subsequent_crit = [a for a in subsequent_alerts if a.get("alert_key") == f"{session_id}-landslide-critical"]
    assert len(subsequent_crit) == 1, f"Expected deduplication to maintain exactly 1 alert, got {len(subsequent_crit)}"
    assert subsequent_crit[0]["first_detected_at"] == first_detected_at


def test_step7_query_alert_api_returns_active_landslide_alert(client):
    """TEST 7: Query alert API. Expected: ACTIVE Landslide alert is returned."""
    start_res = client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]

    client.post("/hazards/landslide/profile", json={"profile": "CRITICAL_LANDSLIDE"})
    for _ in range(3):
        client.post("/scenario/tick")

    # 1. GET /alerts/active
    active_api_res = client.get("/alerts/active")
    assert active_api_res.status_code == 200
    active_data = active_api_res.json()
    assert active_data["count"] > 0
    landslide_in_active = [
        a for a in active_data["alerts"]
        if "landslide" in a.get("hazard_type", "").lower() or "landslide" in a.get("alert_title", "").lower()
    ]
    assert len(landslide_in_active) > 0
    assert landslide_in_active[0]["status"] == "ACTIVE"
    assert landslide_in_active[0]["severity"] == "CRITICAL"

    # 2. GET /alerts
    alerts_res = client.get("/alerts")
    assert alerts_res.status_code == 200
    events = alerts_res.json().get("events", [])
    landslide_events = [
        e for e in events
        if "landslide" in e.get("type", "").lower() or "landslide" in e.get("message", "").lower()
    ]
    assert len(landslide_events) > 0


def test_step8_commander_retrieves_active_alert_and_action(client):
    """TEST 8: Commander retrieves active alert. Expected: Landslide CRITICAL incident and recommended action visible."""
    start_res = client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})
    assert start_res.status_code == 200

    client.post("/hazards/landslide/profile", json={"profile": "CRITICAL_LANDSLIDE"})
    for _ in range(3):
        client.post("/scenario/tick")

    # Check /hazards/landslide/current
    curr_res = client.get("/hazards/landslide/current")
    assert curr_res.status_code == 200
    curr_data = curr_res.json()
    assert curr_data["assessment"]["risk_level"] == "CRITICAL"
    assert "evacuation" in curr_data["assessment"]["recommended_action"].lower() or "slope" in curr_data["assessment"]["recommended_action"].lower()

    # Check /scenario/assessment
    assess_res = client.get("/scenario/assessment")
    assert assess_res.status_code == 200
    assess_data = assess_res.json()
    assert assess_data["overall_risk"] == "CRITICAL"
    assert len(assess_data["recommended_actions"]) > 0


def test_step9_hazard_clears_alert_resolves(client):
    """TEST 9: Hazard clears. Expected: Alert transitions to RESOLVED."""
    start_res = client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]

    # Trigger Critical Landslide
    client.post("/hazards/landslide/profile", json={"profile": "CRITICAL_LANDSLIDE"})
    for _ in range(3):
        client.post("/scenario/tick")

    active_before = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    crit_alerts = [
        a for a in active_before
        if a.get("severity") == "CRITICAL" and ("landslide" in a.get("hazard_type", "").lower() or "landslide" in a.get("alert_title", "").lower())
    ]
    crit_keys = [a["alert_key"] for a in crit_alerts]
    assert len(crit_alerts) > 0

    # Hazard clears: Switch to RECOVERY / NORMAL profile
    client.post("/hazards/landslide/profile", json={"profile": "RECOVERY"})
    for _ in range(8):
        client.post("/scenario/tick")

    # Active alerts should no longer have the critical alert
    active_after = db.list_active_alerts(session_id=session_id, status="ACTIVE")
    crit_after = [
        a for a in active_after
        if a.get("severity") == "CRITICAL" and ("landslide" in a.get("hazard_type", "").lower() or "landslide" in a.get("alert_title", "").lower())
    ]
    assert len(crit_after) == 0, f"Expected critical alerts to be resolved, still active: {crit_after}"

    # Resolved alerts in DB ledger should contain them
    resolved = db.list_active_alerts(session_id=session_id, status="RESOLVED")
    resolved_keys = [a["alert_key"] for a in resolved]
    for k in crit_keys:
        assert k in resolved_keys, f"Alert key {k} missing from RESOLVED ledger"


def test_landslide_multi_operations_isolation(client):
    """Verify independent operations maintain isolated landslide simulation states."""
    # Start Operation 1
    op1_res = client.post("/scenario/start", json={"scenario_id": "wayanad_landslide"})
    assert op1_res.status_code == 200
    op1_id = op1_res.json()["operation_id"]

    # Start Operation 2
    op2_res = client.post("/scenario/start", json={"scenario_id": "himalaya_avalanche"})
    assert op2_res.status_code == 200
    op2_id = op2_res.json()["operation_id"]

    # Set different profiles
    client.post(f"/operations/{op1_id}/hazards/landslide/profile", json={"profile": "CRITICAL_LANDSLIDE"})
    client.post(f"/operations/{op2_id}/hazards/landslide/profile", json={"profile": "NORMAL"})

    # Tick both operations
    client.post(f"/operations/{op1_id}/scenario/tick")
    client.post(f"/operations/{op1_id}/scenario/tick")
    client.post(f"/operations/{op2_id}/scenario/tick")

    # Op 1 should have elevated/critical score, Op 2 should have nominal score
    op1_risk = client.get(f"/operations/{op1_id}/hazards/landslide/current").json()["assessment"]
    op2_risk = client.get(f"/operations/{op2_id}/hazards/landslide/current").json()["assessment"]

    assert op1_risk["soil_moisture_pct"] > op2_risk["soil_moisture_pct"]

