"""
Test Watch Module State Transitions:
STANDBY ➔ GO ➔ EN ROUTE ➔ ARRIVED ➔ RESCUED
Validates that the Watch module correctly reflects the rescuer's active operational state
as the Commander assigns work and the rescuer moves towards and reaches the needy people.
"""

from api import operations
from models import MemberStatus, GPSCoordinate


def test_teams_endpoint_returns_roster(started_client):
    """Ensure /teams returns the structured team and member roster."""
    res = started_client.get("/teams")
    assert res.status_code == 200
    data = res.json()
    assert "teams" in data
    assert "team_members" in data
    assert len(data["teams"]) >= 1
    assert len(data["team_members"]) >= 1
    member_ids = [m["member_id"] for m in data["team_members"]]
    assert "ALPHA-M001" in member_ids


def test_watch_state_unassigned_is_standby(started_client):
    """Ensure unassigned member returns status 'hold' (STANDBY)."""
    res = started_client.get("/watch/ALPHA-M001")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "hold"
    assert data.get("assigned_victim_id") is None
    assert data.get("distance_m", 0.0) == 0.0


def test_watch_state_assigned_and_en_route(started_client):
    """Ensure Commander assignment transitions member to 'en_route' with live bearing and distance."""
    # Find a valid victim
    overview = started_client.get("/commander/overview").json()
    victims = overview["victims"]
    assert len(victims) > 0
    victim_id = victims[0]["victim_id"]

    # Assign ALPHA-M001 to the victim
    assign_res = started_client.post(
        "/commander/assign",
        json={"member_id": "ALPHA-M001", "victim_id": victim_id},
    )
    assert assign_res.status_code == 200

    # Query Watch view
    watch_res = started_client.get("/watch/ALPHA-M001")
    assert watch_res.status_code == 200
    watch_data = watch_res.json()

    assert watch_data["status"] == "en_route"
    assert watch_data["assigned_victim_id"] == victim_id
    assert watch_data["distance_m"] > 0
    assert "compass_label" in watch_data
    assert "bearing_deg" in watch_data


def test_watch_state_arrival_at_victim_location(started_client):
    """Ensure rescuer reaching target location transitions to 'arrived' state."""
    overview = started_client.get("/commander/overview").json()
    victim_id = overview["victims"][0]["victim_id"]

    # Assign ALPHA-M001
    started_client.post(
        "/commander/assign",
        json={"member_id": "ALPHA-M001", "victim_id": victim_id},
    )

    # Move ALPHA-M001 directly to victim location to simulate arrival
    op = next(iter(operations.values()))
    target_victim = next(v for v in op.config.victims if v.victim_id == victim_id)
    alpha_member = next(
        m for members in op.team_members.values() for m in members if m.member_id == "ALPHA-M001"
    )
    alpha_member.location = GPSCoordinate(
        latitude=target_victim.location.latitude,
        longitude=target_victim.location.longitude,
        altitude_m=target_victim.location.altitude_m,
    )

    # Watch endpoint should now detect arrival
    watch_res = started_client.get("/watch/ALPHA-M001")
    assert watch_res.status_code == 200
    watch_data = watch_res.json()

    assert watch_data["status"] == "arrived"
    assert watch_data["distance_m"] <= 15.0


def test_watch_state_rescued_complete(started_client):
    """Ensure completed rescue reflects rescued status."""
    overview = started_client.get("/commander/overview").json()
    victim_id = overview["victims"][0]["victim_id"]

    started_client.post(
        "/commander/assign",
        json={"member_id": "ALPHA-M001", "victim_id": victim_id},
    )

    op = next(iter(operations.values()))
    alpha_member = next(
        m for members in op.team_members.values() for m in members if m.member_id == "ALPHA-M001"
    )
    alpha_member.status = MemberStatus.RESCUED

    watch_res = started_client.get("/watch/ALPHA-M001")
    assert watch_res.status_code == 200
    watch_data = watch_res.json()
    assert watch_data["status"] == "rescued"
