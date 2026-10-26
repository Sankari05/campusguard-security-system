"""
test_fusion_engine_water.py
-----------------------------
Tests for Step 1: water/flood as a real fusion input.

Covers:
  - water level raises hazard multiplier / SPS without changing triage class
    (medical class stays a function of sensor evidence only - design invariant)
  - rising water reorders the priority queue within the same triage class
  - the water sensor is gated off by default (no fake readings on dry scenarios)
  - scenario_loader correctly parses water_exposure into VictimProfile

Run with:
    python -m pytest tests/test_fusion_engine_water.py -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from models import SensorType, SensorReading, GPSCoordinate, HIMALAYA_VICTIMS
from fusion_engine import fuse_victim, rank_victims, HazardContext
from sensor_simulator import SensorSimulator
import scenario_loader


LOC = GPSCoordinate(latitude=26.1445, longitude=91.7362, altitude_m=55)


def make_reading(sensor_type, value, confidence=1.0, unit="", victim_id="TEST"):
    return SensorReading(
        sensor_type=sensor_type,
        value=value,
        unit=unit,
        location=LOC,
        victim_id=victim_id,
        confidence=confidence,
    )


class TestWaterHazardMultiplier(unittest.TestCase):
    def test_water_level_increases_hazard_multiplier(self):
        readings = [
            make_reading(SensorType.HEART_RATE_RADAR, 45.0),
            make_reading(SensorType.THERMAL_IMAGING, 20.0),
            make_reading(SensorType.ACOUSTIC, 10.0),
        ]

        dry_hazard = HazardContext(water_level_cm=0.0)
        wet_hazard = HazardContext(water_level_cm=150.0)

        dry_result = fuse_victim(readings, hazard=dry_hazard, victim_id="V_DRY")
        wet_result = fuse_victim(readings, hazard=wet_hazard, victim_id="V_WET")

        # Same underlying sensor evidence -> same Confidence % and same
        # medical triage class. Water must not leak into either.
        self.assertAlmostEqual(dry_result.confidence_pct, wet_result.confidence_pct, places=6)
        self.assertEqual(dry_result.triage_class, wet_result.triage_class)

        # But the hazard-adjusted SPS (urgency) must be strictly higher.
        self.assertGreater(wet_result.sps, dry_result.sps)
        self.assertGreater(wet_result.hazard_multiplier, dry_result.hazard_multiplier)


class TestRisingWaterReordersQueue(unittest.TestCase):
    def test_rising_water_reorders_priority_queue(self):
        readings = [
            make_reading(SensorType.HEART_RATE_RADAR, 45.0),
            make_reading(SensorType.THERMAL_IMAGING, 20.0),
            make_reading(SensorType.ACOUSTIC, 10.0),
        ]

        slow_rise = HazardContext(water_level_cm=50.0, water_rising_rate_cm_per_cycle=0.5)
        fast_rise = HazardContext(water_level_cm=50.0, water_rising_rate_cm_per_cycle=4.0)

        slow_result = fuse_victim(readings, hazard=slow_rise, victim_id="V_SLOW")
        fast_result = fuse_victim(readings, hazard=fast_rise, victim_id="V_FAST")

        # Both should land in the same triage class (same sensor evidence).
        self.assertEqual(slow_result.triage_class, fast_result.triage_class)

        ranked = rank_victims([slow_result, fast_result])
        self.assertEqual(ranked[0].victim_id, "V_FAST")
        self.assertEqual(ranked[1].victim_id, "V_SLOW")


class TestWaterSensorGating(unittest.TestCase):
    def test_water_sensor_gated_off_by_default(self):
        sim = SensorSimulator(HIMALAYA_VICTIMS, seed=1, enable_water_sensor=False)
        readings = sim.generate_cycle()
        water_readings = [r for r in readings if r.sensor_type == SensorType.WATER_LEVEL]
        self.assertEqual(water_readings, [])
        self.assertEqual(sim.water_report(), {})

    def test_water_sensor_enabled_produces_readings(self):
        sim = SensorSimulator(HIMALAYA_VICTIMS, seed=1, enable_water_sensor=True)
        readings = sim.generate_cycle()
        water_readings = [r for r in readings if r.sensor_type == SensorType.WATER_LEVEL]
        # Every victim node should emit a WATER_LEVEL reading when enabled
        # (unless it happened to drop out this cycle due to degradation).
        self.assertGreater(len(water_readings), 0)


class TestScenarioLoaderParsesWaterExposure(unittest.TestCase):
    def test_scenario_loader_parses_water_exposure(self):
        cfg = scenario_loader.load_scenario("flood_urban")
        by_id = {v.victim_id: v for v in cfg.victims}

        self.assertEqual(by_id["V1"].initial_water_level_cm, 180.0)
        self.assertEqual(by_id["V1"].water_rising_rate_cm_per_cycle, 1.0)

        self.assertEqual(by_id["V2"].initial_water_level_cm, 90.0)
        self.assertEqual(by_id["V2"].water_rising_rate_cm_per_cycle, 4.0)

        self.assertEqual(by_id["V4"].initial_water_level_cm, 0.0)
        self.assertEqual(by_id["V4"].water_rising_rate_cm_per_cycle, 0.0)

    def test_non_flood_scenario_defaults_water_to_zero(self):
        # Backward-compatibility check: scenarios with no water_exposure /
        # water_level_cm block at all (earthquake, avalanche) must still
        # load cleanly with water fields defaulting to 0.
        cfg = scenario_loader.load_scenario("himalaya_avalanche")
        for v in cfg.victims:
            self.assertEqual(v.initial_water_level_cm, 0.0)
            self.assertEqual(v.water_rising_rate_cm_per_cycle, 0.0)
            self.assertEqual(v.signature_range.water_level_cm, (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
