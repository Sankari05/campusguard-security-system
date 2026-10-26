"""
test_scenario_ledger_sync.py
----------------------------
Integration tests for Scenario Ledger ↔ Dashboard Active/Inactive synchronization:
1. Scenario creation defaults to ACTIVE in ledger and is visible in GET /scenarios.
2. Deactivating a scenario sets status to INACTIVE in ledger, annotates status in GET /scenarios,
   and blocks starting via POST /scenario/start (HTTP 400).
3. Reactivating a scenario sets status to ACTIVE in ledger, allows starting via POST /scenario/start.
4. Toggling status preserves scenario data in database (never deletes records).
5. Supports POST and PATCH status routes.
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_scenario_created_defaults_to_active(started_client):
    scen_name = f"Avalanche Sync Drill {uuid.uuid4().hex[:6]}"
    create_res = started_client.post(
        "/admin/scenario/create",
        json={
            "scenario_name": scen_name,
            "hazard_type": "avalanche",
            "victim_count": 3,
            "latitude": 32.3739,
            "longitude": 77.2491,
            "altitude_m": 3900.0,
            "seed": 101,
        },
    )
    assert create_res.status_code == 200
    scen_id = create_res.json()["scenario_id"]

    # Check ledger
    ledger_res = started_client.get("/admin/scenarios")
    assert ledger_res.status_code == 200
    ledger_items = ledger_res.json()["scenarios"]
    match = next((s for s in ledger_items if s["scenario_ref_id"] == scen_id), None)
    assert match is not None
    assert match["status"] == "Active"

    # Check GET /scenarios
    scenarios_res = started_client.get("/scenarios")
    assert scenarios_res.status_code == 200
    scenarios = scenarios_res.json()["scenarios"]
    scen_match = next((s for s in scenarios if s.get("scenario_id") == scen_id or s.get("id") == scen_id), None)
    assert scen_match is not None
    assert scen_match.get("status") == "Active"


def test_deactivate_and_reactivate_scenario_flow(started_client):
    scen_name = f"Quake Drill {uuid.uuid4().hex[:6]}"
    create_res = started_client.post(
        "/admin/scenario/create",
        json={
            "scenario_name": scen_name,
            "hazard_type": "earthquake",
            "victim_count": 4,
            "latitude": 28.6139,
            "longitude": 77.2090,
            "altitude_m": 216.0,
            "seed": 202,
        },
    )
    assert create_res.status_code == 200
    scen_id = create_res.json()["scenario_id"]

    # 1. Deactivate scenario via POST /admin/scenarios/{id}/status
    deact_res = started_client.post(
        f"/admin/scenarios/{scen_id}/status",
        json={"status": "Inactive"},
    )
    assert deact_res.status_code == 200
    assert deact_res.json()["status"] == "Inactive"

    # Check ledger reflects Inactive
    ledger_res = started_client.get("/admin/scenarios")
    ledger_items = ledger_res.json()["scenarios"]
    match = next((s for s in ledger_items if s["scenario_ref_id"] == scen_id), None)
    assert match is not None
    assert match["status"] == "Inactive"

    # Check GET /scenarios reflects Inactive
    scenarios_res = started_client.get("/scenarios")
    scenarios = scenarios_res.json()["scenarios"]
    scen_match = next((s for s in scenarios if s.get("scenario_id") == scen_id or s.get("id") == scen_id), None)
    assert scen_match is not None
    assert scen_match.get("status") == "Inactive"

    # Attempting to start Inactive scenario must be blocked (HTTP 400)
    start_fail = started_client.post(
        "/scenario/start",
        json={"scenario": scen_id},
    )
    assert start_fail.status_code == 400
    assert "Inactive" in start_fail.json()["detail"]

    # 2. Reactivate scenario via PATCH /scenarios/{id}/status
    react_res = started_client.patch(
        f"/scenarios/{scen_id}/status",
        json={"status": "Active"},
    )
    assert react_res.status_code == 200
    assert react_res.json()["status"] == "Active"

    # Verify starting active scenario now succeeds (HTTP 200)
    start_ok = started_client.post(
        "/scenario/start",
        json={"scenario": scen_id},
    )
    assert start_ok.status_code == 200
    assert start_ok.json()["status"] == "started"


def test_builtin_scenario_status_toggle(started_client):
    builtin_id = "himalaya_avalanche"

    # Deactivate built-in scenario
    deact_res = started_client.post(
        f"/admin/scenarios/{builtin_id}/status",
        json={"status": "Inactive"},
    )
    assert deact_res.status_code == 200

    # Starting himalaya_avalanche should now fail with 400
    start_fail = started_client.post(
        "/scenario/start",
        json={"scenario": builtin_id},
    )
    assert start_fail.status_code == 400

    # Reactivate himalaya_avalanche
    react_res = started_client.patch(
        f"/admin/scenarios/{builtin_id}/status",
        json={"status": "Active"},
    )
    assert react_res.status_code == 200

    # Starting himalaya_avalanche should now succeed
    start_ok = started_client.post(
        "/scenario/start",
        json={"scenario": builtin_id},
    )
    assert start_ok.status_code == 200
