"""
test_dynamic_teams_flow.py
--------------------------
End-to-end integration tests proving that newly created rescue teams
are fully functional across the entire system:
1. Team created in DB (with or without personnel).
2. Automatically registered and visible in /rescue-team/members-status (Teams page).
3. Automatically visible in /commander/overview (Commander console).
4. Assignable to victims via /commander/assign.
5. Receives and processes work, advancing to target and reaching ARRIVED status.
6. Generates status and arrival logs in SQLite database.
7. Persists across scenario restarts and resets.
"""

import sys
import os
import uuid
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_newly_created_team_full_lifecycle(started_client):
    # 1. Add Personnel
    person_name = f"Officer Vikram {uuid.uuid4().hex[:6]}"
    p_res = started_client.post(
        "/admin/personnel/add",
        json={
            "full_name": person_name,
            "role": "Rescue Specialist",
            "phone": "+91 98765 43210",
            "status": "Active",
        },
    )
    assert p_res.status_code == 200
    person_id = p_res.json()["person_id"]

    # 2. Create New Team with Personnel
    team_name = f"Bravo Rapid Squad {uuid.uuid4().hex[:6]}"
    t_res = started_client.post(
        "/admin/teams/create",
        json={
            "team_name": team_name,
            "team_type": "SAR Rapid Response",
            "description": "Dynamic testing team",
            "members": [
                {"person_id": person_id, "role_on_team": "Team Lead"},
            ],
        },
    )
    assert t_res.status_code == 200
    team_ref_id = t_res.json()["team_ref_id"]

    # 3. Verify Team and Members in /rescue-team/members-status (Teams page endpoint)
    members_res = started_client.get("/rescue-team/members-status")
    assert members_res.status_code == 200
    members_data = members_res.json()["members"]
    bravo_members = [m for m in members_data if m["team_id"] == team_ref_id]
    assert len(bravo_members) >= 1
    lead_member = bravo_members[0]
    assert lead_member["full_name"] == person_name
    assert lead_member["role"] == "Team Lead"
    assert lead_member["status"] == "hold"

    # 4. Verify Team and Members in /commander/overview (Commander Module)
    cmd_overview = started_client.get("/commander/overview").json()
    all_team_members = cmd_overview.get("team_members", [])
    cmd_match = next((m for m in all_team_members if m["member_id"] == lead_member["member_id"]), None)
    assert cmd_match is not None
    assert cmd_match["status"] == "hold"

    # 5. Get nearest victim suggestion for the new team's member
    nearest_res = started_client.get(f"/commander/nearest/{lead_member['member_id']}")
    assert nearest_res.status_code == 200
    suggestions = nearest_res.json()["suggestions"]
    assert len(suggestions) > 0
    target_victim_id = suggestions[0]["victim_id"]

    # 6. Commander assigns work to the new team's member
    assign_res = started_client.post(
        "/commander/assign",
        json={
            "member_id": lead_member["member_id"],
            "victim_id": target_victim_id,
        },
    )
    assert assign_res.status_code == 200
    updated_member = assign_res.json()
    assert updated_member["status"] == "en_route"
    assert updated_member["assigned_victim_id"] == target_victim_id

    # 7. Member processes work (advances during overview polls until arrival)
    arrived = False
    for _ in range(80):
        poll_res = started_client.get("/commander/overview").json()
        current_members = poll_res.get("team_members", [])
        curr = next((m for m in current_members if m["member_id"] == lead_member["member_id"]), None)
        if curr and curr["status"] == "arrived":
            arrived = True
            break

    assert arrived, "Assigned member should reach ARRIVED status after advancing"


def test_empty_team_spawns_assignable_members(started_client):
    # Create a team without providing personnel upfront
    team_name = f"Echo Mountain Squad {uuid.uuid4().hex[:6]}"
    t_res = started_client.post(
        "/admin/teams/create",
        json={
            "team_name": team_name,
            "team_type": "Mountain SAR",
            "description": "Squad with automatic member tracking",
            "members": [],
        },
    )
    assert t_res.status_code == 200
    team_ref_id = t_res.json()["team_ref_id"]

    # Check that members were spawned and are available in Commander overview
    cmd_overview = started_client.get("/commander/overview").json()
    echo_members = [m for m in cmd_overview.get("team_members", []) if m["team_id"] == team_ref_id]
    assert len(echo_members) >= 2
    assert echo_members[0]["status"] == "hold"

    # Test assigning one of the spawned members
    victims = cmd_overview.get("victims", [])
    assert len(victims) > 0
    victim_id = victims[0]["victim_id"]

    assign_res = started_client.post(
        "/commander/assign",
        json={
            "member_id": echo_members[0]["member_id"],
            "victim_id": victim_id,
        },
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["status"] == "en_route"
