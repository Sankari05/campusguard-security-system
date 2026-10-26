"""
test_rescue_team_member_arrivals.py
--------------------------------------
Tests for Step 26: GET /rescue-team/member-arrivals - the public,
unauthenticated, read-only rolling arrivals feed for the Dashboard's
alert log. Deliberately does NOT trigger movement itself - movement
ticking is still sourced only from /commander/overview (Step 23).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_member_arrivals_requires_no_auth(started_client):
    r = started_client.get("/rescue-team/member-arrivals")
    assert r.status_code == 200


def test_member_arrivals_starts_empty(started_client):
    r = started_client.get("/rescue-team/member-arrivals")
    assert r.json()["arrivals"] == []


def test_member_arrivals_reflects_a_real_arrival(started_client):
    overview = started_client.get("/commander/overview").json()
    member_id = overview["team_members"][0]["member_id"]
    victim_id = overview["victims"][0]["victim_id"]

    started_client.post(
        "/commander/assign", json={"member_id": member_id, "victim_id": victim_id},
    )

    arrived = False
    for _ in range(50):
        poll = started_client.get("/commander/overview").json()
        m = next(x for x in poll["team_members"] if x["member_id"] == member_id)
        if m["status"] == "arrived":
            arrived = True
            break
    assert arrived

    r = started_client.get("/rescue-team/member-arrivals")
    arrivals = r.json()["arrivals"]
    assert any(a["member_id"] == member_id and a["victim_id"] == victim_id for a in arrivals)


def test_member_arrivals_since_cursor_excludes_old_entries(started_client):
    overview = started_client.get("/commander/overview").json()
    member_id = overview["team_members"][0]["member_id"]
    victim_id = overview["victims"][0]["victim_id"]

    started_client.post(
        "/commander/assign", json={"member_id": member_id, "victim_id": victim_id},
    )
    for _ in range(50):
        poll = started_client.get("/commander/overview").json()
        m = next(x for x in poll["team_members"] if x["member_id"] == member_id)
        if m["status"] == "arrived":
            break

    first = started_client.get("/rescue-team/member-arrivals").json()["arrivals"]
    assert len(first) >= 1
    last_ts = first[-1]["arrived_at"]

    from urllib.parse import quote
    since_r = started_client.get(f"/rescue-team/member-arrivals?since={quote(last_ts, safe='')}")
    assert since_r.json()["arrivals"] == []


def test_polling_member_arrivals_does_not_move_members():
    """Safety: this endpoint must never trigger advance_team_members() itself."""
    from fastapi.testclient import TestClient
    from api import app

    client = TestClient(app)
    client.post("/scenario/reset")
    client.post("/scenario/start", json={"seed": 42, "enable_degradation": False})

    overview = client.get("/commander/overview").json()
    member_id = overview["team_members"][0]["member_id"]
    victim_id = overview["victims"][0]["victim_id"]

    client.post(
        "/commander/assign", json={"member_id": member_id, "victim_id": victim_id},
    )

    watch_before = client.get(f"/watch/{member_id}").json()
    distance_before = watch_before.get("distance_m")

    # Poll the public arrivals feed repeatedly - this must NOT tick movement.
    for _ in range(10):
        client.get("/rescue-team/member-arrivals")

    watch_after = client.get(f"/watch/{member_id}").json()
    distance_after = watch_after.get("distance_m")

    assert distance_before is not None and distance_after is not None
    assert distance_after == distance_before, \
        "member moved after only polling /rescue-team/member-arrivals - safety gate violated"

    client.post("/scenario/reset")
