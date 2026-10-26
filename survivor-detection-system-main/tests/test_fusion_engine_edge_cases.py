"""
test_fusion_engine_edge_cases.py
----------------------------------
Additional edge-case coverage for backend/fusion_engine.py, written in
pytest style to complement the existing unittest-based
tests/test_fusion_engine.py (which covers the core required test matrix:
empty rubble, person present, tapping override, hazard-adjusted SPS,
weak/uncertain signal, and full doctrine ordering).

This file focuses on boundary conditions and numerical edge cases:
  * exact-threshold classification boundaries (HIGH/MEDIUM/LOW cutoffs)
  * score clamping for out-of-range / negative / extreme sensor values
  * hazard multiplier saturation at its documented cap
  * multi-cycle same-sensor averaging
  * SAFE classification taking priority over tapping
  * reliability = 0 (fully untrustworthy readings)
  * fuse_all() bookkeeping across multiple victims, including victims
    with zero readings
"""

import pytest

from models import SensorType
from fusion_engine import (
    fuse_victim,
    fuse_all,
    rank_victims,
    group_readings_by_victim,
    TriageClass,
    HazardContext,
    HAZARD_MULTIPLIER_CAP,
    HIGH_THRESHOLD_PCT,
    MEDIUM_THRESHOLD_PCT,
    LOW_THRESHOLD_PCT,
)

from tests.conftest import make_reading


# --------------------------------------------------------------------------- #
# Threshold boundary edge cases
# --------------------------------------------------------------------------- #

class TestClassificationBoundaries:
    """The classifier uses >= at each cutoff; probe just above/below each one."""

    def _fuse_with_confidence(self, target_pct: float):
        # Use radar alone (weight 0.35) with reliability 1.0 so
        # confidence_pct == 100 * WEIGHT_RADAR * radar_score, then solve
        # radar_score algebraically to hit a target confidence. A tiny
        # positive epsilon is added so floating-point round-off in the
        # forward computation (bpm -> radar_score -> confidence_pct) lands
        # on the >= side of the boundary rather than a hair under it.
        weight_radar = 0.35
        radar_score = target_pct / (100.0 * weight_radar)
        # radar_score = clamp01((bpm - 15) / 60) => bpm = radar_score*60 + 15
        bpm = radar_score * 60.0 + 15.0 + 1e-6
        return fuse_victim(
            [make_reading(SensorType.HEART_RATE_RADAR, bpm)],
            victim_id="BOUNDARY",
        )

    def test_exactly_at_high_threshold_is_high(self):
        result = self._fuse_with_confidence(HIGH_THRESHOLD_PCT)
        assert result.confidence_pct == pytest.approx(HIGH_THRESHOLD_PCT, abs=0.05)
        assert result.triage_class == TriageClass.HIGH

    def test_just_below_high_threshold_is_medium(self):
        result = self._fuse_with_confidence(HIGH_THRESHOLD_PCT - 0.5)
        assert result.triage_class == TriageClass.MEDIUM

    def test_exactly_at_medium_threshold_is_medium(self):
        result = self._fuse_with_confidence(MEDIUM_THRESHOLD_PCT)
        assert result.triage_class == TriageClass.MEDIUM

    def test_just_below_medium_threshold_is_low(self):
        result = self._fuse_with_confidence(MEDIUM_THRESHOLD_PCT - 0.5)
        assert result.triage_class == TriageClass.LOW

    def test_exactly_at_low_threshold_is_low(self):
        result = self._fuse_with_confidence(LOW_THRESHOLD_PCT)
        assert result.triage_class == TriageClass.LOW

    def test_just_below_low_threshold_is_no_vital_signs(self):
        result = self._fuse_with_confidence(LOW_THRESHOLD_PCT - 0.5)
        assert result.triage_class == TriageClass.NO_VITAL_SIGNS

    def test_zero_confidence_is_no_vital_signs(self):
        result = self._fuse_with_confidence(0.0)
        assert result.triage_class == TriageClass.NO_VITAL_SIGNS
        assert result.confidence_pct == pytest.approx(0.0, abs=1e-6)


# --------------------------------------------------------------------------- #
# Score clamping / out-of-range sensor input
# --------------------------------------------------------------------------- #

class TestScoreClamping:
    def test_extreme_high_readings_do_not_exceed_100_percent(self):
        readings = [
            make_reading(SensorType.THERMAL_IMAGING, 500.0),
            make_reading(SensorType.HEART_RATE_RADAR, 10_000.0),
            make_reading(SensorType.ACOUSTIC, 500.0),
            make_reading(SensorType.PIR_MOTION, 999.0),
            make_reading(SensorType.CO2, 1_000_000.0),
            make_reading(SensorType.RGB_CAMERA, 999.0),
        ]
        result = fuse_victim(readings, victim_id="OVERLOAD")
        assert result.confidence_pct <= 100.0 + 1e-6
        for sub_score in result.score_breakdown.values():
            assert 0.0 <= sub_score <= 1.0

    def test_negative_and_below_ambient_readings_clamp_to_zero_subscore(self):
        readings = [
            make_reading(SensorType.THERMAL_IMAGING, -50.0),   # far below ambient floor
            make_reading(SensorType.HEART_RATE_RADAR, -20.0),  # nonsensical negative bpm
            make_reading(SensorType.ACOUSTIC, -10.0),
            make_reading(SensorType.PIR_MOTION, -1.0),
            make_reading(SensorType.CO2, 0.0),                  # below ambient CO2 baseline
            make_reading(SensorType.RGB_CAMERA, -5.0),
        ]
        result = fuse_victim(readings, victim_id="SUBZERO")
        assert result.triage_class == TriageClass.NO_VITAL_SIGNS
        assert result.confidence_pct == pytest.approx(0.0, abs=1e-6)
        for sub_score in result.score_breakdown.values():
            assert sub_score == pytest.approx(0.0, abs=1e-9)

    def test_radar_below_noise_floor_scores_zero_not_negative(self):
        # bpm just below HR_NOISE_FLOOR_BPM (15.0) must floor to 0, not go negative
        readings = [make_reading(SensorType.HEART_RATE_RADAR, 14.9)]
        result = fuse_victim(readings, victim_id="NOISE_FLOOR")
        assert result.score_breakdown[SensorType.HEART_RATE_RADAR.value] == 0.0


# --------------------------------------------------------------------------- #
# Hazard multiplier saturation
# --------------------------------------------------------------------------- #

class TestHazardMultiplierCap:
    def test_extreme_hazard_inputs_never_exceed_documented_cap(self):
        extreme = HazardContext(
            burial_depth_m=1000.0,       # far beyond HAZARD_DEPTH_REF_M
            secondary_hazard=True,
            exposure_minutes=100_000.0,  # far beyond HAZARD_EXPOSURE_REF_MIN
        )
        assert extreme.multiplier() <= HAZARD_MULTIPLIER_CAP

    def test_extreme_hazard_inputs_saturate_individual_bonus_terms(self):
        # each bonus term (depth, secondary, exposure) is independently
        # capped at its own max even when the raw input is far beyond the
        # reference value used to normalize it
        extreme = HazardContext(
            burial_depth_m=1000.0, secondary_hazard=True, exposure_minutes=100_000.0,
        )
        moderate = HazardContext(
            burial_depth_m=3.0, secondary_hazard=True, exposure_minutes=240.0,
        )
        # both are already at (or beyond) each term's reference value, so
        # their multipliers should match exactly - extra input beyond the
        # reference doesn't add further bonus
        assert extreme.multiplier() == pytest.approx(moderate.multiplier())

    def test_zero_hazard_multiplier_is_exactly_one(self):
        assert HazardContext().multiplier() == pytest.approx(1.0)

    def test_hazard_multiplier_monotonic_in_each_factor(self):
        base = HazardContext().multiplier()
        deeper = HazardContext(burial_depth_m=2.0).multiplier()
        secondary = HazardContext(secondary_hazard=True).multiplier()
        longer_exposure = HazardContext(exposure_minutes=120.0).multiplier()
        assert deeper > base
        assert secondary > base
        assert longer_exposure > base


# --------------------------------------------------------------------------- #
# Multi-cycle averaging
# --------------------------------------------------------------------------- #

class TestMultiCycleAveraging:
    def test_same_sensor_type_readings_are_averaged_not_summed(self):
        readings = [
            make_reading(SensorType.HEART_RATE_RADAR, 60.0),
            make_reading(SensorType.HEART_RATE_RADAR, 80.0),
        ]
        result = fuse_victim(readings, victim_id="AVG")
        # average bpm = 70 -> radar_score = (70-15)/60
        expected_radar_score = (70.0 - 15.0) / 60.0
        assert result.score_breakdown[SensorType.HEART_RATE_RADAR.value] == pytest.approx(
            expected_radar_score, abs=1e-6
        )

    def test_mixed_confidence_readings_average_reliability(self):
        readings = [
            make_reading(SensorType.HEART_RATE_RADAR, 70.0, confidence=1.0),
            make_reading(SensorType.THERMAL_IMAGING, 20.0, confidence=0.5),
        ]
        result = fuse_victim(readings, victim_id="MIXCONF")
        assert result.reliability == pytest.approx(0.75, abs=1e-6)

    def test_zero_reliability_yields_zero_confidence_even_with_strong_signal(self):
        readings = [
            make_reading(SensorType.HEART_RATE_RADAR, 90.0, confidence=0.0),
            make_reading(SensorType.THERMAL_IMAGING, 30.0, confidence=0.0),
        ]
        result = fuse_victim(readings, victim_id="DEADSENSOR")
        assert result.reliability == pytest.approx(0.0, abs=1e-9)
        assert result.confidence_pct == pytest.approx(0.0, abs=1e-6)
        # NB: sensors technically "saw" strong vitals, but zero measurement
        # reliability must still zero out the fused confidence
        assert result.triage_class == TriageClass.NO_VITAL_SIGNS


# --------------------------------------------------------------------------- #
# SAFE overrides tapping
# --------------------------------------------------------------------------- #

class TestSafeOverridesTapping:
    def test_visually_confirmed_safe_wins_even_if_tapping_detected(self):
        readings = [
            make_reading(SensorType.RGB_CAMERA, 0.95),
            make_reading(SensorType.PIR_MOTION, 0.9),        # also above tap threshold
            make_reading(SensorType.THERMAL_IMAGING, 30.0),
            make_reading(SensorType.ACOUSTIC, 60.0),          # loud, would normally tap
        ]
        result = fuse_victim(readings, victim_id="LOUD_BUT_SAFE")
        assert result.tapping_detected is True
        assert result.triage_class == TriageClass.SAFE


# --------------------------------------------------------------------------- #
# fuse_all() / group_readings_by_victim() bookkeeping
# --------------------------------------------------------------------------- #

class TestFuseAllBookkeeping:
    def test_fuse_all_covers_every_victim_including_empty_ones(self):
        readings_by_victim = {
            "HAS_DATA": [make_reading(SensorType.HEART_RATE_RADAR, 80.0, victim_id="HAS_DATA")],
            "NO_DATA": [],
        }
        results = fuse_all(readings_by_victim)
        assert set(results.keys()) == {"HAS_DATA", "NO_DATA"}
        assert results["NO_DATA"].triage_class == TriageClass.NO_VITAL_SIGNS

    def test_fuse_all_applies_per_victim_hazard_context(self):
        readings_by_victim = {
            "A": [make_reading(SensorType.HEART_RATE_RADAR, 80.0, victim_id="A")],
            "B": [make_reading(SensorType.HEART_RATE_RADAR, 80.0, victim_id="B")],
        }
        hazard_by_victim = {"B": HazardContext(secondary_hazard=True)}
        results = fuse_all(readings_by_victim, hazard_by_victim=hazard_by_victim)
        assert results["A"].hazard_multiplier == pytest.approx(1.0)
        assert results["B"].hazard_multiplier > 1.0
        # same sensor evidence -> same confidence regardless of hazard
        assert results["A"].confidence_pct == pytest.approx(results["B"].confidence_pct)

    def test_group_readings_by_victim_groups_correctly(self):
        r1 = make_reading(SensorType.HEART_RATE_RADAR, 80.0, victim_id="X")
        r2 = make_reading(SensorType.THERMAL_IMAGING, 20.0, victim_id="X")
        r3 = make_reading(SensorType.HEART_RATE_RADAR, 60.0, victim_id="Y")
        grouped = group_readings_by_victim([r1, r2, r3])
        assert set(grouped.keys()) == {"X", "Y"}
        assert len(grouped["X"]) == 2
        assert len(grouped["Y"]) == 1


# --------------------------------------------------------------------------- #
# rank_victims() edge cases
# --------------------------------------------------------------------------- #

class TestRankVictimsEdgeCases:
    def test_empty_input_returns_empty_list(self):
        assert rank_victims([]) == []

    def test_single_victim_returns_single_element_list(self):
        result = fuse_victim(
            [make_reading(SensorType.HEART_RATE_RADAR, 80.0)], victim_id="SOLO"
        )
        ranked = rank_victims([result])
        assert [r.victim_id for r in ranked] == ["SOLO"]

    def test_exact_sps_tie_is_stable_by_input_order(self):
        # two identical NO_VITAL_SIGNS results (SPS == 0.0 for both) -
        # Python's sort is stable, so original relative order is preserved.
        a = fuse_victim([], victim_id="TIE_A")
        b = fuse_victim([], victim_id="TIE_B")
        ranked = rank_victims([a, b])
        assert [r.victim_id for r in ranked] == ["TIE_A", "TIE_B"]
