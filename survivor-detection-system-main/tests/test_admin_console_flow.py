"""
test_admin_console_flow.py
--------------------------
End-to-end integration tests for the Console flow:
- Personnel staff registration & view-only ledger persistence
- Custom disaster scenario creation, launching & view-only historical ledger
- Team formation with personnel assignment & view-only ledger
- Direct unauthenticated access for all operations
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_complete_admin_console_workflow(api_client):
    # 1. Register multiple rescue personnel staff
    p1_name = f"Arun Kumar {uuid.uuid4().hex[:6]}"
    p1_res = api_client.post(
        "/admin/personnel/add",
        json={
            "full_name": p1_name,
            "role": "Rescuer",
            "phone": "+91 98765 11111",
            "email": "arun@ridgewatch.org",
            "badge_id": "B-001",
            "status": "Active",
        },
    )
    assert p1_res.status_code == 200
    p1_id = p1_res.json()["person_id"]
    assert p1_id.startswith("P")

    p2_name = f"Deepa Nair {uuid.uuid4().hex[:6]}"
    p2_res = api_client.post(
        "/admin/personnel/add",
        json={
            "full_name": p2_name,
            "role": "Medic",
            "phone": "+91 98765 22222",
            "email": "deepa@ridgewatch.org",
            "badge_id": "B-002",
            "status": "Active",
        },
    )
    assert p2_res.status_code == 200
    p2_id = p2_res.json()["person_id"]

    # 2. View Persons Ledger
    persons_ledger = api_client.get("/admin/personnel")
    assert persons_ledger.status_code == 200
    personnel_list = persons_ledger.json()["personnel"]
    
    match_p1 = next((p for p in personnel_list if p["person_id"] == p1_id), None)
    assert match_p1 is not None
    assert match_p1["full_name"] == p1_name
    assert match_p1["role"] == "Rescuer"
    assert match_p1["created_at"] is not None

    match_p2 = next((p for p in personnel_list if p["person_id"] == p2_id), None)
    assert match_p2 is not None
    assert match_p2["role"] == "Medic"

    # 3. Create a custom disaster scenario
    scenario_name = f"Rohtang Landslide Drill {uuid.uuid4().hex[:6]}"
    scen_res = api_client.post(
        "/admin/scenario/create",
        json={
            "scenario_name": scenario_name,
            "hazard_type": "earthquake",
            "victim_count": 3,
            "latitude": 32.3716,
            "longitude": 77.2466,
            "altitude_m": 3950.0,
            "seed": 101,
            "enable_degradation": True,
        },
    )
    assert scen_res.status_code == 200
    scen_data = scen_res.json()
    assert scen_data["created"] is True
    scen_id = scen_data["scenario_id"]

    # 4. View Scenarios Ledger
    scenarios_ledger = api_client.get("/admin/scenarios")
    assert scenarios_ledger.status_code == 200
    scenarios_list = scenarios_ledger.json()["scenarios"]
    match_scen = next((s for s in scenarios_list if s["scenario_ref_id"] == scen_id), None)
    assert match_scen is not None
    assert match_scen["scenario_name"] == scenario_name
    assert match_scen["hazard_type"] == "earthquake"
    assert match_scen["victim_count"] == 3
    assert abs(match_scen["latitude"] - 32.3716) < 0.0001
    assert abs(match_scen["longitude"] - 77.2466) < 0.0001
    assert match_scen["created_at"] is not None

    # 5. Form a Rescue Team with the registered personnel
    team_name = f"Alpha Mountain Unit {uuid.uuid4().hex[:6]}"
    team_res = api_client.post(
        "/admin/teams/create",
        json={
            "team_name": team_name,
            "team_type": "Search & Rescue",
            "description": "High altitude rapid deployment unit",
            "members": [
                {"person_id": p1_id, "role_on_team": "Team Leader"},
                {"person_id": p2_id, "role_on_team": "Lead Medic"},
            ],
        },
    )
    assert team_res.status_code == 200
    team_ref_id = team_res.json()["team_ref_id"]
    assert team_ref_id.startswith("T")

    # 6. View Rescue Teams Ledger
    teams_ledger = api_client.get("/admin/teams")
    assert teams_ledger.status_code == 200
    teams_list = teams_ledger.json()["teams"]
    match_team = next((t for t in teams_list if t["team_ref_id"] == team_ref_id), None)
    assert match_team is not None
    assert match_team["team_name"] == team_name
    assert match_team["team_type"] == "Search & Rescue"
    assert match_team["member_count"] == 2
    assert len(match_team["members"]) == 2
    assert {m["person_id"] for m in match_team["members"]} == {p1_id, p2_id}
    assert match_team["created_at"] is not None
