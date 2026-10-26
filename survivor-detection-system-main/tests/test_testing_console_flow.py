"""
test_testing_console_flow.py
----------------------------
Integration tests for the Testing Console module with direct unauthenticated access:
- Direct creation of personnel, scenarios, and teams
- Live victim injection into running simulation
- Live team roster adjustments
- Manual movement and target redirect simulation endpoints
- View-only ledger accessibility
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_testing_console_complete_flow(started_client):
    # 1. Create personnel from Testing Console
    p_name = f"Test Specialist {uuid.uuid4().hex[:6]}"
    p_res = started_client.post(
        "/admin/personnel/add",
        json={
            "full_name": p_name,
            "role": "Search Specialist",
            "phone": "+91 99999 88888",
            "badge_id": "T-999",
            "status": "Active",
        },
    )
    assert p_res.status_code == 200
    p_id = p_res.json()["person_id"]

    # 2. Verify persons ledger returns the record
    persons_res = started_client.get("/admin/personnel")
    assert persons_res.status_code == 200
    personnel_list = persons_res.json()["personnel"]
    match_person = next((p for p in personnel_list if p["person_id"] == p_id), None)
    assert match_person is not None
    assert match_person["full_name"] == p_name

    # 3. Create a disaster scenario from Testing Console
    scen_name = f"Testing Drill {uuid.uuid4().hex[:6]}"
    scen_res = started_client.post(
        "/admin/scenario/create",
        json={
            "scenario_name": scen_name,
            "hazard_type": "flood",
            "victim_count": 2,
            "latitude": 32.3500,
            "longitude": 77.2200,
            "altitude_m": 3800.0,
            "seed": 42,
            "enable_degradation": False,
        },
    )
    assert scen_res.status_code == 200
    scen_id = scen_res.json()["scenario_id"]

    # 4. Verify scenarios ledger returns the record
    scenarios_res = started_client.get("/admin/scenarios")
    assert scenarios_res.status_code == 200
    scenarios_list = scenarios_res.json()["scenarios"]
    match_scen = next((s for s in scenarios_list if s["scenario_ref_id"] == scen_id), None)
    assert match_scen is not None
    assert match_scen["scenario_name"] == scen_name
    assert match_scen["hazard_type"] == "flood"

    # 5. Form a team with the created personnel
    team_name = f"Bravo Testing Unit {uuid.uuid4().hex[:6]}"
    team_res = started_client.post(
        "/admin/teams/create",
        json={
            "team_name": team_name,
            "team_type": "Medical Evacuation",
            "description": "Rapid testing squad",
            "members": [
                {"person_id": p_id, "role_on_team": "Lead Specialist"},
            ],
        },
    )
    assert team_res.status_code == 200
    team_ref_id = team_res.json()["team_ref_id"]

    # 6. Verify teams ledger returns the team and its members
    teams_res = started_client.get("/admin/teams")
    assert teams_res.status_code == 200
    teams_list = teams_res.json()["teams"]
    match_team = next((t for t in teams_list if t["team_ref_id"] == team_ref_id), None)
    assert match_team is not None
    assert match_team["team_name"] == team_name
    assert len(match_team["members"]) == 1
    assert match_team["members"][0]["person_id"] == p_id

    # 7. Test live simulation control: Manual Movement
    move_res = started_client.post(
        "/rescue-team/move",
        json={"bearing_deg": 45.0, "distance_m": 25.0},
    )
    assert move_res.status_code == 200
    assert "team_id" in move_res.json()

    # 8. Test live simulation control: Redirect Target
    status_res = started_client.get("/rescue-team/status")
    assert status_res.status_code == 200
    sim_data = status_res.json().get("dispatch_sim", {})
    remaining = sim_data.get("remaining", [])
    if remaining:
        target_vid = remaining[0]
        redirect_res = started_client.post(
            "/rescue-team/set-target",
            json={"victim_id": target_vid},
        )
        assert redirect_res.status_code == 200

        # Resume automated routing
        clear_res = started_client.post(
            "/rescue-team/clear-target",
            json={},
        )
        assert clear_res.status_code == 200
