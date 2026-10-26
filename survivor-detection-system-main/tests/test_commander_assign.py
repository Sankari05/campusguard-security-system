"""
test_commander_assign.py
---------------------------
Tests for Step 23: manual member assignment (POST /commander/assign) +
automatic movement/arrival simulation (advance_team_members()) with direct unauthenticated access.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_assign_flips_member_to_en_route(started_client):
    overview = started_client.get("/commander/overview").json()
    member_id = overview["team_members"][0]["member_id"]
    victim_id = overview["victims"][0]["victim_id"]

    r = started_client.post(
        "/commander/assign", json={"member_id": member_id, "victim_id": victim_id},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "en_route"
    assert r.json()["assigned_victim_id"] == victim_id


def test_assign_unknown_member_is_404(started_client):
    overview = started_client.get("/commander/overview").json()
    victim_id = overview["victims"][0]["victim_id"]

    r = started_client.post(
        "/commander/assign", json={"member_id": "GHOST-M999", "victim_id": victim_id},
    )
    assert r.status_code == 404


def test_assign_unknown_victim_is_404(started_client):
    overview = started_client.get("/commander/overview").json()
    member_id = overview["team_members"][0]["member_id"]

    r = started_client.post(
        "/commander/assign", json={"member_id": member_id, "victim_id": "GHOST-V999"},
    )
    assert r.status_code == 404


def test_assigned_member_moves_toward_victim_over_polls(started_client):
    overview = started_client.get("/commander/overview").json()
    member = overview["team_members"][0]
    victim = overview["victims"][0]
    started_client.post(
        "/commander/assign", json={"member_id": member["member_id"], "victim_id": victim["victim_id"]},
    )

    from rescue_dispatch import haversine_distance_m
    from models import GPSCoordinate

    before = started_client.get("/commander/overview").json()
    m_before = next(m for m in before["team_members"] if m["member_id"] == member["member_id"])
    dist_before = haversine_distance_m(
        GPSCoordinate(**m_before["location"]), GPSCoordinate(**victim["location"])
    )

    after = started_client.get("/commander/overview").json()
    m_after = next(m for m in after["team_members"] if m["member_id"] == member["member_id"])
    dist_after = haversine_distance_m(
        GPSCoordinate(**m_after["location"]), GPSCoordinate(**victim["location"])
    )

    assert dist_after < dist_before or m_after["status"] == "arrived"
