"""
test_default_teams_and_members.py
---------------------------------
Comprehensive verification of the 2-team (2 members each, 4 total) baseline,
dynamic Admin expansion (Team 3+), persistence across restarts, and uninterrupted
operation of all 5 scenarios and sensor/fusion pipelines.

Covers the 13 required test specifications:
TEST 1: Fresh/default system contains exactly 2 teams (team_count == 2).
TEST 2: Fresh/default system contains exactly 4 default members (member_count == 4).
TEST 3: Team 1 has exactly 2 members.
TEST 4: Team 2 has exactly 2 members.
TEST 5: No duplicate default teams.
TEST 6: No duplicate default members.
TEST 7: Admin can create Team 3 (team_count == 3).
TEST 8: Admin can add a member to Team 3.
TEST 9: Restart/persistence does not delete Team 3.
TEST 10: Team 3 appears in team listing.
TEST 11: Team 3 can participate in rescue assignment.
TEST 12: Existing five scenarios still work.
TEST 13: Existing sensor/fusion/rescue pipeline still works.
"""

import os
import sys
import uuid
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import db
import scenario_loader


@pytest.fixture(autouse=True)
def clean_baseline():
    """Reset SQLite default admin tables to clean 2-team, 4-member, and 5-scenario baseline."""
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


def test_1_fresh_system_contains_exactly_2_teams(api_client):
    """TEST 1: Fresh/default system contains exactly 2 teams (Rescue Team Alpha, Rescue Team Bravo)."""
    resp = api_client.get("/admin/teams")
    assert resp.status_code == 200
    teams = resp.json().get("teams", [])
    assert len(teams) == 2
    team_ids = {t["team_ref_id"] for t in teams}
    assert team_ids == {"ALPHA", "BRAVO"}
    team_names = {t["team_name"] for t in teams}
    assert team_names == {"Rescue Team Alpha", "Rescue Team Bravo"}


def test_2_fresh_system_contains_exactly_4_default_members(api_client):
    """TEST 2: Fresh/default system contains exactly 4 default members."""
    resp = api_client.get("/admin/personnel")
    assert resp.status_code == 200
    personnel = resp.json().get("personnel", [])
    assert len(personnel) == 4
    person_ids = {p["person_id"] for p in personnel}
    assert person_ids == {"P-ALPHA-01", "P-ALPHA-02", "P-BRAVO-01", "P-BRAVO-02"}
    names = {p["full_name"] for p in personnel}
    assert names == {"Alpha Member 1", "Alpha Member 2", "Bravo Member 1", "Bravo Member 2"}


def test_3_team_1_has_exactly_2_members(api_client):
    """TEST 3: Team 1 (Rescue Team Alpha) has exactly 2 members."""
    resp = api_client.get("/admin/teams")
    assert resp.status_code == 200
    teams = resp.json().get("teams", [])
    team_1 = next((t for t in teams if t["team_ref_id"] == "ALPHA"), None)
    assert team_1 is not None
    assert team_1["team_name"] == "Rescue Team Alpha"
    assert team_1["member_count"] == 2
    assert len(team_1["members"]) == 2
    member_ids = {m["person_id"] for m in team_1["members"]}
    assert member_ids == {"P-ALPHA-01", "P-ALPHA-02"}
    member_names = {m["full_name"] for m in team_1["members"]}
    assert member_names == {"Alpha Member 1", "Alpha Member 2"}


def test_4_team_2_has_exactly_2_members(api_client):
    """TEST 4: Team 2 (Rescue Team Bravo) has exactly 2 members."""
    resp = api_client.get("/admin/teams")
    assert resp.status_code == 200
    teams = resp.json().get("teams", [])
    team_2 = next((t for t in teams if t["team_ref_id"] == "BRAVO"), None)
    assert team_2 is not None
    assert team_2["team_name"] == "Rescue Team Bravo"
    assert team_2["member_count"] == 2
    assert len(team_2["members"]) == 2
    member_ids = {m["person_id"] for m in team_2["members"]}
    assert member_ids == {"P-BRAVO-01", "P-BRAVO-02"}
    member_names = {m["full_name"] for m in team_2["members"]}
    assert member_names == {"Bravo Member 1", "Bravo Member 2"}


def test_5_no_duplicate_default_teams(tmp_path):
    """TEST 5: No duplicate default teams after multiple seed invocations."""
    t_db = str(tmp_path / "test_no_dup_teams.db")
    db.init_db(t_db)
    # Seed multiple times
    db.seed_builtin_teams(t_db)
    db.seed_builtin_teams(t_db)
    db.seed_builtin_teams(t_db)

    teams = db.list_admin_teams(t_db)
    assert len(teams) == 2
    team_ids = [t["team_ref_id"] for t in teams]
    assert team_ids.count("ALPHA") == 1
    assert team_ids.count("BRAVO") == 1


def test_6_no_duplicate_default_members(tmp_path):
    """TEST 6: No duplicate default members after multiple seed invocations."""
    t_db = str(tmp_path / "test_no_dup_members.db")
    db.init_db(t_db)
    db.seed_builtin_teams(t_db)
    db.seed_builtin_teams(t_db)
    db.seed_builtin_teams(t_db)

    personnel = db.list_personnel(t_db)
    assert len(personnel) == 4
    person_ids = [p["person_id"] for p in personnel]
    assert len(set(person_ids)) == 4


def test_7_commander_api_returns_exactly_2_teams_and_4_members(started_client):
    """TEST 7: Commander overview API returns exactly 2 teams and 4 active team members."""
    overview = started_client.get("/commander/overview").json()
    team_members = overview.get("team_members", [])
    assert len(team_members) == 4

    alpha_m = [m for m in team_members if m["team_id"] == "ALPHA"]
    bravo_m = [m for m in team_members if m["team_id"] == "BRAVO"]
    assert len(alpha_m) == 2
    assert len(bravo_m) == 2

    # Check that no old/demo/testing teams appear
    team_ids = {m["team_id"] for m in team_members}
    assert team_ids == {"ALPHA", "BRAVO"}


def test_8_admin_can_create_team_3_and_add_members(started_client):
    """TEST 8: Admin creates Rescue Team Charlie and adds 2 members, appearing in Commander."""
    # 1. Add Personnel
    p1 = started_client.post("/admin/personnel/add", json={
        "full_name": "Charlie Member 1",
        "role": "HazMat Lead",
        "scenarios": ["chemical_leak", "wildfire", "earthquake"],
    }).json()["person_id"]

    p2 = started_client.post("/admin/personnel/add", json={
        "full_name": "Charlie Member 2",
        "role": "Fire Specialist",
        "scenarios": ["chemical_leak", "wildfire", "urban_fire"],
    }).json()["person_id"]

    # 2. Create Team 3
    t_resp = started_client.post("/admin/teams/create", json={
        "team_name": "Rescue Team Charlie",
        "team_type": "Fire & HazMat",
        "description": "Hazardous materials and structural fire suppression squad",
        "members": [
            {"person_id": p1, "role_on_team": "Team Lead"},
            {"person_id": p2, "role_on_team": "Specialist"},
        ],
    })
    assert t_resp.status_code == 200
    team_3_id = t_resp.json()["team_ref_id"]

    # 3. Verify in /admin/teams
    teams = started_client.get("/admin/teams").json().get("teams", [])
    assert len(teams) == 3
    assert any(t["team_name"] == "Rescue Team Charlie" for t in teams)

    # 4. Verify in Commander Overview
    cmd_overview = started_client.get("/commander/overview").json()
    cmd_members = cmd_overview.get("team_members", [])
    assert len(cmd_members) == 6

    charlie_members = [m for m in cmd_members if m["team_id"] == team_3_id]
    assert len(charlie_members) == 2
    assert {m["full_name"] for m in charlie_members} == {"Charlie Member 1", "Charlie Member 2"}


def test_9_restart_persistence_does_not_duplicate_team_3(tmp_path):
    """TEST 9: Restart/re-seed preserves Team 3 without duplicates."""
    t_db = str(tmp_path / "test_persistence.db")
    db.init_db(t_db)
    db.seed_builtin_scenarios(t_db)
    db.seed_builtin_teams(t_db)

    # Initial state: 2 teams, 4 members
    assert len(db.list_admin_teams(t_db)) == 2
    assert len(db.list_personnel(t_db)) == 4

    # Admin creates Team 3 and adds members
    db.create_admin_team("T-CHARLIE", "Rescue Team Charlie", "Fire & HazMat", "HazMat squad", db_path=t_db)
    db.add_personnel("P-CH-01", "Charlie Member 1", "HazMat Lead", scenarios=["chemical_leak"], db_path=t_db)
    db.add_personnel("P-CH-02", "Charlie Member 2", "Fire Rescuer", scenarios=["chemical_leak"], db_path=t_db)
    db.add_team_member("T-CHARLIE", "P-CH-01", "Lead", db_path=t_db)
    db.add_team_member("T-CHARLIE", "P-CH-02", "Rescuer", db_path=t_db)

    assert len(db.list_admin_teams(t_db)) == 3
    assert len(db.list_personnel(t_db)) == 6

    # Simulate backend server restart: calling seed_builtin_scenarios + seed_builtin_teams again
    db.seed_builtin_scenarios(t_db)
    db.seed_builtin_teams(t_db)

    # Team 3 and its members MUST persist without duplicates
    teams_after_restart = db.list_admin_teams(t_db)
    assert len(teams_after_restart) == 3
    team_ids = {t["team_ref_id"] for t in teams_after_restart}
    assert "T-CHARLIE" in team_ids

    team_3 = next(t for t in teams_after_restart if t["team_ref_id"] == "T-CHARLIE")
    assert team_3["member_count"] == 2
    assert len(team_3["members"]) == 2


def test_10_team_3_appears_in_live_members_listing(started_client):
    """TEST 10: Team 3 appears in live operation team listing (/rescue-team/members-status)."""
    p_res = started_client.post("/admin/personnel/add", json={
        "full_name": "Charlie Member 1",
        "role": "Search Specialist",
        "scenarios": ["avalanche", "earthquake", "building_collapse"],
    })
    p_id = p_res.json()["person_id"]

    t_res = started_client.post("/admin/teams/create", json={
        "team_name": "Rescue Team Charlie",
        "team_type": "K9 Alpine",
        "description": "Canine search specialist unit",
        "members": [{"person_id": p_id, "role_on_team": "Lead"}],
    })
    t_id = t_res.json()["team_ref_id"]

    members_resp = started_client.get("/rescue-team/members-status")
    assert members_resp.status_code == 200
    members = members_resp.json()["members"]
    t3_members = [m for m in members if m["team_id"] == t_id]
    assert len(t3_members) >= 1
    assert t3_members[0]["full_name"] == "Charlie Member 1"


def test_11_team_3_can_participate_in_rescue_assignment(started_client):
    """TEST 11: Team 3 member can be assigned to a victim in Commander console."""
    p_res = started_client.post("/admin/personnel/add", json={
        "full_name": "Charlie Member 1",
        "role": "Rescue Specialist",
        "scenarios": ["flood", "avalanche", "earthquake"],
    })
    p_id = p_res.json()["person_id"]

    t_res = started_client.post("/admin/teams/create", json={
        "team_name": "Rescue Team Charlie",
        "team_type": "Water SAR",
        "members": [{"person_id": p_id, "role_on_team": "Specialist"}],
    })
    t_id = t_res.json()["team_ref_id"]

    overview = started_client.get("/commander/overview").json()
    t3_m = next((m for m in overview["team_members"] if m["team_id"] == t_id), None)
    assert t3_m is not None
    m_id = t3_m["member_id"]

    assign_resp = started_client.post("/commander/assign", json={
        "member_id": m_id,
        "victim_id": "V2",
    })
    assert assign_resp.status_code == 200
    assert assign_resp.json()["status"] == "en_route"
    assert assign_resp.json()["assigned_victim_id"] == "V2"


def test_12_existing_five_scenarios_still_work(api_client):
    """TEST 12: Existing five scenarios all load and run without errors."""
    scenarios_resp = api_client.get("/scenarios")
    assert scenarios_resp.status_code == 200
    scenarios = scenarios_resp.json()["scenarios"]
    sc_ids = {s.get("scenario_id") or s.get("id") for s in scenarios if (s.get("status") or "Active").lower() == "active"}

    expected_5 = {
        "earthquake_building_collapse",
        "flood_urban",
        "wildfire_forest",
        "chemical_gas_leak",
        "himalaya_avalanche",
    }
    assert expected_5 <= sc_ids

    # Start each of the 5 scenarios and verify 2 default teams with 2 members each are loaded
    for sc_id in expected_5:
        start_res = api_client.post("/scenario/start", json={"scenario": sc_id, "seed": 42})
        assert start_res.status_code == 200, f"Failed starting scenario {sc_id}"

        status_res = api_client.get("/rescue-team/status")
        assert status_res.status_code == 200
        teams = status_res.json().get("teams", [])
        assert len(teams) >= 2, f"Scenario {sc_id} should have at least 2 default teams"

        members_res = api_client.get("/rescue-team/members-status")
        assert members_res.status_code == 200
        members = members_res.json().get("members", [])
        assert len(members) >= 4, f"Scenario {sc_id} should have at least 4 default members"

        api_client.post("/scenario/reset")


def test_13_existing_sensor_fusion_rescue_pipeline_works(started_client):
    """TEST 13: Full sensor -> fusion -> intelligence -> alert -> dispatch pipeline operates correctly."""
    # 1. Step simulation ticks
    for _ in range(3):
        started_client.post("/scenario/tick")

    # 2. Multi-sensor fusion queue operates
    queue = started_client.get("/queue").json()["queue"]
    assert len(queue) == 4  # Himalaya avalanche has 4 victims

    # 3. Scenario intelligence assessment operates
    assess = started_client.get("/scenario/assessment").json()
    assert "assessment" in assess
    assert assess["cycle"] >= 3

    # 4. Barometric pressure telemetry operates
    pressure = started_client.get("/sensors/pressure/current").json()["pressure"]
    assert "pressure_hpa" in pressure

    # 5. Rescue team auto-dispatch operates
    dispatch_status = started_client.get("/rescue-team/status").json()
    assert len(dispatch_status["teams"]) >= 2
    assert "dispatch_sim" in dispatch_status
