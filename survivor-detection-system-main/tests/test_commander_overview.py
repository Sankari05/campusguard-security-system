"""
test_commander_overview.py
------------------------------
Tests for Step 21: GET /commander/overview (dual-layer map data) with direct unauthenticated access.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_commander_overview_dual_layer_payload(started_client):
    r = started_client.get("/commander/overview")
    assert r.status_code == 200
    body = r.json()
    assert "victims" in body and "team_members" in body and "scenario" in body
    assert len(body["victims"]) == 4   # default himalaya_avalanche scenario has 4 victims

    # victims carry triage/priority fields, same shape as /queue
    for v in body["victims"]:
        assert "victim_id" in v and "triage_class" in v and "sps" in v

    # team_members is flattened across all teams (ALPHA + BRAVO tracked samples)
    assert len(body["team_members"]) > 0
    for m in body["team_members"]:
        assert "member_id" in m and "callsign" in m and "status" in m


def test_commander_overview_requires_running_scenario(api_client):
    r = api_client.get("/commander/overview")
    assert r.status_code == 409   # _require_running() (same pattern as /queue)
