"""
test_fusion_engine.py
----------------------
Unit tests for backend/fusion_engine.py covering the required test matrix:

  1. empty rubble          -> no survivor          (NO_VITAL_SIGNS)
  2. person present        -> survivor detected     (not NO_VITAL_SIGNS)
  3. person + tapping      -> HIGH                  (deliberate signal overrides weak baseline)
  4. hazard condition      -> adjusted SPS           (same triage class, higher SPS)
  5. weak/uncertain signal -> LOW

Plus a doctrine test for the priority queue (rank_victims).

Run with:
    python -m unittest tests/test_fusion_engine.py -v
or:
    python -m pytest tests/test_fusion_engine.py -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from models import SensorType, SensorReading, GPSCoordinate
from fusion_engine import (
    fuse_victim,
    rank_victims,
    TriageClass,
    HazardContext,
)


LOC = GPSCoordinate(latitude=32.374, longitude=77.249, altitude_m=3950)


def make_reading(sensor_type, value, confidence=1.0, unit=""):
    return SensorReading(
        sensor_type=sensor_type,
        value=value,
        unit=unit,
        location=LOC,
        victim_id="TEST",
        confidence=confidence,
    )


class TestEmptyRubble(unittest.TestCase):
    """1. empty rubble -> no survivor"""

    def test_no_readings_at_all(self):
        result = fuse_victim([], victim_id="EMPTY")
        self.assertEqual(result.triage_class, TriageClass.NO_VITAL_SIGNS)
        self.assertEqual(result.confidence_pct, 0.0)

    def test_ambient_only_readings(self):
        # sensors are present and working, but every value is pure ambient / zero -
        # i.e. genuinely nothing alive at this location
        readings = [
            make_reading(SensorType.THERMAL_IMAGING, -5.0, unit="degC"),
            make_reading(SensorType.HEART_RATE_RADAR, 0.0, unit="bpm"),
            make_reading(SensorType.ACOUSTIC, 1.0, unit="dB"),
            make_reading(SensorType.PIR_MOTION, 0.0, unit="motion_index"),
            make_reading(SensorType.CO2, 405.0, unit="ppm"),
            make_reading(SensorType.RGB_CAMERA, 0.0, unit="confidence"),
        ]
        result = fuse_victim(readings, victim_id="EMPTY2")
        self.assertEqual(result.triage_class, TriageClass.NO_VITAL_SIGNS)
        self.assertLess(result.confidence_pct, 5.0)


class TestPersonPresent(unittest.TestCase):
    """2. person present -> survivor detected"""

    def test_live_person_detected(self):
        # moderate/strong vitals, no tapping, not visually confirmed -> should
        # still register as a detected survivor (i.e. NOT no-vital-signs)
        readings = [
            make_reading(SensorType.THERMAL_IMAGING, 20.0, unit="degC"),
            make_reading(SensorType.HEART_RATE_RADAR, 70.0, unit="bpm"),
            make_reading(SensorType.ACOUSTIC, 10.0, unit="dB"),
            make_reading(SensorType.PIR_MOTION, 0.05, unit="motion_index"),
            make_reading(SensorType.CO2, 900.0, unit="ppm"),
            make_reading(SensorType.RGB_CAMERA, 0.35, unit="confidence"),
        ]
        result = fuse_victim(readings, victim_id="SURVIVOR")
        self.assertNotEqual(result.triage_class, TriageClass.NO_VITAL_SIGNS)
        self.assertGreater(result.confidence_pct, 20.0)


class TestTappingOverride(unittest.TestCase):
    """3. person + tapping -> HIGH"""

    def test_tapping_forces_high_even_with_weak_baseline_vitals(self):
        # deliberately weak radar/thermal/co2/camera (would land in MEDIUM/LOW
        # on their own) but strong deliberate acoustic tapping is present -
        # doctrine says a conscious, signaling victim is always HIGH priority
        readings = [
            make_reading(SensorType.THERMAL_IMAGING, 3.0, unit="degC"),
            make_reading(SensorType.HEART_RATE_RADAR, 16.0, unit="bpm"),
            make_reading(SensorType.ACOUSTIC, 45.0, unit="dB"),   # clear tapping/calling
            make_reading(SensorType.PIR_MOTION, 0.02, unit="motion_index"),
            make_reading(SensorType.CO2, 430.0, unit="ppm"),
            make_reading(SensorType.RGB_CAMERA, 0.05, unit="confidence"),
        ]
        result = fuse_victim(readings, victim_id="TAPPER")
        self.assertTrue(result.tapping_detected)
        self.assertEqual(result.triage_class, TriageClass.HIGH)

    def test_without_tapping_same_weak_baseline_is_not_high(self):
        # control case: identical weak baseline, but acoustic/motion below the
        # tapping thresholds -> should NOT reach HIGH
        readings = [
            make_reading(SensorType.THERMAL_IMAGING, 3.0, unit="degC"),
            make_reading(SensorType.HEART_RATE_RADAR, 16.0, unit="bpm"),
            make_reading(SensorType.ACOUSTIC, 6.0, unit="dB"),    # below tap threshold
            make_reading(SensorType.PIR_MOTION, 0.02, unit="motion_index"),
            make_reading(SensorType.CO2, 430.0, unit="ppm"),
            make_reading(SensorType.RGB_CAMERA, 0.05, unit="confidence"),
        ]
        result = fuse_victim(readings, victim_id="NOTAP")
        self.assertFalse(result.tapping_detected)
        self.assertNotEqual(result.triage_class, TriageClass.HIGH)


class TestHazardAdjustedPriority(unittest.TestCase):
    """4. hazard condition -> adjusted priority (SPS), same triage class"""

    def _medium_band_readings(self):
        return [
            make_reading(SensorType.THERMAL_IMAGING, 10.0, unit="degC"),
            make_reading(SensorType.HEART_RATE_RADAR, 30.0, unit="bpm"),
            make_reading(SensorType.ACOUSTIC, 8.0, unit="dB"),
            make_reading(SensorType.PIR_MOTION, 0.05, unit="motion_index"),
            make_reading(SensorType.CO2, 500.0, unit="ppm"),
            make_reading(SensorType.RGB_CAMERA, 0.15, unit="confidence"),
        ]

    def test_hazard_raises_sps_without_changing_triage_class(self):
        baseline = fuse_victim(self._medium_band_readings(), victim_id="HAZ_BASE")
        hazardous = fuse_victim(
            self._medium_band_readings(),
            hazard=HazardContext(burial_depth_m=3.0, secondary_hazard=True, exposure_minutes=180),
            victim_id="HAZ_ADJ",
        )

        # sanity: this scenario is genuinely MEDIUM band before hazard is applied
        self.assertEqual(baseline.triage_class, TriageClass.MEDIUM)

        # medical classification is driven by sensor evidence only, so it
        # should be unchanged by hazard context
        self.assertEqual(hazardous.triage_class, baseline.triage_class)

        # but operational urgency (SPS) must increase under hazard
        self.assertGreater(hazardous.sps, baseline.sps)
        self.assertGreater(hazardous.hazard_multiplier, baseline.hazard_multiplier)

        # confidence % itself (pure sensor evidence) is unaffected by hazard
        self.assertAlmostEqual(hazardous.confidence_pct, baseline.confidence_pct, places=6)

    def test_hazard_can_reorder_the_rescue_queue(self):
        # two MEDIUM victims with identical vitals; the one in the hazardous
        # location must be dispatched to before the safer one
        calm = fuse_victim(self._medium_band_readings(), victim_id="CALM_SITE")
        risky = fuse_victim(
            self._medium_band_readings(),
            hazard=HazardContext(burial_depth_m=2.5, secondary_hazard=True),
            victim_id="RISKY_SITE",
        )
        queue = rank_victims([calm, risky])
        self.assertEqual(queue[0].victim_id, "RISKY_SITE")


class TestWaterFlowHazardBonus(unittest.TestCase):
    """Step 5: water flow (current velocity) is a hazard-urgency signal,
    not a life-sign score - same confidence, higher SPS under faster current."""

    def _medium_band_readings(self):
        return [
            make_reading(SensorType.THERMAL_IMAGING, 10.0, unit="degC"),
            make_reading(SensorType.HEART_RATE_RADAR, 30.0, unit="bpm"),
            make_reading(SensorType.ACOUSTIC, 8.0, unit="dB"),
            make_reading(SensorType.PIR_MOTION, 0.05, unit="motion_index"),
            make_reading(SensorType.CO2, 500.0, unit="ppm"),
            make_reading(SensorType.RGB_CAMERA, 0.15, unit="confidence"),
        ]

    def test_water_flow_increases_hazard_multiplier(self):
        readings = self._medium_band_readings()

        calm = fuse_victim(readings, hazard=HazardContext(water_flow_ms=0.0), victim_id="V_CALM")
        fast = fuse_victim(readings, hazard=HazardContext(water_flow_ms=2.5), victim_id="V_FAST")

        # same underlying sensor evidence -> same Confidence % and triage class
        self.assertAlmostEqual(calm.confidence_pct, fast.confidence_pct, places=6)
        self.assertEqual(calm.triage_class, fast.triage_class)

        # but hazard-adjusted SPS (urgency) must be strictly higher under fast current
        self.assertGreater(fast.sps, calm.sps)
        self.assertGreater(fast.hazard_multiplier, calm.hazard_multiplier)

    def test_water_flow_bonus_caps_at_reference(self):
        readings = self._medium_band_readings()

        at_ref = fuse_victim(readings, hazard=HazardContext(water_flow_ms=2.5), victim_id="V_AT_REF")
        beyond_ref = fuse_victim(readings, hazard=HazardContext(water_flow_ms=6.0), victim_id="V_BEYOND_REF")

        # flow speed above the reference (WATER_FLOW_REF_MS) must not add
        # any further hazard bonus - the multiplier caps out
        self.assertAlmostEqual(at_ref.hazard_multiplier, beyond_ref.hazard_multiplier, places=6)
        self.assertAlmostEqual(at_ref.sps, beyond_ref.sps, places=6)


class TestRainHazardBonus(unittest.TestCase):
    """Step 6: site-wide rain intensity is a hazard-urgency signal,
    not a life-sign score - same confidence, higher SPS under heavier rain."""

    def _medium_band_readings(self):
        return [
            make_reading(SensorType.THERMAL_IMAGING, 10.0, unit="degC"),
            make_reading(SensorType.HEART_RATE_RADAR, 30.0, unit="bpm"),
            make_reading(SensorType.ACOUSTIC, 8.0, unit="dB"),
            make_reading(SensorType.PIR_MOTION, 0.05, unit="motion_index"),
            make_reading(SensorType.CO2, 500.0, unit="ppm"),
            make_reading(SensorType.RGB_CAMERA, 0.15, unit="confidence"),
        ]

    def test_rain_increases_hazard_multiplier(self):
        readings = self._medium_band_readings()

        dry = fuse_victim(readings, hazard=HazardContext(rainfall_mm_hr=0.0), victim_id="V_DRY")
        soaked = fuse_victim(readings, hazard=HazardContext(rainfall_mm_hr=40.0), victim_id="V_SOAKED")

        # same underlying sensor evidence -> same Confidence % and triage class
        self.assertAlmostEqual(dry.confidence_pct, soaked.confidence_pct, places=6)
        self.assertEqual(dry.triage_class, soaked.triage_class)

        # but hazard-adjusted SPS (urgency) must be strictly higher under heavy rain
        self.assertGreater(soaked.sps, dry.sps)
        self.assertGreater(soaked.hazard_multiplier, dry.hazard_multiplier)

    def test_rain_bonus_caps_at_reference(self):
        readings = self._medium_band_readings()

        at_ref = fuse_victim(readings, hazard=HazardContext(rainfall_mm_hr=40.0), victim_id="V_AT_REF")
        beyond_ref = fuse_victim(readings, hazard=HazardContext(rainfall_mm_hr=100.0), victim_id="V_BEYOND_REF")

        # rain intensity above the reference (RAIN_RISK_REF_MM_HR) must not
        # add any further hazard bonus - the multiplier caps out
        self.assertAlmostEqual(at_ref.hazard_multiplier, beyond_ref.hazard_multiplier, places=6)
        self.assertAlmostEqual(at_ref.sps, beyond_ref.sps, places=6)


class TestSoilSaturationLandslideCoupling(unittest.TestCase):
    """Step 7: soil saturation only becomes a hazard bonus when cross-coupled
    with an active secondary hazard (landslide) path - a saturated slope
    with no active slide path doesn't add urgency by itself."""

    def _medium_band_readings(self):
        return [
            make_reading(SensorType.THERMAL_IMAGING, 10.0, unit="degC"),
            make_reading(SensorType.HEART_RATE_RADAR, 30.0, unit="bpm"),
            make_reading(SensorType.ACOUSTIC, 8.0, unit="dB"),
            make_reading(SensorType.PIR_MOTION, 0.05, unit="motion_index"),
            make_reading(SensorType.CO2, 500.0, unit="ppm"),
            make_reading(SensorType.RGB_CAMERA, 0.15, unit="confidence"),
        ]

    def test_soil_saturation_raises_hazard_only_with_secondary_hazard(self):
        readings = self._medium_band_readings()

        no_secondary = fuse_victim(
            readings,
            hazard=HazardContext(secondary_hazard=False, soil_moisture_pct=90.0),
            victim_id="V_NO_SLIDE_PATH",
        )
        baseline = fuse_victim(
            readings,
            hazard=HazardContext(secondary_hazard=False, soil_moisture_pct=0.0),
            victim_id="V_BASELINE",
        )
        # high soil saturation with no active secondary hazard adds nothing
        self.assertAlmostEqual(no_secondary.hazard_multiplier, baseline.hazard_multiplier, places=6)

        with_secondary = fuse_victim(
            readings,
            hazard=HazardContext(secondary_hazard=True, soil_moisture_pct=90.0),
            victim_id="V_SLIDE_PATH",
        )
        secondary_only = fuse_victim(
            readings,
            hazard=HazardContext(secondary_hazard=True, soil_moisture_pct=0.0),
            victim_id="V_SLIDE_PATH_DRY",
        )
        # same secondary_hazard flag, but saturated soil pushes the multiplier higher
        self.assertGreater(with_secondary.hazard_multiplier, secondary_only.hazard_multiplier)
        self.assertGreater(with_secondary.sps, secondary_only.sps)

    def test_soil_bonus_below_threshold_is_zero(self):
        readings = self._medium_band_readings()

        below_threshold = fuse_victim(
            readings,
            hazard=HazardContext(secondary_hazard=True, soil_moisture_pct=50.0),
            victim_id="V_BELOW",
        )
        dry = fuse_victim(
            readings,
            hazard=HazardContext(secondary_hazard=True, soil_moisture_pct=0.0),
            victim_id="V_DRY",
        )
        # soil_moisture_pct=50 is below SOIL_SATURATION_LANDSLIDE_THRESHOLD_PCT (60)
        # so it must not add any hazard bonus, even with an active secondary hazard
        self.assertAlmostEqual(below_threshold.hazard_multiplier, dry.hazard_multiplier, places=6)


class TestSeismicVibrationHazard(unittest.TestCase):
    """Step 8: site-wide seismic sensor - ground vibration raises hazard
    urgency, and an active aftershock striking already-saturated soil
    compounds with the Step 7 landslide-risk bonus."""

    def _medium_band_readings(self):
        return [
            make_reading(SensorType.THERMAL_IMAGING, 10.0, unit="degC"),
            make_reading(SensorType.HEART_RATE_RADAR, 30.0, unit="bpm"),
            make_reading(SensorType.ACOUSTIC, 8.0, unit="dB"),
            make_reading(SensorType.PIR_MOTION, 0.05, unit="motion_index"),
            make_reading(SensorType.CO2, 500.0, unit="ppm"),
            make_reading(SensorType.RGB_CAMERA, 0.15, unit="confidence"),
        ]

    def test_vibration_increases_hazard_multiplier(self):
        readings = self._medium_band_readings()

        quiet = fuse_victim(readings, hazard=HazardContext(vibration_mm_s=0.0), victim_id="V_QUIET")
        shaking = fuse_victim(readings, hazard=HazardContext(vibration_mm_s=20.0), victim_id="V_SHAKING")

        # same underlying sensor evidence -> same Confidence % and triage class
        self.assertAlmostEqual(quiet.confidence_pct, shaking.confidence_pct, places=6)
        self.assertEqual(quiet.triage_class, shaking.triage_class)

        # but hazard-adjusted SPS (urgency) must be strictly higher under active shaking
        self.assertGreater(shaking.sps, quiet.sps)
        self.assertGreater(shaking.hazard_multiplier, quiet.hazard_multiplier)

    def test_compound_bonus_requires_both_aftershock_and_saturated_soil(self):
        readings = self._medium_band_readings()

        aftershock_only = fuse_victim(
            readings,
            hazard=HazardContext(aftershock_active=True, soil_moisture_pct=0.0),
            victim_id="V_AFTERSHOCK_DRY",
        )
        saturated_only = fuse_victim(
            readings,
            hazard=HazardContext(aftershock_active=False, soil_moisture_pct=90.0),
            victim_id="V_SATURATED_QUIET",
        )
        baseline = fuse_victim(
            readings,
            hazard=HazardContext(aftershock_active=False, soil_moisture_pct=0.0),
            victim_id="V_BASELINE",
        )
        both = fuse_victim(
            readings,
            hazard=HazardContext(aftershock_active=True, soil_moisture_pct=90.0),
            victim_id="V_BOTH",
        )

        # aftershock alone (dry soil) adds nothing beyond the plain vibration
        # bonus - no compound term without saturated soil
        self.assertAlmostEqual(aftershock_only.hazard_multiplier, baseline.hazard_multiplier, places=6)
        # saturated soil alone (no aftershock, no secondary_hazard) adds
        # nothing either - soil_bonus is gated on secondary_hazard and the
        # compound bonus is gated on aftershock_active
        self.assertAlmostEqual(saturated_only.hazard_multiplier, baseline.hazard_multiplier, places=6)
        # both together - the compound bonus kicks in
        self.assertGreater(both.hazard_multiplier, baseline.hazard_multiplier)
        self.assertGreater(both.sps, baseline.sps)


class TestTiltHazard(unittest.TestCase):
    """Step 9: site-wide inclinometer - ground/structure tilt only becomes a
    hazard bonus when cross-coupled with an active secondary hazard path
    (same gating pattern as Step 7 soil), and only once it crosses the
    danger threshold."""

    def _medium_band_readings(self):
        return [
            make_reading(SensorType.THERMAL_IMAGING, 10.0, unit="degC"),
            make_reading(SensorType.HEART_RATE_RADAR, 30.0, unit="bpm"),
            make_reading(SensorType.ACOUSTIC, 8.0, unit="dB"),
            make_reading(SensorType.PIR_MOTION, 0.05, unit="motion_index"),
            make_reading(SensorType.CO2, 500.0, unit="ppm"),
            make_reading(SensorType.RGB_CAMERA, 0.15, unit="confidence"),
        ]

    def test_tilt_raises_hazard_only_with_secondary_hazard(self):
        readings = self._medium_band_readings()

        no_secondary = fuse_victim(
            readings,
            hazard=HazardContext(secondary_hazard=False, tilt_deg=12.0),
            victim_id="V_NO_SLIDE_PATH",
        )
        baseline = fuse_victim(
            readings,
            hazard=HazardContext(secondary_hazard=False, tilt_deg=0.0),
            victim_id="V_BASELINE",
        )
        # high tilt with no active secondary hazard adds nothing
        self.assertAlmostEqual(no_secondary.hazard_multiplier, baseline.hazard_multiplier, places=6)

        with_secondary = fuse_victim(
            readings,
            hazard=HazardContext(secondary_hazard=True, tilt_deg=12.0),
            victim_id="V_SLIDE_PATH",
        )
        secondary_only = fuse_victim(
            readings,
            hazard=HazardContext(secondary_hazard=True, tilt_deg=0.0),
            victim_id="V_SLIDE_PATH_LEVEL",
        )
        # same secondary_hazard flag, but a real tilt shift pushes the multiplier higher
        self.assertGreater(with_secondary.hazard_multiplier, secondary_only.hazard_multiplier)
        self.assertGreater(with_secondary.sps, secondary_only.sps)

    def test_tilt_below_danger_threshold_is_zero(self):
        readings = self._medium_band_readings()

        below_threshold = fuse_victim(
            readings,
            hazard=HazardContext(secondary_hazard=True, tilt_deg=3.0),
            victim_id="V_BELOW",
        )
        level = fuse_victim(
            readings,
            hazard=HazardContext(secondary_hazard=True, tilt_deg=0.0),
            victim_id="V_LEVEL",
        )
        # tilt_deg=3.0 is below TILT_DANGER_THRESHOLD_DEG (5.0), so it must
        # not add any hazard bonus, even with an active secondary hazard
        self.assertAlmostEqual(below_threshold.hazard_multiplier, level.hazard_multiplier, places=6)


class TestWeakUncertainSignal(unittest.TestCase):
    """5. weak/uncertain signal -> LOW"""

    def test_low_confidence_noisy_reading_classified_low(self):
        # borderline-above-noise-floor raw values AND poor measurement
        # reliability (e.g. low battery / degraded sensor confidence)
        readings = [
            make_reading(SensorType.THERMAL_IMAGING, 2.0, confidence=0.6, unit="degC"),
            make_reading(SensorType.HEART_RATE_RADAR, 20.0, confidence=0.6, unit="bpm"),
            make_reading(SensorType.ACOUSTIC, 6.0, confidence=0.6, unit="dB"),
            make_reading(SensorType.PIR_MOTION, 0.05, confidence=0.6, unit="motion_index"),
            make_reading(SensorType.CO2, 460.0, confidence=0.6, unit="ppm"),
            make_reading(SensorType.RGB_CAMERA, 0.15, confidence=0.6, unit="confidence"),
        ]
        result = fuse_victim(readings, victim_id="WEAK")
        self.assertEqual(result.triage_class, TriageClass.LOW)
        self.assertFalse(result.tapping_detected)
        self.assertLess(result.reliability, 1.0)


class TestPriorityQueueDoctrine(unittest.TestCase):
    """Priority queue ordering follows real triage doctrine, SPS breaks ties."""

    def test_full_doctrine_ordering(self):
        high1 = fuse_victim(
            [make_reading(SensorType.HEART_RATE_RADAR, 90.0),
             make_reading(SensorType.THERMAL_IMAGING, 25.0)],
            victim_id="HIGH_LOW_SPS",
        )
        high2 = fuse_victim(
            [make_reading(SensorType.HEART_RATE_RADAR, 90.0),
             make_reading(SensorType.THERMAL_IMAGING, 25.0)],
            hazard=HazardContext(secondary_hazard=True),
            victim_id="HIGH_HIGH_SPS",
        )
        medium = fuse_victim(
            [make_reading(SensorType.HEART_RATE_RADAR, 30.0),
             make_reading(SensorType.THERMAL_IMAGING, 10.0)],
            victim_id="MEDIUM",
        )
        low = fuse_victim(
            [
                make_reading(SensorType.THERMAL_IMAGING, 2.0, confidence=0.6),
                make_reading(SensorType.HEART_RATE_RADAR, 20.0, confidence=0.6),
                make_reading(SensorType.ACOUSTIC, 6.0, confidence=0.6),
                make_reading(SensorType.PIR_MOTION, 0.05, confidence=0.6),
                make_reading(SensorType.CO2, 460.0, confidence=0.6),
                make_reading(SensorType.RGB_CAMERA, 0.15, confidence=0.6),
            ],
            victim_id="LOW",
        )
        no_vitals = fuse_victim([], victim_id="NO_VITALS")
        safe = fuse_victim(
            [make_reading(SensorType.RGB_CAMERA, 0.9),
             make_reading(SensorType.PIR_MOTION, 0.8),
             make_reading(SensorType.THERMAL_IMAGING, 31.0)],
            victim_id="SAFE",
        )

        # shuffle the input order on purpose
        scrambled = [safe, no_vitals, medium, low, high2, high1]
        queue = rank_victims(scrambled)
        classes_in_order = [r.triage_class for r in queue]

        self.assertEqual(
            classes_in_order,
            [
                TriageClass.HIGH, TriageClass.HIGH,
                TriageClass.MEDIUM,
                TriageClass.LOW,
                TriageClass.NO_VITAL_SIGNS,
                TriageClass.SAFE,
            ],
        )
        # within the tied HIGH class, higher-SPS (hazardous) victim goes first
        self.assertEqual(queue[0].victim_id, "HIGH_HIGH_SPS")
        self.assertEqual(queue[1].victim_id, "HIGH_LOW_SPS")
        # SAFE is always last regardless of its own (high) confidence/SPS
        self.assertEqual(queue[-1].triage_class, TriageClass.SAFE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
