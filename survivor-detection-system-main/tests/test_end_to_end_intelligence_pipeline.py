"""
tests/test_end_to_end_intelligence_pipeline.py
-----------------------------------------------
Comprehensive end-to-end integration and unit tests for the strengthened
Sensor -> Validation -> Sensor Health -> Trend/Anomaly -> Multi-Sensor Fusion
-> Scenario Intelligence -> Alert -> Commander -> Rescue Dispatch Pipeline.
"""

import sys
import os
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from models import (
    SensorType,
    SensorReading,
    GPSCoordinate,
    SensorHealthStatus,
    SensorValidator,
    SensorHealth,
    SensorTrend,
    SensorEvidence,
)
from fusion_engine import (
    fuse_victim,
    rank_victims,
    TriageClass,
    HazardContext,
)
from scenario_intelligence import (
    SensorHealthMonitor,
    SensorTrendTracker,
    SensorEvidenceExtractor,
    DisasterScenarioInferenceEngine,
    MultiHazardCascadeEngine,
    AlertLifecycleManager,
    ScenarioIntelligenceEngine,
    RiskLevel,
)
from rescue_dispatch import (
    RescueDispatchAgent,
    haversine_distance_m,
)


class TestEndToEndSensorValidationAndHealth(unittest.TestCase):
    """Verifies that the validation and health layer filters noise and marks states."""

    def setUp(self):
        self.validator = SensorValidator()
        self.loc = GPSCoordinate(latitude=32.374, longitude=77.249, altitude_m=3950)

    def test_all_15_sensor_modalities_validation(self):
        """All 15 sensor types pass validation with normal values."""
        modalities = [
            (SensorType.HEART_RATE_RADAR, 72.0, "bpm"),
            (SensorType.PIR_MOTION, 0.45, "motion_index"),
            (SensorType.ACOUSTIC, 25.0, "dB"),
            (SensorType.CO2, 600.0, "ppm"),
            (SensorType.THERMAL_IMAGING, 34.5, "degC"),
            (SensorType.RGB_CAMERA, 0.85, "confidence"),
            (SensorType.WATER_LEVEL, 45.0, "cm"),
            (SensorType.WATER_FLOW, 1.1, "m/s"),
            (SensorType.IMU_TILT, 2.3, "degrees"),
            (SensorType.IMU_VIBRATION, 0.05, "g"),
            (SensorType.GAS_CONCENTRATION, 35.0, "ppm"),
            (SensorType.SMOKE_DENSITY, 15.0, "%"),
            (SensorType.BAROMETRIC_PRESSURE, 1010.0, "hPa"),
            (SensorType.RAINFALL_INTENSITY, 18.0, "mm/hr"),
            (SensorType.SOIL_MOISTURE, 42.0, "%"),
            (SensorType.TEMPERATURE, 22.0, "degC"),
            (SensorType.HUMIDITY, 55.0, "%"),
            (SensorType.GPS, 0.0, "lat_lon"),
        ]
        for stype, val, unit in modalities:
            r = SensorReading(
                sensor_type=stype,
                value=val,
                unit=unit,
                location=self.loc,
                confidence=0.95,
            )
            is_valid, msg = self.validator.validate_reading(r)
            self.assertTrue(is_valid, f"Expected {stype.value} to be valid, got: {msg}")

    def test_invalid_negative_or_nan_readings_rejected(self):
        """Negative values for strictly positive sensors and NaN/Inf are rejected."""
        r_neg = SensorReading(
            sensor_type=SensorType.HEART_RATE_RADAR,
            value=-10.0,
            unit="bpm",
            location=self.loc,
        )
        is_valid, _ = self.validator.validate_reading(r_neg)
        self.assertFalse(is_valid)

        r_nan = SensorReading(
            sensor_type=SensorType.WATER_LEVEL,
            value=float("nan"),
            unit="cm",
            location=self.loc,
        )
        is_valid, _ = self.validator.validate_reading(r_nan)
        self.assertFalse(is_valid)


class TestMultiSensorFusionStrengthening(unittest.TestCase):
    """Verifies fusion engine health-aware weighting, animal filtering, and triage."""

    def setUp(self):
        self.loc = GPSCoordinate(latitude=32.374, longitude=77.249, altitude_m=3950)

    def test_offline_sensor_readings_excluded_from_positive_vitals(self):
        """An offline sensor must not generate a positive life sign."""
        readings = [
            SensorReading(
                sensor_type=SensorType.HEART_RATE_RADAR,
                value=80.0,
                unit="bpm",
                confidence=1.0,
                location=self.loc,
                status=SensorHealthStatus.OFFLINE,
            ),
            SensorReading(
                sensor_type=SensorType.THERMAL_IMAGING,
                value=35.0,
                unit="degC",
                confidence=1.0,
                location=self.loc,
                status=SensorHealthStatus.OFFLINE,
            ),
        ]
        result = fuse_victim(readings, victim_id="V_OFFLINE")
        self.assertEqual(result.triage_class, TriageClass.NO_VITAL_SIGNS)
        self.assertEqual(result.confidence_pct, 0.0)

    def test_animal_classification_suppresses_survivor_detection(self):
        """Camera ANIMAL + Thermal ANIMAL must NOT count as a human survivor."""
        readings = [
            SensorReading(
                sensor_type=SensorType.RGB_CAMERA,
                value=0.85,
                unit="confidence",
                location=self.loc,
                raw_data={"classification": "ANIMAL"},
            ),
            SensorReading(
                sensor_type=SensorType.THERMAL_IMAGING,
                value=36.0,
                unit="degC",
                location=self.loc,
                raw_data={"detection_type": "ANIMAL_HEAT_SIGNATURE"},
            ),
            SensorReading(
                sensor_type=SensorType.HEART_RATE_RADAR,
                value=0.0,  # No distinct human radar pulse
                unit="bpm",
                location=self.loc,
            ),
        ]
        result = fuse_victim(readings, victim_id="V_ANIMAL")
        self.assertEqual(result.triage_class, TriageClass.NO_VITAL_SIGNS)
        self.assertEqual(result.confidence_pct, 0.0)
        self.assertIn("Animal signature detected", result.notes)

    def test_human_classification_corroborated_with_vitals_elevates_confidence(self):
        """Camera HUMAN + Thermal HUMAN + Radar vitals produce strong HIGH triage."""
        readings = [
            SensorReading(
                sensor_type=SensorType.RGB_CAMERA,
                value=0.90,
                unit="confidence",
                location=self.loc,
                raw_data={"classification": "HUMAN"},
            ),
            SensorReading(
                sensor_type=SensorType.THERMAL_IMAGING,
                value=34.0,
                unit="degC",
                location=self.loc,
                raw_data={"classification": "HUMAN_HEAT_SIGNATURE"},
            ),
            SensorReading(
                sensor_type=SensorType.HEART_RATE_RADAR,
                value=72.0,
                unit="bpm",
                location=self.loc,
            ),
            SensorReading(
                sensor_type=SensorType.ACOUSTIC,
                value=15.0,
                unit="dB",
                location=self.loc,
            ),
        ]
        result = fuse_victim(readings, victim_id="V_HUMAN")
        self.assertEqual(result.triage_class, TriageClass.HIGH)
        self.assertGreater(result.confidence_pct, 40.0)

    def test_degraded_sensor_health_discounts_confidence(self):
        """Degraded sensor confidence is discounted relative to a healthy sensor."""
        healthy_readings = [
            SensorReading(
                sensor_type=SensorType.HEART_RATE_RADAR,
                value=70.0,
                unit="bpm",
                confidence=0.8,
                location=self.loc,
                status=SensorHealthStatus.ONLINE,
            )
        ]
        degraded_readings = [
            SensorReading(
                sensor_type=SensorType.HEART_RATE_RADAR,
                value=70.0,
                unit="bpm",
                confidence=0.8,
                location=self.loc,
                status=SensorHealthStatus.DEGRADED,
            )
        ]
        res_healthy = fuse_victim(healthy_readings, victim_id="V_HEALTHY")
        res_degraded = fuse_victim(degraded_readings, victim_id="V_DEGRADED")
        self.assertGreater(res_healthy.confidence_pct, res_degraded.confidence_pct)


class TestScenarioIntelligenceAndRescueDispatch(unittest.TestCase):
    """Verifies scenario intelligence inference, cascading, and rescue dispatch."""

    def setUp(self):
        self.engine = ScenarioIntelligenceEngine()
        self.loc = GPSCoordinate(latitude=32.374, longitude=77.249, altitude_m=3950)

    def test_landslide_inference_requires_multi_sensor_corroboration(self):
        """Single soil moisture reading alone without tilt or rain cannot trigger critical landslide."""
        extractor = SensorEvidenceExtractor()
        inference = DisasterScenarioInferenceEngine()

        # Only soil moisture high, but no rain, no tilt
        readings = [
            SensorReading(
                sensor_type=SensorType.SOIL_MOISTURE,
                value=75.0,
                unit="%",
                location=self.loc,
            )
        ]
        env = {
            "soil_moisture_pct": 75.0,
            "tilt_deg": 0.0,
            "rainfall_mm_hr": 0.0,
        }
        evidence = extractor.extract_evidence(readings, env_report=env)
        results = inference.infer_scenarios(evidence, env_report=env)
        landslide_res = next((r for r in results if r.scenario_id == "landslide"), None)
        self.assertIsNotNone(landslide_res)
        # Without tilt or heavy rain, landslide confidence must be bounded, not CRITICAL
        self.assertNotEqual(landslide_res.risk_level, RiskLevel.CRITICAL)

    def test_multi_hazard_cascade_preservation(self):
        """Earthquake triggering a secondary fire and landslide preserves secondary hazards."""
        cascade_engine = MultiHazardCascadeEngine()
        from scenario_intelligence import ScenarioInferenceResult

        primary = ScenarioInferenceResult(
            scenario_id="earthquake",
            scenario_name="Earthquake Disaster",
            confidence_pct=90.0,
            risk_level=RiskLevel.CRITICAL,
            primary_evidence=[],
            secondary_hazards=["Building Collapse", "Landslide Risk", "Gas Leak / Fire Hazard"],
            recommended_action="Deploy USAR teams with seismic and acoustic monitoring.",
        )
        secondaries = [
            ScenarioInferenceResult(
                scenario_id="urban_fire",
                scenario_name="Urban Fire",
                confidence_pct=70.0,
                risk_level=RiskLevel.HIGH,
                primary_evidence=[],
                secondary_hazards=[],
                recommended_action="Dispatch firefighting units.",
            )
        ]
        cascades = cascade_engine.evaluate_cascades(primary, secondaries)
        self.assertGreaterEqual(len(cascades), 1)

    def test_rescue_dispatch_agent_prioritization(self):
        """Rescue dispatch agent walks the ranked priority queue in strict SPS order."""
        v1 = SensorReading(
            sensor_type=SensorType.HEART_RATE_RADAR,
            value=75.0,
            unit="bpm",
            location=GPSCoordinate(latitude=32.374, longitude=77.249, altitude_m=3950),
        )
        v2 = SensorReading(
            sensor_type=SensorType.HEART_RATE_RADAR,
            value=35.0,
            unit="bpm",
            location=GPSCoordinate(latitude=32.375, longitude=77.250, altitude_m=3940),
        )

        res1 = fuse_victim([v1], victim_id="V_HIGH", location=v1.location)
        res2 = fuse_victim([v2], victim_id="V_LOW", location=v2.location)

        ranked = rank_victims([res2, res1])
        self.assertEqual(ranked[0].victim_id, "V_HIGH")

        agent = RescueDispatchAgent(team_id="RESCUE_ALPHA", speed_mps=1.5)
        agent.load_queue(ranked)
        self.assertEqual(agent.current_target_id(), "V_HIGH")


if __name__ == "__main__":
    unittest.main()
