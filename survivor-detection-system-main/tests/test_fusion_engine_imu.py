"""
test_fusion_engine_imu.py
-----------------------------
Tests for Step 10: kit-level IMU (tilt/vibration) as a fusion hazard input.

Covers:
  - kit_disturbed=True raises the hazard multiplier by exactly
    KIT_IMU_RISK_BONUS relative to kit_disturbed=False, without changing
    medical triage class (same design invariant as water/tilt/vibration -
    hazard context affects urgency, not the medical class itself)
  - the kit IMU bonus is a flat, uncoupled bonus: it does NOT require
    secondary_hazard=True (unlike TILT_RISK_MAX_BONUS/soil), matching
    fusion_engine's KIT_IMU_RISK_BONUS docstring
  - a disturbed kit reorders the priority queue relative to an otherwise
    identical, undisturbed kit

Run with:
    python -m pytest tests/test_fusion_engine_imu.py -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from models import SensorType, SensorReading, GPSCoordinate
from fusion_engine import fuse_victim, rank_victims, HazardContext, KIT_IMU_RISK_BONUS


LOC = GPSCoordinate(latitude=32.374, longitude=77.249, altitude_m=3950)


def make_reading(sensor_type, value, confidence=1.0, unit="", victim_id="TEST"):
    return SensorReading(
        sensor_type=sensor_type,
        value=value,
        unit=unit,
        location=LOC,
        victim_id=victim_id,
        confidence=confidence,
    )


class TestKitImuHazardMultiplier(unittest.TestCase):
    def test_kit_disturbed_raises_multiplier_by_exactly_the_bonus(self):
        readings = [
            make_reading(SensorType.HEART_RATE_RADAR, 45.0),
            make_reading(SensorType.THERMAL_IMAGING, 20.0),
            make_reading(SensorType.ACOUSTIC, 10.0),
        ]

        calm_hazard = HazardContext(kit_disturbed=False)
        disturbed_hazard = HazardContext(kit_disturbed=True)

        calm_result = fuse_victim(readings, hazard=calm_hazard, victim_id="V_CALM")
        disturbed_result = fuse_victim(readings, hazard=disturbed_hazard, victim_id="V_DISTURBED")

        # Same underlying sensor evidence -> same Confidence % and same
        # medical triage class. kit_disturbed must not leak into either.
        self.assertAlmostEqual(calm_result.confidence_pct, disturbed_result.confidence_pct, places=6)
        self.assertEqual(calm_result.triage_class, disturbed_result.triage_class)

        # The hazard multiplier must differ by exactly KIT_IMU_RISK_BONUS -
        # kit_disturbed is a boolean flag, not a magnitude-scaled reading,
        # so it's a flat bonus rather than a graduated one.
        self.assertAlmostEqual(
            disturbed_result.hazard_multiplier - calm_result.hazard_multiplier,
            KIT_IMU_RISK_BONUS,
            places=6,
        )
        self.assertGreater(disturbed_result.sps, calm_result.sps)

    def test_kit_disturbed_bonus_applies_without_secondary_hazard(self):
        # Unlike tilt_bonus/soil_bonus, the kit IMU bonus is uncoupled - it
        # must fire even when secondary_hazard is False, since a kit getting
        # knocked could be debris/an animal/a rescuer, not a confirmed
        # slope/structure failure path.
        calm = HazardContext(secondary_hazard=False, kit_disturbed=False)
        disturbed = HazardContext(secondary_hazard=False, kit_disturbed=True)

        self.assertAlmostEqual(
            disturbed.multiplier() - calm.multiplier(),
            KIT_IMU_RISK_BONUS,
            places=6,
        )


class TestKitImuReordersQueue(unittest.TestCase):
    def test_disturbed_kit_outranks_identical_calm_kit(self):
        readings = [
            make_reading(SensorType.HEART_RATE_RADAR, 45.0),
            make_reading(SensorType.THERMAL_IMAGING, 20.0),
            make_reading(SensorType.ACOUSTIC, 10.0),
        ]

        calm_hazard = HazardContext(kit_disturbed=False)
        disturbed_hazard = HazardContext(kit_disturbed=True)

        calm_result = fuse_victim(readings, hazard=calm_hazard, victim_id="V_CALM")
        disturbed_result = fuse_victim(readings, hazard=disturbed_hazard, victim_id="V_DISTURBED")

        # Same triage class (medical evidence identical) but the disturbed
        # kit should be ranked ahead due to the higher urgency (SPS).
        self.assertEqual(calm_result.triage_class, disturbed_result.triage_class)

        ranked = rank_victims([calm_result, disturbed_result])
        self.assertEqual(ranked[0].victim_id, "V_DISTURBED")
        self.assertEqual(ranked[1].victim_id, "V_CALM")


if __name__ == "__main__":
    unittest.main()
