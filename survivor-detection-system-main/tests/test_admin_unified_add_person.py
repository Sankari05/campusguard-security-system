"""
test_admin_unified_add_person.py
---------------------------------
Comprehensive unit and integration tests for the unified Add Person workflow:
1. Extended AddVictimRequest with clinical and demographic fields.
2. Custom burial_depth_m override on victim addition.
3. Auto-generation of victim_id when omitted.
4. Adding unassigned team member linked to persistent DB personnel ID.
5. Error cases (400 if no scenario running, 409 duplicate ID).
6. Commander team transfer / assignment endpoint.
7. Verification that unassigned members appear in commander overview and members-status.
"""

import pytest
from models import MemberStatus


def test_add_victim_with_extended_clinical_fields(started_client):
    r = started_client.post(
        "/admin/victims/add",
        json={
            "label": "Priya Sharma (Trapped Climber)",
            "status": "HIGH",
            "latitude": 32.3742,
            "longitude": 77.2494,
            "altitude_m": 3955.0,
            "burial_depth_m": 0.8,
            "consciousness": "Semi-conscious",
            "mobility": "Immobile",
            "injury_notes": "Right leg fracture, signs of hypothermia",
            "age": 28,
            "gender": "Female",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["added"] is True
    assert data["victim_id"].startswith("V")
    assert data["status"] == "HIGH"

    # Check that victim is returned with extended fields in victim payload
    victim_data = data["victim"]
    assert victim_data["burial_depth_m"] == 0.8
    assert victim_data["consciousness"] == "Semi-conscious"
    assert victim_data["mobility"] == "Immobile"
    assert victim_data["age"] == 28
    assert victim_data["gender"] == "Female"
    assert "hypothermia" in victim_data["notes"]

    # Verify live ticker reflects new victim
    started_client.get("/victims")
    victims = started_client.get("/victims").json()["victims"]
    match = next((v for v in victims if v["victim_id"] == data["victim_id"]), None)
    assert match is not None
    assert pytest.approx(match["location"]["latitude"], abs=0.005) == 32.3742


def test_add_unassigned_team_member_requires_running_scenario(api_client):
    r = api_client.post(
        "/admin/team-members/add-unassigned",
        json={
            "person_id": "P9999",
            "full_name": "Dr. Aarav Mehta",
            "role": "Medic",
        },
    )
    assert r.status_code == 400
    assert "running" in r.json()["detail"].lower()


def test_add_unassigned_team_member_live_lifecycle(started_client):
    # 1. Register staff in DB ledger
    personnel_res = started_client.post(
        "/admin/personnel/add",
        json={
            "full_name": "Kavita Rao",
            "role": "Medic",
            "phone": "9876543210",
            "email": "kavita@ridgewatch.org",
            "status": "Active",
            "badge_id": "MED-404",
        },
    )
    assert personnel_res.status_code == 200
    p_id = personnel_res.json()["person_id"]

    # 2. Add as unassigned team member to active scenario
    unassigned_res = started_client.post(
        "/admin/team-members/add-unassigned",
        json={
            "person_id": p_id,
            "full_name": "Kavita Rao",
            "role": "Medic",
            "phone": "9876543210",
            "badge_id": "MED-404",
        },
    )
    assert unassigned_res.status_code == 200
    m_data = unassigned_res.json()["member"]
    assert m_data["team_id"] == "UNASSIGNED"
    assert m_data["personnel_id"] == p_id
    assert m_data["status"] == "hold"

    # 3. Verify member appears in Commander overview
    overview = started_client.get("/commander/overview").json()
    members = overview["team_members"]
    pool_member = next((m for m in members if m["personnel_id"] == p_id), None)
    assert pool_member is not None
    assert pool_member["team_id"] == "UNASSIGNED"
    assert pool_member["full_name"] == "Kavita Rao"

    # 4. Verify member appears in /rescue-team/members-status
    status_res = started_client.get("/rescue-team/members-status").json()
    assert any(m["personnel_id"] == p_id for m in status_res["members"])

    # 5. Duplicate unassigned addition is rejected
    dup_res = started_client.post(
        "/admin/team-members/add-unassigned",
        json={
            "person_id": p_id,
            "full_name": "Kavita Rao",
            "role": "Medic",
        },
    )
    assert dup_res.status_code == 409


def test_assign_unassigned_member_to_team(started_client):
    # Register and link unassigned staff
    p_res = started_client.post(
        "/admin/personnel/add",
        json={"full_name": "Siddharth Verma", "role": "Technician"},
    )
    p_id = p_res.json()["person_id"]

    u_res = started_client.post(
        "/admin/team-members/add-unassigned",
        json={"person_id": p_id, "full_name": "Siddharth Verma", "role": "Technician"},
    )
    m_id = u_res.json()["member"]["member_id"]

    # Assign from UNASSIGNED pool to ALPHA team
    assign_team_res = started_client.post(
        "/commander/team/assign-member",
        json={"member_id": m_id, "target_team_id": "ALPHA", "role": "Lead Tech"},
    )
    assert assign_team_res.status_code == 200
    updated_member = assign_team_res.json()["member"]
    assert updated_member["team_id"] == "ALPHA"
    assert updated_member["role"] == "Lead Tech"

    # Confirm commander overview shows updated squad membership
    overview = started_client.get("/commander/overview").json()
    m_in_overview = next(m for m in overview["team_members"] if m["member_id"] == m_id)
    assert m_in_overview["team_id"] == "ALPHA"


def test_unassigned_member_direct_victim_assignment(started_client):
    # Register unassigned staff
    p_res = started_client.post(
        "/admin/personnel/add",
        json={"full_name": "Deepak Joshi", "role": "Rescuer"},
    )
    p_id = p_res.json()["person_id"]
    u_res = started_client.post(
        "/admin/team-members/add-unassigned",
        json={"person_id": p_id, "full_name": "Deepak Joshi", "role": "Rescuer"},
    )
    m_id = u_res.json()["member"]["member_id"]

    # Assign directly to victim V2
    assign_res = started_client.post(
        "/commander/assign",
        json={"member_id": m_id, "victim_id": "V2"},
    )
    assert assign_res.status_code == 200
    assigned_data = assign_res.json()
    assert assigned_data["member_id"] == m_id
    assert assigned_data["assigned_victim_id"] == "V2"
    assert assigned_data["status"] == "en_route"

    # Confirm member is EN_ROUTE in overview
    overview = started_client.get("/commander/overview").json()
    m = next(x for x in overview["team_members"] if x["member_id"] == m_id)
    assert m["status"] == "en_route"
    assert m["assigned_victim_id"] == "V2"
