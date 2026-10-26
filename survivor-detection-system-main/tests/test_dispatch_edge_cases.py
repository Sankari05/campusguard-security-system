"""
test_dispatch_edge_cases.py
------------------------------
Additional edge-case coverage for backend/rescue_dispatch.py, complementing
the existing end-to-end tests/test_rescue_dispatch.py (full 4-victim
Himalaya sequence via the REST API). This file unit-tests the
RescueDispatchAgent and haversine_distance_m directly, covering:

  * haversine distance sanity (zero distance, known reference distance)
  * empty queue / no-op advance behavior
  * single-victim queue
  * exact-arrival vs. partial-step movement
  * mid-simulation re-prioritization (load_queue called again with a new
    order while a walk is in progress)
  * is_complete() / status_dict() consistency
  * zero-speed team (eta_seconds_to_current_target must be None, not raise)
"""

import math

import pytest

from models import GPSCoordinate
from rescue_dispatch import RescueDispatchAgent, haversine_distance_m


ORIGIN = GPSCoordinate(latitude=32.3739, longitude=77.2491, altitude_m=3950)
V1 = GPSCoordinate(latitude=32.37401, longitude=77.24898, altitude_m=3946)
V2 = GPSCoordinate(latitude=32.37378, longitude=77.24935, altitude_m=3948)


class TestHaversineDistance:
    def test_distance_to_self_is_zero(self):
        assert haversine_distance_m(ORIGIN, ORIGIN) == pytest.approx(0.0, abs=1e-6)

    def test_distance_is_symmetric(self):
        d1 = haversine_distance_m(ORIGIN, V1)
        d2 = haversine_distance_m(V1, ORIGIN)
        assert d1 == pytest.approx(d2)

    def test_known_reference_distance_one_degree_latitude(self):
        # 1 degree of latitude is ~111.32 km everywhere on Earth
        a = GPSCoordinate(latitude=0.0, longitude=0.0)
        b = GPSCoordinate(latitude=1.0, longitude=0.0)
        d_km = haversine_distance_m(a, b) / 1000.0
        assert d_km == pytest.approx(111.19, rel=0.01)

    def test_distance_is_positive_for_distinct_points(self):
        assert haversine_distance_m(ORIGIN, V1) > 0.0


class TestEmptyAndSingleVictimQueues:
    def test_empty_queue_advance_is_a_noop(self):
        agent = RescueDispatchAgent(position=ORIGIN)
        agent.load_queue([])
        entry = agent.advance(seconds=60)
        assert entry is None
        assert agent.is_complete() is True  # started, but nothing to reach

    def test_advance_before_load_queue_is_a_noop(self):
        agent = RescueDispatchAgent(position=ORIGIN)
        entry = agent.advance(seconds=60)
        assert entry is None
        assert agent.is_complete() is False  # never started

    def test_single_victim_queue_reaches_and_completes(self):
        agent = RescueDispatchAgent(position=ORIGIN, speed_mps=5.0)
        agent.load_queue([{"victim_id": "SOLO", "location": V1}])
        distance = haversine_distance_m(ORIGIN, V1)
        seconds_needed = distance / 5.0

        entry = None
        for _ in range(10_000):
            entry = agent.advance(seconds=max(seconds_needed / 10, 1.0))
            if entry is not None:
                break
        assert entry is not None
        assert entry.victim_id == "SOLO"
        assert entry.order == 1
        assert agent.is_complete() is True


class TestPartialVsExactArrival:
    def test_small_step_moves_partway_without_arriving(self):
        agent = RescueDispatchAgent(position=ORIGIN, speed_mps=0.6)
        agent.load_queue([{"victim_id": "V1", "location": V1}])
        distance = haversine_distance_m(ORIGIN, V1)

        # advance by a tiny amount of time, far less than needed to arrive
        entry = agent.advance(seconds=1.0)
        assert entry is None
        remaining = haversine_distance_m(agent.position, V1)
        assert remaining < distance
        assert remaining > 0.0

    def test_overshoot_step_snaps_exactly_to_target_not_past_it(self):
        agent = RescueDispatchAgent(position=ORIGIN, speed_mps=1000.0)  # absurdly fast
        agent.load_queue([{"victim_id": "V1", "location": V1}])
        entry = agent.advance(seconds=60)  # way more than enough to cover the leg
        assert entry is not None
        assert agent.position.latitude == pytest.approx(V1.latitude)
        assert agent.position.longitude == pytest.approx(V1.longitude)


class TestReprioritizationMidWalk:
    def test_reloading_queue_retargets_to_new_priority_order(self):
        agent = RescueDispatchAgent(position=ORIGIN, speed_mps=0.6)
        agent.load_queue([
            {"victim_id": "FIRST", "location": V1},
            {"victim_id": "SECOND", "location": V2},
        ])
        # small step, not enough to arrive anywhere yet
        agent.advance(seconds=1.0)
        assert agent.victim_status("FIRST") == "pending"

        # priorities flip: SECOND now first, FIRST now second
        agent.load_queue([
            {"victim_id": "SECOND", "location": V2},
            {"victim_id": "FIRST", "location": V1},
        ])
        status = agent.status_dict()
        assert status["queue_order"] == ["SECOND", "FIRST"]
        assert status["current_target"] == "SECOND"

    def test_already_reached_victims_are_skipped_on_reload(self):
        agent = RescueDispatchAgent(position=ORIGIN, speed_mps=1000.0)
        agent.load_queue([{"victim_id": "A", "location": V1}])
        entry = agent.advance(seconds=60)
        assert entry is not None
        assert agent.victim_status("A") == "reached"

        # reload with A still present (e.g. it's still technically in the
        # priority list) plus a new victim B - A must not be re-visited
        agent.load_queue([
            {"victim_id": "A", "location": V1},
            {"victim_id": "B", "location": V2},
        ])
        status = agent.status_dict()
        assert status["current_target"] == "B"


class TestZeroSpeedTeam:
    def test_zero_speed_eta_is_none_not_a_crash(self):
        agent = RescueDispatchAgent(position=ORIGIN, speed_mps=0.0)
        agent.load_queue([{"victim_id": "V1", "location": V1}])
        assert agent.eta_seconds_to_current_target() is None

    def test_zero_speed_advance_never_arrives(self):
        agent = RescueDispatchAgent(position=ORIGIN, speed_mps=0.0)
        agent.load_queue([{"victim_id": "V1", "location": V1}])
        for _ in range(5):
            entry = agent.advance(seconds=1000)
            assert entry is None
        assert agent.is_complete() is False


class TestStatusDictConsistency:
    def test_status_dict_remaining_matches_unreached_victims(self):
        agent = RescueDispatchAgent(position=ORIGIN, speed_mps=1000.0)
        agent.load_queue([
            {"victim_id": "A", "location": V1},
            {"victim_id": "B", "location": V2},
        ])
        agent.advance(seconds=60)  # reaches A
        status = agent.status_dict()
        assert status["remaining"] == ["B"]
        assert status["victim_status"]["A"]["status"] == "reached"
        assert status["victim_status"]["A"]["reached_at"] is not None
        assert status["victim_status"]["B"]["status"] == "pending"
        assert status["victim_status"]["B"]["reached_at"] is None
        assert status["complete"] is False

        agent.advance(seconds=60)  # reaches B
        status = agent.status_dict()
        assert status["remaining"] == []
        assert status["complete"] is True
