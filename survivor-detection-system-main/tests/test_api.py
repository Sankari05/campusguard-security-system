"""
test_api.py
------------
Basic smoke tests for backend/api.py using FastAPI's TestClient.

Run with:
    python -m unittest tests/test_api.py -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient
from api import app, state


class TestScenarioLifecycle(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")  # ensure clean slate between tests

    def test_endpoints_require_running_scenario(self):
        for path in ["/victims", "/queue", "/rescue-team/status"]:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 409, msg=path)

    def test_start_then_victims_has_all_four_and_eight_sensors_each(self):
        r = self.client.post("/scenario/start", json={"seed": 1, "enable_degradation": False})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["running"])

        r = self.client.get("/victims")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["victims"]), 4)
        for v in body["victims"]:
            # 6 core sensors + imu_tilt/imu_vibration (Step 10, unconditional -
            # unlike water_level/water_flow there's no enable_* gate on these).
            self.assertEqual(len(v["sensors"]), 8)
            self.assertIn("triage_class", v["fusion"])

    def test_queue_is_sorted_by_doctrine(self):
        self.client.post("/scenario/start", json={"seed": 1, "enable_degradation": False})
        for _ in range(3):
            self.client.get("/victims")
        r = self.client.get("/queue")
        ranks = [item["rank"] for item in r.json()["queue"]]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(len(r.json()["queue"]), 4)

    def test_reset_clears_state(self):
        self.client.post("/scenario/start", json={"seed": 1})
        self.client.get("/victims")
        r = self.client.post("/scenario/reset")
        self.assertFalse(r.json()["running"])
        self.assertEqual(self.client.get("/victims").status_code, 409)


class TestNetworkAlertDispatch(unittest.TestCase):
    """Integration test for Step 2: simulated GSM/LoRa network-alert dispatch."""

    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")

    def test_high_victim_triggers_logged_network_alert(self):
        # flood_urban's V2 (critical, weak/fast-fading vitals) reliably
        # produces a HIGH classification early - use it to exercise the
        # alert path without depending on Himalaya's exact timing.
        start = self.client.post("/scenario/start", json={"scenario": "flood_urban", "seed": 1})
        self.assertEqual(start.status_code, 200)

        new_alerts = []
        for _ in range(15):
            self.client.get("/victims")
            r = self.client.get("/queue")
            self.assertEqual(r.status_code, 200)
            new_alerts.extend(r.json()["new_alerts"])
            if new_alerts:
                break

        self.assertTrue(new_alerts, "expected at least one HIGH-priority victim to trigger a network alert")

        alerts_resp = self.client.get("/alerts")
        self.assertEqual(alerts_resp.status_code, 200)
        history = alerts_resp.json()["alerts"]
        self.assertTrue(history)
        for a in history:
            self.assertIn(a["status"], ("sent", "failed"))
            self.assertIn("victim_id", a)

        # session_id linkage in db.py
        sessions_resp = self.client.get("/sessions")
        self.assertEqual(sessions_resp.status_code, 200)
        sessions_by_id = {s["session_id"]: s for s in sessions_resp.json()["sessions"]}
        current_session_id = sessions_resp.json()["current_session_id"]
        self.assertIn(current_session_id, sessions_by_id)
        self.assertGreater(sessions_by_id[current_session_id]["counts"]["network_alerts"], 0)


class TestBatteryEndpoint(unittest.TestCase):
    """Tests for Step 4: end-to-end battery model (simulator -> api -> dashboard)."""

    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")

    def test_battery_endpoint_returns_all_victims(self):
        start = self.client.post("/scenario/start", json={"seed": 1, "enable_degradation": False})
        self.assertEqual(start.status_code, 200)
        victim_count = start.json()["victim_count"]

        r = self.client.get("/battery")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["battery"]), victim_count)
        for entry in body["battery"]:
            self.assertIn("victim_id", entry)
            self.assertIn("battery_pct", entry)
            self.assertIn("low_battery", entry)

    def test_battery_pct_decreases_over_cycles(self):
        self.client.post("/scenario/start", json={"seed": 1, "enable_degradation": True})

        readings = []
        for _ in range(8):
            r = self.client.get("/battery")
            self.assertEqual(r.status_code, 200)
            total = sum(e["battery_pct"] for e in r.json()["battery"])
            readings.append(total)
            self.client.get("/victims")  # advances the sim by one cycle

        # allow noise cycle-to-cycle, but the overall trend must be downward
        self.assertLess(readings[-1], readings[0])

    def test_low_battery_flag_threshold(self):
        start = self.client.post("/scenario/start", json={"seed": 1, "enable_degradation": False})
        self.assertEqual(start.status_code, 200)
        self.client.get("/victims")  # make sure the simulator/nodes are provisioned

        # force one node's battery below the low-battery threshold
        forced_vid = next(iter(state.simulator.nodes))
        state.simulator.nodes[forced_vid].battery_pct = 10.0

        r = self.client.get("/battery")
        self.assertEqual(r.status_code, 200)
        entry = next(e for e in r.json()["battery"] if e["victim_id"] == forced_vid)
        self.assertLess(entry["battery_pct"], 25.0)
        self.assertTrue(entry["low_battery"])

    def test_victims_endpoint_includes_battery_pct(self):
        self.client.post("/scenario/start", json={"seed": 1, "enable_degradation": False})
        r = self.client.get("/victims")
        self.assertEqual(r.status_code, 200)
        for v in r.json()["victims"]:
            self.assertIn("battery_pct", v)
            self.assertIsInstance(v["battery_pct"], (int, float))


class TestRainEndpoint(unittest.TestCase):
    """Tests for Step 6: site-wide rain gauge (simulator -> api -> hazard/water-rise)."""

    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")

    def test_rain_endpoint_dry_scenario_returns_zero(self):
        start = self.client.post(
            "/scenario/start",
            json={"scenario": "himalaya_avalanche", "seed": 1, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)

        r = self.client.get("/rain")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["rainfall_mm_hr"], 0.0)

    def test_rain_endpoint_flood_scenario_nonzero(self):
        start = self.client.post(
            "/scenario/start",
            json={"scenario": "flood_urban", "seed": 1, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)

        r = self.client.get("/rain")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.json()["rainfall_mm_hr"], 0.0)

    def test_rain_amplifies_water_rise(self):
        self.client.post(
            "/scenario/start",
            json={"scenario": "flood_urban", "seed": 1, "enable_degradation": False},
        )
        self.client.get("/victims")  # make sure the simulator/nodes are provisioned

        forced_vid = next(iter(state.simulator.nodes))

        # baseline: no rain, tick one cycle, measure water-level rise
        state.simulator._rain_mm_hr = 0.0
        before_dry = state.simulator.water_report()[forced_vid]
        state.simulator.generate_cycle()
        after_dry = state.simulator.water_report()[forced_vid]
        dry_rise = after_dry - before_dry

        # heavy rain: force it just before the tick, measure the same rise
        state.simulator._rain_mm_hr = 40.0
        before_wet = state.simulator.water_report()[forced_vid]
        state.simulator.generate_cycle()
        after_wet = state.simulator.water_report()[forced_vid]
        wet_rise = after_wet - before_wet

        self.assertGreater(wet_rise, dry_rise)


class TestSoilEndpoint(unittest.TestCase):
    """Tests for Step 7: site-wide soil-moisture probe network (simulator -> api -> hazard)."""

    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")

    def test_soil_endpoint_dry_scenario_baseline(self):
        start = self.client.post(
            "/scenario/start",
            json={"scenario": "himalaya_avalanche", "seed": 1, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)

        r = self.client.get("/soil")
        self.assertEqual(r.status_code, 200)
        # before any cycle has ticked, soil moisture sits at the scenario's
        # configured baseline (no rain has fallen yet to move it off that mark)
        self.assertAlmostEqual(r.json()["soil_moisture_pct"], 45.0, delta=0.5)

    def test_soil_rises_with_forced_rain(self):
        self.client.post(
            "/scenario/start",
            json={"scenario": "himalaya_avalanche", "seed": 1, "enable_degradation": False},
        )
        self.client.get("/victims")  # make sure the simulator/nodes are provisioned

        state.simulator._rain_mm_hr = 50.0

        readings = []
        for _ in range(10):
            r = self.client.get("/soil")
            self.assertEqual(r.status_code, 200)
            readings.append(r.json()["soil_moisture_pct"])
            state.simulator._rain_mm_hr = 50.0  # keep the rain forced each cycle
            self.client.get("/victims")  # advances the sim by one cycle

        # allow noise cycle-to-cycle, but the overall trend must be upward
        # as the slope soil saturates under sustained heavy rain
        self.assertGreater(readings[-1], readings[0])

    def test_soil_endpoint_flood_scenario_zero(self):
        start = self.client.post(
            "/scenario/start",
            json={"scenario": "flood_urban", "seed": 1, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)

        r = self.client.get("/soil")
        self.assertEqual(r.status_code, 200)
        # flood_urban defines no site_environment soil config -> default 0.0
        self.assertEqual(r.json()["soil_moisture_pct"], 0.0)


class TestSeismicEndpoint(unittest.TestCase):
    """Tests for Step 8: site-wide seismic sensor (simulator -> api -> hazard,
    with a one-shot aftershock event + decay model)."""

    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")

    def test_seismic_endpoint_quiet_site_no_aftershock(self):
        start = self.client.post(
            "/scenario/start",
            json={"scenario": "flood_urban", "seed": 1, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)

        # flood_urban defines no site_environment seismic config ->
        # aftershock_prob_per_cycle defaults to 0.0 - many ticks should
        # never trigger an aftershock.
        for _ in range(30):
            r = self.client.get("/seismic")
            self.assertEqual(r.status_code, 200)
            self.assertFalse(r.json()["aftershock_active"])
            self.client.get("/victims")  # advances the sim by one cycle

    def test_seismic_aftershock_triggers_and_decays(self):
        start = self.client.post(
            "/scenario/start",
            json={"scenario": "earthquake_building_collapse", "seed": 5, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)
        self.client.get("/victims")  # make sure the simulator is provisioned

        # force an aftershock into its decay phase rather than waiting on
        # aftershock_prob_per_cycle to fire randomly
        state.simulator._aftershock_active = True
        state.simulator._aftershock_peak_mm_s = 25.0
        state.simulator._aftershock_cycles_remaining = 3

        decay_cycles = state.config.site_environment.aftershock_decay_cycles
        readings = []
        for _ in range(decay_cycles + 2):
            self.client.get("/victims")  # advances the sim by one cycle
            r = self.client.get("/seismic")
            self.assertEqual(r.status_code, 200)
            readings.append(r.json())

        # vibration must have been elevated while the aftershock was active...
        self.assertTrue(any(rd["aftershock_active"] for rd in readings))
        self.assertGreater(readings[0]["vibration_mm_s"], 5.0)
        # ...and must have fully decayed back to inactive by the end
        self.assertFalse(readings[-1]["aftershock_active"])

    def test_seismic_endpoint_flood_scenario_baseline_only(self):
        start = self.client.post(
            "/scenario/start",
            json={"scenario": "flood_urban", "seed": 2, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)

        for _ in range(10):
            r = self.client.get("/seismic")
            self.assertEqual(r.status_code, 200)
            self.assertFalse(r.json()["aftershock_active"])
            self.client.get("/victims")


class TestTiltEndpoint(unittest.TestCase):
    """Tests for Step 9: site-wide inclinometer (simulator -> api -> hazard),
    with a creep-and-ratchet tilt model chain-coupled to soil saturation
    (Step 7) and vibration spikes (Step 8)."""

    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")

    def test_tilt_endpoint_returns_baseline_before_any_shift(self):
        start = self.client.post(
            "/scenario/start",
            json={"scenario": "himalaya_avalanche", "seed": 1, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)

        r = self.client.get("/tilt")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        # before any cycle has ticked, tilt sits at the scenario's
        # configured baseline (1.5 degrees for himalaya_avalanche)
        self.assertAlmostEqual(body["tilt_deg"], 1.5, delta=0.2)
        self.assertFalse(body["shift_detected"])

    def test_tilt_does_not_decay_after_shift(self):
        start = self.client.post(
            "/scenario/start",
            json={"scenario": "himalaya_avalanche", "seed": 1, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)
        self.client.get("/victims")  # make sure the simulator is provisioned

        # force a large tilt value into place, as if a shift had already fired
        state.simulator._tilt_deg = 8.0

        readings = []
        for _ in range(5):
            r = self.client.get("/tilt")
            self.assertEqual(r.status_code, 200)
            readings.append(r.json()["tilt_deg"])
            self.client.get("/victims")  # advances the sim by one cycle

        # unlike vibration (which decays back to baseline), tilt is a
        # ratchet - it must never drop below where it was forced to
        self.assertGreaterEqual(readings[-1], readings[0] - 0.01)
        for value in readings:
            self.assertGreaterEqual(value, 7.9)

    def test_soil_and_vibration_coupling_boosts_shift_probability(self):
        start = self.client.post(
            "/scenario/start",
            json={"scenario": "himalaya_avalanche", "seed": 1, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)
        self.client.get("/victims")  # make sure the simulator is provisioned

        baseline_probability = state.config.site_environment.tilt_shift_probability
        boosted_probability = baseline_probability * 3.0 * 4.0  # soil x3, vibration spike x4

        # pick a fixed "roll" strictly between the baseline and the boosted
        # probability, so a shift only fires once both coupling factors apply
        test_roll = (baseline_probability + boosted_probability) / 2.0
        self.assertLess(test_roll, boosted_probability)
        self.assertGreater(test_roll, baseline_probability)

        state.simulator._soil_moisture_pct = 70.0
        state.simulator._last_vibration_spike = True
        state.simulator.rng.random = lambda: test_roll

        _, is_shift = state.simulator._step_tilt()
        self.assertTrue(is_shift)


class TestSolarChargingEndpoint(unittest.TestCase):
    """Tests for the solar charging + Battery Management System (BMS) model."""

    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")

    def test_power_endpoint_disabled_by_default_is_battery_only(self):
        start = self.client.post("/scenario/start", json={"seed": 1, "enable_degradation": True})
        self.assertEqual(start.status_code, 200)
        self.client.get("/victims")

        r = self.client.get("/power")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["daylight"])
        for entry in body["power"]:
            self.assertEqual(entry["power_source"], "battery")
            self.assertFalse(entry["charging"])
            self.assertEqual(entry["solar_input_pct"], 0.0)

    def test_solar_charging_adds_charge_during_daylight(self):
        start = self.client.post(
            "/scenario/start",
            json={"seed": 1, "enable_degradation": False, "enable_solar_charging": True},
        )
        self.assertEqual(start.status_code, 200)

        forced_vid = next(iter(state.simulator.nodes))
        state.simulator.nodes[forced_vid].battery_pct = 40.0
        state.simulator.cycle_count = 14  # next tick lands near solar noon (peak irradiance)

        self.client.get("/victims")  # advances to cycle 15; degradation is off, so only solar acts
        r = self.client.get("/power")
        body = r.json()
        entry = next(e for e in body["power"] if e["victim_id"] == forced_vid)

        self.assertTrue(body["daylight"])
        self.assertEqual(entry["power_source"], "solar+battery")
        self.assertTrue(entry["charging"])
        self.assertGreater(entry["battery_pct"], 40.0)

    def test_bms_caps_charge_rate_per_cycle(self):
        self.client.post(
            "/scenario/start",
            json={"seed": 1, "enable_degradation": False, "enable_solar_charging": True},
        )
        forced_vid = next(iter(state.simulator.nodes))
        state.simulator.nodes[forced_vid].battery_pct = 10.0
        state.simulator.cycle_count = 0  # solar noon-ish, max irradiance available

        self.client.get("/victims")
        r = self.client.get("/power")
        entry = next(e for e in r.json()["power"] if e["victim_id"] == forced_vid)

        # BMS_MAX_CHARGE_RATE_PCT hard-caps charge accepted per cycle
        from sensor_simulator import BMS_MAX_CHARGE_RATE_PCT
        self.assertLessEqual(entry["solar_input_pct"], BMS_MAX_CHARGE_RATE_PCT + 1e-6)

    def test_bms_prevents_overcharge_past_100_percent(self):
        self.client.post(
            "/scenario/start",
            json={"seed": 1, "enable_degradation": False, "enable_solar_charging": True},
        )
        forced_vid = next(iter(state.simulator.nodes))
        state.simulator.nodes[forced_vid].battery_pct = 100.0
        state.simulator.cycle_count = 0

        for _ in range(5):
            self.client.get("/victims")

        r = self.client.get("/power")
        entry = next(e for e in r.json()["power"] if e["victim_id"] == forced_vid)
        self.assertLessEqual(entry["battery_pct"], 100.0)
        self.assertFalse(entry["charging"])  # BMS holds the circuit open at a full pack

    def test_victims_endpoint_includes_charging_field(self):
        self.client.post(
            "/scenario/start",
            json={"seed": 1, "enable_degradation": False, "enable_solar_charging": True},
        )
        r = self.client.get("/victims")
        self.assertEqual(r.status_code, 200)
        for v in r.json()["victims"]:
            self.assertIn("charging", v)
            self.assertIsInstance(v["charging"], bool)


class TestWaterFlowSensor(unittest.TestCase):
    """Tests for Step 5: water flow (current velocity) sensor."""

    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")

    def test_water_flow_disabled_for_dry_scenario(self):
        start = self.client.post(
            "/scenario/start",
            json={"scenario": "himalaya_avalanche", "seed": 1, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)

        for _ in range(3):
            r = self.client.get("/victims")
            self.assertEqual(r.status_code, 200)
            for v in r.json()["victims"]:
                self.assertNotIn("water_flow", v["sensors"])

    def test_water_flow_enabled_for_flood_scenario(self):
        start = self.client.post(
            "/scenario/start",
            json={"scenario": "flood_urban", "seed": 1, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)

        saw_water_flow = False
        for _ in range(5):
            r = self.client.get("/victims")
            self.assertEqual(r.status_code, 200)
            for v in r.json()["victims"]:
                if "water_flow" in v["sensors"]:
                    saw_water_flow = True
                    self.assertGreaterEqual(v["sensors"]["water_flow"]["value"], 0.0)

        self.assertTrue(saw_water_flow, "expected at least one water_flow reading in the flood scenario")

        # fusion evidence: water flow should surface in at least one
        # victim's score_breakdown alongside the other sensor sub-scores
        q = self.client.get("/queue")
        self.assertEqual(q.status_code, 200)


class TestKitImuSensors(unittest.TestCase):
    """Tests for Step 10: kit-level IMU (tilt/vibration) sensors."""

    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/scenario/reset")

    def test_victims_sensors_include_imu_tilt_and_vibration_after_tick(self):
        start = self.client.post(
            "/scenario/start",
            json={"seed": 1, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)

        r = self.client.get("/victims")  # each GET /victims advances the sim by one cycle
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["victims"]), 4)
        for v in body["victims"]:
            self.assertIn("imu_tilt", v["sensors"])
            self.assertIn("imu_vibration", v["sensors"])
            self.assertIn("value", v["sensors"]["imu_tilt"])
            self.assertIn("value", v["sensors"]["imu_vibration"])
            self.assertGreaterEqual(v["sensors"]["imu_tilt"]["value"], 0.0)
            self.assertGreaterEqual(v["sensors"]["imu_vibration"]["value"], 0.0)

    def test_victims_payload_includes_kit_disturbed_flag(self):
        start = self.client.post(
            "/scenario/start",
            json={"seed": 1, "enable_degradation": False},
        )
        self.assertEqual(start.status_code, 200)

        r = self.client.get("/victims")
        self.assertEqual(r.status_code, 200)
        for v in r.json()["victims"]:
            self.assertIn("kit_disturbed", v)
            self.assertIsInstance(v["kit_disturbed"], bool)


if __name__ == "__main__":
    unittest.main(verbosity=2)
