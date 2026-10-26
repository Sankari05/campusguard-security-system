"""
test_admin_registry_api.py
-------------------------------
API-level tests for Step 29.2: personnel/scenario-history/team-registry
create + view-only ledger endpoints with direct unauthenticated access.
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


# --- Personnel -------------------------------------------------------- #

def test_add_and_list_personnel(api_client):
    unique_name = f"Test Rescuer {uuid.uuid4().hex[:8]}"
    r = api_client.post(
        "/admin/personnel/add",
        json={"full_name": unique_name, "role": "Rescuer", "phone": "9876543210", "badge_id": "B-999"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["created"] is True
    person_id = body["person_id"]
    assert person_id.startswith("P")

    ledger = api_client.get("/admin/personnel")
    assert ledger.status_code == 200
    people = ledger.json()["personnel"]
    match = next((p for p in people if p["person_id"] == person_id), None)
    assert match is not None
    assert match["full_name"] == unique_name
    assert match["role"] == "Rescuer"
    assert match["status"] == "Active"   # default


# --- Scenario history --------------------------------------------------- #

def test_creating_custom_scenario_persists_to_scenario_ledger(api_client):
    unique_name = f"Test Avalanche {uuid.uuid4().hex[:8]}"
    r = api_client.post(
        "/admin/scenario/create",
        json={
            "hazard_type": "avalanche",
            "victim_count": 2,
            "latitude": 32.30,
            "longitude": 77.20,
            "scenario_name": unique_name,
            "seed": 7,
            "enable_degradation": False,
        },
    )
    assert r.status_code == 200
    scenario_id = r.json()["scenario_id"]

    ledger = api_client.get("/admin/scenarios")
    assert ledger.status_code == 200
    scenarios = ledger.json()["scenarios"]
    match = next((s for s in scenarios if s["scenario_ref_id"] == scenario_id), None)
    assert match is not None
    assert match["scenario_name"] == unique_name
    assert match["hazard_type"] == "avalanche"
    assert match["victim_count"] == 2


# --- Team registry ------------------------------------------------------- #

def test_create_team_with_members_and_view_ledger(api_client):
    # need real personnel rows first, since add_team_member's JOIN in
    # list_admin_teams() requires a matching personnel row to appear
    p1 = api_client.post(
        "/admin/personnel/add",
        json={"full_name": f"Lead {uuid.uuid4().hex[:8]}", "role": "Rescuer"},
    ).json()["person_id"]
    p2 = api_client.post(
        "/admin/personnel/add",
        json={"full_name": f"Medic {uuid.uuid4().hex[:8]}", "role": "Medic"},
    ).json()["person_id"]

    unique_team_name = f"Test Squad {uuid.uuid4().hex[:8]}"
    r = api_client.post(
        "/admin/teams/create",
        json={
            "team_name": unique_team_name,
            "team_type": "SAR",
            "description": "test squad",
            "members": [
                {"person_id": p1, "role_on_team": "Lead"},
                {"person_id": p2, "role_on_team": "Medic"},
            ],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["created"] is True
    team_ref_id = body["team_ref_id"]
    assert team_ref_id.startswith("T")

    ledger = api_client.get("/admin/teams")
    assert ledger.status_code == 200
    teams = ledger.json()["teams"]
    match = next((t for t in teams if t["team_ref_id"] == team_ref_id), None)
    assert match is not None
    assert match["team_name"] == unique_team_name
    assert match["member_count"] == 2
    member_ids = {m["person_id"] for m in match["members"]}
    assert member_ids == {p1, p2}


def test_create_team_with_no_members_is_allowed(api_client):
    r = api_client.post(
        "/admin/teams/create",
        json={"team_name": f"Empty Squad {uuid.uuid4().hex[:8]}"},
    )
    assert r.status_code == 200
    assert r.json()["created"] is True


def test_team_registry_is_independent_of_running_scenario(api_client):
    r = api_client.post(
        "/admin/teams/create",
        json={"team_name": f"No Scenario Squad {uuid.uuid4().hex[:8]}"},
    )
    assert r.status_code == 200
