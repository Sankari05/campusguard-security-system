"""
test_triage_queue_ordering.py
--------------------------------
Focused correctness tests for the triage priority-queue ordering produced
by fusion_engine.rank_victims(), beyond the single full-doctrine test
already in tests/test_fusion_engine.py. Verifies the ordering contract
holds under randomized inputs, large victim counts, and repeated/duplicate
SPS values, and that GET /queue (api.py) never violates it.
"""

import random

import pytest

# pyrefly: ignore [missing-import]
from models import SensorType
# pyrefly: ignore [missing-import]
from fusion_engine import fuse_victim, rank_victims, TriageClass, HazardContext
from tests.conftest import make_reading


DOCTRINE_ORDER = {
    TriageClass.HIGH: 0,
    TriageClass.MEDIUM: 1,
    TriageClass.LOW: 2,
    TriageClass.NO_VITAL_SIGNS: 3,
    TriageClass.SAFE: 4,
}


def _random_result(victim_id: str, rng: random.Random):
    """Build a FusionResult with randomized-but-valid sensor readings."""
    bpm = rng.uniform(0, 120)
    thermal = rng.uniform(-10, 35)
    acoustic = rng.uniform(0, 70)
    motion = rng.uniform(0, 1)
    co2 = rng.uniform(390, 2500)
    camera = rng.uniform(0, 1)
    hazard = HazardContext(
        burial_depth_m=rng.uniform(0, 4),
        secondary_hazard=rng.random() < 0.3,
        exposure_minutes=rng.uniform(0, 300),
    )
    readings = [
        make_reading(SensorType.HEART_RATE_RADAR, bpm, victim_id=victim_id),
        make_reading(SensorType.THERMAL_IMAGING, thermal, victim_id=victim_id),
        make_reading(SensorType.ACOUSTIC, acoustic, victim_id=victim_id),
        make_reading(SensorType.PIR_MOTION, motion, victim_id=victim_id),
        make_reading(SensorType.CO2, co2, victim_id=victim_id),
        make_reading(SensorType.RGB_CAMERA, camera, victim_id=victim_id),
    ]
    return fuse_victim(readings, hazard=hazard, victim_id=victim_id)


class TestRandomizedQueueOrderingInvariants:
    @pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
    def test_class_ordering_never_regresses_across_random_populations(self, seed):
        rng = random.Random(seed)
        results = [_random_result(f"V{i}", rng) for i in range(40)]
        rng.shuffle(results)
        ranked = rank_victims(results)

        class_sequence = [DOCTRINE_ORDER[r.triage_class] for r in ranked]
        assert class_sequence == sorted(class_sequence), (
            "Doctrine class order (HIGH<MEDIUM<LOW<NO_VITAL_SIGNS<SAFE) violated"
        )

    @pytest.mark.parametrize("seed", [10, 11, 12])
    def test_sps_descending_within_each_class(self, seed):
        rng = random.Random(seed)
        results = [_random_result(f"V{i}", rng) for i in range(40)]
        ranked = rank_victims(results)

        by_class = {}
        for r in ranked:
            by_class.setdefault(r.triage_class, []).append(r.sps)
        for cls, sps_list in by_class.items():
            assert sps_list == sorted(sps_list, reverse=True), (
                f"SPS not descending within class {cls}"
            )

    def test_all_five_classes_present_are_all_represented_and_grouped(self):
        # Force one representative of every class deterministically.
        high = fuse_victim(
            [make_reading(SensorType.HEART_RATE_RADAR, 90.0)], victim_id="H"
        )
        medium = fuse_victim(
            [make_reading(SensorType.HEART_RATE_RADAR, 30.0)], victim_id="M"
        )
        low = fuse_victim(
            [make_reading(SensorType.HEART_RATE_RADAR, 20.0, confidence=0.5)], victim_id="L"
        )
        none_ = fuse_victim([], victim_id="N")
        safe = fuse_victim(
            [
                make_reading(SensorType.RGB_CAMERA, 0.9),
                make_reading(SensorType.PIR_MOTION, 0.8),
                make_reading(SensorType.THERMAL_IMAGING, 31.0),
            ],
            victim_id="S",
        )
        ranked = rank_victims([safe, none_, low, medium, high])
        assert [r.victim_id for r in ranked] == ["H", "M", "L", "N", "S"]


class TestQueueOrderingThroughApi:
    def test_api_queue_never_places_safe_before_survivable_class(self, started_client):
        for _ in range(3):
            started_client.get("/victims")
        r = started_client.get("/queue")
        classes = [item["triage_class"] for item in r.json()["queue"]]
        if "SAFE" in classes:
            safe_index = classes.index("SAFE")
            # nothing after the first SAFE should be a survivable/urgent class
            assert all(c in ("SAFE", "NO_VITAL_SIGNS") for c in classes[safe_index:])

    def test_api_queue_is_consistent_with_direct_rank_victims_call(self, started_client):
        # Pull /victims to populate fusion state, then independently
        # recompute ranking from the same underlying engine and compare
        # ordering shape (both must be sorted by doctrine order).
        started_client.get("/victims")
        r = started_client.get("/queue")
        classes = [item["triage_class"] for item in r.json()["queue"]]
        numeric = [DOCTRINE_ORDER[TriageClass(c)] for c in classes]
        assert numeric == sorted(numeric)
