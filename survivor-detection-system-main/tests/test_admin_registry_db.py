"""
test_admin_registry_db.py
------------------------------
Tests for Step 29.1: persistent admin registry tables (personnel,
admin_scenarios, admin_teams, admin_team_members) in db.py. These are
deliberately separate from victims (V1-V4, needy people) and from
scenario reset/restart - personnel/team/scenario-history records must
survive a reset.
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import db


def _tmp_db(tmp_path):
    return str(tmp_path / f"test_{uuid.uuid4().hex}.db")


def test_init_db_creates_all_admin_registry_tables(tmp_path):
    path = _tmp_db(tmp_path)
    db.init_db(path)
    import sqlite3
    conn = sqlite3.connect(path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"personnel", "admin_scenarios", "admin_teams", "admin_team_members"} <= tables


def test_add_and_list_personnel(tmp_path):
    path = _tmp_db(tmp_path)
    db.init_db(path)
    db.add_personnel("P001", "Ravi Kumar", "Rescuer", phone="9876543210", badge_id="B-101", db_path=path)
    db.add_personnel("P002", "Meena S", "Medic", email="meena@example.com", db_path=path)

    people = db.list_personnel(db_path=path)
    assert len(people) == 2
    ids = {p["person_id"] for p in people}
    assert ids == {"P001", "P002"}
    ravi = next(p for p in people if p["person_id"] == "P001")
    assert ravi["role"] == "Rescuer"
    assert ravi["status"] == "Active"   # default
    assert ravi["badge_id"] == "B-101"


def test_personnel_list_ordered_newest_first(tmp_path):
    path = _tmp_db(tmp_path)
    db.init_db(path)
    db.add_personnel("P001", "First", "Rescuer", created_at="2026-01-01T00:00:00+00:00", db_path=path)
    db.add_personnel("P002", "Second", "Medic", created_at="2026-01-02T00:00:00+00:00", db_path=path)
    people = db.list_personnel(db_path=path)
    assert [p["person_id"] for p in people] == ["P002", "P001"]


def test_log_and_list_admin_scenarios(tmp_path):
    path = _tmp_db(tmp_path)
    db.init_db(path)
    db.log_admin_scenario("SC001", "Himalaya Avalanche", "avalanche", 4, latitude=32.37, longitude=77.25, db_path=path)
    scenarios = db.list_admin_scenarios(db_path=path)
    assert len(scenarios) == 1
    assert scenarios[0]["scenario_name"] == "Himalaya Avalanche"
    assert scenarios[0]["victim_count"] == 4
    assert scenarios[0]["status"] == "Active"   # default


def test_create_team_add_members_and_list_with_join(tmp_path):
    path = _tmp_db(tmp_path)
    db.init_db(path)
    db.add_personnel("P001", "Ravi Kumar", "Rescuer", phone="9876543210", db_path=path)
    db.add_personnel("P002", "Meena S", "Medic", db_path=path)
    db.create_admin_team("T001", "Alpha Squad", team_type="SAR", description="Search and rescue", db_path=path)
    db.add_team_member("T001", "P001", role_on_team="Lead", db_path=path)
    db.add_team_member("T001", "P002", role_on_team="Medic", db_path=path)

    teams = db.list_admin_teams(db_path=path)
    assert len(teams) == 1
    team = teams[0]
    assert team["team_name"] == "Alpha Squad"
    assert team["member_count"] == 2
    member_names = {m["full_name"] for m in team["members"]}
    assert member_names == {"Ravi Kumar", "Meena S"}
    # the JOIN pulls phone from personnel, not just the FK id
    ravi_member = next(m for m in team["members"] if m["person_id"] == "P001")
    assert ravi_member["phone"] == "9876543210"
    assert ravi_member["role_on_team"] == "Lead"


def test_team_with_no_members_has_empty_list(tmp_path):
    path = _tmp_db(tmp_path)
    db.init_db(path)
    db.create_admin_team("T002", "Bravo Squad", db_path=path)
    teams = db.list_admin_teams(db_path=path)
    assert teams[0]["member_count"] == 0
    assert teams[0]["members"] == []


def test_admin_registry_persists_across_scenario_reset(tmp_path):
    """
    The whole point of these being separate tables from the sensor-fusion
    schema: personnel/team/scenario-history records must NOT depend on
    ScenarioState.reset() clearing in-memory state - they only ever live
    in SQLite, so a reset can't touch them at all. This test asserts that
    property directly rather than relying on ScenarioState wiring (which
    isn't part of 29.1 - db.py has no concept of "scenario reset").
    """
    path = _tmp_db(tmp_path)
    db.init_db(path)
    db.add_personnel("P001", "Ravi Kumar", "Rescuer", db_path=path)
    db.create_admin_team("T001", "Alpha Squad", db_path=path)
    db.log_admin_scenario("SC001", "Himalaya Avalanche", "avalanche", 4, db_path=path)

    # simulate "app restart" by re-running init_db against the same file -
    # CREATE TABLE IF NOT EXISTS must not wipe existing rows
    db.init_db(path)

    assert len(db.list_personnel(db_path=path)) == 1
    assert len(db.list_admin_teams(db_path=path)) == 1
    assert len(db.list_admin_scenarios(db_path=path)) == 1
