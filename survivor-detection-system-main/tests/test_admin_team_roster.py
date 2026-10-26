"""
test_admin_team_roster.py
----------------------------
Tests for Step 20: team roster resizing (member count
increase/decrease + tracked-sample spawning) with direct unauthenticated access.

Note: uses "ALPHA" as the team_id under test, not "TEAM-A" - the default
himalaya_avalanche scenario (loaded by the started_client fixture) defines
its rescue teams as ALPHA/BRAVO (see backend/scenarios/himalaya_avalanche.json
and backend/api.py's docstrings), so "TEAM-A" would 422 as an unknown team.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_increase_member_count_to_500_updates_team(started_client):
    r = started_client.post(
        "/admin/teams/ALPHA/roster", json={"member_count": 500},
    )
    assert r.status_code == 200
    assert r.json()["team"]["members"] == 500


def test_tracked_sample_capped_even_with_500_members(started_client):
    r = started_client.post(
        "/admin/teams/ALPHA/roster", json={"member_count": 500},
    )
    assert len(r.json()["tracked_members"]) == 8   # TRACKED_MEMBER_SAMPLE_SIZE


def test_decrease_member_count_shrinks_tracked_sample(started_client):
    started_client.post("/admin/teams/ALPHA/roster", json={"member_count": 20})
    r = started_client.post("/admin/teams/ALPHA/roster", json={"member_count": 3})
    assert r.status_code == 200
    assert r.json()["team"]["members"] == 3
    assert len(r.json()["tracked_members"]) == 3


def test_negative_member_count_is_rejected(started_client):
    r = started_client.post("/admin/teams/ALPHA/roster", json={"member_count": -5})
    assert r.status_code == 422


def test_unknown_team_id_is_rejected(started_client):
    r = started_client.post("/admin/teams/NOT-A-TEAM/roster", json={"member_count": 10})
    assert r.status_code == 422


def test_roster_resize_requires_running_scenario(api_client):
    r = api_client.post("/admin/teams/ALPHA/roster", json={"member_count": 10})
    assert r.status_code == 400
