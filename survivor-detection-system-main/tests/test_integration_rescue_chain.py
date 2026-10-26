"""
test_integration_rescue_chain.py
------------------------------------
Step 25: end-to-end integration test walking the FULL rescue-team chain
across Steps 19-24 in one continuous flow directly with zero authentication:

  increase roster -> commander sees the new member (HOLD) -> nearest-suggestion
  -> assign -> watch shows GO -> member physically moves over successive polls
  -> arrives -> watch shows ARRIVED -> dashboard's alert log reflects the arrival.

Note: uses "ALPHA" as the team_id under test, not "TEAM-A" - the default
Himalaya Avalanche scenario names its rescue teams ALPHA/BRAVO (see
backend/scenarios/himalaya_avalanche.json), so "TEAM-A" would 422 as an
unknown team.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_full_rescue_chain_admin_to_watch_arrival(started_client):
    # 1. Increase ALPHA's roster (Step 20)
    roster_r = started_client.post(
        "/admin/teams/ALPHA/roster", json={"member_count": 12},
    )
    assert roster_r.status_code == 200
    assert roster_r.json()["team"]["members"] == 12

    # 2. Commander overview sees the new members, all starting HOLD (Step 21)
    overview = started_client.get("/commander/overview").json()
    team_a_members = [m for m in overview["team_members"] if m["team_id"] == "ALPHA"]
    assert len(team_a_members) == min(12, 8)   # TRACKED_MEMBER_SAMPLE_SIZE cap
    assert all(m["status"] == "hold" for m in team_a_members)

    member_id = team_a_members[0]["member_id"]

    # 3. Watch, before assignment, shows HOLD (Step 24) - matches commander view
    watch_before = started_client.get(f"/watch/{member_id}").json()
    assert watch_before["status"] == "hold"

    # 4. Nearest-suggestion (Step 22) returns a real candidate
    nearest = started_client.get(f"/commander/nearest/{member_id}").json()
    assert len(nearest["suggestions"]) > 0
    target_victim_id = nearest["suggestions"][0]["victim_id"]

    # 5. Commander assigns (Step 23) - the ONLY action that should change status
    assign_r = started_client.post(
        "/commander/assign", json={"member_id": member_id, "victim_id": target_victim_id},
    )
    assert assign_r.status_code == 200
    assert assign_r.json()["status"] == "en_route"

    # 6. Watch immediately reflects the GO signal (Step 24)
    watch_after_assign = started_client.get(f"/watch/{member_id}").json()
    assert watch_after_assign["status"] == "en_route"
    assert watch_after_assign["assigned_victim_id"] == target_victim_id
    assert "distance_label" in watch_after_assign and "compass_label" in watch_after_assign

    # 7. Successive commander polls physically move the member closer (Step 23 movement sim)
    for _ in range(50):   # enough polls at MEMBER_WALK_SPEED_MPS to guarantee arrival on a ~180m-span site
        poll = started_client.get("/commander/overview").json()
        m = next(x for x in poll["team_members"] if x["member_id"] == member_id)
        if m["status"] == "arrived":
            break

    # 8. Member eventually arrives (Step 23 arrival threshold)
    final_poll = started_client.get("/commander/overview").json()
    final_member = next(x for x in final_poll["team_members"] if x["member_id"] == member_id)
    assert final_member["status"] == "arrived"

    # 9. Watch reflects ARRIVED too - loop fully closed (Step 24)
    watch_final = started_client.get(f"/watch/{member_id}").json()
    assert watch_final["status"] == "arrived"


# --------------------------------------------------------------------------- #
# Safety-gate negative tests - no auto-assignment anywhere
# --------------------------------------------------------------------------- #

def test_new_roster_members_always_start_hold(started_client):
    """Safety gate: increasing roster count must NEVER auto-assign anyone."""
    started_client.post("/admin/teams/ALPHA/roster", json={"member_count": 8})
    overview = started_client.get("/commander/overview").json()

    assert all(m["status"] == "hold" and m["assigned_victim_id"] is None for m in overview["team_members"])


def test_polling_overview_never_changes_hold_members(started_client):
    """Safety gate: advance_team_members() must only move EN_ROUTE members, never touch HOLD ones."""
    before = started_client.get("/commander/overview").json()
    hold_locations_before = {
        m["member_id"]: m["location"] for m in before["team_members"] if m["status"] == "hold"
    }

    for _ in range(5):
        started_client.get("/commander/overview")

    after = started_client.get("/commander/overview").json()
    for m in after["team_members"]:
        if m["member_id"] in hold_locations_before:
            assert m["location"] == hold_locations_before[m["member_id"]], \
                f"{m['member_id']} moved despite never being assigned - safety gate violated"


def test_watch_endpoint_never_exposes_other_members_data(started_client):
    """A watch can only ever see its OWN assignment - never the full roster/victim list."""
    overview = started_client.get("/commander/overview").json()
    member_id = overview["team_members"][0]["member_id"]

    watch_data = started_client.get(f"/watch/{member_id}").json()
    assert "team_members" not in watch_data
    assert "victims" not in watch_data
    assert set(watch_data.keys()) <= {
        "member_id", "callsign", "status", "message", "assigned_victim_id",
        "distance_m", "distance_label", "bearing_deg", "compass_label",
    }
