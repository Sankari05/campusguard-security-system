"""
test_environment_temp_humidity.py
-----------------------------------
Unit + API tests for the ambient temperature & humidity environmental
sensors (site-wide, like rain/soil/seismic/tilt):

  1. Cold exposure raises hazard-adjusted SPS without touching Confidence %
     or triage class (same pattern as test_rain_increases_hazard_multiplier).
  2. The cold-exposure bonus caps at the reference cold temperature.
  3. Heat alone (dry) adds no bonus - it's a compound signal, gated on
     humidity crossing its threshold too (same pattern as the
     aftershock/soil compound bonus).
  4. Heat + humidity together raises hazard-adjusted SPS.
  5. SensorSimulator produces sane, in-range temperature/humidity reports
     and a humid scenario's humidity responds to rainfall.
  6. GET /environment exposes both readings through the live API and feeds
     the live hazard context used by /queue.

Run with:
    python -m pytest tests/test_environment_temp_humidity.py -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from models import SensorType, SensorReading, GPSCoordinate
from fusion_engine import fuse_victim, HazardContext

LOC = GPSCoordinate(latitude=32.374, longitude=77.249, altitude_m=3950)


def make_reading(sensor_type, value, confidence=1.0, unit="", victim_id="TEST", location=LOC):
    return SensorReading(
        sensor_type=sensor_type,
        value=value,
        unit=unit,
        location=location,
        victim_id=victim_id,
        confidence=confidence,
    )


class TestColdExposureHazard(unittest.TestCase):
    """Cold ambient temperature is an uncoupled hazard bonus, same shape as rain."""

    def _medium_band_readings(self):
        return [
            make_reading(SensorType.THERMAL_IMAGING, 10.0, unit="degC"),
            make_reading(SensorType.HEART_RATE_RADAR, 30.0, unit="bpm"),
            make_reading(SensorType.ACOUSTIC, 8.0, unit="dB"),
            make_reading(SensorType.PIR_MOTION, 0.05, unit="motion_index"),
            make_reading(SensorType.CO2, 500.0, unit="ppm"),
            make_reading(SensorType.RGB_CAMERA, 0.15, unit="confidence"),
        ]

    def test_cold_increases_hazard_multiplier(self):
        readings = self._medium_band_readings()

        mild = fuse_victim(readings, hazard=HazardContext(ambient_temp_c=15.0), victim_id="V_MILD")
        freezing = fuse_victim(readings, hazard=HazardContext(ambient_temp_c=-15.0), victim_id="V_FREEZING")

        # same underlying sensor evidence -> same Confidence % and triage class
        self.assertAlmostEqual(mild.confidence_pct, freezing.confidence_pct, places=6)
        self.assertEqual(mild.triage_class, freezing.triage_class)

        # but hazard-adjusted SPS (urgency) must be strictly higher in the cold
        self.assertGreater(freezing.sps, mild.sps)
        self.assertGreater(freezing.hazard_multiplier, mild.hazard_multiplier)

    def test_cold_above_threshold_adds_nothing(self):
        readings = self._medium_band_readings()

        warm = fuse_victim(readings, hazard=HazardContext(ambient_temp_c=20.0), victim_id="V_WARM")
        baseline = fuse_victim(readings, hazard=HazardContext(ambient_temp_c=15.0), victim_id="V_BASELINE")

        # both above COLD_EXPOSURE_THRESHOLD_C (5.0) -> zero cold bonus for either
        self.assertAlmostEqual(warm.hazard_multiplier, baseline.hazard_multiplier, places=6)

    def test_cold_bonus_caps_at_reference(self):
        readings = self._medium_band_readings()

        at_ref = fuse_victim(readings, hazard=HazardContext(ambient_temp_c=-20.0), victim_id="V_AT_REF")
        beyond_ref = fuse_victim(readings, hazard=HazardContext(ambient_temp_c=-40.0), victim_id="V_BEYOND_REF")

        # colder than the reference (COLD_EXPOSURE_REF_C) must not add
        # further hazard bonus - the multiplier caps out
        self.assertAlmostEqual(at_ref.hazard_multiplier, beyond_ref.hazard_multiplier, places=6)
        self.assertAlmostEqual(at_ref.sps, beyond_ref.sps, places=6)


class TestHeatHumidityCompoundHazard(unittest.TestCase):
    """Heat only becomes a hazard bonus when humidity is ALSO high - a
    compound signal, same pattern as the aftershock/soil coupling."""

    def _medium_band_readings(self):
        return [
            make_reading(SensorType.THERMAL_IMAGING, 10.0, unit="degC"),
            make_reading(SensorType.HEART_RATE_RADAR, 30.0, unit="bpm"),
            make_reading(SensorType.ACOUSTIC, 8.0, unit="dB"),
            make_reading(SensorType.PIR_MOTION, 0.05, unit="motion_index"),
            make_reading(SensorType.CO2, 500.0, unit="ppm"),
            make_reading(SensorType.RGB_CAMERA, 0.15, unit="confidence"),
        ]

    def test_heat_alone_dry_adds_no_bonus(self):
        readings = self._medium_band_readings()

        hot_dry = fuse_victim(
            readings, hazard=HazardContext(ambient_temp_c=40.0, humidity_pct=20.0), victim_id="V_HOT_DRY"
        )
        baseline = fuse_victim(
            readings, hazard=HazardContext(ambient_temp_c=15.0, humidity_pct=20.0), victim_id="V_BASELINE"
        )

        self.assertAlmostEqual(hot_dry.hazard_multiplier, baseline.hazard_multiplier, places=6)

    def test_humidity_alone_mild_temp_adds_no_bonus(self):
        readings = self._medium_band_readings()

        humid_mild = fuse_victim(
            readings, hazard=HazardContext(ambient_temp_c=15.0, humidity_pct=95.0), victim_id="V_HUMID_MILD"
        )
        baseline = fuse_victim(
            readings, hazard=HazardContext(ambient_temp_c=15.0, humidity_pct=20.0), victim_id="V_BASELINE"
        )

        self.assertAlmostEqual(humid_mild.hazard_multiplier, baseline.hazard_multiplier, places=6)

    def test_heat_and_humidity_together_raises_hazard(self):
        readings = self._medium_band_readings()

        hot_humid = fuse_victim(
            readings, hazard=HazardContext(ambient_temp_c=40.0, humidity_pct=90.0), victim_id="V_HOT_HUMID"
        )
        baseline = fuse_victim(
            readings, hazard=HazardContext(ambient_temp_c=15.0, humidity_pct=20.0), victim_id="V_BASELINE"
        )

        self.assertAlmostEqual(hot_humid.confidence_pct, baseline.confidence_pct, places=6)
        self.assertEqual(hot_humid.triage_class, baseline.triage_class)
        self.assertGreater(hot_humid.sps, baseline.sps)
        self.assertGreater(hot_humid.hazard_multiplier, baseline.hazard_multiplier)


class TestSensorSimulatorEnvironmentReports(unittest.TestCase):
    """SensorSimulator-level checks for temperature_report()/humidity_report()."""

    def setUp(self):
        from scenario_loader import load_scenario
        from sensor_simulator import SensorSimulator

        self.load_scenario = load_scenario
        self.SensorSimulator = SensorSimulator

    def test_reports_present_and_in_sane_range(self):
        cfg = self.load_scenario("himalaya_avalanche")
        sim = self.SensorSimulator(cfg.victims, seed=7, site_environment=cfg.site_environment)
        for _ in range(10):
            sim.generate_cycle()

        temp = sim.temperature_report()
        humidity = sim.humidity_report()

        self.assertIn("ambient_temp_c", temp)
        self.assertIn("humidity_pct", humidity)
        # a cold Himalayan avalanche scenario shouldn't wander into tropical numbers
        self.assertLess(temp["ambient_temp_c"], 20.0)
        self.assertGreaterEqual(humidity["humidity_pct"], 0.0)
        self.assertLessEqual(humidity["humidity_pct"], 100.0)

    def test_humidity_responds_to_rainfall(self):
        cfg = self.load_scenario("flood_urban")
        sim = self.SensorSimulator(cfg.victims, seed=3, site_environment=cfg.site_environment)
        for _ in range(20):
            sim.generate_cycle()

        # flood_urban is configured with sustained rain and a high humidity
        # target - after enough cycles it should have drifted well above a
        # bone-dry baseline, not sat at the class default (50%).
        humidity = sim.humidity_report()["humidity_pct"]
        self.assertGreater(humidity, 60.0)


class TestEnvironmentApiEndpoint(unittest.TestCase):
    """GET /environment + live-hazard wiring through the running scenario."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from api import app

        self.client = TestClient(app)
        self.client.post("/scenario/reset")

    def tearDown(self):
        self.client.post("/scenario/reset")

    def test_environment_requires_running_scenario(self):
        resp = self.client.get("/environment")
        self.assertEqual(resp.status_code, 409)

    def test_environment_endpoint_shape(self):
        start = self.client.post(
            "/scenario/start", json={"scenario": "flood_urban", "seed": 5, "enable_degradation": False}
        )
        self.assertEqual(start.status_code, 200)

        resp = self.client.get("/environment")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("ambient_temp_c", body)
        self.assertIn("humidity_pct", body)
        self.assertIn("scenario", body)

    def test_queue_still_works_with_environment_hazard_wired_in(self):
        start = self.client.post(
            "/scenario/start", json={"scenario": "flood_urban", "seed": 5, "enable_degradation": False}
        )
        self.assertEqual(start.status_code, 200)

        resp = self.client.get("/queue")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("queue", body)
        self.assertGreater(len(body["queue"]), 0)
        for entry in body["queue"]:
            self.assertIn("sps", entry)
            self.assertIn("triage_class", entry)


if __name__ == "__main__":
    unittest.main()
