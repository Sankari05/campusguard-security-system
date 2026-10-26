"""
test_commander_nearest.py
----------------------------
Tests for Step 22: nearest-needy-people suggestions for a team member
(GET /commander/nearest/{member_id}) with direct unauthenticated access.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_nearest_returns_sorted_by_distance(started_client):
    overview = started_client.get("/commander/overview").json()
    assert len(overview["team_members"]) > 0
    member_id = overview["team_members"][0]["member_id"]

    r = started_client.get(f"/commander/nearest/{member_id}")
    assert r.status_code == 200
    suggestions = r.json()["suggestions"]
    distances = [s["distance_m"] for s in suggestions]
    assert distances == sorted(distances)


def test_nearest_caps_at_suggestion_count(started_client):
    overview = started_client.get("/commander/overview").json()
    member_id = overview["team_members"][0]["member_id"]

    r = started_client.get(f"/commander/nearest/{member_id}")
    assert len(r.json()["suggestions"]) <= 5


def test_nearest_unknown_member_is_404(started_client):
    r = started_client.get("/commander/nearest/NOT-A-MEMBER")
    assert r.status_code == 404
