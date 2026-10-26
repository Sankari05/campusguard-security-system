"""
test_watch_view.py
--------------------
Tests for Step 24: GET /watch/{member_id} - the unauthenticated,
self-scoped simulated wearable endpoint.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_watch_requires_no_auth(started_client):
    overview = started_client.get("/commander/overview").json()
    member_id = overview["team_members"][0]["member_id"]

    r = started_client.get(f"/watch/{member_id}")
    assert r.status_code == 200


def test_watch_hold_status_before_assignment(started_client):
    overview = started_client.get("/commander/overview").json()
    member_id = overview["team_members"][0]["member_id"]

    r = started_client.get(f"/watch/{member_id}")
    body = r.json()
    assert body["status"] == "hold"
    assert body["member_id"] == member_id


def test_watch_en_route_shows_distance_and_compass(started_client):
    overview = started_client.get("/commander/overview").json()
    member_id = overview["team_members"][0]["member_id"]
    victim_id = overview["victims"][0]["victim_id"]

    started_client.post(
        "/commander/assign", json={"member_id": member_id, "victim_id": victim_id},
    )

    r = started_client.get(f"/watch/{member_id}")
    body = r.json()
    assert body["status"] == "en_route"
    assert body["assigned_victim_id"] == victim_id
    assert "distance_m" in body
    assert "compass_label" in body
    assert body["compass_label"] in ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def test_watch_unknown_member_is_404(started_client):
    r = started_client.get("/watch/GHOST-M999")
    assert r.status_code == 404
