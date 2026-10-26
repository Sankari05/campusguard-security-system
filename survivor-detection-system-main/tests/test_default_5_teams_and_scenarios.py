"""
test_default_5_teams_and_scenarios.py
-------------------------------------
Comprehensive test suite verifying the 2-team and 5-scenario default baseline
and ensuring unrestricted dynamic expansion capabilities (Add Team / Add Scenario).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import db
import scenario_loader
from scenario_intelligence import DisasterScenarioInferenceEngine
from fusion_engine import rank_victims


@pytest.fixture(autouse=True)
def reset_clean_baseline():
    """Reset SQLite default admin tables to clean 2-team and 5-scenario baseline before and after each test."""
    db.init_db()
    with db._connect() as conn:
        conn.execute("DELETE FROM admin_scenarios")
        conn.execute("DELETE FROM admin_team_members")
        conn.execute("DELETE FROM admin_teams")
        conn.execute("DELETE FROM personnel_scenarios")
        conn.execute("DELETE FROM personnel")
    db.seed_builtin_scenarios()
    db.seed_builtin_teams()
    yield
    with db._connect() as conn:
        conn.execute("DELETE FROM admin_scenarios")
        conn.execute("DELETE FROM admin_team_members")
        conn.execute("DELETE FROM admin_teams")
        conn.execute("DELETE FROM personnel_scenarios")
        conn.execute("DELETE FROM personnel")
    db.seed_builtin_scenarios()
    db.seed_builtin_teams()


def test_1_initial_active_team_count(api_client):
    """TEST 1: Initial active team count in admin registry == 2."""
    resp = api_client.get("/admin/teams")
    assert resp.status_code == 200
    teams = resp.json().get("teams", [])
    assert len(teams) == 2
    team_ids = {t["team_ref_id"] for t in teams}
    assert team_ids == {"ALPHA", "BRAVO"}


def test_2_initial_active_scenario_count(api_client):
    """TEST 2: Initial active scenario count in scenarios ledger == 5."""
    resp = api_client.get("/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json().get("scenarios", [])
    active_scenarios = [s for s in scenarios if (s.get("status") or "Active").lower() == "active"]
    assert len(active_scenarios) == 5
    scenario_ids = {s.get("scenario_id") or s.get("id") for s in active_scenarios}
    assert scenario_ids == {
        "earthquake_building_collapse",
        "flood_urban",
        "wildfire_forest",
        "chemical_gas_leak",
        "himalaya_avalanche",
    }


def test_3_add_team_creates_team_3(api_client):
    """TEST 3: Admin Add Team creates team #3 successfully without error."""
    resp = api_client.post("/admin/teams/create", json={
        "team_name": "Foxtrot Coastal K9 Unit",
        "team_type": "K9 / Coastal Search",
        "description": "Specialized coastal search and detection canine unit",
        "members": [
            {"person_id": "P-ALPHA-01", "role_on_team": "Lead Specialist"}
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("created") is True
    team_ref_id = data.get("team_ref_id")
    assert team_ref_id is not None

    # Verify team count is now at least 3
    list_resp = api_client.get("/admin/teams")
    assert list_resp.status_code == 200
    teams = list_resp.json().get("teams", [])
    assert len(teams) >= 3
    assert any(t["team_ref_id"] == team_ref_id for t in teams)


def test_4_add_scenario_creates_scenario_6(api_client):
    """TEST 4: Admin Add Scenario creates scenario #6 successfully."""
    resp = api_client.post("/admin/scenario/create", json={
        "hazard_type": "cyclone",
        "victim_count": 3,
        "latitude": 19.076,
        "longitude": 72.877,
        "scenario_name": "Cyclone Coastal Emergency Drill",
        "seed": 99,
        "enable_degradation": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("created") is True
    sc_id = data.get("scenario_id") or data.get("id")

    # Verify scenario list reflects the new scenario
    list_resp = api_client.get("/admin/scenarios")
    assert list_resp.status_code == 200
    scenarios = list_resp.json().get("scenarios", [])
    assert len(scenarios) >= 6
    assert any(s["scenario_ref_id"] == sc_id for s in scenarios)


def test_5_no_maximum_teams_restriction(api_client):
    """TEST 5: Verify system allows 3rd, 4th, and 5th teams and scenarios with no limit errors."""
    for i in range(3, 7):
        t_resp = api_client.post("/admin/teams/create", json={
            "team_name": f"Dynamic Test Team #{i}",
            "team_type": "Special Operations",
            "description": f"Dynamic team creation test {i}",
            "members": [],
        })
        assert t_resp.status_code == 200

    teams = api_client.get("/admin/teams").json().get("teams", [])
    assert len(teams) >= 6


def test_6_restart_idempotency_teams(tmp_path):
    """TEST 6: Re-running seed_builtin_teams does not duplicate default teams."""
    t_db = str(tmp_path / "test_reseed.db")
    db.init_db(t_db)
    db.seed_builtin_teams(t_db)
    teams_1 = db.list_admin_teams(t_db)
    assert len(teams_1) == 2

    # Second seed invocation (simulating app restart)
    db.seed_builtin_teams(t_db)
    teams_2 = db.list_admin_teams(t_db)
    assert len(teams_2) == 2
    assert {t["team_ref_id"] for t in teams_2} == {"ALPHA", "BRAVO"}


def test_7_restart_idempotency_scenarios(tmp_path):
    """TEST 7: Re-running seed_builtin_scenarios does not duplicate default scenarios."""
    t_db = str(tmp_path / "test_reseed_sc.db")
    db.init_db(t_db)
    db.seed_builtin_scenarios(t_db)
    sc_1 = db.list_admin_scenarios(t_db)
    assert len(sc_1) == 5

    # Second seed invocation
    db.seed_builtin_scenarios(t_db)
    sc_2 = db.list_admin_scenarios(t_db)
    assert len(sc_2) == 5
    assert {s["scenario_ref_id"] for s in sc_2} == {
        "earthquake_building_collapse",
        "flood_urban",
        "wildfire_forest",
        "chemical_gas_leak",
        "himalaya_avalanche",
    }


def test_8_existing_rescue_assignments_work(started_client):
    """TEST 8: Verify active rescue team assignments and status polling work with default 2 teams."""
    status_resp = started_client.get("/rescue-team/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert len(data.get("teams", [])) >= 2

    members_resp = started_client.get("/rescue-team/members-status")
    assert members_resp.status_code == 200
    members = members_resp.json().get("members", [])
    assert len(members) >= 4


def test_9_existing_scenario_intelligence_works(started_client):
    """TEST 9: Verify scenario intelligence assessment functions with the active scenario."""
    # Step scenario
    for _ in range(3):
        started_client.post("/scenario/tick")

    assess_resp = started_client.get("/scenario/assessment")
    assert assess_resp.status_code == 200
    data = assess_resp.json()
    assert "assessment" in data
    assert data.get("cycle") == 3


def test_10_existing_sensor_fusion_works(started_client):
    """TEST 10: Verify multi-sensor fusion triage queue operates correctly."""
    queue_resp = started_client.get("/queue")
    assert queue_resp.status_code == 200
    queue = queue_resp.json().get("queue", [])
    assert len(queue) == 4  # himalaya_avalanche has 4 victims


def test_11_commander_assignment_workflow(started_client):
    """TEST 11: Commander can assign one of the active teams and advance mission."""
    overview = started_client.get("/commander/overview").json()
    assert len(overview.get("team_members", [])) > 0

    # Pick a member from ALPHA
    alpha_members = [m for m in overview["team_members"] if m["team_id"] == "ALPHA"]
    assert len(alpha_members) > 0
    m_id = alpha_members[0]["member_id"]

    # Assign member to a victim
    assign_resp = started_client.post("/commander/assign", json={
        "member_id": m_id,
        "victim_id": "V2",
    })
    assert assign_resp.status_code == 200
    assert assign_resp.json()["assigned_victim_id"] == "V2"
    assert assign_resp.json()["status"] == "en_route"


def test_12_admin_additional_teams(api_client):
    """TEST 12: Admin can create and list multiple custom teams dynamically."""
    initial_count = len(api_client.get("/admin/teams").json().get("teams", []))
    for idx in range(3):
        resp = api_client.post("/admin/teams/create", json={
            "team_name": f"Batch Custom Team {idx}",
            "team_type": "Multi-Hazard SAR",
            "description": "Dynamic scaling test",
            "members": [],
        })
        assert resp.status_code == 200

    new_count = len(api_client.get("/admin/teams").json().get("teams", []))
    assert new_count == initial_count + 3


def test_13_admin_additional_scenarios(api_client):
    """TEST 13: Admin can create multiple custom scenarios dynamically."""
    initial_count = len(api_client.get("/admin/scenarios").json().get("scenarios", []))
    for idx in range(2):
        resp = api_client.post("/admin/scenario/create", json={
            "hazard_type": "flood",
            "victim_count": 2,
            "latitude": 26.14,
            "longitude": 91.73,
            "scenario_name": f"Custom Drill {idx}",
            "seed": 10 + idx,
        })
        assert resp.status_code == 200

    new_count = len(api_client.get("/admin/scenarios").json().get("scenarios", []))
    assert new_count == initial_count + 2
