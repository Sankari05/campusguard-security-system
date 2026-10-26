"""
test_cmd_leader_auth.py
--------------------------
Verifies that Commander endpoints are directly accessible without any authentication tokens.
"""


def test_commander_overview_direct_access(started_client):
    r = started_client.get("/commander/overview")
    assert r.status_code == 200
    body = r.json()
    assert "scenario" in body
    assert "victims" in body
    assert "team_members" in body


def test_commander_nearest_direct_access(started_client):
    r = started_client.get("/commander/overview")
    members = r.json()["team_members"]
    if members:
        member_id = members[0]["member_id"]
        res = started_client.get(f"/commander/nearest/{member_id}")
        assert res.status_code == 200
        assert "suggestions" in res.json()


def test_commander_assign_direct_access(started_client):
    r = started_client.get("/commander/overview")
    body = r.json()
    members = body["team_members"]
    victims = body["victims"]
    if members and victims:
        member_id = members[0]["member_id"]
        victim_id = victims[0]["victim_id"]
        res = started_client.post("/commander/assign", json={"member_id": member_id, "victim_id": victim_id})
        assert res.status_code == 200
        assert res.json()["status"] == "en_route"
